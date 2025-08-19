# tests/test_core_game_data.py
"""
Comprehensive test suite for core_game_data module.
Tests database operations, base model functionality, and utility functions.
"""

import pytest
import sqlite3
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from game_data.core_game_data import (
    BaseModel,
    DatabaseConnection,
    GameDatabase,
    create_database,
    load_database,
    json_serialize,
    json_deserialize
)


# Test Fixtures

@pytest.fixture
def temp_dir():
    """Create temporary directory for test databases."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def db_path(temp_dir):
    """Create path for test database."""
    return temp_dir / "test_game.db"


@pytest.fixture
def game_db(db_path):
    """Create GameDatabase instance for testing."""
    db = GameDatabase(db_path)
    yield db
    db.close()


@pytest.fixture
def sample_table_schema():
    """SQL schema for test table."""
    return """
        CREATE TABLE IF NOT EXISTS test_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value INTEGER DEFAULT 0,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """


# Sample Model Implementation for Testing

class TestItem(BaseModel):
    """Test implementation of BaseModel."""
    
    def __init__(self, name: str, value: int = 0, description: str = ""):
        self.name = name
        self.value = value
        self.description = description
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'value': self.value,
            'description': self.description,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestItem':
        item = cls(
            name=data['name'],
            value=data.get('value', 0),
            description=data.get('description', '')
        )
        if 'created_at' in data:
            if isinstance(data['created_at'], str):
                item.created_at = datetime.fromisoformat(data['created_at'])
            elif isinstance(data['created_at'], datetime):
                item.created_at = data['created_at']
        return item
    
    @classmethod
    def table_schema(cls) -> str:
        return """
            CREATE TABLE IF NOT EXISTS test_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value INTEGER DEFAULT 0,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    
    @classmethod
    def table_name(cls) -> str:
        return "test_items"


# DatabaseConnection Tests

class TestDatabaseConnection:
    """Test DatabaseConnection class."""
    
    def test_connection_creation(self, db_path):
        """Test database connection creation."""
        conn_manager = DatabaseConnection(db_path)
        conn = conn_manager.connection
        
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        
        # Test connection is reused
        conn2 = conn_manager.connection
        assert conn is conn2
        
        conn_manager.close()
    
    def test_connection_close(self, db_path):
        """Test connection closing."""
        conn_manager = DatabaseConnection(db_path)
        conn = conn_manager.connection
        conn_manager.close()
        
        # Connection should be reset
        assert conn_manager._connection is None
    
    def test_context_manager(self, db_path):
        """Test connection as context manager."""
        conn_manager = DatabaseConnection(db_path)
        
        with conn_manager as conn:
            assert isinstance(conn, sqlite3.Connection)
            conn.execute("CREATE TABLE test (id INTEGER)")
        
        # Table should exist after commit
        cursor = conn_manager.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
        )
        assert cursor.fetchone() is not None
        
        conn_manager.close()
    
    def test_context_manager_rollback(self, db_path):
        """Test rollback on exception."""
        conn_manager = DatabaseConnection(db_path)
        
        # First verify the context manager properly handles exceptions
        with pytest.raises(ValueError):
            with conn_manager as conn:
                conn.execute("CREATE TABLE test (id INTEGER)")
                raise ValueError("Test exception")
        
        # For now, SQLite doesn't rollback DDL statements (CREATE TABLE)
        # So let's test with DML (INSERT) instead
        conn_manager.connection.execute("CREATE TABLE test_data (id INTEGER, value TEXT)")
        
        # This should rollback
        with pytest.raises(ValueError):
            with conn_manager as conn:
                conn.execute("INSERT INTO test_data (id, value) VALUES (1, 'test')")
                raise ValueError("Test exception")
        
        # Verify the insert was rolled back
        cursor = conn_manager.connection.execute("SELECT * FROM test_data")
        assert cursor.fetchone() is None
        
        conn_manager.close()


# GameDatabase Tests

class TestGameDatabase:
    """Test GameDatabase class."""
    
    def test_initialization(self, game_db):
        """Test database initialization."""
        assert game_db.db_path.exists()
        assert game_db.table_exists('db_metadata')
        
        # Check schema version
        version = game_db.get_schema_version()
        assert version == GameDatabase.SCHEMA_VERSION
    
    def test_directory_creation(self, temp_dir):
        """Test automatic directory creation."""
        nested_path = temp_dir / "nested" / "dir" / "game.db"
        db = GameDatabase(nested_path)
        
        assert nested_path.parent.exists()
        assert nested_path.exists()
        
        db.close()
    
    def test_create_table(self, game_db, sample_table_schema):
        """Test table creation."""
        game_db.create_table(sample_table_schema)
        assert game_db.table_exists('test_items')
        
        # Test table info
        info = game_db.get_table_info('test_items')
        assert len(info) == 5  # 5 columns
        column_names = [col['name'] for col in info]
        assert 'id' in column_names
        assert 'name' in column_names
    
    def test_insert(self, game_db, sample_table_schema):
        """Test record insertion."""
        game_db.create_table(sample_table_schema)
        
        data = {
            'name': 'Test Item',
            'value': 42,
            'description': 'A test item'
        }
        
        row_id = game_db.insert('test_items', data)
        assert row_id > 0
        
        # Verify insertion
        result = game_db.get_by_id('test_items', row_id)
        assert result is not None
        assert result['name'] == 'Test Item'
        assert result['value'] == 42
    
    def test_update(self, game_db, sample_table_schema):
        """Test record update."""
        game_db.create_table(sample_table_schema)
        
        # Insert initial record
        row_id = game_db.insert('test_items', {'name': 'Original', 'value': 1})
        
        # Update record
        game_db.update('test_items', row_id, {'name': 'Updated', 'value': 2})
        
        # Verify update
        result = game_db.get_by_id('test_items', row_id)
        assert result['name'] == 'Updated'
        assert result['value'] == 2
    
    def test_delete(self, game_db, sample_table_schema):
        """Test record deletion."""
        game_db.create_table(sample_table_schema)
        
        # Insert record
        row_id = game_db.insert('test_items', {'name': 'To Delete'})
        
        # Verify exists
        assert game_db.get_by_id('test_items', row_id) is not None
        
        # Delete record
        deleted = game_db.delete('test_items', row_id)
        assert deleted is True
        
        # Verify deleted
        assert game_db.get_by_id('test_items', row_id) is None
        
        # Test deleting non-existent record
        deleted = game_db.delete('test_items', 9999)
        assert deleted is False
    
    def test_get_all(self, game_db, sample_table_schema):
        """Test getting all records."""
        game_db.create_table(sample_table_schema)
        
        # Insert multiple records
        for i in range(5):
            game_db.insert('test_items', {'name': f'Item {i}', 'value': i})
        
        # Get all records
        results = game_db.get_all('test_items')
        assert len(results) == 5
        
        # Test with ordering
        results = game_db.get_all('test_items', order_by='value DESC')
        assert results[0]['value'] == 4
        assert results[-1]['value'] == 0
    
    def test_find(self, game_db, sample_table_schema):
        """Test finding records with conditions."""
        game_db.create_table(sample_table_schema)
        
        # Insert test data
        game_db.insert('test_items', {'name': 'Sword', 'value': 100})
        game_db.insert('test_items', {'name': 'Shield', 'value': 50})
        game_db.insert('test_items', {'name': 'Potion', 'value': 50})
        
        # Find by single condition
        results = game_db.find('test_items', {'value': 50})
        assert len(results) == 2
        
        # Find by multiple conditions
        results = game_db.find('test_items', {'name': 'Shield', 'value': 50})
        assert len(results) == 1
        assert results[0]['name'] == 'Shield'
    
    def test_find_one(self, game_db, sample_table_schema):
        """Test finding single record."""
        game_db.create_table(sample_table_schema)
        
        game_db.insert('test_items', {'name': 'Unique', 'value': 999})
        game_db.insert('test_items', {'name': 'Common', 'value': 1})
        
        # Find existing record
        result = game_db.find_one('test_items', {'value': 999})
        assert result is not None
        assert result['name'] == 'Unique'
        
        # Find non-existent record
        result = game_db.find_one('test_items', {'value': 777})
        assert result is None
    
    def test_execute(self, game_db):
        """Test arbitrary SQL execution."""
        # Create table with custom query
        game_db.execute("""
            CREATE TABLE custom_table (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        """)
        
        assert game_db.table_exists('custom_table')
        
        # Insert with parameters
        cursor = game_db.execute(
            "INSERT INTO custom_table (data) VALUES (?)",
            ("test data",)
        )
        assert cursor.lastrowid > 0
    
    def test_execute_script(self, game_db):
        """Test SQL script execution."""
        script = """
            CREATE TABLE table1 (id INTEGER PRIMARY KEY);
            CREATE TABLE table2 (id INTEGER PRIMARY KEY);
            INSERT INTO table1 (id) VALUES (1), (2), (3);
        """
        
        game_db.execute_script(script)
        
        assert game_db.table_exists('table1')
        assert game_db.table_exists('table2')
        
        results = game_db.get_all('table1')
        assert len(results) == 3
    
    def test_transaction(self, game_db, sample_table_schema):
        """Test transaction context manager."""
        game_db.create_table(sample_table_schema)
        
        # Successful transaction
        with game_db.transaction() as conn:
            conn.execute(
                "INSERT INTO test_items (name, value) VALUES (?, ?)",
                ("Transaction Item", 123)
            )
        
        results = game_db.find('test_items', {'name': 'Transaction Item'})
        assert len(results) == 1
        
        # Failed transaction (should rollback)
        try:
            with game_db.transaction() as conn:
                conn.execute(
                    "INSERT INTO test_items (name, value) VALUES (?, ?)",
                    ("Rollback Item", 456)
                )
                raise ValueError("Force rollback")
        except ValueError:
            pass
        
        results = game_db.find('test_items', {'name': 'Rollback Item'})
        assert len(results) == 0
    
    def test_backup(self, game_db, temp_dir, sample_table_schema):
        """Test database backup."""
        game_db.create_table(sample_table_schema)
        game_db.insert('test_items', {'name': 'Backup Test'})
        
        backup_path = temp_dir / "backup.db"
        game_db.backup(backup_path)
        
        assert backup_path.exists()
        
        # Verify backup contains data
        backup_db = GameDatabase(backup_path)
        assert backup_db.table_exists('test_items')
        results = backup_db.get_all('test_items')
        assert len(results) == 1
        assert results[0]['name'] == 'Backup Test'
        
        backup_db.close()
    
    def test_vacuum(self, game_db, sample_table_schema):
        """Test database vacuum."""
        game_db.create_table(sample_table_schema)
        
        # Insert and delete many records
        for i in range(100):
            game_db.insert('test_items', {'name': f'Item {i}'})
        
        for i in range(1, 51):  # Delete half
            game_db.delete('test_items', i)
        
        # Vacuum should not raise errors
        game_db.vacuum()
        
        # Data should still be intact
        results = game_db.get_all('test_items')
        assert len(results) == 50
    
    def test_get_tables(self, game_db):
        """Test getting list of tables."""
        # Initially only metadata table
        tables = game_db.get_tables()
        assert 'db_metadata' in tables
        
        # Create additional tables
        game_db.create_table("CREATE TABLE table_a (id INTEGER)")
        game_db.create_table("CREATE TABLE table_b (id INTEGER)")
        
        tables = game_db.get_tables()
        assert 'table_a' in tables
        assert 'table_b' in tables
        assert 'db_metadata' in tables


# Utility Function Tests

class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_database(self, temp_dir):
        """Test database creation."""
        db_path = temp_dir / "new_game.db"
        db = create_database(db_path)
        
        assert db is not None
        assert db_path.exists()
        assert db.table_exists('db_metadata')
        
        db.close()
    
    def test_load_database(self, temp_dir):
        """Test database loading."""
        db_path = temp_dir / "existing.db"
        
        # Create database first
        db1 = create_database(db_path)
        db1.close()
        
        # Load existing database
        db2 = load_database(db_path)
        assert db2 is not None
        assert db2.table_exists('db_metadata')
        
        db2.close()
        
        # Test loading non-existent database
        fake_path = temp_dir / "nonexistent.db"
        db3 = load_database(fake_path)
        assert db3 is None
    
    def test_json_serialize(self):
        """Test JSON serialization with datetime."""
        data = {
            'name': 'Test',
            'created': datetime(2024, 1, 1, 12, 0, 0),
            'values': [1, 2, 3],
            'nested': {'key': 'value'}
        }
        
        json_str = json_serialize(data)
        assert isinstance(json_str, str)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed['name'] == 'Test'
        assert '2024-01-01' in parsed['created']
    
    def test_json_deserialize(self):
        """Test JSON deserialization."""
        json_str = '{"name": "Test", "value": 42, "items": [1, 2, 3]}'
        
        data = json_deserialize(json_str)
        assert data['name'] == 'Test'
        assert data['value'] == 42
        assert len(data['items']) == 3


# BaseModel Tests

class TestBaseModel:
    """Test BaseModel implementation."""
    
    def test_model_implementation(self):
        """Test model serialization and deserialization."""
        # Create test item
        item = TestItem(name="Sword", value=100, description="A sharp blade")
        
        # Test to_dict
        data = item.to_dict()
        assert data['name'] == "Sword"
        assert data['value'] == 100
        assert 'created_at' in data
        
        # Test from_dict
        item2 = TestItem.from_dict(data)
        assert item2.name == item.name
        assert item2.value == item.value
        assert item2.description == item.description
    
    def test_model_with_database(self, game_db):
        """Test model integration with database."""
        # Create table from model schema
        game_db.create_table(TestItem.table_schema())
        assert game_db.table_exists(TestItem.table_name())
        
        # Create and store model
        item = TestItem(name="Potion", value=50, description="Heals 50 HP")
        
        # Store only the data fields, let database handle created_at
        insert_data = {
            'name': item.name,
            'value': item.value,
            'description': item.description
        }
        
        row_id = game_db.insert(TestItem.table_name(), insert_data)
        
        # Retrieve and reconstruct model
        stored_data = game_db.get_by_id(TestItem.table_name(), row_id)
        
        # Handle created_at field - it comes from database as a datetime or string
        if 'created_at' in stored_data:
            if isinstance(stored_data['created_at'], datetime):
                stored_data['created_at'] = stored_data['created_at'].isoformat()
            elif stored_data['created_at'] is None:
                stored_data['created_at'] = datetime.now().isoformat()
        else:
            stored_data['created_at'] = datetime.now().isoformat()
        
        retrieved_item = TestItem.from_dict(stored_data)
        
        assert retrieved_item.name == "Potion"
        assert retrieved_item.value == 50
        assert retrieved_item.description == "Heals 50 HP"


# Integration Tests

@pytest.mark.integration
class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_workflow(self, temp_dir):
        """Test complete database workflow."""
        # Create database
        db_path = temp_dir / "game.db"
        db = create_database(db_path)
        
        # Create tables
        db.create_table("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                class TEXT
            )
        """)
        
        db.create_table("""
            CREATE TABLE inventory (
                id INTEGER PRIMARY KEY,
                character_id INTEGER,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (character_id) REFERENCES characters(id)
            )
        """)
        
        # Insert character
        char_id = db.insert('characters', {
            'name': 'Aragorn',
            'level': 10,
            'class': 'Ranger'
        })
        
        # Insert inventory items
        db.insert('inventory', {
            'character_id': char_id,
            'item_name': 'Andúril',
            'quantity': 1
        })
        
        db.insert('inventory', {
            'character_id': char_id,
            'item_name': 'Elven Cloak',
            'quantity': 1
        })
        
        # Query data
        character = db.get_by_id('characters', char_id)
        assert character['name'] == 'Aragorn'
        
        items = db.find('inventory', {'character_id': char_id})
        assert len(items) == 2
        
        # Update character level
        db.update('characters', char_id, {'level': 11})
        
        # Verify update
        character = db.get_by_id('characters', char_id)
        assert character['level'] == 11
        
        # Clean up
        db.close()
        
        # Reload and verify persistence
        db2 = load_database(db_path)
        character = db2.get_by_id('characters', char_id)
        assert character['name'] == 'Aragorn'
        assert character['level'] == 11
        
        db2.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])