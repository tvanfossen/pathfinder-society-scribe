# src/models/campaign.py
"""Campaign and session models for game management."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any, Set
from .base import TimestampedModel


@dataclass
class CampaignSession(TimestampedModel):
    """Individual game session data."""
    
    session_number: int
    session_date: date
    duration_minutes: int = 0
    
    # Progress tracking
    experience_awarded: int = 0
    milestone_reached: bool = False
    
    # Treasure and rewards
    gold_found: int = 0  # In copper pieces
    items_found: List[str] = field(default_factory=list)
    
    # Story and notes
    story_summary: str = ""
    dm_notes: str = ""
    player_notes: Dict[str, str] = field(default_factory=dict)
    
    # Attendance
    players_present: Set[str] = field(default_factory=set)
    characters_present: Set[str] = field(default_factory=set)
    
    # Location and events
    location: str = ""
    major_events: List[str] = field(default_factory=list)
    npcs_met: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize base class."""
        super().__init__()
    
    @property
    def duration_hours(self) -> float:
        """Session duration in hours."""
        return self.duration_minutes / 60.0
    
    @property
    def gold_found_gp(self) -> float:
        """Gold found in gold pieces."""
        return self.gold_found / 100.0
    
    def add_player(self, player_name: str, character_name: str) -> None:
        """Add a player and their character to the session."""
        self.players_present.add(player_name)
        self.characters_present.add(character_name)
        self.touch()
    
    def add_treasure(self, gold_cp: int, items: List[str]) -> None:
        """Add treasure found in the session."""
        self.gold_found += gold_cp
        self.items_found.extend(items)
        self.touch()
    
    def add_event(self, event: str) -> None:
        """Add a major event to the session."""
        if event not in self.major_events:
            self.major_events.append(event)
            self.touch()
    
    def add_npc(self, npc_name: str) -> None:
        """Add an NPC met in the session."""
        if npc_name not in self.npcs_met:
            self.npcs_met.append(npc_name)
            self.touch()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'session_number': self.session_number,
            'session_date': self.session_date.isoformat(),
            'duration_minutes': self.duration_minutes,
            'experience_awarded': self.experience_awarded,
            'milestone_reached': self.milestone_reached,
            'gold_found': self.gold_found,
            'items_found': self.items_found,
            'story_summary': self.story_summary,
            'dm_notes': self.dm_notes,
            'player_notes': self.player_notes,
            'players_present': list(self.players_present),
            'characters_present': list(self.characters_present),
            'location': self.location,
            'major_events': self.major_events,
            'npcs_met': self.npcs_met,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CampaignSession':
        """Create from dictionary."""
        if 'session_date' in data and isinstance(data['session_date'], str):
            data['session_date'] = date.fromisoformat(data['session_date'])
        
        if 'players_present' in data:
            data['players_present'] = set(data['players_present'])
        if 'characters_present' in data:
            data['characters_present'] = set(data['characters_present'])
        
        # Remove timestamps as they're handled by parent
        if 'created_at' in data:
            del data['created_at']
        if 'updated_at' in data:
            del data['updated_at']
        
        return cls(**data)


@dataclass
class Campaign(TimestampedModel):
    """Campaign-level data and configuration."""
    
    # Identity
    name: str
    description: str = ""
    setting: str = "Golarion"
    
    # Game master
    dm_name: str = ""
    dm_email: Optional[str] = None
    
    # Players
    players: Dict[str, str] = field(default_factory=dict)  # name -> email
    
    # Campaign settings
    starting_level: int = 1
    current_level: int = 1
    level_progression: str = "milestone"  # "milestone" or "experience"
    
    # Rules and restrictions
    allowed_sources: List[str] = field(default_factory=lambda: ["Core Rulebook"])
    banned_options: List[str] = field(default_factory=list)
    house_rules: List[str] = field(default_factory=list)
    
    # Character creation rules
    ability_score_method: str = "standard"  # standard, rolled, point-buy
    starting_gold: int = 1500  # in copper pieces
    free_archetype: bool = False
    ancestry_paragon: bool = False
    
    # Progress tracking
    sessions: List[CampaignSession] = field(default_factory=list)
    current_session_number: int = 0
    next_session_date: Optional[date] = None
    
    # Story elements
    current_chapter: str = ""
    story_arc: str = ""
    major_npcs: Dict[str, str] = field(default_factory=dict)  # name -> description
    important_locations: Dict[str, str] = field(default_factory=dict)
    
    # Campaign status
    is_active: bool = True
    on_hiatus: bool = False
    completed: bool = False
    
    def __post_init__(self):
        """Initialize base class."""
        super().__init__()
    
    @property
    def total_sessions(self) -> int:
        """Get total number of sessions."""
        return len(self.sessions)
    
    @property
    def total_playtime_hours(self) -> float:
        """Get total campaign playtime in hours."""
        return sum(session.duration_hours for session in self.sessions)
    
    @property
    def average_session_length(self) -> float:
        """Get average session length in hours."""
        if not self.sessions:
            return 0.0
        return self.total_playtime_hours / len(self.sessions)
    
    @property
    def last_session(self) -> Optional[CampaignSession]:
        """Get the most recent session."""
        if not self.sessions:
            return None
        return max(self.sessions, key=lambda s: s.session_date)
    
    def add_session(self, session: CampaignSession) -> None:
        """Add a new session to the campaign."""
        self.sessions.append(session)
        self.current_session_number = max(
            self.current_session_number,
            session.session_number
        )
        self.touch()
    
    def add_player(self, name: str, email: Optional[str] = None) -> None:
        """Add a player to the campaign."""
        self.players[name] = email or ""  # This is correct
        self.touch()
    
    def remove_player(self, name: str) -> None:
        """Remove a player from the campaign."""
        if name in self.players:
            del self.players[name]
            self.touch()
    
    def add_house_rule(self, rule: str) -> None:
        """Add a house rule."""
        if rule not in self.house_rules:
            self.house_rules.append(rule)
            self.touch()
    
    def add_npc(self, name: str, description: str) -> None:
        """Add or update a major NPC."""
        self.major_npcs[name] = description
        self.touch()
    
    def add_location(self, name: str, description: str) -> None:
        """Add or update an important location."""
        self.important_locations[name] = description
        self.touch()
    
    def set_hiatus(self, on_hiatus: bool = True) -> None:
        """Put campaign on hiatus or resume."""
        self.on_hiatus = on_hiatus
        self.is_active = not on_hiatus
        self.touch()
    
    def complete_campaign(self) -> None:
        """Mark campaign as completed."""
        self.completed = True
        self.is_active = False
        self.on_hiatus = False
        self.touch()
    
    def get_attendance_report(self) -> Dict[str, int]:
        """Get attendance count for each player."""
        attendance = {}
        for session in self.sessions:
            for player in session.players_present:
                attendance[player] = attendance.get(player, 0) + 1
        return attendance
    
    def get_treasure_summary(self) -> Dict[str, Any]:
        """Get summary of all treasure found."""
        total_gold = sum(session.gold_found for session in self.sessions)
        all_items = []
        for session in self.sessions:
            all_items.extend(session.items_found)
        
        return {
            'total_gold_cp': total_gold,
            'total_gold_gp': total_gold / 100.0,
            'items': all_items,
            'unique_items': list(set(all_items))
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'setting': self.setting,
            'dm_name': self.dm_name,
            'dm_email': self.dm_email,
            'players': self.players,
            'starting_level': self.starting_level,
            'current_level': self.current_level,
            'level_progression': self.level_progression,
            'allowed_sources': self.allowed_sources,
            'banned_options': self.banned_options,
            'house_rules': self.house_rules,
            'ability_score_method': self.ability_score_method,
            'starting_gold': self.starting_gold,
            'free_archetype': self.free_archetype,
            'ancestry_paragon': self.ancestry_paragon,
            'sessions': [session.to_dict() for session in self.sessions],
            'current_session_number': self.current_session_number,
            'next_session_date': self.next_session_date.isoformat() if self.next_session_date else None,
            'current_chapter': self.current_chapter,
            'story_arc': self.story_arc,
            'major_npcs': self.major_npcs,
            'important_locations': self.important_locations,
            'is_active': self.is_active,
            'on_hiatus': self.on_hiatus,
            'completed': self.completed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Campaign':
        """Create from dictionary."""
        if 'next_session_date' in data and data['next_session_date']:
            data['next_session_date'] = date.fromisoformat(data['next_session_date'])
        
        if 'sessions' in data:
            data['sessions'] = [
                CampaignSession.from_dict(session) for session in data['sessions']
            ]
        
        # Remove timestamps as they're handled by parent
        if 'created_at' in data:
            del data['created_at']
        if 'updated_at' in data:
            del data['updated_at']
        
        return cls(**data)