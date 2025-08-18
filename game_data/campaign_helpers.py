"""
Modern campaign management system with optimized class structures.
Follows SOLID principles, DRY, KISS, and modern Python best practices.
"""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union, Protocol, ClassVar
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, IntEnum
from abc import ABC, abstractmethod
import logging
from functools import cached_property

log = logging.getLogger(__name__)

# Constants
ABILITY_SCORE_DEFAULT = 10
SPELL_LEVELS_MAX = 10


class Alignment(Enum):
    """Character alignment with descriptive properties."""
    LAWFUL_GOOD = ("LG", "Lawful Good")
    NEUTRAL_GOOD = ("NG", "Neutral Good")
    CHAOTIC_GOOD = ("CG", "Chaotic Good")
    LAWFUL_NEUTRAL = ("LN", "Lawful Neutral")
    TRUE_NEUTRAL = ("N", "True Neutral")
    CHAOTIC_NEUTRAL = ("CN", "Chaotic Neutral")
    LAWFUL_EVIL = ("LE", "Lawful Evil")
    NEUTRAL_EVIL = ("NE", "Neutral Evil")
    CHAOTIC_EVIL = ("CE", "Chaotic Evil")
    
    def __init__(self, code: str, description: str):
        self.code = code
        self.description = description
    
    @property
    def is_good(self) -> bool:
        return self in (self.LAWFUL_GOOD, self.NEUTRAL_GOOD, self.CHAOTIC_GOOD)
    
    @property
    def is_evil(self) -> bool:
        return self in (self.LAWFUL_EVIL, self.NEUTRAL_EVIL, self.CHAOTIC_EVIL)
    
    @property
    def is_lawful(self) -> bool:
        return self in (self.LAWFUL_GOOD, self.LAWFUL_NEUTRAL, self.LAWFUL_EVIL)
    
    @property
    def is_chaotic(self) -> bool:
        return self in (self.CHAOTIC_GOOD, self.CHAOTIC_NEUTRAL, self.CHAOTIC_EVIL)


class Size(IntEnum):
    """Creature size categories with space calculations."""
    TINY = 1
    SMALL = 2
    MEDIUM = 3
    LARGE = 4
    HUGE = 5
    GARGANTUAN = 6
    
    @property
    def space_feet(self) -> int:
        """Space occupied in feet."""
        return {
            self.TINY: 2.5,
            self.SMALL: 5,
            self.MEDIUM: 5,
            self.LARGE: 10,
            self.HUGE: 15,
            self.GARGANTUAN: 20
        }[self]
    
    @property
    def reach_feet(self) -> int:
        """Natural reach in feet."""
        return 5 if self <= self.MEDIUM else self.space_feet


class Ability(Enum):
    """Ability scores with their key attributes."""
    STRENGTH = ("str", "Strength")
    DEXTERITY = ("dex", "Dexterity")
    CONSTITUTION = ("con", "Constitution")
    INTELLIGENCE = ("int", "Intelligence")
    WISDOM = ("wis", "Wisdom")
    CHARISMA = ("cha", "Charisma")
    
    def __init__(self, abbrev: str, full_name: str):
        self.abbrev = abbrev
        self.full_name = full_name


class Skill(Enum):
    """Skills with their key abilities."""
    ACROBATICS = ("Acrobatics", Ability.DEXTERITY)
    ARCANA = ("Arcana", Ability.INTELLIGENCE)
    ATHLETICS = ("Athletics", Ability.STRENGTH)
    CRAFTING = ("Crafting", Ability.INTELLIGENCE)
    DECEPTION = ("Deception", Ability.CHARISMA)
    DIPLOMACY = ("Diplomacy", Ability.CHARISMA)
    INTIMIDATION = ("Intimidation", Ability.CHARISMA)
    LORE = ("Lore", Ability.INTELLIGENCE)
    MEDICINE = ("Medicine", Ability.WISDOM)
    NATURE = ("Nature", Ability.WISDOM)
    OCCULTISM = ("Occultism", Ability.INTELLIGENCE)
    PERCEPTION = ("Perception", Ability.WISDOM)
    PERFORMANCE = ("Performance", Ability.CHARISMA)
    RELIGION = ("Religion", Ability.WISDOM)
    SOCIETY = ("Society", Ability.INTELLIGENCE)
    STEALTH = ("Stealth", Ability.DEXTERITY)
    SURVIVAL = ("Survival", Ability.WISDOM)
    THIEVERY = ("Thievery", Ability.DEXTERITY)
    
    def __init__(self, name: str, key_ability: Ability):
        self.skill_name = name
        self.key_ability = key_ability


class ProficiencyRank(IntEnum):
    """Proficiency ranks with bonuses."""
    UNTRAINED = 0
    TRAINED = 2
    EXPERT = 4
    MASTER = 6
    LEGENDARY = 8


@dataclass
class AbilityScores:
    """Character ability scores with validation and calculated modifiers."""
    strength: int = ABILITY_SCORE_DEFAULT
    dexterity: int = ABILITY_SCORE_DEFAULT
    constitution: int = ABILITY_SCORE_DEFAULT
    intelligence: int = ABILITY_SCORE_DEFAULT
    wisdom: int = ABILITY_SCORE_DEFAULT
    charisma: int = ABILITY_SCORE_DEFAULT
    
    def __post_init__(self):
        """Validate ability scores."""
        for ability_name in ('strength', 'dexterity', 'constitution', 
                           'intelligence', 'wisdom', 'charisma'):
            value = getattr(self, ability_name)
            if not isinstance(value, int) or value < 1 or value > 30:
                raise ValueError(f"{ability_name} must be between 1 and 30, got {value}")
    
    @staticmethod
    def calculate_modifier(score: int) -> int:
        """Calculate ability modifier from score."""
        return (score - 10) // 2
    
    def get_score(self, ability: Ability) -> int:
        """Get ability score by enum."""
        return getattr(self, ability.abbrev + 'erity' if ability == Ability.DEXTERITY 
                      else ability.abbrev + 'ength' if ability == Ability.STRENGTH
                      else ability.abbrev + 'titution' if ability == Ability.CONSTITUTION
                      else ability.abbrev + 'elligence' if ability == Ability.INTELLIGENCE
                      else ability.full_name.lower())
    
    def get_modifier(self, ability: Ability) -> int:
        """Get ability modifier by enum."""
        return self.calculate_modifier(self.get_score(ability))
    
    @property
    def all_modifiers(self) -> Dict[Ability, int]:
        """Get all ability modifiers."""
        return {ability: self.get_modifier(ability) for ability in Ability}


@dataclass
class SkillProficiency:
    """Skill proficiency with rank and modifiers."""
    skill: Skill
    rank: ProficiencyRank = ProficiencyRank.UNTRAINED
    item_bonus: int = 0
    circumstance_bonus: int = 0
    
    def total_bonus(self, level: int, abilities: AbilityScores) -> int:
        """Calculate total skill bonus."""
        ability_mod = abilities.get_modifier(self.skill.key_ability)
        proficiency_bonus = self.rank.value + (level if self.rank > ProficiencyRank.UNTRAINED else 0)
        return ability_mod + proficiency_bonus + self.item_bonus + self.circumstance_bonus


@dataclass
class SpellcastingEntry:
    """Spellcasting tradition with comprehensive spell management."""
    tradition: str
    key_ability: Ability
    proficiency_rank: ProficiencyRank = ProficiencyRank.UNTRAINED
    focus_points: int = 0
    is_spontaneous: bool = True
    
    # Spell slots per level (0-10)
    spell_slots: List[int] = field(default_factory=lambda: [0] * (SPELL_LEVELS_MAX + 1))
    
    # Known/prepared spells by level
    spells: Dict[int, List[str]] = field(default_factory=dict)
    
    def spell_attack_bonus(self, level: int, abilities: AbilityScores) -> int:
        """Calculate spell attack bonus."""
        ability_mod = abilities.get_modifier(self.key_ability)
        prof_bonus = self.proficiency_rank.value + (level if self.proficiency_rank > ProficiencyRank.UNTRAINED else 0)
        return ability_mod + prof_bonus
    
    def spell_dc(self, level: int, abilities: AbilityScores) -> int:
        """Calculate spell DC."""
        return 10 + self.spell_attack_bonus(level, abilities)


class Equipment(ABC):
    """Abstract base for all equipment."""
    
    def __init__(self, name: str, bulk: float = 0.0, value_cp: int = 0, 
                 quantity: int = 1, description: str = ""):
        self.name = name
        self.bulk = bulk
        self.value_cp = value_cp
        self.quantity = quantity
        self.description = description
        self._worn = False
        self._invested = False
    
    @property
    def worn(self) -> bool:
        return self._worn
    
    @worn.setter
    def worn(self, value: bool):
        if value and not self.can_be_worn():
            raise ValueError(f"{self.name} cannot be worn")
        self._worn = value
    
    @property
    def invested(self) -> bool:
        return self._invested
    
    @invested.setter
    def invested(self, value: bool):
        if value and not self.can_be_invested():
            raise ValueError(f"{self.name} cannot be invested")
        self._invested = value
    
    @property
    def value_gp(self) -> float:
        """Value in gold pieces."""
        return self.value_cp / 100.0
    
    @property
    def total_bulk(self) -> float:
        """Total bulk considering quantity."""
        return self.bulk * self.quantity
    
    @abstractmethod
    def can_be_worn(self) -> bool:
        """Check if this equipment can be worn."""
        pass
    
    @abstractmethod
    def can_be_invested(self) -> bool:
        """Check if this equipment can be invested."""
        pass


@dataclass
class SimpleEquipment(Equipment):
    """Basic equipment item."""
    
    def can_be_worn(self) -> bool:
        return False
    
    def can_be_invested(self) -> bool:
        return False


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
        return self.range_increment is not None
    
    @property
    def is_melee(self) -> bool:
        return not self.is_ranged
    
    def can_be_worn(self) -> bool:
        return True  # Weapons can be "worn" (wielded)
    
    def can_be_invested(self) -> bool:
        return "magical" in self.traits


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
    
    def can_be_worn(self) -> bool:
        return True
    
    def can_be_invested(self) -> bool:
        return "magical" in self.armor_traits
    
    def effective_dex_bonus(self, dex_modifier: int) -> int:
        """Calculate effective dexterity bonus considering cap."""
        if self.dex_cap is None:
            return dex_modifier
        return min(dex_modifier, self.dex_cap)


@dataclass
class PlayerCharacter:
    """Complete player character with modern encapsulation."""
    
    # Core Identity
    name: str
    player_name: str = ""
    ancestry: str = ""
    heritage: str = ""
    background: str = ""
    character_class: str = ""
    level: int = 1
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    size: Size = Size.MEDIUM
    
    # Core Stats
    abilities: AbilityScores = field(default_factory=AbilityScores)
    max_hit_points: int = 0
    current_hit_points: Optional[int] = None
    hero_points: int = 1
    experience_points: int = 0
    
    # Proficiencies
    skills: Dict[Skill, SkillProficiency] = field(default_factory=dict)
    perception_rank: ProficiencyRank = ProficiencyRank.TRAINED
    save_ranks: Dict[str, ProficiencyRank] = field(default_factory=lambda: {
        'fortitude': ProficiencyRank.UNTRAINED,
        'reflex': ProficiencyRank.UNTRAINED,
        'will': ProficiencyRank.UNTRAINED
    })
    
    # Character Features
    feats: List[str] = field(default_factory=list)
    class_features: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    
    # Equipment
    equipment: List[Equipment] = field(default_factory=list)
    
    # Spellcasting
    spellcasting: List[SpellcastingEntry] = field(default_factory=list)
    
    # Metadata
    deity: str = ""
    notes: str = ""
    created_date: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Initialize calculated values."""
        if self.current_hit_points is None:
            self.current_hit_points = self.max_hit_points
        
        # Initialize basic skills if not present
        for skill in Skill:
            if skill not in self.skills:
                self.skills[skill] = SkillProficiency(skill)
    
    @property
    def hit_points(self) -> int:
        """Current hit points (alias for compatibility)."""
        return self.current_hit_points or 0
    
    @hit_points.setter
    def hit_points(self, value: int):
        """Set current hit points with validation."""
        self.current_hit_points = max(0, min(value, self.max_hit_points))
    
    @cached_property
    def armor_class(self) -> int:
        """Calculate AC from worn armor and dexterity."""
        base_ac = 10
        dex_mod = self.abilities.get_modifier(Ability.DEXTERITY)
        
        # Find worn armor
        worn_armor = self.get_worn_armor()
        if worn_armor:
            return base_ac + worn_armor.ac_bonus + worn_armor.effective_dex_bonus(dex_mod)
        
        return base_ac + dex_mod
    
    def get_worn_armor(self) -> Optional[Armor]:
        """Get currently worn armor."""
        for item in self.equipment:
            if isinstance(item, Armor) and item.worn:
                return item
        return None
    
    def get_skill_bonus(self, skill: Skill) -> int:
        """Calculate total skill bonus."""
        if skill not in self.skills:
            # Untrained skill
            ability_mod = self.abilities.get_modifier(skill.key_ability)
            return ability_mod
        
        return self.skills[skill].total_bonus(self.level, self.abilities)
    
    def get_save_bonus(self, save_name: str) -> int:
        """Calculate save bonus."""
        save_abilities = {
            'fortitude': Ability.CONSTITUTION,
            'reflex': Ability.DEXTERITY,
            'will': Ability.WISDOM
        }
        
        ability = save_abilities.get(save_name)
        if not ability:
            raise ValueError(f"Unknown save: {save_name}")
        
        ability_mod = self.abilities.get_modifier(ability)
        rank = self.save_ranks.get(save_name, ProficiencyRank.UNTRAINED)
        prof_bonus = rank.value + (self.level if rank > ProficiencyRank.UNTRAINED else 0)
        
        return ability_mod + prof_bonus
    
    @property
    def perception_bonus(self) -> int:
        """Calculate perception bonus."""
        ability_mod = self.abilities.get_modifier(Ability.WISDOM)
        prof_bonus = self.perception_rank.value + (self.level if self.perception_rank > ProficiencyRank.UNTRAINED else 0)
        return ability_mod + prof_bonus
    
    def add_equipment(self, item: Equipment):
        """Add equipment with automatic timestamp update."""
        self.equipment.append(item)
        self.update_timestamp()
    
    def remove_equipment(self, item_name: str) -> bool:
        """Remove equipment by name."""
        for i, item in enumerate(self.equipment):
            if item.name == item_name:
                del self.equipment[i]
                self.update_timestamp()
                return True
        return False
    
    def update_timestamp(self):
        """Update last modified timestamp."""
        self.last_updated = datetime.now()
        # Clear cached properties
        if hasattr(self, '__dict__'):
            self.__dict__.pop('armor_class', None)
    
    def heal(self, amount: int):
        """Heal the character."""
        self.hit_points = min(self.max_hit_points, self.hit_points + amount)
    
    def take_damage(self, amount: int):
        """Apply damage to the character."""
        self.hit_points = max(0, self.hit_points - amount)
    
    @property
    def is_conscious(self) -> bool:
        """Check if character is conscious."""
        return self.hit_points > 0
    
    @property
    def total_bulk(self) -> float:
        """Calculate total equipment bulk."""
        return sum(item.total_bulk for item in self.equipment)


# Manager classes would follow similar modernization patterns
class CharacterDataManager:
    """Manages character persistence with modern practices."""
    
    def __init__(self, data_directory: Union[str, Path] = "game_data/characters"):
        self.data_dir = Path(data_directory)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def save_character(self, character: PlayerCharacter) -> bool:
        """Save character with proper error handling."""
        filename = self._get_filename(character.name)
        filepath = self.data_dir / filename
        
        character.update_timestamp()
        
        try:
            # Use a more robust serialization approach
            data = self._serialize_character(character)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            log.info("Saved character %s to %s", character.name, filepath)
            return True
        except Exception as e:
            log.error("Failed to save character %s: %s", character.name, e)
            return False
    
    def _get_filename(self, character_name: str) -> str:
        """Generate safe filename from character name."""
        safe_name = "".join(c for c in character_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        return f"{safe_name.lower().replace(' ', '_')}.json"
    
    def _serialize_character(self, character: PlayerCharacter) -> Dict[str, Any]:
        """Serialize character to dictionary with enum handling."""
        # Implementation would handle modern serialization
        # This is a placeholder for the actual implementation
        return {}


# Additional improvements would include:
# - Custom exceptions for domain-specific errors
# - Repository pattern for data access
# - Factory methods for character creation
# - Validation decorators
# - Event system for character changes
# - Plugin system for house rules