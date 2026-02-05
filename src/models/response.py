"""Output models for route planning responses."""

from enum import Enum
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """GPS coordinates."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    
    def as_tuple(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)
    
    @classmethod
    def from_tuple(cls, coords: tuple[float, float]) -> "Coordinates":
        return cls(latitude=coords[0], longitude=coords[1])


class CampingType(str, Enum):
    """Types of camping accommodations."""
    CAMPGROUND = "campground"
    WILD_CAMPING = "wild_camping"
    SHELTER = "shelter"
    BIVOUAC = "bivouac"
    HOSTEL = "hostel"


class CampingSite(BaseModel):
    """A camping or overnight accommodation option."""
    
    coords: Coordinates
    name: str
    type: CampingType
    amenities: list[str] = Field(default_factory=list)
    rating: float | None = Field(default=None, ge=0, le=5)
    distance_from_route_m: float = Field(
        default=0,
        description="Distance from main route in meters"
    )
    booking_url: str | None = None
    notes: str | None = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "coords": {"latitude": 48.0598, "longitude": 12.2287},
                "name": "Campingplatz Wasserburg",
                "type": "campground",
                "amenities": ["showers", "wifi", "shop"],
                "rating": 4.2,
                "distance_from_route_m": 150,
                "booking_url": "https://example.com/book",
                "notes": "Quiet site by the river"
            }
        }


class POICategory(str, Enum):
    """Categories for points of interest."""
    VIEWPOINT = "viewpoint"
    WATER_SOURCE = "water_source"
    FOOD = "food"
    REST_AREA = "rest_area"
    HISTORIC = "historic"
    NATURE = "nature"
    BIKE_SHOP = "bike_shop"
    SUPERMARKET = "supermarket"


class POI(BaseModel):
    """A point of interest along the route."""
    
    coords: Coordinates
    name: str
    category: POICategory
    description: str | None = None
    distance_from_start_km: float = Field(
        ...,
        description="Distance from day's start in km"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "coords": {"latitude": 48.2544, "longitude": 12.8456},
                "name": "Inn River Viewpoint",
                "category": "viewpoint",
                "description": "Beautiful panoramic view of the Inn valley",
                "distance_from_start_km": 35.5
            }
        }


class DailySegment(BaseModel):
    """A single day's route segment."""
    
    day_number: int = Field(..., ge=1)
    start_coords: Coordinates
    end_coords: Coordinates
    distance_km: float = Field(..., ge=0)
    elevation_gain_m: float = Field(default=0, ge=0)
    elevation_loss_m: float = Field(default=0, ge=0)
    surface_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Percentage of each surface type"
    )
    estimated_duration_hours: float = Field(
        default=0,
        description="Estimated riding time in hours"
    )
    camping_options: list[CampingSite] = Field(default_factory=list)
    pause_spots: list[POI] = Field(default_factory=list)
    gpx_track: str | None = Field(
        default=None,
        description="GPX format track data for this segment"
    )
    route_description: str | None = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "day_number": 1,
                "start_coords": {"latitude": 48.1351, "longitude": 11.5820},
                "end_coords": {"latitude": 48.0614, "longitude": 12.2311},
                "distance_km": 78.5,
                "elevation_gain_m": 450,
                "elevation_loss_m": 380,
                "surface_breakdown": {"gravel": 60, "paved": 35, "trail": 5},
                "estimated_duration_hours": 5.5,
                "camping_options": [],
                "pause_spots": [],
                "route_description": "Follow the Inn River cycle path eastward"
            }
        }


class RouteOutput(BaseModel):
    """Complete route planning output."""
    
    total_distance_km: float = Field(..., ge=0)
    estimated_days: int = Field(..., ge=1)
    total_elevation_gain_m: float = Field(default=0, ge=0)
    total_elevation_loss_m: float = Field(default=0, ge=0)
    daily_segments: list[DailySegment] = Field(default_factory=list)
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_distance_km": 420.0,
                "estimated_days": 5,
                "total_elevation_gain_m": 2500,
                "total_elevation_loss_m": 2450,
                "daily_segments": [],
                "summary": "5-day bike packing route from Munich to Vienna",
                "warnings": ["Day 3 has limited water sources"]
            }
        }
