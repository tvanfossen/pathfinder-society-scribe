# mcp_server/registry/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from mcp.server.fastmcp import FastMCP


class BaseToolRegistry(ABC):
    """Base class for modular tool registries."""

    @abstractmethod
    def register(self, mcp: FastMCP) -> None:
        """Implementations should decorate/register tools on the given FastMCP instance."""
        raise NotImplementedError
