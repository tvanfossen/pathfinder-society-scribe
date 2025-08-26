# tests/test_managers.py
"""Tests for data managers using tutorial campaign."""

import pytest
import json
import shutil
from pathlib import Path
from datetime import date

from src.managers.character_manager import CharacterManager
from src.managers.campaign_manager import CampaignManager
from src.models.character import PlayerCharacter
from src.models.campaign import Campaign, CampaignSession
from src.models.base import Alignment, Size, Skill, Proficiency


class TestCharacterManager:
    """Test character manager functionality with tutorial data."""
    
    @pytest.fixture
    def base_dir(self):
        """Get base directory for campaign data."""
        # Use home directory path for campaigns
        base = Path.home() / "pf2e-campaigns" / "tutorial"
        base.mkdir(parents=True, exist_ok=True)
        return base
    
    @pytest.fixture
    def manager(self, base_dir):
        """Create character manager for tutorial campaign."""
        char_dir = base_dir / "characters"
        char_dir.mkdir(parents=True, exist_ok=True)
        return CharacterManager(char_dir)
    
    @pytest.fixture(autouse=True)
    def setup_tutorial_character(self, manager):
        """Create tutorial character for testing."""
        # Create a sample tutorial character
        tutorial_char = PlayerCharacter(
            name="Tutorial Hero",
            player_name="New Player",
            level=1,
            character_class="Fighter",
            ancestry="Human",
            background="Guard",
            max_hit_points=20,
            current_hit_points=20
        )
        
        # Set some abilities
        tutorial_char.abilities.strength = 16
        tutorial_char.abilities.dexterity = 14
        tutorial_char.abilities.constitution = 14
        
        # Add some skills
        tutorial_char.skills.set_proficiency(Skill.ATHLETICS, Proficiency.TRAINED)
        tutorial_char.skills.set_proficiency(Skill.INTIMIDATION, Proficiency.TRAINED)
        
        # Save the tutorial character
        manager.save(tutorial_char)
        
        yield
        
        # Cleanup is optional - we might want to keep tutorial data
    
    def test_load_tutorial_character(self, manager):
        """Test loading the tutorial character."""
        character = manager.load("Tutorial Hero")
        assert character is not None
        assert character.name == "Tutorial Hero"
        assert character.level == 1
        assert character.character_class == "Fighter"
    
    def test_list_includes_tutorial(self, manager):
        """Test that tutorial character appears in list."""
        characters = manager.list_characters()
        assert "Tutorial Hero" in characters
    
    def test_create_additional_character(self, manager):
        """Test creating additional characters in tutorial."""
        new_char = manager.create_character(
            name="Tutorial Wizard",
            player_name="New Player",
            level=1,
            character_class="Wizard",
            ancestry="Elf"
        )
        
        new_char.abilities.intelligence = 18
        new_char.abilities.constitution = 12
        
        assert manager.save(new_char)
        assert manager.exists("Tutorial Wizard")
        
        # Verify both characters exist
        characters = manager.list_characters()
        assert "Tutorial Hero" in characters
        assert "Tutorial Wizard" in characters
    
    def test_duplicate_tutorial_character(self, manager):
        """Test creating a copy of tutorial character."""
        duplicate = manager.duplicate_character("Tutorial Hero", "Tutorial Hero Copy")
        assert duplicate is not None
        assert duplicate.name == "Tutorial Hero Copy"
        assert duplicate.level == 1
        assert duplicate.abilities.strength == 16
        
        # Save the duplicate
        manager.save(duplicate)
        assert manager.exists("Tutorial Hero Copy")
    
    def test_character_summary(self, manager):
        """Test getting summary of tutorial character."""
        summary = manager.get_character_summary("Tutorial Hero")
        assert summary is not None
        assert summary['name'] == "Tutorial Hero"
        assert summary['level'] == 1
        assert summary['class'] == "Fighter"
        assert summary['hp']['current'] == 20
        assert summary['hp']['max'] == 20
    
    def test_export_tutorial_character(self, manager, base_dir):
        """Test exporting tutorial character."""
        export_dir = base_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        export_path = export_dir / "tutorial_hero.json"
        
        assert manager.export_character("Tutorial Hero", export_path)
        assert export_path.exists()
        
        # Verify exported data
        with export_path.open('r') as f:
            data = json.load(f)
        assert data['name'] == "Tutorial Hero"
        assert data['level'] == 1
    
    def test_modify_tutorial_character(self, manager):
        """Test modifying and saving tutorial character."""
        character = manager.load("Tutorial Hero")
        assert character is not None
        
        # Level up
        character.level = 2
        character.max_hit_points = 28
        character.current_hit_points = 28
        
        # Add a feat
        character.feats.append("Power Attack")
        
        # Save changes
        assert manager.save(character)
        
        # Reload and verify
        reloaded = manager.load("Tutorial Hero")
        assert reloaded.level == 2
        assert reloaded.max_hit_points == 28
        assert "Power Attack" in reloaded.feats


class TestCampaignManager:
    """Test campaign manager functionality with tutorial campaign."""
    
    @pytest.fixture
    def base_dir(self):
        """Get base directory for campaign data."""
        base = Path.home() / "pf2e-campaigns" / "tutorial"
        base.mkdir(parents=True, exist_ok=True)
        return base
    
    @pytest.fixture
    def manager(self, base_dir):
        """Create campaign manager for tutorial."""
        campaign_dir = base_dir / "campaigns"
        campaign_dir.mkdir(parents=True, exist_ok=True)
        return CampaignManager(campaign_dir)
    
    @pytest.fixture(autouse=True)
    def setup_tutorial_campaign(self, manager):
        """Create tutorial campaign for testing."""
        # Create the tutorial campaign
        tutorial = Campaign(
            name="Tutorial Campaign",
            description="A beginner-friendly campaign to learn Pathfinder 2e",
            dm_name="Tutorial GM",
            starting_level=1,
            current_level=1
        )
        
        # Add tutorial-specific settings
        tutorial.allowed_sources = ["Core Rulebook", "Beginner Box"]
        tutorial.house_rules = [
            "Hero points refresh at the start of each session",
            "Free archetype variant rule",
            "Gradual ability boosts"
        ]
        
        # Add a sample player
        tutorial.add_player("New Player", "player@example.com")
        
        # Add a sample NPC
        tutorial.add_npc("Tavern Keeper", "Friendly innkeeper who gives quests")
        
        # Add a sample location
        tutorial.add_location("Sandpoint", "A small coastal town where adventures begin")
        
        session1 = CampaignSession(
            session_number=1,
            session_date=date(2024, 1, 1),
            duration_minutes=180,
            location="Sandpoint Tavern",
            story_summary="The heroes meet in a tavern and accept their first quest."
        )
        session1.add_player("New Player", "Tutorial Hero")
        session1.add_event("Party formation")
        session1.add_npc("Tavern Keeper")
        tutorial.add_session(session1)
            
        # Save the tutorial campaign
        manager.save(tutorial)
        
        yield
    
    def test_load_tutorial_campaign(self, manager):
        """Test loading the tutorial campaign."""
        campaign = manager.load("Tutorial Campaign")
        assert campaign is not None
        assert campaign.name == "Tutorial Campaign"
        assert campaign.dm_name == "Tutorial GM"
        assert campaign.starting_level == 1
    
    def test_tutorial_campaign_content(self, manager):
        """Test tutorial campaign has expected content."""
        campaign = manager.load("Tutorial Campaign")
        
        # Check house rules
        assert len(campaign.house_rules) == 3
        assert "Free archetype variant rule" in campaign.house_rules
        
        # Check NPCs and locations
        assert "Tavern Keeper" in campaign.major_npcs
        assert "Sandpoint" in campaign.important_locations
        
        # Check session
        assert campaign.total_sessions == 1
        assert campaign.last_session is not None
        assert campaign.last_session.location == "Sandpoint Tavern"
    
    def test_add_session_to_tutorial(self, manager):
        """Test adding a new session to tutorial campaign."""
        # Create new session
        new_session = manager.create_session(
            "Tutorial Campaign",
            session_date=date(2024, 1, 8),
            duration_minutes=240,
            location="Goblin Cave",
            story_summary="The party explores their first dungeon."
        )
        
        assert new_session is not None
        assert new_session.session_number == 2
        
        # Verify campaign updated
        campaign = manager.load("Tutorial Campaign")
        assert campaign.total_sessions == 2
        assert campaign.current_session_number == 2
    
    def test_tutorial_campaign_summary(self, manager):
        """Test getting summary of tutorial campaign."""
        summary = manager.get_campaign_summary("Tutorial Campaign")
        
        assert summary is not None
        assert summary['name'] == "Tutorial Campaign"
        assert summary['dm'] == "Tutorial GM"
        assert summary['progress']['current_level'] == 1
        assert summary['progress']['total_sessions'] == 1
        assert "New Player" in summary['players']
    
    def test_list_includes_tutorial(self, manager):
        """Test that tutorial campaign appears in list."""
        campaigns = manager.list_campaigns()
        assert "Tutorial Campaign" in campaigns
        
        # Should also appear in active campaigns
        active = manager.list_campaigns(active_only=True)
        assert "Tutorial Campaign" in active
    
    def test_export_tutorial_campaign(self, manager, base_dir):
        """Test exporting tutorial campaign."""
        export_dir = base_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        export_path = export_dir / "tutorial_campaign.json"
        
        assert manager.export_campaign(
            "Tutorial Campaign",
            export_path,
            include_sessions=True
        )
        assert export_path.exists()
        
        # Verify exported data
        with export_path.open('r') as f:
            data = json.load(f)
        assert data['name'] == "Tutorial Campaign"
        assert len(data['sessions']) == 1
        assert len(data['house_rules']) == 3
    
    def test_tutorial_attendance(self, manager):
        """Test attendance tracking in tutorial campaign."""
        campaign = manager.load("Tutorial Campaign")
        attendance = campaign.get_attendance_report()
        
        assert "New Player" in attendance
        assert attendance["New Player"] == 1
        
        # Add another session with same player
        session2 = CampaignSession(
            session_number=2,
            session_date=date(2024, 1, 8),
            duration_minutes=180
        )
        session2.add_player("New Player", "Tutorial Hero")
        manager.add_session("Tutorial Campaign", session2)
        
        # Check updated attendance
        campaign = manager.load("Tutorial Campaign")
        attendance = campaign.get_attendance_report()
        assert attendance["New Player"] == 2
    
    def test_tutorial_treasure_tracking(self, manager):
        """Test treasure tracking in tutorial campaign."""
        # Add treasure to a new session
        session = CampaignSession(
            session_number=3,
            session_date=date(2024, 1, 15),
            duration_minutes=180
        )
        session.add_treasure(1500, ["Healing Potion", "+1 Shortsword"])
        session.add_player("New Player", "Tutorial Hero")
        manager.add_session("Tutorial Campaign", session)
        
        # Check treasure summary
        campaign = manager.load("Tutorial Campaign")
        treasure = campaign.get_treasure_summary()
        
        assert treasure['total_gold_gp'] == 15.0
        assert "Healing Potion" in treasure['items']
        assert "+1 Shortsword" in treasure['items']


class TestIntegration:
    """Integration tests using tutorial campaign and characters."""
    
    @pytest.fixture
    def base_dir(self):
        """Get base directory for campaign data."""
        base = Path.home() / "pf2e-campaigns" / "tutorial"
        base.mkdir(parents=True, exist_ok=True)
        return base
    
    @pytest.fixture
    def char_manager(self, base_dir):
        """Character manager for tutorial."""
        return CharacterManager(base_dir / "characters")
    
    @pytest.fixture
    def campaign_manager(self, base_dir):
        """Campaign manager for tutorial."""
        return CampaignManager(base_dir / "campaigns")
    
    def test_tutorial_setup_complete(self, char_manager, campaign_manager):
        """Verify complete tutorial setup."""
        # Check character exists
        character = char_manager.load("Tutorial Hero")
        assert character is not None
        
        # Check campaign exists
        campaign = campaign_manager.load("Tutorial Campaign")
        assert campaign is not None
        
        # Verify they're connected through the FIRST session (not last)
        first_session = campaign.sessions[0]  # Get first session instead of last
        assert "Tutorial Hero" in first_session.characters_present
        assert "New Player" in first_session.players_present