# mcp_bridge.py
from __future__ import annotations
import asyncio
import time
from contextlib import AsyncExitStack
from typing import Any, Optional
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import logging
from utility.logging_config import setup_logging

# Safe for stdio MCP: logs go to STDERR
setup_logging()
log = logging.getLogger(__name__)

class MCPBridge:
    def __init__(self, server_module: str = "pf2e_mcp.server", env: dict[str, str] | None = None):
        self.server_module = server_module
        self.env = env or {}
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None
        self._started = asyncio.Event()
        log.debug("MCPBridge.__init__(server_module=%r, env_keys=%s)", server_module, list(self.env.keys()))

    async def start(self) -> None:
        """Spawn the MCP stdio server (as a module) and initialize a client session."""
        params = StdioServerParameters(
            command=sys.executable,          # same interpreter/venv as caller
            args=["-m", self.server_module], # run as module -> package imports work
            env=self.env,
        )
        log.info("Starting MCP stdio server: %s -m %s", sys.executable, self.server_module)
        t0 = time.perf_counter()
        try:
            stdio, write = await self.exit_stack.enter_async_context(stdio_client(params))
            self.session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
            await self.session.initialize()
            self._started.set()
            log.info("MCP server initialized in %.2fs", time.perf_counter() - t0)
        except Exception as e:
            log.exception("Failed to start MCP server (%s): %r", self.server_module, e)
            raise

    async def wait_ready(self) -> None:
        log.debug("MCPBridge.wait_ready()")
        await self._started.wait()
        log.debug("MCPBridge: ready")

    async def close(self) -> None:
        log.info("Shutting down MCPBridge…")
        try:
            await self.exit_stack.aclose()
            log.info("MCPBridge closed cleanly")
        except Exception:
            log.exception("Error during MCPBridge close")

    async def list_tools(self):
        assert self.session, "MCP session not initialized"
        log.debug("Listing MCP tools…")
        t0 = time.perf_counter()
        try:
            resp = await self.session.list_tools()
            names = [t.name for t in resp.tools]
            log.info("Listed %d tools in %.2fs: %s", len(names), time.perf_counter() - t0, names)
            return resp.tools
        except Exception as e:
            log.exception("list_tools failed: %r", e)
            raise

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        assert self.session, "MCP session not initialized"
        log.info("Calling tool '%s' with args=%s", name, arguments)
        t0 = time.perf_counter()
        try:
            result = await self.session.call_tool(name, arguments)
            dt = time.perf_counter() - t0
            # Lightweight summary of returned content
            try:
                c_types = [getattr(c, "type", type(c).__name__) for c in getattr(result, "content", [])]
            except Exception:
                c_types = ["<unknown>"]
            log.info("Tool '%s' completed in %.2fs (content=%s)", name, dt, c_types)
            return result
        except Exception as e:
            log.exception("Tool '%s' failed: %r", name, e)
            raise

    @staticmethod
    def extract_json(result) -> Any:
        """Best-effort extraction of JSON/text from MCP tool result."""
        log.debug("extract_json: attempting to parse result content")
        try:
            for c in result.content:
                ctype = getattr(c, "type", "")
                if ctype == "json":
                    log.debug("extract_json: found JSON content")
                    return c.data
            for c in result.content:
                ctype = getattr(c, "type", "")
                if ctype == "text":
                    preview = (c.text or "")[:200]
                    log.debug("extract_json: found TEXT content (preview=%r)", preview)
                    return c.text
        except Exception as e:
            log.warning("extract_json failed to parse result content: %r", e)
        log.debug("extract_json: returning raw result")
        return result

    def tools_from_mcp(self, mcp_tools):
        tools = []
        for t in mcp_tools:
            schema = getattr(t, "input_schema", None) or {"type": "object", "properties": {}}
            tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": (t.description or "")[:512],
                    "parameters": schema  # should already be JSON-schema-like
                }
            })
        return tools