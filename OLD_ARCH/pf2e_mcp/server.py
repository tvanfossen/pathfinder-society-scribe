# pf2e_mcp/server.py
# stdio-only MCP server for Pathfinder 2e tools
from __future__ import annotations
from typing import Iterable
from mcp.server.fastmcp import FastMCP

from pf2e_mcp.registry.base import BaseToolRegistry
from pf2e_mcp.tools.dice import DiceToolset
from pf2e_mcp.tools.db_tools import PF2eDBToolset
from pf2e_mcp.tools.campaign_tools import CampaignToolset

import logging
from utility.logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)

def build_mcp(registries: Iterable[BaseToolRegistry] | None = None) -> FastMCP:
    """Build the MCP server with all available toolsets."""
    m = FastMCP(name="Pathfinder2e-MCP")
    
    # Default registries include dice, database tools, and campaign management
    regs = registries or (
        DiceToolset(), 
        PF2eDBToolset(), 
        CampaignToolset()
    )
    
    for r in regs:
        log.info("Registering toolset: %s", r.__class__.__name__)
        r.register(m)
    
    log.info("MCP server built with %d toolsets", len(list(regs)))
    return m


# expose a module-level object for `mcp dev`
mcp = build_mcp()

if __name__ == "__main__":
    # run over stdio (what MCP clients/dev runner expect)
    log.info("Starting Pathfinder 2e MCP server...")
    mcp.run()