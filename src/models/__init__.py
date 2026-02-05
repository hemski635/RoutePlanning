"""Data models for route planning."""

from .request import RouteRequest, SurfaceType
from .response import (
    RouteOutput,
    DailySegment,
    CampingSite,
    CampingType,
    POI,
    POICategory,
    Coordinates,
)

__all__ = [
    "RouteRequest",
    "SurfaceType",
    "RouteOutput",
    "DailySegment",
    "CampingSite",
    "CampingType",
    "POI",
    "POICategory",
    "Coordinates",
]
