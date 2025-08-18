# stdio-only MCP server for Pathfinder 2e tools
from __future__ import annotations
from typing import Iterable
from mcp.server.fastmcp import FastMCP

from pf2e_mcp.registry.base import BaseToolRegistry
from pf2e_mcp.tools.dice import DiceToolset
from pf2e_mcp.tools.db_tools import PF2eDBToolset

import logging
from utility.logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)

def build_mcp(registries: Iterable[BaseToolRegistry] | None = None) -> FastMCP:
    m = FastMCP(name="Pathfinder2e-MCP")
    regs = registries or (DiceToolset(), PF2eDBToolset())
    for r in regs:
        r.register(m)
    return m


# expose a module-level object for `mcp dev`
mcp = build_mcp()

if __name__ == "__main__":
    # run over stdio (what MCP clients/dev runner expect)
    mcp.run()
