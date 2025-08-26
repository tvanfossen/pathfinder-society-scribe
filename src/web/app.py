# src/web/app.py
"""
Minimal FastAPI application for PF2e Society Scribe.
This is a placeholder to get the container running.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pathlib import Path
import os

# Create the FastAPI application
app = FastAPI(
    title="PF2e Society Scribe",
    description="AI-powered Pathfinder 2e campaign assistant",
    version="0.1.0"
)

@app.get("/")
async def root():
    """Root endpoint - basic status check."""
    return {
        "status": "running",
        "application": "PF2e Society Scribe",
        "campaign": os.environ.get("CAMPAIGN_NAME", "unknown"),
        "model": os.environ.get("MODEL_FILE", "not specified")
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    campaign_path = Path(os.environ.get("CAMPAIGN_DATA_PATH", "/campaign-data"))
    model_path = Path(os.environ.get("MODEL_PATH", "/models"))
    
    return {
        "status": "healthy",
        "paths": {
            "campaign_data": str(campaign_path),
            "campaign_exists": campaign_path.exists(),
            "models": str(model_path),
            "models_exists": model_path.exists()
        }
    }

@app.get("/api/test")
async def test_endpoint():
    """Test API endpoint."""
    return {"message": "API is working", "timestamp": "2024-01-01T00:00:00Z"}

# Add CORS middleware for development
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)