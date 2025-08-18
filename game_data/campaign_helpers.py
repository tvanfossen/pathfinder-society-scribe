# game_data/campaign_helpers.py
"""
Enhanced campaign management helpers with modern Python patterns.
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
from abc import ABC, abstractmethod
import logging

log = logging.getLogger(__name__)


# Custom Exceptions
class CampaignDataError(Exception):
    """Base exception for campaign data operations."""
    pass


class CampaignNotFoundError(CampaignDataError):
    """Raised when a campaign cannot be found."""
    pass


class CharacterNotFoundError(CampaignDataError):
    """Raised when a character cannot be found."""
    pass


class ValidationError(CampaignDataError):
    """Raised when data validation fails."""
    pass


# Enums
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


class AttendanceStatus(Enum):
    """Session attendance status options."""
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    LEFT_EARLY = "left_early"


# Data Models
@dataclass
class AbilityScores:
    """Character ability scores with validation."""
    strength: int = field(default=10, metadata={"min": 1, "max": 30})
    dexterity: int = field(default=10, metadata={"min": 1, "max": 30})
    constitution: int = field(default=10, metadata={"min": 1, "max": 30})
    intelligence: int = field(default=10, metadata={"min": 1, "max": 30})
    wisdom: int = field(default=10, metadata={"min": 1, "max": 30})
    charisma: int = field(default=10, metadata={"min": 1, "max": 30})
    
    def __post_init__(self):
        """Validate ability scores on creation."""
        for field_name, value in self.__dict__.items():
            field_info = self.__dataclass_fields__[field_name]
            min_val = field_info.metadata.get("min", 1)
            max_val = field_info.metadata.get("max", 30)
            if not (min_val <= value <= max_val):
                raise ValidationError(f"{field_name} must be between {min_val} and {max_val}, got {value}")
    
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
    
    def __post_init__(self):
        """Validate spellcasting data."""
        valid_traditions = {'arcane', 'divine', 'occult', 'primal'}
        if self.tradition.lower() not in valid_traditions:
            raise ValidationError(f"Invalid tradition: {self.tradition}. Must be one of {valid_traditions}")
        
        valid_abilities = {'str', 'dex', 'con', 'int', 'wis', 'cha'}
        if self.ability.lower() not in valid_abilities:
            raise ValidationError(f"Invalid ability: {self.ability}. Must be one of {valid_abilities}")
    
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
    quantity: int = field(default=1, metadata={"min": 0})
    bulk: float = field(default=0.0, metadata={"min": 0.0})
    value_cp: int = field(default=0, metadata={"min": 0})  # Value in copper pieces
    worn: bool = False
    invested: bool = False
    description: str = ""
    
    def __post_init__(self):
        """Validate equipment data."""
        if not self.name.strip():
            raise ValidationError("Equipment name cannot be empty")
        
        for field_name, value in [("quantity", self.quantity), ("bulk", self.bulk), ("value_cp", self.value_cp)]:
            field_info = self.__dataclass_fields__[field_name]
            min_val = field_info.metadata.get("min", 0)
            if value < min_val:
                raise ValidationError(f"{field_name} cannot be negative, got {value}")
    
    @property
    def value_gp(self) -> float:
        """Value in gold pieces."""
        return self.value_cp / 100.0
    
    @property
    def total_bulk(self) -> float:
        """Total bulk for this item stack."""
        return self.bulk * self.quantity


@dataclass
class Weapon(Equipment):
    """Weapon with combat statistics."""
    damage_dice: str = "1d4"
    damage_type: str = "bludgeoning"
    weapon_group: str = ""
    traits: List[str] = field(default_factory=list)
    range_increment: Optional[int] = None
    reload: Optional[int] = None
    
    def __post_init__(self):
        """Validate weapon data."""
        super().__post_init__()
        
        if self.range_increment is not None and self.range_increment <= 0:
            raise ValidationError("Range increment must be positive")
        
        if self.reload is not None and self.reload < 0:
            raise ValidationError("Reload value cannot be negative")
    
    @property
    def is_ranged(self) -> bool:
        """Check if weapon is ranged."""
        return self.range_increment is not None


@dataclass
class Armor(Equipment):
    """Armor with defensive statistics."""
    ac_bonus: int = field(default=0, metadata={"min": 0})
    dex_cap: Optional[int] = None
    check_penalty: int = field(default=0, metadata={"max": 0})
    speed_penalty: int = field(default=0, metadata={"max": 0})
    strength_requirement: int = field(default=0, metadata={"min": 0})
    armor_group: str = ""
    armor_traits: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate armor data."""
        super().__post_init__()
        
        if self.ac_bonus < 0:
            raise ValidationError("AC bonus cannot be negative")
        
        if self.check_penalty > 0:
            raise ValidationError("Check penalty must be zero or negative")
        
        if self.speed_penalty > 0:
            raise ValidationError("Speed penalty must be zero or negative")


@dataclass
class PlayerCharacter:
    """Complete player character data with validation."""
    # Basic Information
    name: str
    player_name: str = ""
    character_class: str = ""
    level: int = field(default=1, metadata={"min": 1, "max": 20})
    ancestry: str = ""
    heritage: str = ""
    background: str = ""
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    size: Size = Size.MEDIUM
    
    # Core Stats
    abilities: AbilityScores = field(default_factory=AbilityScores)
    hit_points: int = field(default=0, metadata={"min": 0})
    max_hit_points: int = field(default=0, metadata={"min": 1})
    hero_points: int = field(default=1, metadata={"min": 0, "max": 3})
    
    # Experience and Advancement
    experience_points: int = field(default=0, metadata={"min": 0})
    
    # Combat Stats
    armor_class: int = field(default=10, metadata={"min": 10})
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
    
    def __post_init__(self):
        """Validate character data."""
        if not self.name.strip():
            raise ValidationError("Character name cannot be empty")
        
        # Validate level constraints
        field_info = self.__dataclass_fields__["level"]
        min_level = field_info.metadata.get("min", 1)
        max_level = field_info.metadata.get("max", 20)
        if not (min_level <= self.level <= max_level):
            raise ValidationError(f"Level must be between {min_level} and {max_level}")
        
        # Validate hit points
        if self.hit_points > self.max_hit_points:
            raise ValidationError("Current hit points cannot exceed maximum hit points")
        
        # Validate hero points
        field_info = self.__dataclass_fields__["hero_points"]
        max_hero = field_info.metadata.get("max", 3)
        if self.hero_points > max_hero:
            raise ValidationError(f"Hero points cannot exceed {max_hero}")
    
    def update_timestamp(self) -> None:
        """Update the last modified timestamp."""
        self.last_updated = datetime.now()
    
    @property
    def ability_modifiers(self) -> Dict[str, int]:
        """Get all ability modifiers as a dictionary."""
        return {
            'str': self.abilities.str_modifier,
            'dex': self.abilities.dex_modifier,
            'con': self.abilities.con_modifier,
            'int': self.abilities.int_modifier,
            'wis': self.abilities.wis_modifier,
            'cha': self.abilities.cha_modifier
        }
    
    @property
    def total_bulk_carried(self) -> float:
        """Calculate total bulk of carried equipment."""
        total = sum(item.total_bulk for item in self.equipment)
        total += sum(weapon.total_bulk for weapon in self.weapons)
        total += sum(armor_piece.total_bulk for armor_piece in self.armor)
        return total
    
    @property
    def bulk_limit(self) -> int:
        """Calculate bulk carrying capacity."""
        return 5 + self.abilities.str_modifier
    
    @property
    def is_encumbered(self) -> bool:
        """Check if character is encumbered by bulk."""
        return self.total_bulk_carried > self.bulk_limit
    
    def get_skill_bonus(self, skill_name: str) -> int:
        """Calculate total skill bonus."""
        base_proficiency = self.skills.get(skill_name, 0)
        # Would need skill-to-ability mapping to be completely accurate
        return base_proficiency
    
    def add_equipment(self, item: Equipment) -> None:
        """Add equipment item with validation."""
        if not isinstance(item, Equipment):
            raise ValidationError("Item must be an Equipment instance")
        self.equipment.append(item)
        self.update_timestamp()
    
    def add_weapon(self, weapon: Weapon) -> None:
        """Add weapon with validation."""
        if not isinstance(weapon, Weapon):
            raise ValidationError("Item must be a Weapon instance")
        self.weapons.append(weapon)
        self.update_timestamp()