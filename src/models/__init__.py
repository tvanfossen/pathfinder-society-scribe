# src/models/__init__.py
"""
Models package for Pathfinder 2e campaign management.

This package provides clean, modern class structures for managing
game data including characters, campaigns, equipment, and spellcasting.
"""

from .base import (
    Alignment,
    Size,
    DamageType,
    Tradition,
    ArmorCategory,
    WeaponCategory,
    Skill,
    Ability,
    Proficiency,
    Rarity,
    TimestampedModel,
)

from .abilities import AbilityScores

from .equipment import (
    Equipment,
    Weapon,
    Armor,
    Shield,
)

from .spellcasting import (
    Spell,
    SpellSlot,
    SpellcastingEntry,
)

from .character import (
    CharacterSkills,
    CharacterDefenses,
    PlayerCharacter,
)

from .campaign import (
    CampaignSession,
    Campaign,
)

__all__ = [
    # Base enums and classes
    'Alignment',
    'Size',
    'DamageType',
    'Tradition',
    'ArmorCategory',
    'WeaponCategory',
    'Skill',
    'Ability',
    'Proficiency',
    'Rarity',
    'TimestampedModel',
    
    # Abilities
    'AbilityScores',
    
    # Equipment
    'Equipment',
    'Weapon',
    'Armor',
    'Shield',
    
    # Spellcasting
    'Spell',
    'SpellSlot',
    'SpellcastingEntry',
    
    # Character
    'CharacterSkills',
    'CharacterDefenses',
    'PlayerCharacter',
    
    # Campaign
    'CampaignSession',
    'Campaign',
]