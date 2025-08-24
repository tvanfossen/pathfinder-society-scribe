#!/usr/bin/env python3
"""
Setup script to create tutorial campaign and characters.
Run this to initialize the tutorial data for testing and new users.
"""

import sys
from pathlib import Path
from datetime import date

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.managers.character_manager import CharacterManager
from src.managers.campaign_manager import CampaignManager
from src.models.character import PlayerCharacter
from src.models.campaign import Campaign, CampaignSession
from src.models.equipment import Equipment, Weapon, Armor
from src.models.base import (
    Alignment, Size, Skill, Proficiency, 
    DamageType, WeaponCategory, ArmorCategory
)


def create_tutorial_characters():
    """Create tutorial characters."""
    base_dir = Path.home() / "pf2e-campaigns" / "tutorial" / "characters"
    base_dir.mkdir(parents=True, exist_ok=True)
    
    manager = CharacterManager(base_dir)
    
    # Create Fighter character
    fighter = PlayerCharacter(
        name="Valeros",
        player_name="Tutorial Player",
        level=1,
        character_class="Fighter",
        ancestry="Human",
        heritage="Versatile Heritage",
        background="Guard",
        alignment=Alignment.NEUTRAL_GOOD,
        deity="Cayden Cailean",
        max_hit_points=20,
        current_hit_points=20,
        speed=25
    )
    
    # Set abilities
    fighter.abilities.strength = 18
    fighter.abilities.dexterity = 14
    fighter.abilities.constitution = 14
    fighter.abilities.intelligence = 10
    fighter.abilities.wisdom = 12
    fighter.abilities.charisma = 10
    
    # Set skills
    fighter.skills.set_proficiency(Skill.ATHLETICS, Proficiency.TRAINED)
    fighter.skills.set_proficiency(Skill.INTIMIDATION, Proficiency.TRAINED)
    fighter.skills.set_proficiency(Skill.SOCIETY, Proficiency.TRAINED)
    
    # Set defenses
    fighter.defenses.fortitude_proficiency = Proficiency.EXPERT
    fighter.defenses.reflex_proficiency = Proficiency.EXPERT
    fighter.defenses.will_proficiency = Proficiency.TRAINED
    fighter.perception_proficiency = Proficiency.EXPERT
    
    # Add equipment
    longsword = Weapon(
        name="Longsword",
        damage_dice="1d8",
        damage_type=DamageType.SLASHING,
        weapon_category=WeaponCategory.MARTIAL,
        hands="1+",
        value_cp=1500,
        bulk=1.0
    )
    fighter.weapons.append(longsword)
    
    scale_mail = Armor(
        name="Scale Mail",
        ac_bonus=3,
        dex_cap=2,
        check_penalty=-2,
        speed_penalty=5,
        armor_category=ArmorCategory.MEDIUM,
        value_cp=500,
        bulk=2.0
    )
    fighter.armor = scale_mail
    fighter.defenses.armor_class = 18  # 10 + 2 dex + 3 armor + 3 trained
    
    # Add starting gear
    fighter.equipment.extend([
        Equipment(name="Backpack", bulk=0.0, value_cp=10),
        Equipment(name="Bedroll", bulk=0.1, value_cp=10),
        Equipment(name="Rope (50 ft)", bulk=1.0, value_cp=100),
        Equipment(name="Rations (5 days)", bulk=0.5, value_cp=25),
        Equipment(name="Waterskin", bulk=0.1, value_cp=5),
    ])
    
    # Add feats
    fighter.feats = ["Shield Block", "Reactive Shield", "Sudden Charge"]
    fighter.languages.update(["Common", "Dwarven"])
    
    manager.save(fighter)
    print(f"✓ Created fighter character: {fighter.name}")
    
    # Create Wizard character
    wizard = PlayerCharacter(
        name="Ezren",
        player_name="Tutorial Player",
        level=1,
        character_class="Wizard",
        ancestry="Human",
        heritage="Skilled Heritage",
        background="Scholar",
        alignment=Alignment.NEUTRAL_GOOD,
        max_hit_points=15,
        current_hit_points=15,
        speed=25
    )
    
    # Set abilities
    wizard.abilities.strength = 10
    wizard.abilities.dexterity = 14
    wizard.abilities.constitution = 12
    wizard.abilities.intelligence = 18
    wizard.abilities.wisdom = 14
    wizard.abilities.charisma = 10
    
    # Set skills
    wizard.skills.set_proficiency(Skill.ARCANA, Proficiency.EXPERT)
    wizard.skills.set_proficiency(Skill.CRAFTING, Proficiency.TRAINED)
    wizard.skills.set_proficiency(Skill.OCCULTISM, Proficiency.TRAINED)
    wizard.skills.set_proficiency(Skill.SOCIETY, Proficiency.TRAINED)
    wizard.skills.set_proficiency(Skill.LORE, Proficiency.TRAINED)  # Academia Lore
    
    # Set defenses
    wizard.defenses.fortitude_proficiency = Proficiency.TRAINED
    wizard.defenses.reflex_proficiency = Proficiency.TRAINED
    wizard.defenses.will_proficiency = Proficiency.EXPERT
    wizard.perception_proficiency = Proficiency.TRAINED
    wizard.defenses.armor_class = 15  # 10 + 2 dex + 0 armor + 3 trained
    
    # Add equipment
    staff = Weapon(
        name="Staff",
        damage_dice="1d4",
        damage_type=DamageType.BLUDGEONING,
        weapon_category=WeaponCategory.SIMPLE,
        hands="1",
        value_cp=0,
        bulk=1.0
    )
    wizard.weapons.append(staff)
    
    # Add wizard gear
    wizard.equipment.extend([
        Equipment(name="Spellbook", bulk=1.0, value_cp=100),
        Equipment(name="Component Pouch", bulk=0.1, value_cp=50),
        Equipment(name="Backpack", bulk=0.0, value_cp=10),
        Equipment(name="Ink and Quill", bulk=0.0, value_cp=10),
        Equipment(name="Scroll Case", bulk=0.1, value_cp=10),
    ])
    
    # Add feats
    wizard.feats = ["Reach Spell", "Eschew Materials"]
    wizard.languages.update(["Common", "Draconic", "Elven", "Goblin"])
    
    manager.save(wizard)
    print(f"✓ Created wizard character: {wizard.name}")
    
    # Create Rogue character
    rogue = PlayerCharacter(
        name="Merisiel",
        player_name="Tutorial Player",
        level=1,
        character_class="Rogue",
        ancestry="Elf",
        heritage="Woodland Elf",
        background="Criminal",
        alignment=Alignment.CHAOTIC_NEUTRAL,
        max_hit_points=17,
        current_hit_points=17,
        speed=30
    )
    
    # Set abilities
    rogue.abilities.strength = 12
    rogue.abilities.dexterity = 18
    rogue.abilities.constitution = 12
    rogue.abilities.intelligence = 14
    rogue.abilities.wisdom = 12
    rogue.abilities.charisma = 10
    
    # Set skills
    rogue.skills.set_proficiency(Skill.ACROBATICS, Proficiency.TRAINED)
    rogue.skills.set_proficiency(Skill.DECEPTION, Proficiency.TRAINED)
    rogue.skills.set_proficiency(Skill.STEALTH, Proficiency.EXPERT)
    rogue.skills.set_proficiency(Skill.THIEVERY, Proficiency.EXPERT)
    rogue.skills.set_proficiency(Skill.ATHLETICS, Proficiency.TRAINED)
    rogue.skills.set_proficiency(Skill.INTIMIDATION, Proficiency.TRAINED)
    
    # Set defenses
    rogue.defenses.fortitude_proficiency = Proficiency.TRAINED
    rogue.defenses.reflex_proficiency = Proficiency.EXPERT
    rogue.defenses.will_proficiency = Proficiency.EXPERT
    rogue.perception_proficiency = Proficiency.EXPERT
    rogue.defenses.armor_class = 18  # 10 + 4 dex + 1 armor + 3 trained
    
    # Add equipment
    rapier = Weapon(
        name="Rapier",
        damage_dice="1d6",
        damage_type=DamageType.PIERCING,
        weapon_category=WeaponCategory.MARTIAL,
        hands="1",
        traits=["Deadly d8", "Disarm", "Finesse"],
        value_cp=200,
        bulk=1.0
    )
    rogue.weapons.append(rapier)
    
    shortbow = Weapon(
        name="Shortbow",
        damage_dice="1d6",
        damage_type=DamageType.PIERCING,
        weapon_category=WeaponCategory.MARTIAL,
        range_increment=60,
        reload=0,
        value_cp=300,
        bulk=1.0
    )
    rogue.weapons.append(shortbow)
    
    leather = Armor(
        name="Leather Armor",
        ac_bonus=1,
        dex_cap=4,
        check_penalty=-1,
        armor_category=ArmorCategory.LIGHT,
        value_cp=200,
        bulk=1.0
    )
    rogue.armor = leather
    
    # Add rogue gear
    rogue.equipment.extend([
        Equipment(name="Thieves' Tools", bulk=0.1, value_cp=300),
        Equipment(name="Backpack", bulk=0.0, value_cp=10),
        Equipment(name="Caltrops", bulk=0.1, value_cp=30),
        Equipment(name="Disguise Kit", bulk=1.0, value_cp=200),
        Equipment(name="Grappling Hook", bulk=1.0, value_cp=10),
    ])
    
    # Add feats
    rogue.feats = ["Nimble Dodge", "Trap Finder", "Twin Feint"]
    rogue.languages.update(["Common", "Elven", "Undercommon"])
    
    manager.save(rogue)
    print(f"✓ Created rogue character: {rogue.name}")
    
    return manager


def create_tutorial_campaign():
    """Create the tutorial campaign."""
    base_dir = Path.home() / "pf2e-campaigns" / "tutorial" / "campaigns"
    base_dir.mkdir(parents=True, exist_ok=True)
    
    manager = CampaignManager(base_dir)
    
    # Create campaign
    campaign = Campaign(
        name="Beginner Box Adventures",
        description="Learn to play Pathfinder 2e with the Beginner Box adventure path",
        setting="Golarion - Inner Sea Region",
        dm_name="Tutorial GM",
        starting_level=1,
        current_level=1,
        ability_score_method="standard"
    )
    
    # Set campaign options
    campaign.allowed_sources = [
        "Core Rulebook",
        "Beginner Box",
        "Advanced Player's Guide (selected options)"
    ]
    
    campaign.house_rules = [
        "Hero points refresh at session start (max 1)",
        "Free archetype variant rule available at level 2",
        "Recall Knowledge gives one piece of useful information on success",
        "Critical fumbles only on natural 1 with a failure",
        "Dying condition increases by 1 (not 2) on critical failure"
    ]
    
    # Add players
    campaign.add_player("Tutorial Player", "player@example.com")
    campaign.add_player("Guest Player", "guest@example.com")
    
    # Add major NPCs
    campaign.add_npc("Tamily Tanderveil", "Fisherman's daughter, quest giver in Otari")
    campaign.add_npc("Wrin Sivinxi", "Tiefling shopkeeper, runs Wrin's Wonders")
    campaign.add_npc("Captain Longsaddle", "Gruff but fair captain of the town guard")
    campaign.add_npc("Mayor Oseph", "Elderly human mayor of Otari")
    
    # Add locations
    campaign.add_location("Otari", "Small fishing town on the coast, population ~1,200")
    campaign.add_location("The Crow's Cask", "Popular tavern and inn run by Tamily")
    campaign.add_location("Menace Under Otari", "Abandoned smuggler's tunnels beneath the town")
    campaign.add_location("Otari Market", "Town square with various shops and stalls")
    
    # Create first session
    session1 = CampaignSession(
        session_number=1,
        session_date=date(2024, 1, 1),
        duration_minutes=180,
        location="The Crow's Cask Tavern",
        story_summary=(
            "The heroes arrived in Otari and met at the Crow's Cask tavern. "
            "Tamily Tanderveil approached them about strange sounds and creatures "
            "coming from the basement. The party investigated and discovered "
            "kobolds had broken through from old smuggling tunnels below."
        ),
        dm_notes="Players handled combat well. Need to emphasize skill checks more.",
        experience_awarded=120,
        milestone_reached=False
    )
    
    session1.add_player("Tutorial Player", "Valeros")
    session1.add_player("Tutorial Player", "Ezren")
    session1.add_player("Guest Player", "Merisiel")
    
    session1.add_treasure(450, [
        "Lesser Healing Potion x2",
        "Scroll of Magic Weapon",
        "Silvered Dagger"
    ])
    
    session1.add_event("Party forms at the Crow's Cask")
    session1.add_event("First combat with kobolds")
    session1.add_event("Discovery of the smuggling tunnels")
    
    session1.add_npc("Tamily Tanderveil")
    session1.add_npc("Wrin Sivinxi")
    
    campaign.add_session(session1)
    
    # Create second session
    session2 = CampaignSession(
        session_number=2,
        session_date=date(2024, 1, 8),
        duration_minutes=240,
        location="Menace Under Otari - Level 1",
        story_summary=(
            "The party descended into the smuggling tunnels. They fought giant rats, "
            "discovered an old shrine, and encountered more kobolds. Found evidence "
            "of a larger kobold tribe deeper in the complex. Rescued a lost cat."
        ),
        dm_notes="Good exploration. Players starting to work as a team.",
        experience_awarded=160,
        milestone_reached=False
    )
    
    session2.add_player("Tutorial Player", "Valeros")
    session2.add_player("Tutorial Player", "Ezren") 
    session2.add_player("Guest Player", "Merisiel")
    
    session2.add_treasure(750, [
        "Lesser Healing Potion x3",
        "Oil of Potency",
        "Jade Cat Statue (worth 20 gp)",
        "Ancient Coins (worth 35 gp)"
    ])
    
    session2.add_event("Explored the first level of tunnels")
    session2.add_event("Defeated giant rat nest")
    session2.add_event("Found and returned Mrs. Whiskers the cat")
    
    campaign.add_session(session2)
    
    # Set next session date
    campaign.next_session_date = date(2024, 1, 15)
    campaign.current_chapter = "Chapter 1: Menace Under Otari"
    campaign.story_arc = "The Beginner Box Adventure Path"
    
    manager.save(campaign)
    print(f"✓ Created campaign: {campaign.name}")
    
    return manager


def main():
    """Run the tutorial setup."""
    print("\n" + "="*60)
    print("Setting up Pathfinder 2e Tutorial Campaign")
    print("="*60 + "\n")
    
    # Create tutorial directory structure
    base_dir = Path.home() / "pf2e-campaigns" / "tutorial"
    base_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created tutorial directory: {base_dir}")
    
    # Create characters
    print("\nCreating tutorial characters...")
    char_manager = create_tutorial_characters()
    
    # Create campaign
    print("\nCreating tutorial campaign...")
    campaign_manager = create_tutorial_campaign()