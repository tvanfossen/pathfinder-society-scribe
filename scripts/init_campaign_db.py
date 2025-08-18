# scripts/init_campaign_db.py
"""
Initialize the campaign database and migrate JSON character data.
Run this script to set up the database structure and import existing character files.
"""

import sqlite3
import logging
import json
from pathlib import Path
import os
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DEFAULT_SAVE_DIR = "save_files"
DEFAULT_CAMPAIGN_DB = os.path.join(DEFAULT_SAVE_DIR, "campaign.db")
DEFAULT_CHARACTER_DIR = "game_data/player_characters"

def init_database(db_path: str = DEFAULT_CAMPAIGN_DB):
    """Initialize the campaign database with all required tables."""
    
    # Ensure save directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    log.info("Initializing campaign database at: %s", db_path)
    
    with sqlite3.connect(db_path) as conn:
        # Create the campaign database schema
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
            
            -- Characters table (migrated from JSON files)
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                player_name TEXT,
                character_class TEXT,
                level INTEGER DEFAULT 1,
                ancestry TEXT,
                heritage TEXT,
                background TEXT,
                alignment TEXT,
                size INTEGER,
                
                -- Core stats
                abilities_json TEXT,  -- AbilityScores as JSON
                current_hit_points INTEGER,
                max_hit_points INTEGER,
                hero_points INTEGER DEFAULT 1,
                experience_points INTEGER DEFAULT 0,
                
                -- Combat stats
                armor_class INTEGER,
                perception INTEGER,
                fortitude INTEGER,
                reflex INTEGER,
                will INTEGER,
                
                -- Character data
                skills_json TEXT,  -- Skills dictionary as JSON
                feats_json TEXT,   -- Feats list as JSON
                class_features_json TEXT,  -- Class features as JSON
                equipment_json TEXT,  -- Equipment list as JSON
                weapons_json TEXT,    -- Weapons list as JSON
                armor_json TEXT,      -- Armor list as JSON
                spellcasting_json TEXT,  -- Spellcasting as JSON
                
                -- Details
                deity TEXT,
                languages_json TEXT,  -- Languages list as JSON
                notes TEXT,
                
                -- Metadata
                created_date TEXT,
                last_updated TEXT,
                campaign_id INTEGER,
                
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
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
            
            -- Bot NPC identities table
            CREATE TABLE IF NOT EXISTS bot_npcs (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                campaign_id INTEGER,
                created_date TEXT,
                last_updated TEXT,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            );
            
            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_characters_campaign 
                ON characters(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_characters_player 
                ON characters(player_name);
            CREATE INDEX IF NOT EXISTS idx_sessions_campaign 
                ON sessions(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_session_attendance_session 
                ON session_attendance(session_id);
            CREATE INDEX IF NOT EXISTS idx_bot_npcs_campaign 
                ON bot_npcs(campaign_id);
        """)
        
        log.info("Database schema created successfully")
        
        # Insert a default bot identity if none exists
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bot_npcs")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO bot_npcs (
                    name, description, created_date, last_updated, active
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                "Pathfinder Assistant",
                "A helpful digital companion for Pathfinder 2e adventures",
                now, now, 1
            ))
            log.info("Created default bot NPC identity: 'Pathfinder Assistant'")
        
        conn.commit()
    
    log.info("Database initialization complete!")

def migrate_json_characters(character_dir: str = DEFAULT_CHARACTER_DIR, 
                          db_path: str = DEFAULT_CAMPAIGN_DB):
    """Migrate existing JSON character files into the database."""
    
    char_path = Path(character_dir)
    if not char_path.exists():
        log.info("No character directory found at %s - skipping migration", character_dir)
        return
    
    json_files = list(char_path.glob("*.json"))
    if not json_files:
        log.info("No JSON character files found - skipping migration")
        return
    
    log.info("Found %d character files to migrate", len(json_files))
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        migrated_count = 0
        
        for json_file in json_files:
            try:
                log.info("Migrating character from %s", json_file.name)
                
                with open(json_file, 'r', encoding='utf-8') as f:
                    char_data = json.load(f)
                
                # Check if character already exists
                cursor.execute("SELECT COUNT(*) FROM characters WHERE name = ?", 
                             (char_data.get('name'),))
                if cursor.fetchone()[0] > 0:
                    log.info("Character '%s' already exists - skipping", char_data.get('name'))
                    continue
                
                # Extract and validate character data
                name = char_data.get('name', 'Unknown')
                player_name = char_data.get('player_name', '')
                character_class = char_data.get('character_class', '')
                level = char_data.get('level', 1)
                ancestry = char_data.get('ancestry', '')
                heritage = char_data.get('heritage', '')
                background = char_data.get('background', '')
                alignment = char_data.get('alignment', 'N')
                size = char_data.get('size', 3)  # Medium
                
                # Core stats
                abilities_json = json.dumps(char_data.get('abilities', {}))
                current_hit_points = char_data.get('hit_points', char_data.get('current_hit_points', 0))
                max_hit_points = char_data.get('max_hit_points', 0)
                hero_points = char_data.get('hero_points', 1)
                experience_points = char_data.get('experience_points', 0)
                
                # Combat stats
                armor_class = char_data.get('armor_class', 10)
                perception = char_data.get('perception', 0)
                fortitude = char_data.get('fortitude', 0)
                reflex = char_data.get('reflex', 0)
                will = char_data.get('will', 0)
                
                # Character data as JSON
                skills_json = json.dumps(char_data.get('skills', {}))
                feats_json = json.dumps(char_data.get('feats', []))
                class_features_json = json.dumps(char_data.get('class_features', []))
                equipment_json = json.dumps(char_data.get('equipment', []))
                weapons_json = json.dumps(char_data.get('weapons', []))
                armor_json = json.dumps(char_data.get('armor', []))
                spellcasting_json = json.dumps(char_data.get('spellcasting', []))
                
                # Details
                deity = char_data.get('deity', '')
                languages_json = json.dumps(char_data.get('languages', []))
                notes = char_data.get('notes', '')
                
                # Metadata
                created_date = char_data.get('created_date', datetime.now().isoformat())
                last_updated = char_data.get('last_updated', datetime.now().isoformat())
                
                # Insert character into database
                cursor.execute("""
                    INSERT INTO characters (
                        name, player_name, character_class, level, ancestry, heritage, 
                        background, alignment, size, abilities_json, current_hit_points, 
                        max_hit_points, hero_points, experience_points, armor_class, 
                        perception, fortitude, reflex, will, skills_json, feats_json, 
                        class_features_json, equipment_json, weapons_json, armor_json, 
                        spellcasting_json, deity, languages_json, notes, created_date, 
                        last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                             ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, player_name, character_class, level, ancestry, heritage,
                    background, alignment, size, abilities_json, current_hit_points,
                    max_hit_points, hero_points, experience_points, armor_class,
                    perception, fortitude, reflex, will, skills_json, feats_json,
                    class_features_json, equipment_json, weapons_json, armor_json,
                    spellcasting_json, deity, languages_json, notes, created_date,
                    last_updated
                ))
                
                migrated_count += 1
                log.info("Successfully migrated character: %s", name)
                
            except Exception as e:
                log.error("Failed to migrate %s: %s", json_file.name, e)
                continue
        
        conn.commit()
        log.info("Migration complete! Migrated %d characters", migrated_count)

if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CAMPAIGN_DB
    char_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CHARACTER_DIR
    
    log.info("=== Campaign Database Initialization ===")
    log.info("Database: %s", db_path)
    log.info("Character source: %s", char_dir)
    
    # Initialize database schema
    init_database(db_path)
    
    # Migrate JSON character files
    migrate_json_characters(char_dir, db_path)
    
    log.info("=== Initialization Complete ===")
    print(f"\nDatabase ready at: {db_path}")
    print("Character data has been migrated from JSON files")
    print("You can now use the MCP tools for campaign management!")