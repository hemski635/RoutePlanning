"""GPX file generation utilities."""

from datetime import datetime
from typing import Sequence

import gpxpy
import gpxpy.gpx

from src.models import Coordinates, DailySegment, RouteOutput


def create_gpx_track(
    name: str,
    coordinates: Sequence[tuple[float, float, float | None]],
    description: str | None = None,
) -> str:
    """
    Create a GPX track from a list of coordinates.
    
    Args:
        name: Name of the track
        coordinates: List of (lat, lon, elevation) tuples
        description: Optional track description
    
    Returns:
        GPX XML string
    """
    gpx = gpxpy.gpx.GPX()
    
    # Create track
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = name
    gpx_track.description = description
    gpx.tracks.append(gpx_track)
    
    # Create segment
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)
    
    # Add points
    for coord in coordinates:
        lat, lon = coord[0], coord[1]
        elevation = coord[2] if len(coord) > 2 else None
        
        point = gpxpy.gpx.GPXTrackPoint(
            latitude=lat,
            longitude=lon,
            elevation=elevation,
        )
        gpx_segment.points.append(point)
    
    return gpx.to_xml()


def create_gpx_from_route(
    route: RouteOutput,
    include_waypoints: bool = True,
) -> str:
    """
    Create a complete GPX file from a RouteOutput.
    
    Args:
        route: The complete route output
        include_waypoints: Whether to include camping sites and POIs as waypoints
    
    Returns:
        GPX XML string
    """
    gpx = gpxpy.gpx.GPX()
    gpx.name = route.summary or "Bike Packing Route"
    gpx.description = f"Total distance: {route.total_distance_km} km over {route.estimated_days} days"
    gpx.creator = "Bike Packing Route Planner"
    gpx.time = datetime.utcnow()
    
    # Add waypoints for camping sites and POIs
    if include_waypoints:
        for segment in route.daily_segments:
            # Add camping sites as waypoints
            for site in segment.camping_options:
                waypoint = gpxpy.gpx.GPXWaypoint(
                    latitude=site.coords.latitude,
                    longitude=site.coords.longitude,
                )
                waypoint.name = site.name
                waypoint.description = f"Type: {site.type.value}"
                waypoint.symbol = "Campground"
                waypoint.type = "Camping"
                gpx.waypoints.append(waypoint)
            
            # Add POIs as waypoints
            for poi in segment.pause_spots:
                waypoint = gpxpy.gpx.GPXWaypoint(
                    latitude=poi.coords.latitude,
                    longitude=poi.coords.longitude,
                )
                waypoint.name = poi.name
                waypoint.description = poi.description
                waypoint.type = poi.category.value
                gpx.waypoints.append(waypoint)
    
    # Add each day as a separate track
    for segment in route.daily_segments:
        track = gpxpy.gpx.GPXTrack()
        track.name = f"Day {segment.day_number}"
        track.description = segment.route_description
        
        # Add metadata
        track.type = "cycling"
        
        gpx.tracks.append(track)
        
        # If we have GPX track data for this segment, parse and add it
        if segment.gpx_track:
            try:
                segment_gpx = gpxpy.parse(segment.gpx_track)
                for seg_track in segment_gpx.tracks:
                    for seg in seg_track.segments:
                        track.segments.append(seg)
            except Exception:
                # If parsing fails, just add start/end points
                gpx_segment = gpxpy.gpx.GPXTrackSegment()
                gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                    latitude=segment.start_coords.latitude,
                    longitude=segment.start_coords.longitude,
                ))
                gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                    latitude=segment.end_coords.latitude,
                    longitude=segment.end_coords.longitude,
                ))
                track.segments.append(gpx_segment)
    
    return gpx.to_xml()


def save_gpx_file(gpx_content: str, filepath: str) -> None:
    """Save GPX content to a file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(gpx_content)


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """
    Decode a Google-style encoded polyline string.
    
    Args:
        encoded: The encoded polyline string
        precision: Coordinate precision (5 for Google, 6 for OSRM)
    
    Returns:
        List of (lat, lon) tuples
    """
    coordinates = []
    index = 0
    lat = 0
    lon = 0
    
    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat
        
        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if result & 1 else result >> 1
        lon += dlon
        
        coordinates.append((lat / 10**precision, lon / 10**precision))
    
    return coordinates
