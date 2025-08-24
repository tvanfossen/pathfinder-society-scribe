# src/models/base.py
"""Base models and enumerations for the Pathfinder 2e campaign system."""

from enum import Enum
from typing import Protocol, Any, Dict
from datetime import datetime


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


class DamageType(Enum):
    """Damage type categories."""
    ACID = "acid"
    BLUDGEONING = "bludgeoning"
    COLD = "cold"
    ELECTRICITY = "electricity"
    FIRE = "fire"
    FORCE = "force"
    MENTAL = "mental"
    NEGATIVE = "negative"
    PIERCING = "piercing"
    POISON = "poison"
    POSITIVE = "positive"
    SLASHING = "slashing"
    SONIC = "sonic"


class Tradition(Enum):
    """Spellcasting traditions."""
    ARCANE = "arcane"
    DIVINE = "divine"
    OCCULT = "occult"
    PRIMAL = "primal"


class ArmorCategory(Enum):
    """Armor categories."""
    UNARMORED = "unarmored"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class WeaponCategory(Enum):
    """Weapon categories."""
    SIMPLE = "simple"
    MARTIAL = "martial"
    ADVANCED = "advanced"
    UNARMED = "unarmed"


class Skill(Enum):
    """Skills in Pathfinder 2e."""
    ACROBATICS = "acrobatics"
    ARCANA = "arcana"
    ATHLETICS = "athletics"
    CRAFTING = "crafting"
    DECEPTION = "deception"
    DIPLOMACY = "diplomacy"
    INTIMIDATION = "intimidation"
    LORE = "lore"
    MEDICINE = "medicine"
    NATURE = "nature"
    OCCULTISM = "occultism"
    PERFORMANCE = "performance"
    RELIGION = "religion"
    SOCIETY = "society"
    STEALTH = "stealth"
    SURVIVAL = "survival"
    THIEVERY = "thievery"


class Ability(Enum):
    """Ability scores."""
    STRENGTH = "str"
    DEXTERITY = "dex"
    CONSTITUTION = "con"
    INTELLIGENCE = "int"
    WISDOM = "wis"
    CHARISMA = "cha"


class Proficiency(Enum):
    """Proficiency ranks."""
    UNTRAINED = 0
    TRAINED = 2
    EXPERT = 4
    MASTER = 6
    LEGENDARY = 8


class Rarity(Enum):
    """Item/feat rarity."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    UNIQUE = "unique"


class SerializableModel(Protocol):
    """Protocol for serializable models."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        ...
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SerializableModel':
        """Create model from dictionary."""
        ...


class TimestampedModel:
    """Mixin for models with timestamps."""
    
    def __init__(self):
        self._created_at = datetime.now()
        self._updated_at = datetime.now()
    
    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at
    
    def touch(self) -> None:
        """Update the last modified timestamp."""
        self._updated_at = datetime.now()