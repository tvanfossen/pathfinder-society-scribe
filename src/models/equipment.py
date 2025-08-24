# src/models/equipment.py
"""Equipment, weapon, and armor models."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .base import DamageType, WeaponCategory, ArmorCategory, Rarity


@dataclass
class Equipment:
    """Base equipment item."""
    
    name: str
    quantity: int = 1
    bulk: float = 0.0
    value_cp: int = 0  # Value in copper pieces
    level: int = 0
    rarity: Rarity = Rarity.COMMON
    worn: bool = False
    invested: bool = False
    description: str = ""
    traits: List[str] = field(default_factory=list)
    
    @property
    def value_gp(self) -> float:
        """Value in gold pieces."""
        return self.value_cp / 100.0
    
    @value_gp.setter
    def value_gp(self, value: float) -> None:
        """Set value in gold pieces."""
        self.value_cp = int(value * 100)
    
    @property
    def value_sp(self) -> float:
        """Value in silver pieces."""
        return self.value_cp / 10.0
    
    @value_sp.setter  
    def value_sp(self, value: float) -> None:
        """Set value in silver pieces."""
        self.value_cp = int(value * 10)
    
    @property
    def total_bulk(self) -> float:
        """Total bulk for all items."""
        return self.bulk * self.quantity
    
    def can_invest(self) -> bool:
        """Check if item can be invested."""
        return self.worn and "invested" in [t.lower() for t in self.traits]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'quantity': self.quantity,
            'bulk': self.bulk,
            'value_cp': self.value_cp,
            'level': self.level,
            'rarity': self.rarity.value,
            'worn': self.worn,
            'invested': self.invested,
            'description': self.description,
            'traits': self.traits
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Equipment':
        """Create from dictionary."""
        if 'rarity' in data and isinstance(data['rarity'], str):
            data['rarity'] = Rarity(data['rarity'])
        return cls(**data)


@dataclass
class Weapon(Equipment):
    """Weapon with combat statistics."""
    
    damage_dice: str = "1d4"
    damage_type: DamageType = DamageType.BLUDGEONING
    weapon_category: WeaponCategory = WeaponCategory.SIMPLE
    weapon_group: str = ""
    hands: str = "1"  # "1", "1+", "2"
    range_increment: Optional[int] = None
    reload: Optional[int] = None
    
    @property
    def is_ranged(self) -> bool:
        """Check if weapon is ranged."""
        return self.range_increment is not None
    
    @property
    def is_melee(self) -> bool:
        """Check if weapon is melee."""
        return self.range_increment is None
    
    @property
    def is_two_handed(self) -> bool:
        """Check if weapon requires two hands."""
        return self.hands == "2"
    
    @property
    def is_versatile(self) -> bool:
        """Check if weapon can be used one or two-handed."""
        return self.hands == "1+"
    
    def get_damage_string(self) -> str:
        """Get formatted damage string."""
        return f"{self.damage_dice} {self.damage_type.value}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update({
            'damage_dice': self.damage_dice,
            'damage_type': self.damage_type.value,
            'weapon_category': self.weapon_category.value,
            'weapon_group': self.weapon_group,
            'hands': self.hands,
            'range_increment': self.range_increment,
            'reload': self.reload
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Weapon':
        """Create from dictionary."""
        if 'damage_type' in data and isinstance(data['damage_type'], str):
            data['damage_type'] = DamageType(data['damage_type'])
        if 'weapon_category' in data and isinstance(data['weapon_category'], str):
            data['weapon_category'] = WeaponCategory(data['weapon_category'])
        if 'rarity' in data and isinstance(data['rarity'], str):
            data['rarity'] = Rarity(data['rarity'])
        return cls(**data)


@dataclass
class Armor(Equipment):
    """Armor with defensive statistics."""
    
    ac_bonus: int = 0
    dex_cap: Optional[int] = None
    check_penalty: int = 0
    speed_penalty: int = 0
    strength_requirement: int = 0
    armor_category: ArmorCategory = ArmorCategory.UNARMORED
    armor_group: str = ""
    
    @property
    def is_heavy(self) -> bool:
        """Check if armor is heavy."""
        return self.armor_category == ArmorCategory.HEAVY
    
    @property
    def is_light(self) -> bool:
        """Check if armor is light."""
        return self.armor_category == ArmorCategory.LIGHT
    
    def calculate_ac_bonus(self, dex_modifier: int) -> int:
        """Calculate total AC bonus with dexterity."""
        if self.dex_cap is not None:
            dex_modifier = min(dex_modifier, self.dex_cap)
        return self.ac_bonus + dex_modifier
    
    def meets_strength_requirement(self, strength: int) -> bool:
        """Check if character meets strength requirement."""
        return strength >= self.strength_requirement
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update({
            'ac_bonus': self.ac_bonus,
            'dex_cap': self.dex_cap,
            'check_penalty': self.check_penalty,
            'speed_penalty': self.speed_penalty,
            'strength_requirement': self.strength_requirement,
            'armor_category': self.armor_category.value,
            'armor_group': self.armor_group
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Armor':
        """Create from dictionary."""
        if 'armor_category' in data and isinstance(data['armor_category'], str):
            data['armor_category'] = ArmorCategory(data['armor_category'])
        if 'rarity' in data and isinstance(data['rarity'], str):
            data['rarity'] = Rarity(data['rarity'])
        return cls(**data)


@dataclass
class Shield(Equipment):
    """Shield with defensive statistics."""
    
    ac_bonus: int = 2
    hardness: int = 5
    hit_points: int = 20
    broken_threshold: int = 10
    
    @property
    def is_broken(self) -> bool:
        """Check if shield is broken."""
        return self.hit_points <= self.broken_threshold
    
    def take_damage(self, damage: int) -> int:
        """Apply damage to shield, returns overflow damage."""
        blocked = min(damage, self.hardness)
        remaining = damage - blocked
        
        if remaining > 0:
            self.hit_points -= remaining
            
        if self.hit_points < 0:
            overflow = abs(self.hit_points)
            self.hit_points = 0
            return overflow
        
        return 0
    
    def repair(self, amount: int) -> None:
        """Repair shield hit points."""
        max_hp = self.broken_threshold * 2
        self.hit_points = min(self.hit_points + amount, max_hp)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update({
            'ac_bonus': self.ac_bonus,
            'hardness': self.hardness,
            'hit_points': self.hit_points,
            'broken_threshold': self.broken_threshold
        })
        return data