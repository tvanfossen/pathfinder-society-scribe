# game_apprentice.py
import os, re, json, asyncio, time, sqlite3
from typing import List, Dict, Any, Optional
from collections import deque

import discord
from dotenv import load_dotenv
from llama_cpp import Llama

from society_scribe.mcp_bridge import MCPBridge

# ---- logging (stderr; safe for MCP stdio) ----
import logging
from utility.logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)

MAX_DISCORD_MSG = 2000
def chunk(s: str, n: int = MAX_DISCORD_MSG) -> List[str]:
    return [s[i:i+n] for i in range(0, len(s), n)]

# Tool-call detection helpers
TOOL_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.S | re.I)
TOOL_TAG_RE   = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S | re.I)
SMART_QUOTES_RE = re.compile(r"[“”«»„‟]|[’‘]")
TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")  # ,} or ,]

MAX_TOOL_CONTENT_CHARS = 1600   # keep tool messages compact in context
MAX_SEARCH_RESULTS_INLINE = 3   # top-N summarization for search results


def compact_tool_payload(name: str, payload: Any) -> str:
    """Return a compact string to place in the tool message content."""
    try:
        if name == "pf2e_db_search" and isinstance(payload, dict):
            q = payload.get("query")
            sec = payload.get("section")
            results = payload.get("results") or []
            lines = [f"search_summary: query={q!r} section={sec!r} count={len(results)}"]
            for i, r in enumerate(results[:MAX_SEARCH_RESULTS_INLINE], 1):
                nm = r.get("name")
                url = r.get("url")
                summ = (r.get("summary") or "")[:140].strip()
                lines.append(f"{i}. {nm} — {url} — {summ}")
            s = "\n".join(lines)
            return s[:MAX_TOOL_CONTENT_CHARS]

        if name == "pf2e_db_get" and isinstance(payload, dict):
            nm = payload.get("name")
            url = payload.get("url")
            level = payload.get("level")
            traits = payload.get("traits")
            summ = (payload.get("summary") or "")[:300].strip()
            text = (payload.get("text") or "")[:1000].strip()
            rec = [
                f"detail_summary: name={nm!r} level={level} url={url}",
                f"traits={traits}",
                f"summary={summ}",
                f"text_excerpt={text}",
            ]
            return "\n".join(rec)[:MAX_TOOL_CONTENT_CHARS]

        # Generic fallback
        s = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
        return s[:MAX_TOOL_CONTENT_CHARS]
    except Exception:
        try:
            return (str(payload) or "")[:MAX_TOOL_CONTENT_CHARS]
        except Exception:
            return "(unprintable tool payload)"


def tool_sig(name: str | None, args: dict | None) -> str:
    if not name:
        return "none"
    try:
        return name + ":" + json.dumps(args or {}, sort_keys=True)
    except Exception:
        return name + ":<unhashable-args>"


def _extract_raw_tool_json(text: str) -> Optional[str]:
    """Find a raw JSON object containing 'tool_call' from ```json fences, <tool_call> tags, or bare JSON."""
    if not text:
        return None
    m = TOOL_FENCE_RE.search(text)
    if m:
        return m.group(1)
    m = TOOL_TAG_RE.search(text)
    if m:
        return m.group(1)
    # bare: scan balanced braces for an object containing "tool_call"
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start:i+1]
                    if "tool_call" in chunk:
                        return chunk
                    break
        start = text.find("{", start+1)
    return None


def _json_sanitize(raw: str) -> str:
    """Lightweight repairs for common LLM JSON issues."""
    s = raw.strip()
    s = SMART_QUOTES_RE.sub('"', s)
    s = s.replace("'", '"')
    s = TRAILING_COMMA_RE.sub(r"\1", s)
    if not (s.startswith("{") and s.endswith("}")):
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last != -1 and last > first:
            s = s[first:last+1]
    return s


def _parse_tool_call(raw: str) -> tuple[Optional[str], Optional[dict]]:
    """Return (name, args) from either:
       {"tool_call":{"name":"...", "arguments":{...}}}  or  {"name":"...","arguments":{...}}.
    """
    def _extract(obj):
        if not isinstance(obj, dict):
            return None, None
        if "tool_call" in obj and isinstance(obj["tool_call"], dict):
            tc = obj["tool_call"]
            name = tc.get("name")
            args = tc.get("arguments", {}) or {}
            return (name, args) if isinstance(args, dict) else (None, None)
        if "name" in obj and "arguments" in obj:
            name = obj.get("name")
            args = obj.get("arguments", {}) or {}
            return (name, args) if isinstance(args, dict) else (None, None)
        return None, None

    # try raw
    try:
        obj = json.loads(raw)
        name, args = _extract(obj)
        if name:
            return name, args
    except Exception:
        pass

    # try repaired
    try:
        obj = json.loads(_json_sanitize(raw))
        name, args = _extract(obj)
        if name:
            return name, args
    except Exception:
        pass

    return None, None


def load_pf2e_categories(db_path: str) -> list[str]:
    """Return all categories present in the local DB, sorted by count desc."""
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT category FROM docs GROUP BY category ORDER BY COUNT(*) DESC"
        ).fetchall()
        return [r["category"] for r in rows]
    except Exception:
        return []
    finally:
        try:
            con.close()
        except Exception:
            pass


def build_rules_primer() -> str:
    return (
        "PF2e quick primer (for structuring answers; do not replace tool calls):\n"
        "• Spells: name, level, traditions (arcane/divine/occult/primal), school, traits, rarity, summary, rules text, AoN URL.\n"
        "• Feats: name, level, prerequisites, traits, summary/rules text, AoN URL.\n"
        "• Actions: name, action cost (🅰️/🅱️/reaction/free), traits, requirements, effects, AoN URL.\n"
        "• Items/Equipment: name, level, price, bulk, traits, usage/activation, effects, AoN URL.\n"
        "• Conditions/Traits: name, definition/effects, AoN URL.\n"
        "When multiple matches exist (e.g., remaster vs legacy), list both with AoN IDs and ask user to choose."
    )


class SocietyScribe:
    def __init__(self, env_path: Optional[str] = None):
        log.debug("Initializing Society Scribe (env_path=%r)", env_path)
        if env_path is None:
            env_path = os.path.join(os.path.dirname(__file__), "apprentice.env")

        loaded = load_dotenv(env_path)
        log.info("Loaded env file %s (loaded=%s)", env_path, loaded)

        self.model_path = os.getenv("MODEL_PATH") or ""
        self.discord_token = os.getenv("DISCORD_BOT_TOKEN") or ""
        self.channel_id = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
        self.server_module = os.getenv("MCP_SERVER_MODULE", "pf2e_mcp.server")
        self.db_path = os.getenv("PF2E_DB_PATH", "pf2e.db")

        log.debug("Config: model_path=%s, channel_id=%s, server_module=%s",
                  self.model_path, self.channel_id, self.server_module)

        if not self.model_path:
            log.critical("MODEL_PATH not set"); raise ValueError("MODEL_PATH not set")
        if not self.discord_token:
            log.critical("DISCORD_BOT_TOKEN not set"); raise ValueError("DISCORD_BOT_TOKEN not set")

        # LLM init
        log.info("Initializing LLM (path=%s, n_ctx=14000, n_batch=512, n_gpu_layers=24, main_gpu=0)", self.model_path)
        t0 = time.perf_counter()
        self.llm = Llama(
            model_path=self.model_path,
            n_gpu_layers=24,
            main_gpu=0,
            n_ctx=14000,
            n_batch=512,
            verbose=True,
        )
        log.info("LLM initialized in %.2fs", time.perf_counter() - t0)

        # System prompt
        self.base_system = """
You are an acting Society Scribe for a party playing in a Pathfinder 2e Campaign. You shall respond to players as if an official scribe of the Pathfinder Society, assigned at the start of a campaign by the Venture-Captain of the local Pathfinder Lodge. 
You are not a player character, but a knowledgeable NPC assistant, in this case an invisible, disembodied scribe (An Aon of Neyths if anyone asks) who is otherwise not perceivable by anyone in the game world, with the sole exception of the player characters.
You possess a tome of arcane knowledge, the Pathfinder Society Codex, which contains all relevant rules, spells, feats, items, actions, conditions, and traits for Pathfinder 2e. For technical purposes, this codex is represented by the MCP tools available to you.
There is a time delay in your responses due to your arcane nature, during which multiple player requests may compiled during your thinking periods. All player responses should be considered, but you should prioritize requests that appear most urgent, or most related to the Game Master's current state.

A player response should be directed at the asking player, and should be concise, informative, and relevant to the current game state.

The Pathfinder Society is a globe-spanning organization based out of Absalom, the City at the Center of the World. 
The membership consists primarily of Pathfinders, adventurers who travel throughout Golarion—usually inconspicuously—and explore, delve, and otherwise experience the lesser-seen parts of the world. 
They send journals documenting their travels back to their venture-captains, who also assigns them new missions and suggests new places to explore. 
The most exciting and illuminating of these journals are compiled in the Pathfinder Chronicles, an ongoing series of books that collect the history and mystery of Golarion for its membership and the general public.

If you feel there is a gap in your knowledge or you are not able to retrieve the information you need from the tome (MCP tools), inform the player that "that page appears to be missing, perhaps you are not asking the right question"

Technical Policy:
• For any Pathfinder 2e rules, spells, feats, items, actions, conditions, or traits, you MUST call an MCP tool first.
• When looking up content, prefer pf2e_db_search first with the functional keywords (including conditions like 'dazzled', 'blinded', 'bright light'), then fetch/quote details.
• Use pf2e_search / pf2e_fetch (or pf2e_db_* tools) to retrieve content. Do NOT answer from memory.
• When calling a tool, reply with ONLY a JSON block inside ```json fences. No other text.

Example:
```json
{"tool_call":{"name":"pf2e_db_search","arguments":{"query":"Fireball","section":"spell","limit":3}}}
"""
        self.messages: List[Dict[str, str]] = [{"role": "system", "content": self.base_system}]
        log.debug("Seeded conversation with system prompt (%d chars)", len(self.base_system))

        # Discord + MCP
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        self.mcp = MCPBridge(self.server_module)
        self.tools_prompt = ""
        self.tools_for_llm = None  # ensure defined even if MCP tool listing fails

        @self.client.event
        async def on_ready():
            log.info("Discord ready as %s (id=%s)", self.client.user, getattr(self.client.user, "id", "?"))
            log.info("Starting MCP server module: %s", self.server_module)
            asyncio.create_task(self.mcp.start())
            await self.mcp.wait_ready()
            log.info("MCP server reported ready")

            try:
                tools = await self.mcp.list_tools()

                # Optional: pass tools to LLM if your MCPBridge supports conversion; guard if not.
                self.tools_for_llm = None
                try:
                    if hasattr(self.mcp, "tools_from_mcp"):
                        self.tools_for_llm = self.mcp.tools_from_mcp(tools)
                except Exception as e:
                    log.warning("tools_from_mcp not available/failed: %r", e)
                    self.tools_for_llm = None

                cats = load_pf2e_categories(self.db_path)
                if cats:
                    self.messages.insert(1, {"role": "system", "content": "Known PF2e sections (categories): " + ", ".join(cats)})

                self.messages.insert(2, {"role": "system", "content": build_rules_primer()})

                lines = []
                for t in tools:
                    schema = getattr(t, "input_schema", None)
                    try:
                        schema_txt = json.dumps(schema, separators=(",", ":"), ensure_ascii=False) if schema else "{}"
                    except Exception as e:
                        log.warning("Failed to serialize tool schema for %s: %r", t.name, e)
                        schema_txt = "{}"
                    lines.append(f"- name: {t.name}\n  desc: {t.description or ''}\n  params: {schema_txt}")
                self.tools_prompt = "Available MCP tools:\n" + "\n".join(lines)
                self.messages.insert(1, {"role": "system", "content": self.tools_prompt})
                log.info("MCP tools ready: %s", [t.name for t in tools])
            except Exception as e:
                log.exception("Error listing/registering MCP tools: %r", e)

        @self.client.event
        async def on_message(message: discord.Message):
            try:
                if message.author == self.client.user:
                    return
                if self.channel_id and message.channel.id != self.channel_id:
                    return
                content = (message.content or "").strip()
                if not content:
                    return

                log.debug("Message in #%s by %s (%s chars): %r",
                          getattr(message.channel, "id", "?"),
                          getattr(message.author, "id", "?"),
                          len(content), content[:200])

                t0 = time.perf_counter()
                reply = await self.chat_with_tools(content)
                dt = time.perf_counter() - t0
                log.info("Responded in %.2fs; reply_len=%d", dt, len(reply))

                for part in chunk(reply):
                    await message.channel.send(part)

            except Exception as e:
                log.exception("on_message error: %r", e)
                try:
                    await message.channel.send("⚠️ An internal error occurred. Check logs.")
                except Exception:
                    pass

    def _llm_chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        log.debug("LLM call: messages=%d (last role=%s, last_len=%d)",
                  len(messages),
                  messages[-1]["role"] if messages else "∅",
                  len(messages[-1]["content"]) if messages else 0)
        t0 = time.perf_counter()
        kwargs = dict(
            messages=messages,
            temperature=0.25,
            top_p=0.95,
            max_tokens=2048,
        )
        if self.tools_for_llm:
            kwargs["tools"] = self.tools_for_llm
            kwargs["tool_choice"] = "auto"
        out = self.llm.create_chat_completion(**kwargs)
        log.debug("LLM completed in %.2fs", time.perf_counter() - t0)
        return out

    async def chat_with_tools(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        log.debug("Appended user message (%d chars); convo_len=%d", len(user_text), len(self.messages))

        recent_calls = deque(maxlen=2)
        max_hops = 10

        for hop in range(1, max_hops + 1):
            log.debug("Tool hop %d/%d", hop, max_hops)
            t0 = time.perf_counter()
            result = await asyncio.to_thread(self._llm_chat, self.messages)
            dt = time.perf_counter() - t0
            text = self._extract_text(result)
            log.debug("Model output (%d chars) in %.2fs", len(text) if text else 0, dt)

            # Try to extract raw tool JSON from fences/tags/bare
            raw_json = _extract_raw_tool_json(text or "")

            if raw_json:
                log.info("Detected tool_call JSON (raw length=%d): %s", len(raw_json), raw_json[:250])
                name, args = _parse_tool_call(raw_json)
                if not name:
                    # Nudge the model to re-emit valid fenced JSON instead of dumping malformed content to chat
                    log.warning("Malformed tool_call JSON after repair; asking model to retry instead of sending to Discord.")
                    self.messages.append({
                        "role": "system",
                        "content": (
                            "Your previous output contained an invalid tool_call JSON. "
                            "Reply again with ONLY a valid fenced JSON block (```json ... ```), "
                            "using the schema {\"tool_call\":{\"name\":\"...\",\"arguments\":{...}}}."
                        ),
                    })
                    continue
            else:
                # No tool call => finalize
                if not text:
                    text = "(no content)"
                self.messages.append({"role": "assistant", "content": text})
                log.debug("Final assistant message appended; convo_len=%d", len(self.messages))
                return text

            # We have a tool call
            sig = tool_sig(name, args)
            recent_calls.append(sig)

            # If repeated exactly back-to-back, push the model to finalize
            if len(recent_calls) == 2 and recent_calls[0] == recent_calls[1]:
                log.info("Same tool call repeated twice (%s); nudging model to finalize.", sig)
                self.messages.append({
                    "role": "system",
                    "content": (
                        "You just called the same tool with identical arguments again. "
                        "Do not call it again. Using the previous tool results, produce a final, concise answer now. "
                        "If you truly need details for ONE top item, call pf2e_db_get ONCE; otherwise answer directly."
                    ),
                })
                continue

            # Execute tool via MCP
            try:
                log.info("Calling MCP tool '%s' with args=%s", name, args)
                t0 = time.perf_counter()
                tool_result = await self.mcp.call_tool(name, args)
                payload = MCPBridge.extract_json(tool_result)
                log.info("Tool '%s' completed in %.2fs", name, time.perf_counter() - t0)
            except Exception as e:
                log.exception("Tool '%s' failed: %r", name, e)
                payload = {"error": f"tool '{name}' failed: {e!r}"}

            compact = compact_tool_payload(name, payload)

            helper = ""
            if name == "pf2e_db_search":
                try:
                    res = payload.get("results") if isinstance(payload, dict) else None
                except Exception:
                    res = None
                if res:
                    helper = (
                        "Use the above search_summary to answer. "
                        "If you need the full text of ONE top item, call pf2e_db_get exactly once with its category and aon_id. "
                        "Otherwise, produce the final answer now without calling pf2e_db_search again."
                    )
                else:
                    helper = (
                        "No results found. You may reformulate the query once (e.g., try synonyms or related conditions) "
                        "or ask the user a brief clarifying question."
                    )

            tool_msg_content = compact if not helper else (compact + "\n\n" + helper)
            self.messages.append({"role": "tool", "name": name, "content": tool_msg_content})
            log.debug("Appended tool message (%d chars); convo_len=%d", len(tool_msg_content), len(self.messages))

        # Safety stop
        log.warning("Tool-call loop guard triggered after %d hops", max_hops)
        fail = "Stopping after multiple tool calls. (Loop guard.)"
        self.messages.append({"role": "assistant", "content": fail})
        return fail

    @staticmethod
    def _extract_text(result: Dict[str, Any]) -> str:
        try:
            return result["choices"][0]["message"]["content"]
        except Exception:
            return result["choices"][0].get("text", "").strip()

    def run(self):
        log.info("Starting Discord bot…")
        try:
            self.client.run(self.discord_token, log_handler=None)
        except Exception:
            log.exception("Discord client crashed")
            raise


if __name__ == "__main__":
    SocietyScribe().run()
