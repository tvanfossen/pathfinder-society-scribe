-- game_data/schema_campaign.sql
-- Database schema for campaign management and session tracking

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- Campaigns table for storing campaign metadata
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    dm_name TEXT,
    created_date TEXT NOT NULL,
    starting_level INTEGER DEFAULT 1,
    current_session INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    settings_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Game sessions table for tracking individual session data
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL,
    session_number INTEGER NOT NULL,
    session_date TEXT NOT NULL,
    duration_minutes INTEGER DEFAULT 0,
    experience_awarded INTEGER DEFAULT 0,
    story_notes TEXT,
    dm_notes TEXT,
    session_data_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    UNIQUE(campaign_id, session_number)
);

-- Session attendance tracking for players and characters
CREATE TABLE IF NOT EXISTS session_attendance (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    character_name TEXT,
    attendance_status TEXT DEFAULT 'present',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
);

-- Character progression tracking (optional - for linking with character files)
CREATE TABLE IF NOT EXISTS character_progression (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL,
    character_name TEXT NOT NULL,
    player_name TEXT NOT NULL,
    level INTEGER DEFAULT 1,
    experience_points INTEGER DEFAULT 0,
    last_session_id INTEGER,
    character_file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    FOREIGN KEY (last_session_id) REFERENCES sessions (id),
    UNIQUE(campaign_id, character_name)
);

-- Treasure/rewards tracking
CREATE TABLE IF NOT EXISTS session_rewards (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    reward_type TEXT NOT NULL, -- 'treasure', 'experience', 'story'
    description TEXT NOT NULL,
    value_cp INTEGER DEFAULT 0, -- value in copper pieces for monetary rewards
    recipient TEXT, -- character name or 'party'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
);

-- Indexes for improved query performance
CREATE INDEX IF NOT EXISTS idx_campaigns_name ON campaigns(name);
CREATE INDEX IF NOT EXISTS idx_campaigns_dm ON campaigns(dm_name);

CREATE INDEX IF NOT EXISTS idx_sessions_campaign ON sessions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_sessions_number ON sessions(session_number);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(session_date);

CREATE INDEX IF NOT EXISTS idx_attendance_session ON session_attendance(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_player ON session_attendance(player_name);

CREATE INDEX IF NOT EXISTS idx_progression_campaign ON character_progression(campaign_id);
CREATE INDEX IF NOT EXISTS idx_progression_character ON character_progression(character_name);
CREATE INDEX IF NOT EXISTS idx_progression_player ON character_progression(player_name);

CREATE INDEX IF NOT EXISTS idx_rewards_session ON session_rewards(session_id);
CREATE INDEX IF NOT EXISTS idx_rewards_type ON session_rewards(reward_type);
CREATE INDEX IF NOT EXISTS idx_rewards_recipient ON session_rewards(recipient);

-- Views for common queries
CREATE VIEW IF NOT EXISTS campaign_summary AS
SELECT 
    c.id,
    c.name,
    c.description,
    c.dm_name,
    c.starting_level,
    c.current_session,
    c.total_sessions,
    COUNT(DISTINCT s.id) as actual_session_count,
    COUNT(DISTINCT cp.character_name) as active_characters,
    MAX(s.session_date) as last_session_date,
    SUM(s.duration_minutes) as total_play_time_minutes
FROM campaigns c
LEFT JOIN sessions s ON c.id = s.campaign_id
LEFT JOIN character_progression cp ON c.id = cp.campaign_id
GROUP BY c.id, c.name, c.description, c.dm_name, c.starting_level, c.current_session, c.total_sessions;

-- View for session attendance summary
CREATE VIEW IF NOT EXISTS session_attendance_summary AS
SELECT 
    s.id as session_id,
    s.campaign_id,
    s.session_number,
    s.session_date,
    COUNT(sa.id) as total_attendees,
    GROUP_CONCAT(sa.player_name, ', ') as attendee_list,
    s.duration_minutes,
    s.experience_awarded
FROM sessions s
LEFT JOIN session_attendance sa ON s.id = sa.session_id AND sa.attendance_status = 'present'
GROUP BY s.id, s.campaign_id, s.session_number, s.session_date, s.duration_minutes, s.experience_awarded;

-- Trigger to automatically update campaign.total_sessions when sessions are added
CREATE TRIGGER IF NOT EXISTS update_campaign_session_count
AFTER INSERT ON sessions
BEGIN
    UPDATE campaigns 
    SET total_sessions = (
        SELECT COUNT(*) FROM sessions WHERE campaign_id = NEW.campaign_id
    ),
    current_session = NEW.session_number,
    updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.campaign_id;
END;

-- Trigger to update updated_at timestamp on campaigns
CREATE TRIGGER IF NOT EXISTS update_campaigns_timestamp
AFTER UPDATE ON campaigns
BEGIN
    UPDATE campaigns SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger to update updated_at timestamp on sessions
CREATE TRIGGER IF NOT EXISTS update_sessions_timestamp
AFTER UPDATE ON sessions
BEGIN
    UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger to update character progression when session attendance is recorded
CREATE TRIGGER IF NOT EXISTS update_character_last_session
AFTER INSERT ON session_attendance
WHEN NEW.character_name IS NOT NULL
BEGIN
    INSERT OR REPLACE INTO character_progression (
        campaign_id, character_name, player_name, last_session_id, updated_at
    ) 
    SELECT 
        s.campaign_id, 
        NEW.character_name, 
        NEW.player_name, 
        NEW.session_id,
        CURRENT_TIMESTAMP
    FROM sessions s 
    WHERE s.id = NEW.session_id;
END;