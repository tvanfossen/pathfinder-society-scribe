# src/models/character.py
"""Player character model with complete game statistics."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from .base import (
    Alignment, Size, Skill, Ability, Proficiency, 
    TimestampedModel
)
from .abilities import AbilityScores
from .equipment import Equipment, Weapon, Armor, Shield
from .spellcasting import SpellcastingEntry


@dataclass
class CharacterSkills:
    """Character skill proficiencies and bonuses."""
    
    _proficiencies: Dict[Skill, Proficiency] = field(default_factory=dict)
    _skill_to_ability: Dict[Skill, Ability] = field(default_factory=lambda: {
        Skill.ACROBATICS: Ability.DEXTERITY,
        Skill.ARCANA: Ability.INTELLIGENCE,
        Skill.ATHLETICS: Ability.STRENGTH,
        Skill.CRAFTING: Ability.INTELLIGENCE,
        Skill.DECEPTION: Ability.CHARISMA,
        Skill.DIPLOMACY: Ability.CHARISMA,
        Skill.INTIMIDATION: Ability.CHARISMA,
        Skill.LORE: Ability.INTELLIGENCE,
        Skill.MEDICINE: Ability.WISDOM,
        Skill.NATURE: Ability.WISDOM,
        Skill.OCCULTISM: Ability.INTELLIGENCE,
        Skill.PERFORMANCE: Ability.CHARISMA,
        Skill.RELIGION: Ability.WISDOM,
        Skill.SOCIETY: Ability.INTELLIGENCE,
        Skill.STEALTH: Ability.DEXTERITY,
        Skill.SURVIVAL: Ability.WISDOM,
        Skill.THIEVERY: Ability.DEXTERITY,
    })
    
    def get_proficiency(self, skill: Skill) -> Proficiency:
        """Get skill proficiency level."""
        return self._proficiencies.get(skill, Proficiency.UNTRAINED)
    
    def set_proficiency(self, skill: Skill, proficiency: Proficiency) -> None:
        """Set skill proficiency level."""
        self._proficiencies[skill] = proficiency
    
    def get_ability_for_skill(self, skill: Skill) -> Ability:
        """Get the ability associated with a skill."""
        return self._skill_to_ability.get(skill, Ability.INTELLIGENCE)
    
    def calculate_bonus(self, skill: Skill, level: int, ability_modifier: int) -> int:
        """Calculate total skill bonus."""
        proficiency = self.get_proficiency(skill)
        if proficiency == Proficiency.UNTRAINED:
            return ability_modifier
        return level + proficiency.value + ability_modifier
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            skill.value: proficiency.value
            for skill, proficiency in self._proficiencies.items()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterSkills':
        """Create from dictionary."""
        instance = cls()
        for skill_name, prof_value in data.items():
            try:
                skill = Skill(skill_name)
                proficiency = Proficiency(prof_value)
                instance._proficiencies[skill] = proficiency
            except (ValueError, KeyError):
                continue
        return instance


@dataclass
class CharacterDefenses:
    """Character defensive statistics."""
    
    armor_class: int = 10
    fortitude_proficiency: Proficiency = Proficiency.TRAINED
    reflex_proficiency: Proficiency = Proficiency.TRAINED
    will_proficiency: Proficiency = Proficiency.TRAINED
    
    def calculate_ac(self, level: int, dex_modifier: int, armor_bonus: int = 0, 
                     shield_bonus: int = 0) -> int:
        """Calculate total AC."""
        base = 10 + dex_modifier + armor_bonus + shield_bonus
        # Add proficiency if wearing armor
        if armor_bonus > 0:
            base += level + Proficiency.TRAINED.value
        return base
    
    def calculate_save(self, save_type: str, level: int, ability_modifier: int) -> int:
        """Calculate saving throw bonus."""
        prof_map = {
            'fortitude': self.fortitude_proficiency,
            'reflex': self.reflex_proficiency,
            'will': self.will_proficiency
        }
        proficiency = prof_map.get(save_type.lower(), Proficiency.TRAINED)
        return level + proficiency.value + ability_modifier
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'armor_class': self.armor_class,
            'fortitude_proficiency': self.fortitude_proficiency.value,
            'reflex_proficiency': self.reflex_proficiency.value,
            'will_proficiency': self.will_proficiency.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterDefenses':
        """Create from dictionary."""
        for key in ['fortitude_proficiency', 'reflex_proficiency', 'will_proficiency']:
            if key in data and isinstance(data[key], int):
                data[key] = Proficiency(data[key])
        return cls(**data)


@dataclass
class PlayerCharacter(TimestampedModel):
    """Complete player character with all game statistics."""
    
    # Identity
    name: str = ""
    player_name: str = ""
    
    # Core details
    level: int = 1
    experience_points: int = 0
    hero_points: int = 1
    
    # Character options
    ancestry: str = ""
    heritage: str = ""
    background: str = ""
    character_class: str = ""
    subclass: Optional[str] = None
    
    # Characteristics
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    size: Size = Size.MEDIUM
    deity: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    
    # Abilities and skills
    abilities: AbilityScores = field(default_factory=AbilityScores)
    skills: CharacterSkills = field(default_factory=CharacterSkills)
    
    # Health
    max_hit_points: int = 0
    current_hit_points: int = 0
    temp_hit_points: int = 0
    
    # Defenses
    defenses: CharacterDefenses = field(default_factory=CharacterDefenses)
    perception_proficiency: Proficiency = Proficiency.TRAINED
    
    # Speed
    speed: int = 25
    speed_penalties: int = 0
    
    # Languages
    languages: Set[str] = field(default_factory=lambda: {"Common"})
    
    # Features
    feats: List[str] = field(default_factory=list)
    class_features: List[str] = field(default_factory=list)
    ancestry_features: List[str] = field(default_factory=list)
    
    # Equipment
    equipment: List[Equipment] = field(default_factory=list)
    weapons: List[Weapon] = field(default_factory=list)
    armor: Optional[Armor] = None
    shield: Optional[Shield] = None
    
    # Spellcasting
    spellcasting: List[SpellcastingEntry] = field(default_factory=list)
    
    # Conditions
    conditions: List[str] = field(default_factory=list)
    
    # Notes
    notes: str = ""
    backstory: str = ""
    
    def __post_init__(self):
        """Initialize base class and validate data."""
        super().__init__()
        if self.current_hit_points == 0 and self.max_hit_points > 0:
            self.current_hit_points = self.max_hit_points
    
    @property
    def hit_points(self) -> int:
        """Current hit points including temp HP."""
        return self.current_hit_points + self.temp_hit_points
    
    @property
    def is_dying(self) -> bool:
        """Check if character is dying."""
        return self.current_hit_points <= 0 and self.current_hit_points > -self.max_hit_points
    
    @property
    def is_dead(self) -> bool:
        """Check if character is dead."""
        return self.current_hit_points <= -self.max_hit_points
    
    @property
    def actual_speed(self) -> int:
        """Get current movement speed with penalties."""
        return max(5, self.speed - self.speed_penalties)
    
    @property
    def total_bulk(self) -> float:
        """Calculate total carried bulk."""
        bulk = sum(item.total_bulk for item in self.equipment)
        bulk += sum(weapon.total_bulk for weapon in self.weapons)
        if self.armor:
            bulk += self.armor.total_bulk
        if self.shield:
            bulk += self.shield.total_bulk
        return bulk
    
    @property
    def encumbered(self) -> bool:
        """Check if character is encumbered."""
        max_bulk = 5 + self.abilities.str_modifier
        return self.total_bulk > max_bulk
    
    @property
    def perception_bonus(self) -> int:
        """Calculate perception bonus."""
        return (self.level + self.perception_proficiency.value + 
                self.abilities.wis_modifier)
    
    @property
    def fortitude_save(self) -> int:
        """Calculate Fortitude save bonus."""
        return self.defenses.calculate_save(
            'fortitude', self.level, self.abilities.con_modifier
        )
    
    @property
    def reflex_save(self) -> int:
        """Calculate Reflex save bonus."""
        return self.defenses.calculate_save(
            'reflex', self.level, self.abilities.dex_modifier
        )
    
    @property
    def will_save(self) -> int:
        """Calculate Will save bonus."""
        return self.defenses.calculate_save(
            'will', self.level, self.abilities.wis_modifier
        )
    
    def take_damage(self, amount: int) -> None:
        """Apply damage to character."""
        # First reduce temp HP
        if self.temp_hit_points > 0:
            if amount <= self.temp_hit_points:
                self.temp_hit_points -= amount
                return
            amount -= self.temp_hit_points
            self.temp_hit_points = 0
        
        # Then reduce actual HP
        self.current_hit_points -= amount
        self.touch()
    
    def heal(self, amount: int) -> None:
        """Heal character hit points."""
        self.current_hit_points = min(
            self.current_hit_points + amount,
            self.max_hit_points
        )
        self.touch()
    
    def add_temp_hp(self, amount: int) -> None:
        """Add temporary hit points (doesn't stack)."""
        self.temp_hit_points = max(self.temp_hit_points, amount)
        self.touch()
    
    def add_condition(self, condition: str) -> None:
        """Add a condition to the character."""
        if condition not in self.conditions:
            self.conditions.append(condition)
            self.touch()
    
    def remove_condition(self, condition: str) -> None:
        """Remove a condition from the character."""
        if condition in self.conditions:
            self.conditions.remove(condition)
            self.touch()
    
    def rest(self) -> None:
        """Perform a long rest."""
        # Restore HP
        self.current_hit_points = self.max_hit_points
        self.temp_hit_points = 0
        
        # Restore spellcasting
        for casting in self.spellcasting:
            casting.rest()
        
        # Clear some conditions
        conditions_to_clear = ['fatigued', 'drained']
        for condition in conditions_to_clear:
            self.remove_condition(condition)
        
        self.touch()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'player_name': self.player_name,
            'level': self.level,
            'experience_points': self.experience_points,
            'hero_points': self.hero_points,
            'ancestry': self.ancestry,
            'heritage': self.heritage,
            'background': self.background,
            'character_class': self.character_class,
            'subclass': self.subclass,
            'alignment': self.alignment.value,
            'size': self.size.value,
            'deity': self.deity,
            'age': self.age,
            'gender': self.gender,
            'height': self.height,
            'weight': self.weight,
            'abilities': self.abilities.to_dict(),
            'skills': self.skills.to_dict(),
            'max_hit_points': self.max_hit_points,
            'current_hit_points': self.current_hit_points,
            'temp_hit_points': self.temp_hit_points,
            'defenses': self.defenses.to_dict(),
            'perception_proficiency': self.perception_proficiency.value,
            'speed': self.speed,
            'speed_penalties': self.speed_penalties,
            'languages': list(self.languages),
            'feats': self.feats,
            'class_features': self.class_features,
            'ancestry_features': self.ancestry_features,
            'equipment': [item.to_dict() for item in self.equipment],
            'weapons': [weapon.to_dict() for weapon in self.weapons],
            'armor': self.armor.to_dict() if self.armor else None,
            'shield': self.shield.to_dict() if self.shield else None,
            'spellcasting': [entry.to_dict() for entry in self.spellcasting],
            'conditions': self.conditions,
            'notes': self.notes,
            'backstory': self.backstory,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerCharacter':
        """Create from dictionary."""
        # Handle enums
        if 'alignment' in data:
            data['alignment'] = Alignment(data['alignment'])
        if 'size' in data:
            data['size'] = Size(data['size'])
        if 'perception_proficiency' in data:
            data['perception_proficiency'] = Proficiency(data['perception_proficiency'])
        
        # Handle complex types
        if 'abilities' in data:
            data['abilities'] = AbilityScores.from_dict(data['abilities'])
        if 'skills' in data:
            data['skills'] = CharacterSkills.from_dict(data['skills'])
        if 'defenses' in data:
            data['defenses'] = CharacterDefenses.from_dict(data['defenses'])
        
        # Handle equipment
        if 'equipment' in data:
            data['equipment'] = [
                Equipment.from_dict(item) for item in data['equipment']
            ]
        if 'weapons' in data:
            data['weapons'] = [
                Weapon.from_dict(item) for item in data['weapons']
            ]
        if 'armor' in data and data['armor']:
            data['armor'] = Armor.from_dict(data['armor'])
        if 'shield' in data and data['shield']:
            data['shield'] = Shield.from_dict(data['shield'])
        
        # Handle spellcasting
        if 'spellcasting' in data:
            data['spellcasting'] = [
                SpellcastingEntry.from_dict(entry) for entry in data['spellcasting']
            ]
        
        # Handle sets
        if 'languages' in data:
            data['languages'] = set(data['languages'])
        
        # Handle timestamps
        if 'created_at' in data:
            del data['created_at']
        if 'updated_at' in data:
            del data['updated_at']
        
        return cls(**data)