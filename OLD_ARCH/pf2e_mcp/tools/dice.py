# mcp_server/tools/dice.py
from __future__ import annotations
import random
from pydantic import BaseModel, Field, conint
from mcp.server.fastmcp import FastMCP
from pf2e_mcp.registry.base import BaseToolRegistry

import logging
from utility.logging_config import setup_logging

setup_logging()
log = logging.getLogger(__name__)

class RollResult(BaseModel):
    faces: conint(ge=2) = Field(..., description="Number of faces on the die.")
    roll: int = Field(..., description="The resulting face value (1..faces).")


class DiceToolset(BaseToolRegistry):
    def register(self, mcp: FastMCP) -> None:

        @mcp.tool(name="roll_dice")
        def roll_dice(dice_faces: conint(ge=2) = 20) -> RollResult:
            """
            Roll a single die with a given number of faces.
            Useful for quick checks (e.g., d20) within chat workflows.
            """
            log.debug("roll_dice: received request to roll %s-faced die", dice_faces)
            try:
                faces_int = int(dice_faces)
                val = random.randint(1, faces_int)
                log.info("roll_dice: rolled d%s -> %s", faces_int, val)
                return RollResult(faces=faces_int, roll=val)
            except Exception as e:
                log.exception("roll_dice: failed to roll die: %r", e)
                raise
