# game_data/core_game_data.py
"""
Core database management and base model classes for Pathfinder 2e game data.
Provides fundamental database operations and base classes for domain models.
"""

from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Type, TypeVar
from datetime import datetime
from contextlib import contextmanager
from abc import ABC, abstractmethod
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar('T', bound='BaseModel')


class BaseModel(ABC):
    """
    Abstract base class for all game data models.
    Provides interface for serialization and database operations.
    """
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize model to dictionary for storage."""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Deserialize model from dictionary."""
        pass
    
    @classmethod
    @abstractmethod
    def table_schema(cls) -> str:
        """Return SQL CREATE TABLE statement for this model."""
        pass
    
    @classmethod
    @abstractmethod
    def table_name(cls) -> str:
        """Return the database table name for this model."""
        pass


class DatabaseConnection:
    """
    Manages SQLite database connection with proper resource handling.
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize database connection manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Lazy connection initialization with row factory setup."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            logger.debug(f"Database connection established: {self.db_path}")
        return self._connection
    
    def close(self) -> None:
        """Close database connection if open."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug(f"Database connection closed: {self.db_path}")
    
    def __enter__(self) -> sqlite3.Connection:
        """Context manager entry."""
        return self.connection
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with automatic cleanup."""
        if exc_type:
            self.connection.rollback()
        else:
            self.connection.commit()


class GameDatabase:
    """
    Core database manager for game data persistence.
    Handles database initialization, schema management, and basic CRUD operations.
    """
    
    SCHEMA_VERSION = "1.0.0"
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize game database.
        
        Args:
            db_path: Path to database file. Defaults to save_files/sample_campaign.db
        """
        if db_path is None:
            db_path = Path("save_files/sample_campaign.db")
        
        self.db_path = Path(db_path)
        self._ensure_directory()
        self._db_connection = DatabaseConnection(self.db_path)
        self._initialize_metadata()
    
    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database directory ensured: {self.db_path.parent}")
    
    def _initialize_metadata(self) -> None:
        """Initialize database metadata table."""
        with self.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Store/update schema version
            conn.execute("""
                INSERT OR REPLACE INTO db_metadata (key, value, updated_at)
                VALUES ('schema_version', ?, CURRENT_TIMESTAMP)
            """, (self.SCHEMA_VERSION,))
            
            # Store database creation time if new
            conn.execute("""
                INSERT OR IGNORE INTO db_metadata (key, value)
                VALUES ('created_at', ?)
            """, (datetime.now().isoformat(),))
            
            logger.info(f"Database metadata initialized with schema v{self.SCHEMA_VERSION}")
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get active database connection."""
        return self._db_connection.connection
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.
        Automatically commits on success or rolls back on error.
        """
        conn = self.connection
        try:
            yield conn
            conn.commit()
            logger.debug("Transaction committed")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise
    
    def close(self) -> None:
        """Close database connection."""
        self._db_connection.close()
    
    # Schema Management
    
    def create_table(self, schema: str) -> None:
        """
        Create table from SQL schema.
        
        Args:
            schema: SQL CREATE TABLE statement
        """
        with self.transaction() as conn:
            conn.execute(schema)
            logger.info(f"Table created/verified from schema")
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists in database."""
        cursor = self.connection.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (table_name,))
        return cursor.fetchone() is not None
    
    def get_schema_version(self) -> str:
        """Get current database schema version."""
        cursor = self.connection.execute(
            "SELECT value FROM db_metadata WHERE key = 'schema_version'"
        )
        row = cursor.fetchone()
        return row['value'] if row else "0.0.0"
    
    # Basic CRUD Operations
    
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        Insert record into table.
        
        Args:
            table: Table name
            data: Column-value pairs
            
        Returns:
            ID of inserted row
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        with self.transaction() as conn:
            cursor = conn.execute(query, list(data.values()))
            row_id = cursor.lastrowid
            logger.debug(f"Inserted row {row_id} into {table}")
            return row_id
    
    def update(self, table: str, row_id: int, data: Dict[str, Any]) -> None:
        """
        Update record in table.
        
        Args:
            table: Table name
            row_id: ID of row to update
            data: Column-value pairs to update
        """
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE id = ?"
        
        with self.transaction() as conn:
            conn.execute(query, list(data.values()) + [row_id])
            logger.debug(f"Updated row {row_id} in {table}")
    
    def delete(self, table: str, row_id: int) -> bool:
        """
        Delete record from table.
        
        Args:
            table: Table name
            row_id: ID of row to delete
            
        Returns:
            True if row was deleted, False if not found
        """
        query = f"DELETE FROM {table} WHERE id = ?"
        
        with self.transaction() as conn:
            cursor = conn.execute(query, (row_id,))
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"Deleted row {row_id} from {table}")
            return deleted
    
    def get_by_id(self, table: str, row_id: int) -> Optional[Dict[str, Any]]:
        """
        Get single record by ID.
        
        Args:
            table: Table name
            row_id: ID of row to retrieve
            
        Returns:
            Row as dictionary or None if not found
        """
        query = f"SELECT * FROM {table} WHERE id = ?"
        cursor = self.connection.execute(query, (row_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def get_all(self, table: str, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all records from table.
        
        Args:
            table: Table name
            order_by: Optional ORDER BY clause
            
        Returns:
            List of rows as dictionaries
        """
        query = f"SELECT * FROM {table}"
        if order_by:
            query += f" ORDER BY {order_by}"
        
        cursor = self.connection.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    
    def find(self, table: str, conditions: Dict[str, Any], 
             order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find records matching conditions.
        
        Args:
            table: Table name
            conditions: Column-value pairs for WHERE clause
            order_by: Optional ORDER BY clause
            
        Returns:
            List of matching rows as dictionaries
        """
        where_clause = ' AND '.join([f"{k} = ?" for k in conditions.keys()])
        query = f"SELECT * FROM {table} WHERE {where_clause}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        cursor = self.connection.execute(query, list(conditions.values()))
        return [dict(row) for row in cursor.fetchall()]
    
    def find_one(self, table: str, conditions: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find single record matching conditions.
        
        Args:
            table: Table name  
            conditions: Column-value pairs for WHERE clause
            
        Returns:
            First matching row as dictionary or None
        """
        results = self.find(table, conditions)
        return results[0] if results else None
    
    def execute(self, query: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        """
        Execute arbitrary SQL query.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            Cursor with results
        """
        if params:
            return self.connection.execute(query, params)
        return self.connection.execute(query)
    
    def execute_script(self, script: str) -> None:
        """
        Execute SQL script (multiple statements).
        
        Args:
            script: SQL script with multiple statements
        """
        with self.transaction() as conn:
            conn.executescript(script)
            logger.info("Executed SQL script")
    
    # Utility Methods
    
    def backup(self, backup_path: Path) -> None:
        """
        Create backup of database.
        
        Args:
            backup_path: Path for backup file
        """
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(backup_path) as backup_conn:
            self.connection.backup(backup_conn)
        
        logger.info(f"Database backed up to {backup_path}")
    
    def vacuum(self) -> None:
        """Vacuum database to reclaim space."""
        self.connection.execute("VACUUM")
        logger.info("Database vacuumed")
    
    def get_table_info(self, table: str) -> List[Dict[str, Any]]:
        """Get column information for table."""
        cursor = self.connection.execute(f"PRAGMA table_info({table})")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in database."""
        cursor = self.connection.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        return [row['name'] for row in cursor.fetchall()]


# Utility Functions

def create_database(db_path: Path) -> GameDatabase:
    """
    Create new game database.
    
    Args:
        db_path: Path for new database file
        
    Returns:
        GameDatabase instance
    """
    db = GameDatabase(db_path)
    logger.info(f"Created new database at {db_path}")
    return db


def load_database(db_path: Path) -> Optional[GameDatabase]:
    """
    Load existing game database.
    
    Args:
        db_path: Path to existing database file
        
    Returns:
        GameDatabase instance or None if file doesn't exist
    """
    if not db_path.exists():
        logger.warning(f"Database file not found: {db_path}")
        return None
    
    db = GameDatabase(db_path)
    logger.info(f"Loaded database from {db_path}")
    return db


def json_serialize(data: Any) -> str:
    """
    Serialize data to JSON string, handling datetime objects.
    
    Args:
        data: Data to serialize
        
    Returns:
        JSON string
    """
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
    
    return json.dumps(data, default=default)


def json_deserialize(json_str: str) -> Any:
    """
    Deserialize JSON string, handling datetime strings.
    
    Args:
        json_str: JSON string to deserialize
        
    Returns:
        Deserialized data
    """
    return json.loads(json_str)