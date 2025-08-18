# game_data/campaign_helpers.py
"""
Campaign management helpers for tracking game state, player characters, and session data.
Provides structured data models and managers for Pathfinder 2e campaigns.
"""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union, Protocol
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import logging

log = logging.getLogger(__name__)


class Alignment(Enum):
    """Character alignment options."""
    LAWFUL_GOOD = "LG"
    NEUTRAL_GOOD = "NG" 
    CHAOTIC_GOOD = "CG"
    LAWFUL_NEUTRAL = "LN"
    TRUE_NEUTRAL = "N"
    CHAOTIC_NEUTRAL = "CN"
    LAWFUL_EVIL = "LE"
    NEUTRAL_EVIL = "NE"
    CHAOTIC_EVIL = "CE"


class Size(Enum):
    """Creature size categories."""
    TINY = 1
    SMALL = 2
    MEDIUM = 3
    LARGE = 4
    HUGE = 5
    GARGANTUAN = 6


@dataclass
class AbilityScores:
    """Character ability scores."""
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    
    @property
    def str_modifier(self) -> int:
        return (self.strength - 10) // 2
    
    @property 
    def dex_modifier(self) -> int:
        return (self.dexterity - 10) // 2
    
    @property
    def con_modifier(self) -> int:
        return (self.constitution - 10) // 2
    
    @property
    def int_modifier(self) -> int:
        return (self.intelligence - 10) // 2
    
    @property
    def wis_modifier(self) -> int:
        return (self.wisdom - 10) // 2
    
    @property
    def cha_modifier(self) -> int:
        return (self.charisma - 10) // 2
    
    def get_modifier(self, ability: str) -> int:
        """Get modifier for named ability."""
        ability_map = {
            'str': self.str_modifier,
            'dex': self.dex_modifier, 
            'con': self.con_modifier,
            'int': self.int_modifier,
            'wis': self.wis_modifier,
            'cha': self.cha_modifier
        }
        return ability_map.get(ability.lower(), 0)


@dataclass
class SpellcastingEntry:
    """Spellcasting tradition and details."""
    tradition: str  # arcane, divine, occult, primal
    ability: str    # key ability (cha, int, wis, etc)
    proficiency: int = 0
    focus_points: int = 0
    spells_per_day: List[int] = field(default_factory=lambda: [0] * 11)
    known_spells: Dict[int, List[str]] = field(default_factory=dict)
    prepared_spells: Dict[int, List[str]] = field(default_factory=dict)
    
    @property
    def is_spontaneous(self) -> bool:
        """Check if this is spontaneous spellcasting."""
        return bool(self.known_spells) and not bool(self.prepared_spells)
    
    @property
    def is_prepared(self) -> bool:
        """Check if this is prepared spellcasting."""
        return bool(self.prepared_spells)


@dataclass 
class Equipment:
    """Equipment item with basic properties."""
    name: str
    quantity: int = 1
    bulk: float = 0.0
    value_cp: int = 0  # Value in copper pieces
    worn: bool = False
    invested: bool = False
    description: str = ""
    
    @property
    def value_gp(self) -> float:
        """Value in gold pieces."""
        return self.value_cp / 100.0


@dataclass
class Weapon(Equipment):
    """Weapon with combat statistics."""
    damage_dice: str = "1d4"
    damage_type: str = "bludgeoning"
    weapon_group: str = ""
    traits: List[str] = field(default_factory=list)
    range_increment: Optional[int] = None
    reload: Optional[int] = None
    
    @property
    def is_ranged(self) -> bool:
        """Check if weapon is ranged."""
        return self.range_increment is not None


@dataclass
class Armor(Equipment):
    """Armor with defensive statistics."""
    ac_bonus: int = 0
    dex_cap: Optional[int] = None
    check_penalty: int = 0
    speed_penalty: int = 0
    strength_requirement: int = 0
    armor_group: str = ""
    armor_traits: List[str] = field(default_factory=list)


@dataclass
class PlayerCharacter:
    """Complete player character data."""
    # Basic Information
    name: str
    player_name: str = ""
    character_class: str = ""
    level: int = 1
    ancestry: str = ""
    heritage: str = ""
    background: str = ""
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    size: Size = Size.MEDIUM
    
    # Core Stats
    abilities: AbilityScores = field(default_factory=AbilityScores)
    hit_points: int = 0
    max_hit_points: int = 0
    hero_points: int = 1
    
    # Experience and Advancement
    experience_points: int = 0
    
    # Combat Stats
    armor_class: int = 10
    perception: int = 0
    
    # Saves
    fortitude: int = 0
    reflex: int = 0
    will: int = 0
    
    # Skills (skill_name -> proficiency_bonus)
    skills: Dict[str, int] = field(default_factory=dict)
    
    # Feats and Features
    feats: List[str] = field(default_factory=list)
    class_features: List[str] = field(default_factory=list)
    
    # Equipment
    equipment: List[Equipment] = field(default_factory=list)
    weapons: List[Weapon] = field(default_factory=list)
    armor: List[Armor] = field(default_factory=list)
    
    # Spellcasting
    spellcasting: List[SpellcastingEntry] = field(default_factory=list)
    
    # Character Details
    deity: str = ""
    languages: List[str] = field(default_factory=list)
    notes: str = ""
    
    # Metadata
    created_date: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def update_timestamp(self) -> None:
        """Update the last modified timestamp."""
        self.last_updated = datetime.now()
    
    @property
    def ability_modifier(self) -> Dict[str, int]:
        """Get all ability modifiers as a dictionary."""
        return {
            'str': self.abilities.str_modifier,
            'dex': self.abilities.dex_modifier,
            'con': self.abilities.con_modifier,
            'int': self.abilities.int_modifier,
            'wis': self.abilities.wis_modifier,
            'cha': self.abilities.cha_modifier
        }
    
    def get_skill_bonus(self, skill_name: str) -> int:
        """Calculate total skill bonus."""
        base_proficiency = self.skills.get(skill_name, 0)
        # Would need skill-to-ability mapping to be completely accurate
        return base_proficiency
    
    def add_equipment(self, item: Equipment) -> None:
        """Add equipment item."""
        self.equipment.append(item)
        self.update_timestamp()
    
    def add_weapon(self, weapon: Weapon) -> None:
        """Add weapon."""
        self.weapons.append(weapon)
        self.update_timestamp()
    
    def add_armor(self, armor: Armor) -> None:
        """Add armor piece."""
        self.armor.append(armor)
        self.update_timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to their values
        data['alignment'] = self.alignment.value
        data['size'] = self.size.value
        # Convert datetime objects
        data['created_date'] = self.created_date.isoformat()
        data['last_updated'] = self.last_updated.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerCharacter':
        """Create from dictionary."""
        # Handle enum fields
        if 'alignment' in data:
            data['alignment'] = Alignment(data['alignment'])
        if 'size' in data:
            data['size'] = Size(data['size'])
        
        # Handle datetime fields
        if 'created_date' in data and isinstance(data['created_date'], str):
            data['created_date'] = datetime.fromisoformat(data['created_date'])
        if 'last_updated' in data and isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        
        # Handle nested dataclasses
        if 'abilities' in data and isinstance(data['abilities'], dict):
            data['abilities'] = AbilityScores(**data['abilities'])
        
        # Handle equipment lists
        if 'equipment' in data:
            data['equipment'] = [Equipment(**item) if isinstance(item, dict) else item 
                               for item in data['equipment']]
        
        if 'weapons' in data:
            data['weapons'] = [Weapon(**item) if isinstance(item, dict) else item 
                             for item in data['weapons']]
        
        if 'armor' in data:
            data['armor'] = [Armor(**item) if isinstance(item, dict) else item 
                           for item in data['armor']]
        
        if 'spellcasting' in data:
            data['spellcasting'] = [SpellcastingEntry(**item) if isinstance(item, dict) else item 
                                  for item in data['spellcasting']]
        
        return cls(**data)


@dataclass
class CampaignSession:
    """Individual game session data."""
    session_number: int
    session_date: date
    duration_minutes: int = 0
    experience_awarded: int = 0
    treasure_found: List[str] = field(default_factory=list)
    story_notes: str = ""
    dm_notes: str = ""
    attendance: List[str] = field(default_factory=list)  # Player names present
    
    @property
    def duration_hours(self) -> float:
        """Session duration in hours."""
        return self.duration_minutes / 60.0


@dataclass 
class Campaign:
    """Campaign-level data and metadata."""
    name: str
    description: str = ""
    dm_name: str = ""
    created_date: date = field(default_factory=date.today)
    
    # Campaign settings
    starting_level: int = 1
    allowed_ancestries: List[str] = field(default_factory=list)
    house_rules: List[str] = field(default_factory=list)
    
    # Progress tracking
    current_session: int = 0
    total_sessions: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['created_date'] = self.created_date.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Campaign':
        """Create from dictionary."""
        if 'created_date' in data and isinstance(data['created_date'], str):
            data['created_date'] = date.fromisoformat(data['created_date'])
        return cls(**data)


class CharacterDataManager:
    """Manages character data persistence and operations."""
    
    def __init__(self, data_directory: Union[str, Path] = "game_data/player_characters"):
        self.data_dir = Path(data_directory)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def save_character(self, character: PlayerCharacter) -> None:
        """Save character to JSON file."""
        filename = f"{character.name.lower().replace(' ', '_')}.json"
        filepath = self.data_dir / filename
        
        character.update_timestamp()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(character.to_dict(), f, indent=2, ensure_ascii=False)
            log.info("Saved character %s to %s", character.name, filepath)
        except Exception as e:
            log.error("Failed to save character %s: %s", character.name, e)
            raise
    
    def load_character(self, character_name: str) -> Optional[PlayerCharacter]:
        """Load character from JSON file."""
        filename = f"{character_name.lower().replace(' ', '_')}.json"
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            log.warning("Character file not found: %s", filepath)
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            character = PlayerCharacter.from_dict(data)
            log.info("Loaded character %s from %s", character.name, filepath)
            return character
        except Exception as e:
            log.error("Failed to load character %s: %s", character_name, e)
            return None
    
    def list_characters(self) -> List[str]:
        """List all available character names."""
        characters = []
        for file_path in self.data_dir.glob("*.json"):
            # Convert filename back to character name
            char_name = file_path.stem.replace('_', ' ').title()
            characters.append(char_name)
        return sorted(characters)
    
    def delete_character(self, character_name: str) -> bool:
        """Delete character file."""
        filename = f"{character_name.lower().replace(' ', '_')}.json"
        filepath = self.data_dir / filename
        
        if filepath.exists():
            try:
                filepath.unlink()
                log.info("Deleted character %s", character_name)
                return True
            except Exception as e:
                log.error("Failed to delete character %s: %s", character_name, e)
                return False
        return False


class CampaignDataManager:
    """Manages campaign-level data and session tracking."""
    
    def __init__(self, database_path: Union[str, Path] = "game_data/campaign.db"):
        self.db_path = Path(database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize campaign database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    dm_name TEXT,
                    created_date TEXT,
                    starting_level INTEGER DEFAULT 1,
                    current_session INTEGER DEFAULT 0,
                    total_sessions INTEGER DEFAULT 0,
                    settings_json TEXT
                );
                
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY,
                    campaign_id INTEGER,
                    session_number INTEGER,
                    session_date TEXT,
                    duration_minutes INTEGER DEFAULT 0,
                    experience_awarded INTEGER DEFAULT 0,
                    story_notes TEXT,
                    dm_notes TEXT,
                    session_data_json TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                );
                
                CREATE TABLE IF NOT EXISTS session_attendance (
                    session_id INTEGER,
                    player_name TEXT,
                    character_name TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                );
            """)
    
    def create_campaign(self, campaign: Campaign) -> int:
        """Create new campaign and return its ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            settings = {
                'allowed_ancestries': campaign.allowed_ancestries,
                'house_rules': campaign.house_rules
            }
            
            cursor.execute("""
                INSERT INTO campaigns 
                (name, description, dm_name, created_date, starting_level, 
                 current_session, total_sessions, settings_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campaign.name, campaign.description, campaign.dm_name,
                campaign.created_date.isoformat(), campaign.starting_level,
                campaign.current_session, campaign.total_sessions,
                json.dumps(settings)
            ))
            
            campaign_id = cursor.lastrowid
            log.info("Created campaign '%s' with ID %d", campaign.name, campaign_id)
            return campaign_id
    
    def get_campaign(self, campaign_name: str) -> Optional[Campaign]:
        """Get campaign by name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM campaigns WHERE name = ?", (campaign_name,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            settings = json.loads(row['settings_json'] or '{}')
            
            return Campaign(
                name=row['name'],
                description=row['description'] or '',
                dm_name=row['dm_name'] or '',
                created_date=date.fromisoformat(row['created_date']),
                starting_level=row['starting_level'],
                current_session=row['current_session'],
                total_sessions=row['total_sessions'],
                allowed_ancestries=settings.get('allowed_ancestries', []),
                house_rules=settings.get('house_rules', [])
            )
    
    def add_session(self, campaign_name: str, session: CampaignSession) -> int:
        """Add session to campaign."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get campaign ID
            cursor.execute("SELECT id FROM campaigns WHERE name = ?", (campaign_name,))
            campaign_row = cursor.fetch