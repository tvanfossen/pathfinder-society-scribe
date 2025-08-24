# src/models/spellcasting.py
"""Spellcasting system models."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from .base import Tradition, Ability, Proficiency


@dataclass
class Spell:
    """Individual spell data."""
    
    name: str
    level: int
    tradition: List[Tradition]
    school: str = ""
    traits: List[str] = field(default_factory=list)
    cast_time: str = "2 actions"
    range: str = "touch"
    targets: str = ""
    duration: str = "instantaneous"
    save: Optional[str] = None
    description: str = ""
    heightened: Dict[int, str] = field(default_factory=dict)
    
    @property
    def is_cantrip(self) -> bool:
        """Check if spell is a cantrip."""
        return self.level == 0
    
    @property
    def is_focus(self) -> bool:
        """Check if spell is a focus spell."""
        return "focus" in [t.lower() for t in self.traits]
    
    def available_at_level(self, caster_level: int) -> bool:
        """Check if spell is available at caster level."""
        if self.is_cantrip:
            return True
        # Spells become available at odd caster levels
        max_spell_level = (caster_level + 1) // 2
        return self.level <= max_spell_level
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'level': self.level,
            'tradition': [t.value for t in self.tradition],
            'school': self.school,
            'traits': self.traits,
            'cast_time': self.cast_time,
            'range': self.range,
            'targets': self.targets,
            'duration': self.duration,
            'save': self.save,
            'description': self.description,
            'heightened': self.heightened
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Spell':
        """Create from dictionary."""
        if 'tradition' in data:
            data['tradition'] = [
                Tradition(t) if isinstance(t, str) else t 
                for t in data['tradition']
            ]
        return cls(**data)


@dataclass
class SpellSlot:
    """Spell slot for prepared/spontaneous casting."""
    
    level: int
    total: int = 0
    used: int = 0
    
    @property
    def remaining(self) -> int:
        """Get remaining spell slots."""
        return self.total - self.used
    
    def can_cast(self) -> bool:
        """Check if slot is available."""
        return self.remaining > 0
    
    def use(self) -> bool:
        """Use a spell slot."""
        if self.can_cast():
            self.used += 1
            return True
        return False
    
    def restore(self, amount: Optional[int] = None) -> None:
        """Restore spell slots."""
        if amount is None:
            self.used = 0
        else:
            self.used = max(0, self.used - amount)


@dataclass
class SpellcastingEntry:
    """Spellcasting tradition and details for a character."""
    
    tradition: Tradition
    ability: Ability
    proficiency: Proficiency = Proficiency.TRAINED
    spell_attack: int = 0
    spell_dc: int = 10
    
    # Spell slots by level (0-10)
    spell_slots: Dict[int, SpellSlot] = field(default_factory=dict)
    
    # Known spells (for spontaneous casters)
    known_spells: Dict[int, Set[str]] = field(default_factory=dict)
    
    # Prepared spells (for prepared casters)
    prepared_spells: Dict[int, List[str]] = field(default_factory=dict)
    
    # Focus spells
    focus_points_max: int = 0
    focus_points_current: int = 0
    focus_spells: List[str] = field(default_factory=list)
    
    # Innate spells
    innate_spells: Dict[str, int] = field(default_factory=dict)  # spell -> uses per day
    
    def __post_init__(self):
        """Initialize spell slots if not provided."""
        if not self.spell_slots:
            for level in range(11):
                self.spell_slots[level] = SpellSlot(level=level)
    
    @property
    def is_spontaneous(self) -> bool:
        """Check if this is spontaneous spellcasting."""
        return bool(self.known_spells) and not bool(self.prepared_spells)
    
    @property
    def is_prepared(self) -> bool:
        """Check if this is prepared spellcasting."""
        return bool(self.prepared_spells)
    
    @property
    def casting_type(self) -> str:
        """Get casting type as string."""
        if self.is_spontaneous:
            return "spontaneous"
        elif self.is_prepared:
            return "prepared"
        else:
            return "innate"
    
    def calculate_spell_attack(self, level: int, ability_modifier: int) -> int:
        """Calculate spell attack bonus."""
        return level + self.proficiency.value + ability_modifier
    
    def calculate_spell_dc(self, level: int, ability_modifier: int) -> int:
        """Calculate spell DC."""
        return 10 + level + self.proficiency.value + ability_modifier
    
    def add_known_spell(self, spell_level: int, spell_name: str) -> None:
        """Add a known spell (spontaneous casters)."""
        if spell_level not in self.known_spells:
            self.known_spells[spell_level] = set()
        self.known_spells[spell_level].add(spell_name)
    
    def prepare_spell(self, spell_level: int, spell_name: str) -> None:
        """Prepare a spell (prepared casters)."""
        if spell_level not in self.prepared_spells:
            self.prepared_spells[spell_level] = []
        self.prepared_spells[spell_level].append(spell_name)
    
    def cast_spell(self, spell_level: int) -> bool:
        """Attempt to cast a spell of given level."""
        if spell_level in self.spell_slots:
            return self.spell_slots[spell_level].use()
        return False
    
    def use_focus_point(self) -> bool:
        """Use a focus point."""
        if self.focus_points_current > 0:
            self.focus_points_current -= 1
            return True
        return False
    
    def refocus(self, points: int = 1) -> None:
        """Regain focus points."""
        self.focus_points_current = min(
            self.focus_points_current + points,
            self.focus_points_max
        )
    
    def rest(self) -> None:
        """Reset daily resources."""
        # Restore spell slots
        for slot in self.spell_slots.values():
            slot.restore()
        
        # Restore focus points
        self.focus_points_current = self.focus_points_max
        
        # Clear prepared spells (they need to be re-prepared)
        if self.is_prepared:
            self.prepared_spells.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tradition': self.tradition.value,
            'ability': self.ability.value,
            'proficiency': self.proficiency.value,
            'spell_attack': self.spell_attack,
            'spell_dc': self.spell_dc,
            'spell_slots': {
                level: {'total': slot.total, 'used': slot.used}
                for level, slot in self.spell_slots.items()
            },
            'known_spells': {
                level: list(spells)
                for level, spells in self.known_spells.items()
            },
            'prepared_spells': {
                level: spells
                for level, spells in self.prepared_spells.items()
            },
            'focus_points_max': self.focus_points_max,
            'focus_points_current': self.focus_points_current,
            'focus_spells': self.focus_spells,
            'innate_spells': self.innate_spells
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpellcastingEntry':
        """Create from dictionary."""
        # Convert enums
        if 'tradition' in data and isinstance(data['tradition'], str):
            data['tradition'] = Tradition(data['tradition'])
        if 'ability' in data and isinstance(data['ability'], str):
            data['ability'] = Ability(data['ability'])
        if 'proficiency' in data:
            if isinstance(data['proficiency'], str):
                data['proficiency'] = Proficiency[data['proficiency'].upper()]
            elif isinstance(data['proficiency'], int):
                data['proficiency'] = Proficiency(data['proficiency'])
        
        # Convert spell slots
        if 'spell_slots' in data:
            slots = {}
            for level, slot_data in data['spell_slots'].items():
                level = int(level)
                slots[level] = SpellSlot(
                    level=level,
                    total=slot_data.get('total', 0),
                    used=slot_data.get('used', 0)
                )
            data['spell_slots'] = slots
        
        # Convert known spells to sets
        if 'known_spells' in data:
            data['known_spells'] = {
                int(level): set(spells)
                for level, spells in data['known_spells'].items()
            }
        
        # Ensure prepared spells are lists
        if 'prepared_spells' in data:
            data['prepared_spells'] = {
                int(level): list(spells)
                for level, spells in data['prepared_spells'].items()
            }
        
        return cls(**data)