# society_scribe/society_scribe.py
import os
import re
import json
import asyncio
import time
import sqlite3
from typing import List, Dict, Any, Optional
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import discord
from dotenv import load_dotenv
from llama_cpp import Llama

from society_scribe.mcp_bridge import MCPBridge

import logging
from utility.logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)


@dataclass
class DiscordConfig:
    """Discord bot configuration."""
    token: str
    channel_id: int = 0
    
    @property
    def is_valid(self) -> bool:
        return bool(self.token)


@dataclass 
class LLMConfig:
    """LLM configuration and settings."""
    model_path: str
    context_size: int = 14000
    batch_size: int = 512
    gpu_layers: int = 24
    main_gpu: int = 0
    temperature: float = 0.25
    top_p: float = 0.95
    max_tokens: int = 2048
    
    @property
    def is_valid(self) -> bool:
        return bool(self.model_path) and Path(self.model_path).exists()


@dataclass
class MCPConfig:
    """MCP server configuration."""
    server_module: str = "pf2e_mcp.server"
    db_path: str = "pf2e.db"
    environment: Dict[str, str] = field(default_factory=dict)


@dataclass
class MessageLimits:
    """Message processing limits and constraints."""
    max_discord_msg: int = 2000
    max_tool_content_chars: int = 1600
    max_search_results_inline: int = 3
    max_tool_hops: int = 10
    commit_every: int = 2000


@dataclass
class ToolCallSignature:
    """Represents a tool call signature for duplicate detection."""
    name: str
    args_hash: str
    
    @classmethod
    def from_call(cls, name: str, args: Dict[str, Any]) -> 'ToolCallSignature':
        try:
            args_str = json.dumps(args or {}, sort_keys=True)
        except Exception:
            args_str = str(args)
        return cls(name=name, args_hash=args_str)


class MessageProcessor:
    """Handles message processing and chunking."""
    
    def __init__(self, limits: MessageLimits):
        self._limits = limits
    
    def chunk_message(self, text: str) -> List[str]:
        """Split message into Discord-compatible chunks."""
        if not text:
            return ["(no content)"]
        
        chunks = []
        for i in range(0, len(text), self._limits.max_discord_msg):
            chunks.append(text[i:i + self._limits.max_discord_msg])
        return chunks
    
    def compact_tool_payload(self, name: str, payload: Any) -> str:
        """Create compact representation of tool payload."""
        try:
            if name == "pf2e_db_search" and isinstance(payload, dict):
                return self._compact_search_payload(payload)
            elif name == "pf2e_db_get" and isinstance(payload, dict):
                return self._compact_get_payload(payload)
            else:
                return self._compact_generic_payload(payload)
        except Exception:
            return "(unprintable tool payload)"
    
    def _compact_search_payload(self, payload: Dict[str, Any]) -> str:
        query = payload.get("query")
        section = payload.get("section")
        results = payload.get("results") or []
        
        lines = [f"search_summary: query={query!r} section={section!r} count={len(results)}"]
        
        for i, result in enumerate(results[:self._limits.max_search_results_inline], 1):
            name = result.get("name")
            url = result.get("url")
            summary = (result.get("summary") or "")[:140].strip()
            lines.append(f"{i}. {name} — {url} — {summary}")
        
        content = "\n".join(lines)
        return content[:self._limits.max_tool_content_chars]
    
    def _compact_get_payload(self, payload: Dict[str, Any]) -> str:
        name = payload.get("name")
        url = payload.get("url")
        level = payload.get("level")
        traits = payload.get("traits")
        summary = (payload.get("summary") or "")[:300].strip()
        text = (payload.get("text") or "")[:1000].strip()
        
        lines = [
            f"detail_summary: name={name!r} level={level} url={url}",
            f"traits={traits}",
            f"summary={summary}",
            f"text_excerpt={text}",
        ]
        
        content = "\n".join(lines)
        return content[:self._limits.max_tool_content_chars]
    
    def _compact_generic_payload(self, payload: Any) -> str:
        if isinstance(payload, str):
            content = payload
        else:
            content = json.dumps(payload, ensure_ascii=False)
        return content[:self._limits.max_tool_content_chars]


class ToolCallParser:
    """Handles parsing and validation of tool calls from LLM output."""
    
    # Regex patterns for tool call detection
    TOOL_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.S | re.I)
    TOOL_TAG_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S | re.I)
    SMART_QUOTES_RE = re.compile(r"[""«»„‟]|['']")
    TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
    
    def extract_tool_call(self, text: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Extract tool call from LLM output text."""
        if not text:
            return None, None
        
        raw_json = self._extract_raw_json(text)
        if not raw_json:
            return None, None
        
        return self._parse_tool_call(raw_json)
    
    def _extract_raw_json(self, text: str) -> Optional[str]:
        """Find raw JSON containing tool_call from various formats."""
        # Try fenced code blocks
        match = self.TOOL_FENCE_RE.search(text)
        if match:
            return match.group(1)
        
        # Try XML-style tags
        match = self.TOOL_TAG_RE.search(text)
        if match:
            return match.group(1)
        
        # Try bare JSON with balanced braces
        return self._find_bare_json(text)
    
    def _find_bare_json(self, text: str) -> Optional[str]:
        """Find balanced JSON object containing 'tool_call'."""
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
            start = text.find("{", start + 1)
        return None
    
    def _parse_tool_call(self, raw_json: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Parse tool call from raw JSON string."""
        # Try parsing as-is
        name, args = self._try_parse_json(raw_json)
        if name:
            return name, args
        
        # Try with sanitization
        sanitized = self._sanitize_json(raw_json)
        return self._try_parse_json(sanitized)
    
    def _try_parse_json(self, json_str: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Attempt to parse JSON and extract tool call."""
        try:
            obj = json.loads(json_str)
            return self._extract_from_object(obj)
        except Exception:
            return None, None
    
    def _extract_from_object(self, obj: Any) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Extract tool call from parsed JSON object."""
        if not isinstance(obj, dict):
            return None, None
        
        # Format: {"tool_call": {"name": "...", "arguments": {...}}}
        if "tool_call" in obj and isinstance(obj["tool_call"], dict):
            tc = obj["tool_call"]
            name = tc.get("name")
            args = tc.get("arguments", {}) or {}
            return (name, args) if isinstance(args, dict) else (None, None)
        
        # Format: {"name": "...", "arguments": {...}}
        if "name" in obj and "arguments" in obj:
            name = obj.get("name")
            args = obj.get("arguments", {}) or {}
            return (name, args) if isinstance(args, dict) else (None, None)
        
        return None, None
    
    def _sanitize_json(self, raw: str) -> str:
        """Clean up common JSON formatting issues."""
        s = raw.strip()
        s = self.SMART_QUOTES_RE.sub('"', s)
        s = s.replace("'", '"')
        s = self.TRAILING_COMMA_RE.sub(r"\1", s)
        
        # Ensure proper JSON boundaries
        if not (s.startswith("{") and s.endswith("}")):
            first = s.find("{")
            last = s.rfind("}")
            if first != -1 and last != -1 and last > first:
                s = s[first:last+1]
        
        return s


class PathfinderDataManager:
    """Manages Pathfinder 2e game data and database operations."""
    
    def __init__(self, db_path: str):
        self._db_path = db_path
    
    def load_categories(self) -> List[str]:
        """Load available Pathfinder categories from database."""
        try:
            with sqlite3.connect(self._db_path) as con:
                con.row_factory = sqlite3.Row
                rows = con.execute(
                    "SELECT category FROM docs GROUP BY category ORDER BY COUNT(*) DESC"
                ).fetchall()
                return [row["category"] for row in rows]
        except Exception as e:
            log.warning(f"Failed to load PF2e categories: {e}")
            return []
    
    def build_rules_primer(self) -> str:
        """Build rules primer for system prompt."""
        return (
            "PF2e quick primer (for structuring answers; do not replace tool calls):\n"
            "• Spells: name, level, traditions (arcane/divine/occult/primal), school, traits, rarity, summary, rules text, AoN URL.\n"
            "• Feats: name, level, prerequisites, traits, summary/rules text, AoN URL.\n"
            "• Actions: name, action cost (🅰️/🅱️/reaction/free), traits, requirements, effects, AoN URL.\n"
            "• Items/Equipment: name, level, price, bulk, traits, usage/activation, effects, AoN URL.\n"
            "• Conditions/Traits: name, definition/effects, AoN URL.\n"
            "When multiple matches exist (e.g., remaster vs legacy), list both with AoN IDs and ask user to choose."
        )


class ConversationManager:
    """Manages conversation state and message history."""
    
    def __init__(self, base_system_prompt: str, limits: MessageLimits):
        self._limits = limits
        self._messages: List[Dict[str, str]] = []
        self._recent_calls: deque[ToolCallSignature] = deque(maxlen=2)
        
        # Initialize with system prompt
        self.add_system_message(base_system_prompt)
    
    @property
    def messages(self) -> List[Dict[str, str]]:
        """Get current conversation messages."""
        return self._messages.copy()
    
    def add_system_message(self, content: str) -> None:
        """Add a system message."""
        self._messages.append({"role": "system", "content": content})
    
    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self._messages.append({"role": "user", "content": content})
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message."""
        self._messages.append({"role": "assistant", "content": content})
    
    def add_tool_message(self, name: str, content: str) -> None:
        """Add a tool result message."""
        self._messages.append({"role": "tool", "name": name, "content": content})
    
    def insert_system_message(self, content: str, position: int = 1) -> None:
        """Insert system message at specific position."""
        self._messages.insert(position, {"role": "system", "content": content})
    
    def track_tool_call(self, name: str, args: Dict[str, Any]) -> bool:
        """Track tool call and detect duplicates. Returns True if duplicate."""
        signature = ToolCallSignature.from_call(name, args)
        self._recent_calls.append(signature)
        
        # Check for back-to-back duplicates
        if len(self._recent_calls) == 2:
            return (self._recent_calls[0].name == self._recent_calls[1].name and 
                   self._recent_calls[0].args_hash == self._recent_calls[1].args_hash)
        return False
    
    def add_duplicate_prevention_message(self) -> None:
        """Add message to prevent duplicate tool calls."""
        self.add_system_message(
            "You just called the same tool with identical arguments again. "
            "Do not call it again. Using the previous tool results, produce a final, concise answer now. "
            "If you truly need details for ONE top item, call pf2e_db_get ONCE; otherwise answer directly."
        )


class SocietyScribe:
    """Main Society Scribe application class."""
    
    def __init__(self, env_path: Optional[str] = None):
        log.debug("Initializing Society Scribe (env_path=%r)", env_path)
        
        # Load configuration
        self._load_environment(env_path)
        self._config = self._build_configuration()
        self._validate_configuration()
        
        # Initialize components
        self._limits = MessageLimits()
        self._message_processor = MessageProcessor(self._limits)
        self._tool_parser = ToolCallParser()
        self._data_manager = PathfinderDataManager(self._config.mcp.db_path)
        
        # Initialize LLM
        self._llm = self._initialize_llm()
        
        # Initialize conversation
        self._conversation = ConversationManager(self._build_base_system_prompt(), self._limits)
        
        # Initialize Discord and MCP
        self._client = self._initialize_discord()
        self._mcp = MCPBridge(self._config.mcp.server_module)
        self._tools_for_llm = None
        
        self._setup_discord_events()
    
    def _load_environment(self, env_path: Optional[str]) -> None:
        """Load environment variables from file."""
        if env_path is None:
            env_path = os.path.join(os.path.dirname(__file__), "apprentice.env")
        
        loaded = load_dotenv(env_path)
        log.info("Loaded env file %s (loaded=%s)", env_path, loaded)
    
    def _build_configuration(self) -> 'SocietyScribeConfig':
        """Build configuration from environment variables."""
        return SocietyScribeConfig(
            discord=DiscordConfig(
                token=os.getenv("DISCORD_BOT_TOKEN", ""),
                channel_id=int(os.getenv("DISCORD_CHANNEL_ID", "0"))
            ),
            llm=LLMConfig(
                model_path=os.getenv("MODEL_PATH", "")
            ),
            mcp=MCPConfig(
                server_module=os.getenv("MCP_SERVER_MODULE", "pf2e_mcp.server"),
                db_path=os.getenv("PF2E_DB_PATH", "pf2e.db")
            )
        )
    
    def _validate_configuration(self) -> None:
        """Validate configuration and raise errors for invalid settings."""
        if not self._config.discord.is_valid:
            raise ValueError("DISCORD_BOT_TOKEN not set")
        if not self._config.llm.is_valid:
            raise ValueError("MODEL_PATH not set or file does not exist")
    
    def _initialize_llm(self) -> Llama:
        """Initialize the LLM with configuration."""
        llm_config = self._config.llm
        log.info(
            "Initializing LLM (path=%s, n_ctx=%d, n_batch=%d, n_gpu_layers=%d, main_gpu=%d)",
            llm_config.model_path, llm_config.context_size, llm_config.batch_size,
            llm_config.gpu_layers, llm_config.main_gpu
        )
        
        t0 = time.perf_counter()
        llm = Llama(
            model_path=llm_config.model_path,
            n_gpu_layers=llm_config.gpu_layers,
            main_gpu=llm_config.main_gpu,
            n_ctx=llm_config.context_size,
            n_batch=llm_config.batch_size,
            verbose=True,
        )
        log.info("LLM initialized in %.2fs", time.perf_counter() - t0)
        return llm
    
    def _build_base_system_prompt(self) -> str:
        """Build the base system prompt."""
        return """
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
    
    def _initialize_discord(self) -> discord.Client:
        """Initialize Discord client with proper intents."""
        intents = discord.Intents.default()
        intents.message_content = True
        return discord.Client(intents=intents)
    
    def _setup_discord_events(self) -> None:
        """Set up Discord event handlers."""
        
        @self._client.event
        async def on_ready():
            log.info("Discord ready as %s (id=%s)", 
                    self._client.user, getattr(self._client.user, "id", "?"))
            
            # Start MCP server
            await self._initialize_mcp()
        
        @self._client.event
        async def on_message(message: discord.Message):
            await self._handle_discord_message(message)
    
    async def _initialize_mcp(self) -> None:
        """Initialize MCP server and tools."""
        log.info("Starting MCP server module: %s", self._config.mcp.server_module)
        asyncio.create_task(self._mcp.start())
        await self._mcp.wait_ready()
        log.info("MCP server reported ready")
        
        try:
            tools = await self._mcp.list_tools()
            
            # Convert tools for LLM if method exists
            if hasattr(self._mcp, "tools_from_mcp"):
                try:
                    self._tools_for_llm = self._mcp.tools_from_mcp(tools)
                except Exception as e:
                    log.warning("tools_from_mcp failed: %r", e)
            
            # Load Pathfinder data
            categories = self._data_manager.load_categories()
            if categories:
                self._conversation.insert_system_message(
                    "Known PF2e sections (categories): " + ", ".join(categories)
                )
            
            self._conversation.insert_system_message(
                self._data_manager.build_rules_primer(), position=2
            )
            
            # Add tool descriptions
            self._add_tool_descriptions(tools)
            
            log.info("MCP tools ready: %s", [t.name for t in tools])
            
        except Exception as e:
            log.exception("Error listing/registering MCP tools: %r", e)
    
    def _add_tool_descriptions(self, tools) -> None:
        """Add tool descriptions to conversation."""
        lines = []
        for tool in tools:
            schema = getattr(tool, "input_schema", None)
            try:
                schema_txt = json.dumps(schema, separators=(",", ":"), ensure_ascii=False) if schema else "{}"
            except Exception as e:
                log.warning("Failed to serialize tool schema for %s: %r", tool.name, e)
                schema_txt = "{}"
            lines.append(f"- name: {tool.name}\n  desc: {tool.description or ''}\n  params: {schema_txt}")
        
        tools_prompt = "Available MCP tools:\n" + "\n".join(lines)
        self._conversation.insert_system_message(tools_prompt, position=1)
    
    async def _handle_discord_message(self, message: discord.Message) -> None:
        """Handle incoming Discord messages."""
        try:
            if message.author == self._client.user:
                return
            
            if (self._config.discord.channel_id and 
                message.channel.id != self._config.discord.channel_id):
                return
            
            content = (message.content or "").strip()
            if not content:
                return
            
            log.debug("Message in #%s by %s (%s chars): %r",
                     getattr(message.channel, "id", "?"),
                     getattr(message.author, "id", "?"),
                     len(content), content[:200])
            
            t0 = time.perf_counter()
            reply = await self._process_user_message(content)
            dt = time.perf_counter() - t0
            log.info("Responded in %.2fs; reply_len=%d", dt, len(reply))
            
            # Send reply in chunks
            for chunk in self._message_processor.chunk_message(reply):
                await message.channel.send(chunk)
        
        except Exception as e:
            log.exception("on_message error: %r", e)
            try:
                await message.channel.send("⚠️ An internal error occurred. Check logs.")
            except Exception:
                pass
    
    async def _process_user_message(self, content: str) -> str:
        """Process user message and return response."""
        self._conversation.add_user_message(content)
        
        for hop in range(1, self._limits.max_tool_hops + 1):
            log.debug("Tool hop %d/%d", hop, self._limits.max_tool_hops)
            
            # Get LLM response
            t0 = time.perf_counter()
            result = await asyncio.to_thread(self._call_llm)
            dt = time.perf_counter() - t0
            text = self._extract_text_from_result(result)
            log.debug("Model output (%d chars) in %.2fs", len(text) if text else 0, dt)
            
            # Check for tool call
            tool_name, tool_args = self._tool_parser.extract_tool_call(text or "")
            
            if not tool_name:
                # No tool call - finalize
                if not text:
                    text = "(no content)"
                self._conversation.add_assistant_message(text)
                return text
            
            # Handle tool call
            if self._conversation.track_tool_call(tool_name, tool_args):
                log.info("Same tool call repeated twice; nudging model to finalize.")
                self._conversation.add_duplicate_prevention_message()
                continue
            
            # Execute tool
            try:
                log.info("Calling MCP tool '%s' with args=%s", tool_name, tool_args)
                t0 = time.perf_counter()
                tool_result = await self._mcp.call_tool(tool_name, tool_args)
                payload = MCPBridge.extract_json(tool_result)
                log.info("Tool '%s' completed in %.2fs", tool_name, time.perf_counter() - t0)
            except Exception as e:
                log.exception("Tool '%s' failed: %r", tool_name, e)
                payload = {"error": f"tool '{tool_name}' failed: {e!r}"}
            
            # Process tool result
            compact = self._message_processor.compact_tool_payload(tool_name, payload)
            helper = self._get_tool_helper_message(tool_name, payload)
            
            tool_content = compact + ("\n\n" + helper if helper else "")
            self._conversation.add_tool_message(tool_name, tool_content)
        
        # Safety stop
        log.warning("Tool-call loop guard triggered after %d hops", self._limits.max_tool_hops)
        error_msg = "Stopping after multiple tool calls. (Loop guard.)"
        self._conversation.add_assistant_message(error_msg)
        return error_msg
    
    def _call_llm(self) -> Dict[str, Any]:
        """Call the LLM with current conversation."""
        messages = self._conversation.messages
        log.debug("LLM call: messages=%d (last role=%s, last_len=%d)",
                 len(messages),
                 messages[-1]["role"] if messages else "∅",
                 len(messages[-1]["content"]) if messages else 0)
        
        kwargs = {
            "messages": messages,
            "temperature": self._config.llm.temperature,
            "top_p": self._config.llm.top_p,
            "max_tokens": self._config.llm.max_tokens,
        }
        
        if self._tools_for_llm:
            kwargs["tools"] = self._tools_for_llm
            kwargs["tool_choice"] = "auto"
        
        return self._llm.create_chat_completion(**kwargs)
    
    def _extract_text_from_result(self, result: Dict[str, Any]) -> str:
        """Extract text content from LLM result."""
        try:
            return result["choices"][0]["message"]["content"]
        except Exception:
            return result["choices"][0].get("text", "").strip()
    
    def _get_tool_helper_message(self, tool_name: str, payload: Any) -> str:
        """Get helper message based on tool results."""
        if tool_name == "pf2e_db_search":
            try:
                results = payload.get("results") if isinstance(payload, dict) else None
            except Exception:
                results = None
            
            if results:
                return (
                    "Use the above search_summary to answer. "
                    "If you need the full text of ONE top item, call pf2e_db_get exactly once with its category and aon_id. "
                    "Otherwise, produce the final answer now without calling pf2e_db_search again."
                )
            else:
                return (
                    "No results found. You may reformulate the query once (e.g., try synonyms or related conditions) "
                    "or ask the user a brief clarifying question."
                )
        return ""
    
    def run(self) -> None:
        """Start the Society Scribe application."""
        log.info("Starting Discord bot…")
        try:
            self._client.run(self._config.discord.token, log_handler=None)
        except Exception:
            log.exception("Discord client crashed")
            raise


@dataclass
class SocietyScribeConfig:
    """Complete configuration for Society Scribe."""
    discord: DiscordConfig
    llm: LLMConfig
    mcp: MCPConfig


if __name__ == "__main__":
    SocietyScribe().run()