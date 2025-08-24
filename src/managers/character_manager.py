# src/managers/character_manager.py
"""Character data management with persistence."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..models.character import PlayerCharacter
from ..models.abilities import AbilityScores
from ..models.equipment import Equipment, Weapon, Armor, Shield


logger = logging.getLogger(__name__)


class CharacterManager:
    """Manages character data persistence and operations."""
    
    def __init__(self, data_directory: Path = None):
        """Initialize character manager.
        
        Args:
            data_directory: Directory for character data storage
        """
        self.data_dir = data_directory or Path("campaign-data/characters")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, PlayerCharacter] = {}
    
    def _get_filename(self, character_name: str) -> Path:
        """Generate filename for character."""
        safe_name = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in character_name.lower()
        )
        return self.data_dir / f"{safe_name}.json"
    
    def save(self, character: PlayerCharacter) -> bool:
        """Save character to disk.
        
        Args:
            character: Character to save
            
        Returns:
            True if successful
        """
        try:
            filepath = self._get_filename(character.name)
            character.touch()  # Update timestamp
            
            with filepath.open('w', encoding='utf-8') as f:
                json.dump(
                    character.to_dict(),
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            
            # Update cache
            self._cache[character.name] = character
            
            logger.info(f"Saved character '{character.name}' to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save character '{character.name}': {e}")
            return False
    
    def load(self, character_name: str) -> Optional[PlayerCharacter]:
        """Load character from disk.
        
        Args:
            character_name: Name of character to load
            
        Returns:
            Character if found, None otherwise
        """
        # Check cache first
        if character_name in self._cache:
            return self._cache[character_name]
        
        try:
            filepath = self._get_filename(character_name)
            
            if not filepath.exists():
                logger.warning(f"Character file not found: {filepath}")
                return None
            
            with filepath.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            character = PlayerCharacter.from_dict(data)
            
            # Update cache
            self._cache[character_name] = character
            
            logger.info(f"Loaded character '{character_name}' from {filepath}")
            return character
            
        except Exception as e:
            logger.error(f"Failed to load character '{character_name}': {e}")
            return None
    
    def delete(self, character_name: str) -> bool:
        """Delete character file.
        
        Args:
            character_name: Name of character to delete
            
        Returns:
            True if successful
        """
        try:
            filepath = self._get_filename(character_name)
            
            if filepath.exists():
                filepath.unlink()
                
                # Remove from cache
                self._cache.pop(character_name, None)
                
                logger.info(f"Deleted character '{character_name}'")
                return True
            
            logger.warning(f"Character '{character_name}' not found")
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete character '{character_name}': {e}")
            return False
    
    def list_characters(self) -> List[str]:
        """List all available character names.
        
        Returns:
            List of character names
        """
        characters = []
        
        for filepath in self.data_dir.glob("*.json"):
            try:
                with filepath.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'name' in data:
                        characters.append(data['name'])
            except Exception as e:
                logger.warning(f"Failed to read {filepath}: {e}")
                continue
        
        return sorted(characters)
    
    def exists(self, character_name: str) -> bool:
        """Check if character exists.
        
        Args:
            character_name: Name of character
            
        Returns:
            True if character exists
        """
        filepath = self._get_filename(character_name)
        return filepath.exists()
    
    def create_character(
        self,
        name: str,
        player_name: str = "",
        **kwargs
    ) -> PlayerCharacter:
        """Create a new character with defaults.
        
        Args:
            name: Character name
            player_name: Player name
            **kwargs: Additional character attributes
            
        Returns:
            New character instance
        """
        character = PlayerCharacter(
            name=name,
            player_name=player_name,
            **kwargs
        )
        
        # Set some sensible defaults if not provided
        if character.max_hit_points == 0:
            # Basic HP calculation
            character.max_hit_points = 8 + character.abilities.con_modifier
            character.current_hit_points = character.max_hit_points
        
        return character
    
    def duplicate_character(
        self,
        source_name: str,
        new_name: str
    ) -> Optional[PlayerCharacter]:
        """Create a copy of an existing character.
        
        Args:
            source_name: Name of character to copy
            new_name: Name for the new character
            
        Returns:
            New character if successful
        """
        source = self.load(source_name)
        if not source:
            return None
        
        # Create dict and update name
        data = source.to_dict()
        data['name'] = new_name
        
        # Create new character
        new_character = PlayerCharacter.from_dict(data)
        
        return new_character
    
    def export_character(
        self,
        character_name: str,
        output_path: Path
    ) -> bool:
        """Export character to a specific location.
        
        Args:
            character_name: Name of character to export
            output_path: Path for export file
            
        Returns:
            True if successful
        """
        character = self.load(character_name)
        if not character:
            return False
        
        try:
            with output_path.open('w', encoding='utf-8') as f:
                json.dump(
                    character.to_dict(),
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            logger.info(f"Exported '{character_name}' to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export character: {e}")
            return False
    
    def import_character(
        self,
        import_path: Path,
        overwrite: bool = False
    ) -> Optional[PlayerCharacter]:
        """Import character from file.
        
        Args:
            import_path: Path to import file
            overwrite: Whether to overwrite existing character
            
        Returns:
            Imported character if successful
        """
        try:
            with import_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            character = PlayerCharacter.from_dict(data)
            
            # Check if exists
            if self.exists(character.name) and not overwrite:
                logger.warning(f"Character '{character.name}' already exists")
                return None
            
            # Save imported character
            if self.save(character):
                logger.info(f"Imported character '{character.name}'")
                return character
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to import character: {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear the character cache."""
        self._cache.clear()
        logger.debug("Cleared character cache")
    
    def get_character_summary(self, character_name: str) -> Optional[Dict[str, Any]]:
        """Get a summary of character information.
        
        Args:
            character_name: Name of character
            
        Returns:
            Summary dict if character exists
        """
        character = self.load(character_name)
        if not character:
            return None
        
        return {
            'name': character.name,
            'player': character.player_name,
            'level': character.level,
            'class': character.character_class,
            'ancestry': character.ancestry,
            'hp': {
                'current': character.current_hit_points,
                'max': character.max_hit_points,
                'temp': character.temp_hit_points
            },
            'ac': character.defenses.armor_class,
            'perception': character.perception_bonus,
            'saves': {
                'fortitude': character.fortitude_save,
                'reflex': character.reflex_save,
                'will': character.will_save
            },
            'conditions': character.conditions,
            'last_updated': character.updated_at.isoformat()
        }