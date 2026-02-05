"""Input models for route planning requests."""

from enum import Enum
from pydantic import BaseModel, Field


class SurfaceType(str, Enum):
    """Types of road/path surfaces."""
    PAVED = "paved"
    GRAVEL = "gravel"
    TRAIL = "trail"
    DIRT = "dirt"
    SAND = "sand"
    ANY = "any"


class RouteRequest(BaseModel):
    """Request model for planning a bike packing route."""
    
    start_point: tuple[float, float] = Field(
        ...,
        description="Starting point as (latitude, longitude)"
    )
    end_point: tuple[float, float] = Field(
        ...,
        description="End point as (latitude, longitude)"
    )
    surface_preferences: list[SurfaceType] = Field(
        default=[SurfaceType.GRAVEL, SurfaceType.PAVED],
        description="Preferred road surface types, in order of preference"
    )
    daily_distance_km: float = Field(
        default=80.0,
        ge=20.0,
        le=200.0,
        description="Target daily travel distance in kilometers"
    )
    trip_days: int | None = Field(
        default=None,
        ge=1,
        le=30,
        description="Optional: fixed number of days for the trip"
    )
    avoid: list[str] = Field(
        default_factory=list,
        description="Features to avoid (e.g., 'highways', 'ferries', 'tunnels')"
    )
    max_elevation_gain_per_day: float | None = Field(
        default=None,
        ge=0,
        description="Maximum elevation gain per day in meters"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_point": (48.1351, 11.5820),  # Munich
                "end_point": (48.2082, 16.3738),    # Vienna
                "surface_preferences": ["gravel", "paved"],
                "daily_distance_km": 80.0,
                "trip_days": None,
                "avoid": ["highways"],
                "max_elevation_gain_per_day": 1000.0
            }
        }
