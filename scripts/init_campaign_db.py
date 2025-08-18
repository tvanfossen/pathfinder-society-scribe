# scripts/init_campaign_db.py
"""
Initialize the campaign database with proper schema for bot integration.
Run this script to set up the database structure before using the Discord bot.
"""

import sqlite3
import logging
from pathlib import Path
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DEFAULT_SAVE_DIR = "save_files"
DEFAULT_CAMPAIGN_DB = os.path.join(DEFAULT_SAVE_DIR, "campaign.db")

def init_database(db_path: str = DEFAULT_CAMPAIGN_DB):
    """Initialize the campaign database with all required tables."""
    
    # Ensure save directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    log.info("Initializing campaign database at: %s", db_path)
    
    with sqlite3.connect(db_path) as conn:
        # Create the standard campaign tables
        conn.executescript("""
            -- Campaigns table
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                dm_name TEXT,
                created_date TEXT,
                starting_level INTEGER DEFAULT 1,
                current_session INTEGER DEFAULT 0,
                total_sessions INTEGER DEFAULT 0,
                settings_json TEXT
            );
            
            -- Sessions table
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                campaign_id INTEGER,
                session_number INTEGER,
                session_date TEXT,
                duration_minutes INTEGER DEFAULT 0,
                experience_awarded INTEGER DEFAULT 0,
                story_notes TEXT,
                dm_notes TEXT,
                session_data_json TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            );
            
            -- Session attendance tracking
            CREATE TABLE IF NOT EXISTS session_attendance (
                session_id INTEGER,
                player_name TEXT,
                character_name TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            );
            
            -- Bot NPC identities table (NEW)
            CREATE TABLE IF NOT EXISTS bot_npcs (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                campaign_id INTEGER,
                created_date TEXT,
                last_updated TEXT,
                personality_traits TEXT,  -- JSON for bot personality
                voice_settings TEXT,      -- JSON for voice/speaking style
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            );
            
            -- Character status tracking (NEW)
            CREATE TABLE IF NOT EXISTS character_status (
                id INTEGER PRIMARY KEY,
                character_name TEXT NOT NULL,
                campaign_id INTEGER,
                current_hp INTEGER,
                max_hp INTEGER,
                conditions TEXT,  -- JSON array of conditions
                temporary_stats TEXT,  -- JSON for temporary modifiers
                last_updated TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            );
            
            -- Discord integration table (NEW)
            CREATE TABLE IF NOT EXISTS discord_integration (
                id INTEGER PRIMARY KEY,
                guild_id TEXT,
                channel_id TEXT,
                campaign_id INTEGER,
                bot_npc_id INTEGER,
                settings_json TEXT,  -- Bot behavior settings per channel
                created_date TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                FOREIGN KEY (bot_npc_id) REFERENCES bot_npcs (id)
            );
            
            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_sessions_campaign 
                ON sessions(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_session_attendance_session 
                ON session_attendance(session_id);
            CREATE INDEX IF NOT EXISTS idx_bot_npcs_campaign 
                ON bot_npcs(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_character_status_campaign 
                ON character_status(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_discord_guild 
                ON discord_integration(guild_id);
        """)
        
        log.info("Database schema created successfully")
        
        # Insert a default bot identity if none exists
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bot_npcs")
        if cursor.fetchone()[0] == 0:
            from datetime import datetime
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO bot_npcs (
                    name, description, created_date, last_updated, 
                    personality_traits, active
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "Pathfinder Assistant",
                "A helpful digital companion for Pathfinder 2e adventures",
                now, now,
                '{"helpful": true, "knowledgeable": true, "encouraging": true}',
                1
            ))
            log.info("Created default bot NPC identity: 'Pathfinder Assistant'")
        
        conn.commit()
    
    log.info("Database initialization complete!")

def create_sample_campaign():
    """Create a sample campaign for testing."""
    from game_data.campaign_helpers import Campaign, CampaignDataManager
    from datetime import date
    
    try:
        campaign_manager = CampaignDataManager(DEFAULT_CAMPAIGN_DB)
        
        # Check if sample campaign already exists
        existing = campaign_manager.get_campaign("Sample Campaign")
        if existing:
            log.info("Sample campaign already exists")
            return
        
        sample_campaign = Campaign(
            name="Sample Campaign",
            description="A sample campaign for testing Discord bot integration",
            dm_name="Bot Master",
            starting_level=1,
            allowed_ancestries=["Human", "Elf", "Dwarf", "Halfling"],
            house_rules=["Free Archetype", "Automatic Bonus Progression"]
        )
        
        campaign_id = campaign_manager.create_campaign(sample_campaign)
        log.info("Created sample campaign with ID: %d", campaign_id)
        
    except Exception as e:
        log.error("Failed to create sample campaign: %s", e)

if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CAMPAIGN_DB
    
    log.info("=== Campaign Database Initialization ===")
    init_database(db_path)
    
    # Optionally create sample data
    create_sample = input("Create sample campaign? (y/N): ").lower().startswith('y')
    if create_sample:
        create_sample_campaign()
    
    log.info("=== Initialization Complete ===")
    print(f"\nDatabase ready at: {db_path}")
    print("You can now use the Discord bot with campaign management features!")