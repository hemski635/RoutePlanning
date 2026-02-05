"""Configuration management."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Settings(BaseModel):
    """Application settings."""
    
    # AI Model settings
    github_token: str | None = Field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN")
    )
    model_id: str = Field(
        default_factory=lambda: os.getenv("MODEL_ID", "openai/gpt-4.1")
    )
    
    # API Keys (optional - BRouter is self-hosted, ORS is fallback)
    openrouteservice_api_key: str | None = Field(
        default_factory=lambda: os.getenv("OPENROUTESERVICE_API_KEY")
    )
    brouter_url: str = Field(
        default_factory=lambda: os.getenv("BROUTER_URL", "http://localhost:17777")
    )
    
    # Default route planning settings
    default_daily_distance_km: float = 80.0
    default_surface_preferences: list[str] = ["gravel", "paved"]
    
    # Output settings
    output_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "output"
    )
    
    def validate_required(self) -> list[str]:
        """Check for missing required configuration."""
        missing = []
        
        if not self.github_token:
            missing.append("GITHUB_TOKEN")
        
        # BRouter is primary, ORS is optional fallback - no API key required
        
        return missing


# Global settings instance
settings = Settings()
