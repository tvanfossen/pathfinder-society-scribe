# pf2e_mcp/tools/campaign_tools.py
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from pydantic import BaseModel, Field, conint
from mcp.server.fastmcp import FastMCP
from pf2e_mcp.registry.base import BaseToolRegistry

# Import the campaign helpers (assuming they're available)
# You'll need to adjust these imports based on your actual file structure
try:
    from game_data.campaign_helpers import (
        PlayerCharacter, Campaign, CampaignSession,
        CharacterDataManager, CampaignDataManager,
        Alignment, Size, Ability, Skill, ProficiencyRank,
        AbilityScores, Equipment, SimpleEquipment, Weapon, Armor
    )
except ImportError:
    # Fallback for development - you might want to handle this differently
    logging.warning("Could not import campaign_helpers - campaign tools may not work properly")

log = logging.getLogger(__name__)

# Configuration
DEFAULT_SAVE_DIR = os.getenv("PF2E_SAVE_DIR", "save_files")
DEFAULT_CAMPAIGN_DB = os.path.join(DEFAULT_SAVE_DIR, "campaign.db")
DEFAULT_CHARACTER_DIR = os.path.join(DEFAULT_SAVE_DIR, "characters")

# Pydantic models for MCP responses
class BotNPCInfo(BaseModel):
    """Information about the bot's NPC identity."""
    name: str
    description: Optional[str] = None
    campaign_id: Optional[int] = None
    created_date: str
    last_updated: str

class CharacterSummary(BaseModel):
    """Summary information about a character."""
    name: str
    player_name: str
    character_class: str
    level: int
    ancestry: str
    alignment: str
    hit_points: int
    max_hit_points: int
    last_updated: str

class CampaignInfo(BaseModel):
    """Campaign information."""
    name: str
    description: str
    dm_name: str
    current_session: int
    total_sessions: int
    created_date: str

class SessionSummary(BaseModel):
    """Session summary information."""
    session_number: int
    session_date: str
    duration_minutes: int
    experience_awarded: int
    attendance: List[str]
    story_notes: Optional[str] = None

class OperationResult(BaseModel):
    """Generic operation result."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class CampaignToolset(BaseToolRegistry):
    """Campaign management tools for Discord bot integration."""
    
    def __init__(self, 
                 save_dir: str = DEFAULT_SAVE_DIR,
                 campaign_db: str = DEFAULT_CAMPAIGN_DB,
                 character_dir: str = DEFAULT_CHARACTER_DIR):
        self.save_dir = Path(save_dir)
        self.campaign_db = campaign_db
        self.character_dir = character_dir
        
        # Ensure directories exist
        self.save_dir.mkdir(parents=True, exist_ok=True)
        Path(character_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize managers
        self.campaign_manager = CampaignDataManager(self.campaign_db)
        self.character_manager = CharacterDataManager(self.character_dir)
        
        log.info("CampaignToolset initialized with save_dir=%s", self.save_dir)

    def register(self, mcp: FastMCP) -> None:
        """Register all campaign management tools."""
        
        @mcp.tool(name="bot_set_npc_identity")
        def bot_set_npc_identity(
            name: str,
            description: Optional[str] = None,
            campaign_name: Optional[str] = None
        ) -> BotNPCInfo:
            """
            Set the bot's identity as an NPC in the campaign database.
            This allows the bot to have a persistent identity within campaigns.
            """
            log.info("Setting bot NPC identity: name=%s, campaign=%s", name, campaign_name)
            
            try:
                # Create the bot identity record in the database
                with self.campaign_manager._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Get campaign ID if campaign name is provided
                    campaign_id = None
                    if campaign_name:
                        cursor.execute("SELECT id FROM campaigns WHERE name = ?", (campaign_name,))
                        row = cursor.fetchone()
                        if row:
                            campaign_id = row[0]
                        else:
                            log.warning("Campaign '%s' not found", campaign_name)
                    
                    # Insert or update bot NPC record
                    now = datetime.now().isoformat()
                    cursor.execute("""
                        INSERT OR REPLACE INTO bot_npcs (
                            name, description, campaign_id, created_date, last_updated
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (name, description, campaign_id, now, now))
                    
                    # Ensure the table exists (create if needed)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS bot_npcs (
                            id INTEGER PRIMARY KEY,
                            name TEXT UNIQUE NOT NULL,
                            description TEXT,
                            campaign_id INTEGER,
                            created_date TEXT,
                            last_updated TEXT,
                            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                        )
                    """)
                    
                    conn.commit()
                
                log.info("Bot NPC identity set successfully: %s", name)
                return BotNPCInfo(
                    name=name,
                    description=description,
                    campaign_id=campaign_id,
                    created_date=now,
                    last_updated=now
                )
                
            except Exception as e:
                log.error("Failed to set bot NPC identity: %s", e)
                raise

        @mcp.tool(name="bot_get_npc_identity")
        def bot_get_npc_identity(name: Optional[str] = None) -> Optional[BotNPCInfo]:
            """
            Get the bot's current NPC identity from the database.
            If no name is provided, returns the most recently updated identity.
            """
            try:
                with self.campaign_manager._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    if name:
                        cursor.execute("""
                            SELECT name, description, campaign_id, created_date, last_updated
                            FROM bot_npcs WHERE name = ?
                        """, (name,))
                    else:
                        cursor.execute("""
                            SELECT name, description, campaign_id, created_date, last_updated
                            FROM bot_npcs ORDER BY last_updated DESC LIMIT 1
                        """)
                    
                    row = cursor.fetchone()
                    if row:
                        return BotNPCInfo(
                            name=row[0],
                            description=row[1],
                            campaign_id=row[2],
                            created_date=row[3],
                            last_updated=row[4]
                        )
                    return None
                    
            except Exception as e:
                log.error("Failed to get bot NPC identity: %s", e)
                return None

        @mcp.tool(name="create_campaign")
        def create_campaign(
            name: str,
            description: str = "",
            dm_name: str = "",
            starting_level: conint(ge=1, le=20) = 1
        ) -> OperationResult:
            """
            Create a new campaign in the database.
            """
            log.info("Creating campaign: %s", name)
            
            try:
                campaign = Campaign(
                    name=name,
                    description=description,
                    dm_name=dm_name,
                    starting_level=int(starting_level)
                )
                
                campaign_id = self.campaign_manager.create_campaign(campaign)
                
                return OperationResult(
                    success=True,
                    message=f"Campaign '{name}' created successfully",
                    data={"campaign_id": campaign_id}
                )
                
            except Exception as e:
                log.error("Failed to create campaign: %s", e)
                return OperationResult(
                    success=False,
                    message=f"Failed to create campaign: {str(e)}"
                )

        @mcp.tool(name="get_campaign")
        def get_campaign(name: str) -> Optional[CampaignInfo]:
            """
            Get campaign information by name.
            """
            try:
                campaign = self.campaign_manager.get_campaign(name)
                if campaign:
                    return CampaignInfo(
                        name=campaign.name,
                        description=campaign.description,
                        dm_name=campaign.dm_name,
                        current_session=campaign.current_session,
                        total_sessions=campaign.total_sessions,
                        created_date=campaign.created_date.isoformat()
                    )
                return None
                
            except Exception as e:
                log.error("Failed to get campaign: %s", e)
                return None

        @mcp.tool(name="save_character")
        def save_character(
            name: str,
            player_name: str,
            character_class: str,
            level: conint(ge=1, le=20) = 1,
            ancestry: str = "",
            background: str = "",
            alignment: str = "N",
            max_hit_points: conint(ge=1) = 1
        ) -> OperationResult:
            """
            Save a player character to the database.
            """
            log.info("Saving character: %s (player: %s)", name, player_name)
            
            try:
                # Create character with basic info
                character = PlayerCharacter(
                    name=name,
                    player_name=player_name,
                    character_class=character_class,
                    level=int(level),
                    ancestry=ancestry,
                    background=background,
                    alignment=Alignment.TRUE_NEUTRAL,  # Default, could parse alignment string
                    max_hit_points=int(max_hit_points)
                )
                
                # Set current HP to max HP initially
                character.hit_points = character.max_hit_points
                
                self.character_manager.save_character(character)
                
                return OperationResult(
                    success=True,
                    message=f"Character '{name}' saved successfully"
                )
                
            except Exception as e:
                log.error("Failed to save character: %s", e)
                return OperationResult(
                    success=False,
                    message=f"Failed to save character: {str(e)}"
                )

        @mcp.tool(name="load_character")
        def load_character(name: str) -> Optional[CharacterSummary]:
            """
            Load a character by name and return summary information.
            """
            try:
                character = self.character_manager.load_character(name)
                if character:
                    return CharacterSummary(
                        name=character.name,
                        player_name=character.player_name,
                        character_class=character.character_class,
                        level=character.level,
                        ancestry=character.ancestry,
                        alignment=character.alignment.value if hasattr(character.alignment, 'value') else str(character.alignment),
                        hit_points=character.hit_points,
                        max_hit_points=character.max_hit_points,
                        last_updated=character.last_updated.isoformat()
                    )
                return None
                
            except Exception as e:
                log.error("Failed to load character: %s", e)
                return None

        @mcp.tool(name="list_characters")
        def list_characters() -> List[str]:
            """
            List all available character names.
            """
            try:
                return self.character_manager.list_characters()
            except Exception as e:
                log.error("Failed to list characters: %s", e)
                return []

        @mcp.tool(name="update_character_hp")
        def update_character_hp(
            name: str,
            current_hp: conint(ge=0),
            max_hp: Optional[conint(ge=1)] = None
        ) -> OperationResult:
            """
            Update a character's hit points.
            """
            try:
                character = self.character_manager.load_character(name)
                if not character:
                    return OperationResult(
                        success=False,
                        message=f"Character '{name}' not found"
                    )
                
                character.hit_points = int(current_hp)
                if max_hp is not None:
                    character.max_hit_points = int(max_hp)
                
                # Ensure current HP doesn't exceed max HP
                character.hit_points = min(character.hit_points, character.max_hit_points)
                
                self.character_manager.save_character(character)
                
                return OperationResult(
                    success=True,
                    message=f"Updated {name}'s HP: {character.hit_points}/{character.max_hit_points}"
                )
                
            except Exception as e:
                log.error("Failed to update character HP: %s", e)
                return OperationResult(
                    success=False,
                    message=f"Failed to update HP: {str(e)}"
                )

        @mcp.tool(name="add_session")
        def add_session(
            campaign_name: str,
            session_number: int,
            session_date: str,  # ISO format YYYY-MM-DD
            duration_minutes: conint(ge=0) = 0,
            experience_awarded: conint(ge=0) = 0,
            story_notes: str = "",
            attendance: List[str] = Field(default_factory=list)
        ) -> OperationResult:
            """
            Add a session record to a campaign.
            """
            log.info("Adding session %d to campaign %s", session_number, campaign_name)
            
            try:
                session_date_obj = date.fromisoformat(session_date)
                
                session = CampaignSession(
                    session_number=session_number,
                    session_date=session_date_obj,
                    duration_minutes=int(duration_minutes),
                    experience_awarded=int(experience_awarded),
                    story_notes=story_notes,
                    attendance=attendance
                )
                
                session_id = self.campaign_manager.add_session(campaign_name, session)
                
                return OperationResult(
                    success=True,
                    message=f"Session {session_number} added to campaign '{campaign_name}'",
                    data={"session_id": session_id}
                )
                
            except Exception as e:
                log.error("Failed to add session: %s", e)
                return OperationResult(
                    success=False,
                    message=f"Failed to add session: {str(e)}"
                )

        @mcp.tool(name="character_heal")
        def character_heal(name: str, amount: conint(ge=1)) -> OperationResult:
            """
            Heal a character by the specified amount.
            """
            try:
                character = self.character_manager.load_character(name)
                if not character:
                    return OperationResult(
                        success=False,
                        message=f"Character '{name}' not found"
                    )
                
                old_hp = character.hit_points
                character.heal(int(amount))
                self.character_manager.save_character(character)
                
                healed = character.hit_points - old_hp
                
                return OperationResult(
                    success=True,
                    message=f"{name} healed {healed} HP ({old_hp} → {character.hit_points}/{character.max_hit_points})"
                )
                
            except Exception as e:
                log.error("Failed to heal character: %s", e)
                return OperationResult(
                    success=False,
                    message=f"Failed to heal character: {str(e)}"
                )

        @mcp.tool(name="character_take_damage")
        def character_take_damage(name: str, amount: conint(ge=1)) -> OperationResult:
            """
            Apply damage to a character.
            """
            try:
                character = self.character_manager.load_character(name)
                if not character:
                    return OperationResult(
                        success=False,
                        message=f"Character '{name}' not found"
                    )
                
                old_hp = character.hit_points
                character.take_damage(int(amount))
                self.character_manager.save_character(character)
                
                damage_taken = old_hp - character.hit_points
                status = " (unconscious)" if not character.is_conscious else ""
                
                return OperationResult(
                    success=True,
                    message=f"{name} took {damage_taken} damage ({old_hp} → {character.hit_points}/{character.max_hit_points}){status}"
                )
                
            except Exception as e:
                log.error("Failed to apply damage: %s", e)
                return OperationResult(
                    success=False,
                    message=f"Failed to apply damage: {str(e)}"
                )

    def _get_connection(self):
        """Helper method to get database connection (for the bot NPC functionality)."""
        import sqlite3
        conn = sqlite3.connect(self.campaign_db)
        conn.row_factory = sqlite3.Row
        return conn