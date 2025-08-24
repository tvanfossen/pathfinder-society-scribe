# src/managers/campaign_manager.py
"""Campaign data management with persistence."""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..models.campaign import Campaign, CampaignSession


logger = logging.getLogger(__name__)


class CampaignManager:
    """Manages campaign data persistence and operations."""
    
    def __init__(self, data_directory: Path = None):
        """Initialize campaign manager.
        
        Args:
            data_directory: Directory for campaign data storage
        """
        self.data_dir = data_directory or Path("campaign-data/campaigns")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Campaign] = {}
    
    def _get_filename(self, campaign_name: str) -> Path:
        """Generate filename for campaign."""
        safe_name = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in campaign_name.lower()
        )
        return self.data_dir / f"{safe_name}.json"
    
    def save(self, campaign: Campaign) -> bool:
        """Save campaign to disk.
        
        Args:
            campaign: Campaign to save
            
        Returns:
            True if successful
        """
        try:
            filepath = self._get_filename(campaign.name)
            campaign.touch()  # Update timestamp
            
            with filepath.open('w', encoding='utf-8') as f:
                json.dump(
                    campaign.to_dict(),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str  # Handle any remaining date/datetime objects
                )
            
            # Update cache
            self._cache[campaign.name] = campaign
            
            logger.info(f"Saved campaign '{campaign.name}' to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save campaign '{campaign.name}': {e}")
            return False
    
    def load(self, campaign_name: str) -> Optional[Campaign]:
        """Load campaign from disk.
        
        Args:
            campaign_name: Name of campaign to load
            
        Returns:
            Campaign if found, None otherwise
        """
        # Check cache first
        if campaign_name in self._cache:
            return self._cache[campaign_name]
        
        try:
            filepath = self._get_filename(campaign_name)
            
            if not filepath.exists():
                logger.warning(f"Campaign file not found: {filepath}")
                return None
            
            with filepath.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            campaign = Campaign.from_dict(data)
            
            # Update cache
            self._cache[campaign_name] = campaign
            
            logger.info(f"Loaded campaign '{campaign_name}' from {filepath}")
            return campaign
            
        except Exception as e:
            logger.error(f"Failed to load campaign '{campaign_name}': {e}")
            return None
    
    def delete(self, campaign_name: str) -> bool:
        """Delete campaign file.
        
        Args:
            campaign_name: Name of campaign to delete
            
        Returns:
            True if successful
        """
        try:
            filepath = self._get_filename(campaign_name)
            
            if filepath.exists():
                filepath.unlink()
                
                # Remove from cache
                self._cache.pop(campaign_name, None)
                
                logger.info(f"Deleted campaign '{campaign_name}'")
                return True
            
            logger.warning(f"Campaign '{campaign_name}' not found")
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete campaign '{campaign_name}': {e}")
            return False
    
    def list_campaigns(self, active_only: bool = False) -> List[str]:
        """List all available campaigns.
        
        Args:
            active_only: Only return active campaigns
            
        Returns:
            List of campaign names
        """
        campaigns = []
        
        for filepath in self.data_dir.glob("*.json"):
            try:
                with filepath.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if active_only and not data.get('is_active', True):
                        continue
                    
                    if 'name' in data:
                        campaigns.append(data['name'])
                        
            except Exception as e:
                logger.warning(f"Failed to read {filepath}: {e}")
                continue
        
        return sorted(campaigns)
    
    def exists(self, campaign_name: str) -> bool:
        """Check if campaign exists.
        
        Args:
            campaign_name: Name of campaign
            
        Returns:
            True if campaign exists
        """
        filepath = self._get_filename(campaign_name)
        return filepath.exists()
    
    def create_campaign(
        self,
        name: str,
        dm_name: str = "",
        **kwargs
    ) -> Campaign:
        """Create a new campaign.
        
        Args:
            name: Campaign name
            dm_name: Game master name
            **kwargs: Additional campaign attributes
            
        Returns:
            New campaign instance
        """
        campaign = Campaign(
            name=name,
            dm_name=dm_name,
            **kwargs
        )
        
        return campaign
    
    def add_session(
        self,
        campaign_name: str,
        session: CampaignSession
    ) -> bool:
        """Add a session to a campaign.
        
        Args:
            campaign_name: Name of campaign
            session: Session to add
            
        Returns:
            True if successful
        """
        campaign = self.load(campaign_name)
        if not campaign:
            logger.error(f"Campaign '{campaign_name}' not found")
            return False
        
        campaign.add_session(session)
        return self.save(campaign)
    
    def create_session(
        self,
        campaign_name: str,
        session_date: date = None,
        **kwargs
    ) -> Optional[CampaignSession]:
        """Create a new session for a campaign.
        
        Args:
            campaign_name: Name of campaign
            session_date: Date of session (defaults to today)
            **kwargs: Additional session attributes
            
        Returns:
            New session if successful
        """
        campaign = self.load(campaign_name)
        if not campaign:
            return None
        
        session_number = campaign.current_session_number + 1
        
        session = CampaignSession(
            session_number=session_number,
            session_date=session_date or date.today(),
            **kwargs
        )
        
        if self.add_session(campaign_name, session):
            return session
        
        return None
    
    def get_latest_session(
        self,
        campaign_name: str
    ) -> Optional[CampaignSession]:
        """Get the most recent session for a campaign.
        
        Args:
            campaign_name: Name of campaign
            
        Returns:
            Latest session if found
        """
        campaign = self.load(campaign_name)
        if not campaign:
            return None
        
        return campaign.last_session
    
    def get_campaign_summary(
        self,
        campaign_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get a summary of campaign information.
        
        Args:
            campaign_name: Name of campaign
            
        Returns:
            Summary dict if campaign exists
        """
        campaign = self.load(campaign_name)
        if not campaign:
            return None
        
        attendance = campaign.get_attendance_report()
        treasure = campaign.get_treasure_summary()
        
        return {
            'name': campaign.name,
            'dm': campaign.dm_name,
            'status': {
                'active': campaign.is_active,
                'on_hiatus': campaign.on_hiatus,
                'completed': campaign.completed
            },
            'progress': {
                'current_level': campaign.current_level,
                'total_sessions': campaign.total_sessions,
                'total_hours': campaign.total_playtime_hours,
                'current_chapter': campaign.current_chapter
            },
            'players': list(campaign.players.keys()),
            'attendance': attendance,
            'treasure': {
                'total_gold_gp': treasure['total_gold_gp'],
                'unique_items': len(treasure['unique_items'])
            },
            'next_session': campaign.next_session_date.isoformat() if campaign.next_session_date else None,
            'last_updated': campaign.updated_at.isoformat()
        }
    
    def archive_campaign(self, campaign_name: str) -> bool:
        """Archive a completed campaign.
        
        Args:
            campaign_name: Name of campaign to archive
            
        Returns:
            True if successful
        """
        campaign = self.load(campaign_name)
        if not campaign:
            return False
        
        # Create archive directory
        archive_dir = self.data_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        # Move file to archive
        source = self._get_filename(campaign_name)
        if source.exists():
            dest = archive_dir / source.name
            source.rename(dest)
            
            # Update campaign status
            campaign.complete_campaign()
            
            # Save to archive location
            with dest.open('w', encoding='utf-8') as f:
                json.dump(
                    campaign.to_dict(),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str
                )
            
            # Remove from cache
            self._cache.pop(campaign_name, None)
            
            logger.info(f"Archived campaign '{campaign_name}'")
            return True
        
        return False
    
    def export_campaign(
        self,
        campaign_name: str,
        output_path: Path,
        include_sessions: bool = True
    ) -> bool:
        """Export campaign to file.
        
        Args:
            campaign_name: Name of campaign
            output_path: Path for export file
            include_sessions: Whether to include session data
            
        Returns:
            True if successful
        """
        campaign = self.load(campaign_name)
        if not campaign:
            return False
        
        try:
            data = campaign.to_dict()
            
            if not include_sessions:
                data['sessions'] = []
            
            with output_path.open('w', encoding='utf-8') as f:
                json.dump(
                    data,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str
                )
            
            logger.info(f"Exported '{campaign_name}' to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export campaign: {e}")
            return False
    
    def import_campaign(
        self,
        import_path: Path,
        overwrite: bool = False
    ) -> Optional[Campaign]:
        """Import campaign from file.
        
        Args:
            import_path: Path to import file
            overwrite: Whether to overwrite existing campaign
            
        Returns:
            Imported campaign if successful
        """
        try:
            with import_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            campaign = Campaign.from_dict(data)
            
            # Check if exists
            if self.exists(campaign.name) and not overwrite:
                logger.warning(f"Campaign '{campaign.name}' already exists")
                return None
            
            # Save imported campaign
            if self.save(campaign):
                logger.info(f"Imported campaign '{campaign.name}'")
                return campaign
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to import campaign: {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear the campaign cache."""
        self._cache.clear()
        logger.debug("Cleared campaign cache")