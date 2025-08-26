# conftest.py
"""
Pytest configuration for Docker-based testing.
"""

import os
import sys
from pathlib import Path
import pytest

# Add src to Python path
sys.path.insert(0, '/app')

# Configuration - Use consistent /app/campaign-data path
CAMPAIGN_DATA_PATH = Path(os.environ.get("CAMPAIGN_DATA_PATH", "/app/campaign-data"))
MODEL_PATH = Path(os.environ.get("MODEL_PATH", "/app/models"))
MODEL_FILE = os.environ.get("MODEL_FILE", "")

# Ensure directories exist
CAMPAIGN_DATA_PATH.mkdir(parents=True, exist_ok=True)
MODEL_PATH.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def campaign_data_dir():
    """Get campaign data directory."""
    return CAMPAIGN_DATA_PATH


@pytest.fixture
def models_dir():
    """Get models directory."""
    return MODEL_PATH


@pytest.fixture
def tutorial_dir():
    """Get tutorial directory."""
    tutorial = CAMPAIGN_DATA_PATH / "tutorial"
    tutorial.mkdir(parents=True, exist_ok=True)
    return tutorial


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment."""
    print(f"\n🔧 Test Environment:")
    print(f"   Campaign data: {CAMPAIGN_DATA_PATH}")
    print(f"   Models: {MODEL_PATH}")
    print(f"   Model file: {MODEL_FILE or 'Not specified'}")
    
    # Create test directories
    test_dirs = [
        CAMPAIGN_DATA_PATH / "test",
        CAMPAIGN_DATA_PATH / "tutorial",
        CAMPAIGN_DATA_PATH / "tutorial" / "characters",
        CAMPAIGN_DATA_PATH / "tutorial" / "campaigns",
    ]
    
    for dir_path in test_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    print("   ✓ Test directories created")


@pytest.fixture
def mock_model_file(models_dir):
    """Create a mock model file if needed."""
    if MODEL_FILE:
        model_path = models_dir / MODEL_FILE
        if model_path.exists():
            return model_path
    
    # Create a minimal mock file for testing
    mock_model = models_dir / "test_model.gguf"
    if not mock_model.exists():
        mock_model.write_bytes(b"GGUF" + b"\x00" * 100)
    return mock_model


# Mark tests that require GPU
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "gpu: mark test as requiring GPU"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )