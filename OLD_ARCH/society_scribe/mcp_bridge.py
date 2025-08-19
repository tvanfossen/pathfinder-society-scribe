# society_scribe/mcp_bridge.py
from __future__ import annotations
import asyncio
import time
import sys
from contextlib import AsyncExitStack
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import logging
from utility.logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for MCP server connection."""
    module_name: str
    environment: Dict[str, str] = field(default_factory=dict)
    command: str = sys.executable
    
    @property
    def args(self) -> List[str]:
        """Command arguments for running the server."""
        return ["-m", self.module_name]
    
    @property
    def parameters(self) -> StdioServerParameters:
        """MCP server parameters for connection."""
        return StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.environment
        )


@dataclass
class ToolDefinition:
    """Tool definition for LLM integration."""
    name: str
    description: str
    parameters: Dict[str, Any]
    
    @classmethod
    def from_mcp_tool(cls, mcp_tool) -> 'ToolDefinition':
        """Create tool definition from MCP tool object."""
        schema = getattr(mcp_tool, "input_schema", None) or {
            "type": "object", 
            "properties": {}
        }
        
        return cls(
            name=mcp_tool.name,
            description=(mcp_tool.description or "")[:512],  # Truncate long descriptions
            parameters=schema
        )
    
    def to_llm_format(self) -> Dict[str, Any]:
        """Convert to LLM tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class MCPConnectionManager:
    """Manages MCP server connection lifecycle."""
    
    def __init__(self, config: MCPServerConfig):
        self._config = config
        self._exit_stack = AsyncExitStack()
        self._session: Optional[ClientSession] = None
        self._started = asyncio.Event()
        self._start_time: Optional[float] = None
    
    @property
    def is_ready(self) -> bool:
        """Check if connection is ready."""
        return self._started.is_set()
    
    @property
    def session(self) -> ClientSession:
        """Get active session (raises if not ready)."""
        if not self._session:
            raise RuntimeError("MCP session not initialized")
        return self._session
    
    async def start(self) -> None:
        """Start MCP server and establish connection."""
        if self.is_ready:
            log.warning("MCP connection already started")
            return
        
        log.info("Starting MCP stdio server: %s %s", 
                self._config.command, " ".join(self._config.args))
        
        self._start_time = time.perf_counter()
        
        try:
            stdio, write = await self._exit_stack.enter_async_context(
                stdio_client(self._config.parameters)
            )
            
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )
            
            await self._session.initialize()
            self._started.set()
            
            elapsed = time.perf_counter() - self._start_time
            log.info("MCP server initialized in %.2fs", elapsed)
            
        except Exception as e:
            log.exception("Failed to start MCP server (%s): %r", 
                         self._config.module_name, e)
            raise
    
    async def wait_ready(self) -> None:
        """Wait for connection to be ready."""
        log.debug("MCPConnectionManager.wait_ready()")
        await self._started.wait()
        log.debug("MCPConnectionManager: ready")
    
    async def close(self) -> None:
        """Close connection and cleanup resources."""
        log.info("Shutting down MCP connection…")
        try:
            await self._exit_stack.aclose()
            self._session = None
            self._started.clear()
            log.info("MCP connection closed cleanly")
        except Exception:
            log.exception("Error during MCP connection close")


class ToolCallExecutor:
    """Handles execution of tool calls through MCP."""
    
    def __init__(self, session_provider):
        self._session_provider = session_provider
    
    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool call and return the result."""
        session = self._session_provider()
        
        log.info("Calling tool '%s' with args=%s", name, arguments)
        start_time = time.perf_counter()
        
        try:
            result = await session.call_tool(name, arguments)
            elapsed = time.perf_counter() - start_time
            
            # Log result summary
            content_types = self._get_content_types(result)
            log.info("Tool '%s' completed in %.2fs (content=%s)", 
                    name, elapsed, content_types)
            
            return result
            
        except Exception as e:
            log.exception("Tool '%s' failed: %r", name, e)
            raise
    
    def _get_content_types(self, result) -> List[str]:
        """Extract content types from MCP result for logging."""
        try:
            content = getattr(result, "content", [])
            return [getattr(c, "type", type(c).__name__) for c in content]
        except Exception:
            return ["<unknown>"]


class ResultExtractor:
    """Extracts and processes results from MCP tool calls."""
    
    @staticmethod
    def extract_json(result) -> Any:
        """Extract JSON/text content from MCP tool result."""
        log.debug("extract_json: attempting to parse result content")
        
        try:
            # Try JSON content first
            for content_item in result.content:
                content_type = getattr(content_item, "type", "")
                if content_type == "json":
                    log.debug("extract_json: found JSON content")
                    return content_item.data
            
            # Fall back to text content
            for content_item in result.content:
                content_type = getattr(content_item, "type", "")
                if content_type == "text":
                    text = getattr(content_item, "text", "") or ""
                    preview = text[:200]
                    log.debug("extract_json: found TEXT content (preview=%r)", preview)
                    return text
                    
        except Exception as e:
            log.warning("extract_json failed to parse result content: %r", e)
        
        log.debug("extract_json: returning raw result")
        return result


class ToolRegistry:
    """Manages available tools and their definitions."""
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
    
    def register_tools(self, mcp_tools) -> None:
        """Register tools from MCP tool list."""
        self._tools.clear()
        
        for mcp_tool in mcp_tools:
            tool_def = ToolDefinition.from_mcp_tool(mcp_tool)
            self._tools[tool_def.name] = tool_def
            log.debug("Registered tool: %s", tool_def.name)
    
    def get_tool_names(self) -> List[str]:
        """Get list of available tool names."""
        return list(self._tools.keys())
    
    def get_llm_tools(self) -> List[Dict[str, Any]]:
        """Get tools in LLM format."""
        return [tool.to_llm_format() for tool in self._tools.values()]
    
    def has_tool(self, name: str) -> bool:
        """Check if tool is available."""
        return name in self._tools
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self._tools.get(name)


class MCPBridge:
    """High-level bridge for MCP server interaction."""
    
    def __init__(self, server_module: str, env: Optional[Dict[str, str]] = None):
        self._config = MCPServerConfig(
            module_name=server_module,
            environment=env or {}
        )
        
        self._connection = MCPConnectionManager(self._config)
        self._executor = ToolCallExecutor(lambda: self._connection.session)
        self._extractor = ResultExtractor()
        self._registry = ToolRegistry()
        
        log.debug("MCPBridge.__init__(server_module=%r, env_keys=%s)", 
                 server_module, list(self._config.environment.keys()))
    
    async def start(self) -> None:
        """Start the MCP bridge."""
        await self._connection.start()
    
    async def wait_ready(self) -> None:
        """Wait for the bridge to be ready."""
        await self._connection.wait_ready()
    
    async def close(self) -> None:
        """Close the bridge and cleanup resources."""
        await self._connection.close()
    
    async def list_tools(self):
        """List available tools from MCP server."""
        session = self._connection.session
        
        log.debug("Listing MCP tools…")
        start_time = time.perf_counter()
        
        try:
            response = await session.list_tools()
            elapsed = time.perf_counter() - start_time
            
            tool_names = [tool.name for tool in response.tools]
            log.info("Listed %d tools in %.2fs: %s", 
                    len(tool_names), elapsed, tool_names)
            
            # Register tools
            self._registry.register_tools(response.tools)
            
            return response.tools
            
        except Exception as e:
            log.exception("list_tools failed: %r", e)
            raise
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]):
        """Call a tool through MCP."""
        if not self._registry.has_tool(name):
            raise ValueError(f"Unknown tool: {name}")
        
        return await self._executor.execute(name, arguments)
    
    def extract_json(self, result) -> Any:
        """Extract JSON content from MCP result."""
        return self._extractor.extract_json(result)
    
    def tools_from_mcp(self, mcp_tools) -> List[Dict[str, Any]]:
        """Convert MCP tools to LLM format."""
        # Update registry if tools provided
        if mcp_tools:
            self._registry.register_tools(mcp_tools)
        
        return self._registry.get_llm_tools()
    
    @property
    def available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return self._registry.get_tool_names()
    
    @property
    def is_ready(self) -> bool:
        """Check if bridge is ready for use."""
        return self._connection.is_ready


# Backwards compatibility - maintain the same interface
def MCPBridge_legacy(server_module: str, env: Optional[Dict[str, str]] = None) -> MCPBridge:
    """Legacy constructor for backwards compatibility."""
    return MCPBridge(server_module, env)


# Export the main class
__all__ = ["MCPBridge", "MCPServerConfig", "ToolDefinition"]