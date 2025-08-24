# src/models/abilities.py
"""Ability scores and modifiers for characters."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .base import Ability


@dataclass
class AbilityScores:
    """Character ability scores with calculated modifiers."""
    
    _scores: Dict[Ability, int] = field(default_factory=lambda: {
        Ability.STRENGTH: 10,
        Ability.DEXTERITY: 10,
        Ability.CONSTITUTION: 10,
        Ability.INTELLIGENCE: 10,
        Ability.WISDOM: 10,
        Ability.CHARISMA: 10
    })
    
    def __post_init__(self):
        """Validate ability scores."""
        for ability in Ability:
            if ability not in self._scores:
                self._scores[ability] = 10
    
    @staticmethod
    def calculate_modifier(score: int) -> int:
        """Calculate ability modifier from score."""
        return (score - 10) // 2
    
    def get_score(self, ability: Ability) -> int:
        """Get ability score."""
        return self._scores.get(ability, 10)
    
    def set_score(self, ability: Ability, value: int) -> None:
        """Set ability score with validation."""
        if not 1 <= value <= 30:
            raise ValueError(f"Ability score must be between 1 and 30, got {value}")
        self._scores[ability] = value
    
    def get_modifier(self, ability: Ability) -> int:
        """Get ability modifier."""
        return self.calculate_modifier(self.get_score(ability))
    
    @property
    def strength(self) -> int:
        """Get Strength score."""
        return self.get_score(Ability.STRENGTH)
    
    @strength.setter
    def strength(self, value: int) -> None:
        """Set Strength score."""
        self.set_score(Ability.STRENGTH, value)
    
    @property
    def dexterity(self) -> int:
        """Get Dexterity score."""
        return self.get_score(Ability.DEXTERITY)
    
    @dexterity.setter
    def dexterity(self, value: int) -> None:
        """Set Dexterity score."""
        self.set_score(Ability.DEXTERITY, value)
    
    @property
    def constitution(self) -> int:
        """Get Constitution score."""
        return self.get_score(Ability.CONSTITUTION)
    
    @constitution.setter
    def constitution(self, value: int) -> None:
        """Set Constitution score."""
        self.set_score(Ability.CONSTITUTION, value)
    
    @property
    def intelligence(self) -> int:
        """Get Intelligence score."""
        return self.get_score(Ability.INTELLIGENCE)
    
    @intelligence.setter
    def intelligence(self, value: int) -> None:
        """Set Intelligence score."""
        self.set_score(Ability.INTELLIGENCE, value)
    
    @property
    def wisdom(self) -> int:
        """Get Wisdom score."""
        return self.get_score(Ability.WISDOM)
    
    @wisdom.setter
    def wisdom(self, value: int) -> None:
        """Set Wisdom score."""
        self.set_score(Ability.WISDOM, value)
    
    @property
    def charisma(self) -> int:
        """Get Charisma score."""
        return self.get_score(Ability.CHARISMA)
    
    @charisma.setter
    def charisma(self, value: int) -> None:
        """Set Charisma score."""
        self.set_score(Ability.CHARISMA, value)
    
    @property
    def str_modifier(self) -> int:
        """Get Strength modifier."""
        return self.get_modifier(Ability.STRENGTH)
    
    @property
    def dex_modifier(self) -> int:
        """Get Dexterity modifier."""
        return self.get_modifier(Ability.DEXTERITY)
    
    @property
    def con_modifier(self) -> int:
        """Get Constitution modifier."""
        return self.get_modifier(Ability.CONSTITUTION)
    
    @property
    def int_modifier(self) -> int:
        """Get Intelligence modifier."""
        return self.get_modifier(Ability.INTELLIGENCE)
    
    @property
    def wis_modifier(self) -> int:
        """Get Wisdom modifier."""
        return self.get_modifier(Ability.WISDOM)
    
    @property
    def cha_modifier(self) -> int:
        """Get Charisma modifier."""
        return self.get_modifier(Ability.CHARISMA)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            ability.value: score 
            for ability, score in self._scores.items()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AbilityScores':
        """Create from dictionary."""
        scores = {}
        for ability in Ability:
            key = ability.value
            if key in data:
                scores[ability] = data[key]
            elif ability.name.lower() in data:
                scores[ability] = data[ability.name.lower()]
        
        instance = cls()
        instance._scores = scores
        return instance