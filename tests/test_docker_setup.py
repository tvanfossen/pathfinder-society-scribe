"""
Basic tests to verify Docker environment is set up correctly.
"""

import os
import sys
from pathlib import Path
import pytest



class TestDockerEnvironment:
    """Test that the Docker container environment is properly configured."""
    
    def test_python_version(self):
        """Verify Python version is 3.10 or higher."""
        version_info = sys.version_info
        assert version_info.major == 3
        assert version_info.minor >= 10
        print(f"Python version: {sys.version}")
    
    def test_pythonpath_set(self):
        """Verify PYTHONPATH is set correctly."""
        pythonpath = os.environ.get('PYTHONPATH')
        assert pythonpath == '/app'
        print(f"PYTHONPATH: {pythonpath}")
    
    def test_app_directories_exist(self):
        """Verify required directories exist."""
        required_dirs = [
            Path('/app'),
            Path('/app/src'),
            Path('/app/tests'),
            Path('/app/campaign-data'),
            Path('/app/data'),
            Path('/app/models'),
        ]
        
        for dir_path in required_dirs:
            assert dir_path.exists(), f"Directory {dir_path} does not exist"
            print(f"✓ Directory exists: {dir_path}")
    
    def test_environment_variables(self):
        """Verify expected environment variables are set."""
        expected_vars = {
            'CAMPAIGN_DATA_PATH': '/app/campaign-data',
            'MODEL_PATH': '/app/models',
            'PF2E_DB_PATH': '/app/data/pf2e.db',
            'PORT': '8000'
        }
        
        for var, expected_value in expected_vars.items():
            actual_value = os.environ.get(var)
            assert actual_value == expected_value, \
                f"{var} = {actual_value}, expected {expected_value}"
            print(f"✓ {var} = {actual_value}")
    
    def test_write_permissions(self):
        """Verify write permissions in campaign-data directory."""
        test_file = Path('/app/campaign-data/test_write.tmp')
        try:
            test_file.write_text('test')
            assert test_file.exists()
            assert test_file.read_text() == 'test'
            test_file.unlink()
            print("✓ Write permissions verified")
        except Exception as e:
            pytest.fail(f"Cannot write to campaign-data: {e}")


class TestPythonDependencies:
    """Test that required Python packages are installed."""
    
    def test_core_packages(self):
        """Verify core packages are importable."""
        packages = [
            'starlette',
            'uvicorn',
            'pydantic',
            'sqlalchemy',
            'aiosqlite',
            'jinja2',
        ]
        
        for package in packages:
            try:
                __import__(package)
                print(f"✓ Package installed: {package}")
            except ImportError:
                pytest.fail(f"Package not installed: {package}")
    
    def test_llama_cpp_python(self):
        """Verify llama-cpp-python is installed."""
        try:
            import llama_cpp
            print(f"✓ llama-cpp-python version: {llama_cpp.__version__}")
        except ImportError:
            pytest.fail("llama-cpp-python not installed")
    
    def test_pytest_plugins(self):
        """Verify pytest plugins are available."""
        import pytest_asyncio
        import pytest_cov
        import pytest_mock
        
        print("✓ pytest plugins installed")


class TestProjectStructure:
    """Test that the project structure is correct."""
    
    def test_source_structure(self):
        """Verify source code structure (will be expanded in Phase 2)."""
        src_path = Path('/app/src')
        
        if src_path.exists():
            # For now, just verify src directory exists
            # Will add more specific checks as we build out the structure
            assert src_path.is_dir()
            print(f"✓ Source directory exists: {src_path}")
    
    def test_campaign_helpers_migration(self):
        """Placeholder for verifying campaign_helpers.py migration."""
        # This will be implemented in Phase 2
        # For now, just pass
        pass


@pytest.fixture
def sample_campaign_data():
    """Fixture for creating sample campaign data."""
    return {
        'name': 'Test Campaign',
        'dm_name': 'Test DM',
        'starting_level': 1
    }


def test_fixture_works(sample_campaign_data):
    """Verify pytest fixtures work correctly."""
    assert sample_campaign_data['name'] == 'Test Campaign'
    print("✓ Pytest fixtures working")


if __name__ == "__main__":
    """Allow running tests directly for debugging."""
    pytest.main([__file__, '-v'])