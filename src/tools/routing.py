"""Routing tools using BRouter (self-hosted) or OpenRouteService as fallback."""

import os
import json
from typing import Annotated

import httpx

# BRouter configuration (Docker container)
BROUTER_BASE_URL = os.getenv("BROUTER_URL", "http://localhost:17777")

# OpenRouteService as fallback
ORS_BASE_URL = "https://api.openrouteservice.org"

# BRouter profile mapping for different bike types
BROUTER_PROFILES = {
    "road": "fastbike",
    "gravel": "trekking",
    "trekking": "trekking", 
    "mountain": "mtb",
    "mtb": "mtb",
    "safety": "safety",
    "shortest": "shortest",
}

# ORS profile mapping (fallback)
ORS_PROFILES = {
    "road": "cycling-road",
    "gravel": "cycling-regular", 
    "mountain": "cycling-mountain",
    "trekking": "cycling-regular",
}


def _get_ors_api_key() -> str | None:
    """Get the OpenRouteService API key from environment (optional fallback)."""
    return os.getenv("OPENROUTESERVICE_API_KEY")


async def _check_brouter_available() -> bool:
    """Check if BRouter is available."""
    try:
        async with httpx.AsyncClient() as client:
            # Just check if the server responds - any response means it's running
            # We use a request that will fail fast but confirms the server is there
            response = await client.get(
                f"{BROUTER_BASE_URL}/brouter",
                params={"lonlats": "0,0", "profile": "trekking", "format": "geojson"},
                timeout=5.0,
            )
            # Any response (even 400 error) means server is running
            return True
    except httpx.ConnectError:
        return False
    except httpx.TimeoutException:
        return False
    except Exception:
        return False


async def geocode_location(
    location_name: Annotated[str, "The name of a place or address to geocode (e.g., 'Munich, Germany')"]
) -> str:
    """
    Convert a place name or address to GPS coordinates.
    
    Use this when the user provides a location name instead of coordinates.
    Returns the coordinates as a JSON string with latitude and longitude.
    
    Note: Uses Nominatim (OpenStreetMap) for geocoding - no API key required.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": location_name,
                "format": "json",
                "limit": 1,
            },
            headers={
                "User-Agent": "BikePacking-Route-Planner/1.0"
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        
    if not data:
        return json.dumps({
            "error": f"Could not find location: {location_name}",
            "suggestion": "Try a more specific location name or provide coordinates directly"
        })
    
    result = data[0]
    
    return json.dumps({
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "name": result.get("display_name", location_name)[:50],
    })


async def calculate_route(
    start_lat: Annotated[float, "Starting point latitude"],
    start_lon: Annotated[float, "Starting point longitude"],
    end_lat: Annotated[float, "End point latitude"],
    end_lon: Annotated[float, "End point longitude"],
    bike_profile: Annotated[str, "Bike profile: 'road', 'gravel', 'trekking', 'mountain', or 'safety'"] = "trekking",
    include_geometry: Annotated[bool, "Include full GPS track (set False to reduce response size)"] = False,
) -> str:
    """
    Calculate a cycling route between two points using BRouter.
    
    Returns route summary: distance, duration, elevation gain/loss.
    Set include_geometry=True only when you need the full GPS track for export.
    """
    # Check if BRouter is available
    brouter_available = await _check_brouter_available()
    
    if brouter_available:
        return await _calculate_route_brouter(
            start_lat, start_lon, end_lat, end_lon, bike_profile, include_geometry
        )
    else:
        # Fallback to OpenRouteService if available
        if _get_ors_api_key():
            return await _calculate_route_ors(
                start_lat, start_lon, end_lat, end_lon, bike_profile
            )
        else:
            return json.dumps({
                "error": "BRouter is not available and no ORS API key configured",
                "suggestion": "Start BRouter with 'docker compose up -d' or set OPENROUTESERVICE_API_KEY"
            })


async def _calculate_route_brouter(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    bike_profile: str,
    include_geometry: bool = False,
) -> str:
    """Calculate route using BRouter."""
    profile = BROUTER_PROFILES.get(bike_profile, "trekking")
    
    # BRouter uses lon,lat format (opposite of most APIs)
    lonlats = f"{start_lon},{start_lat}|{end_lon},{end_lat}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BROUTER_BASE_URL}/brouter",
            params={
                "lonlats": lonlats,
                "profile": profile,
                "alternativeidx": 0,
                "format": "geojson",
            },
            timeout=60.0,
        )
        
        if response.status_code != 200:
            return json.dumps({
                "error": f"BRouter error: {response.status_code}",
                "details": response.text[:500],
            })
        
        geojson = response.json()
    
    # Extract route properties from GeoJSON
    if not geojson.get("features"):
        return json.dumps({
            "error": "No route found between the specified points",
            "suggestion": "Check that segment data is available for this region"
        })
    
    feature = geojson["features"][0]
    props = feature.get("properties", {})
    
    # Parse BRouter-specific properties
    track_length = float(props.get("track-length", 0))  # in meters
    total_time = float(props.get("total-time", 0))  # in seconds
    total_ascend = float(props.get("filtered ascend", props.get("plain-ascend", 0)))
    total_descend = abs(float(props.get("filtered descend", props.get("plain-descend", 0))))
    
    # Get geometry info
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [])
    
    # Build result - only include full geometry if requested
    result = {
        "source": "brouter",
        "profile": profile,
        "distance_km": round(track_length / 1000, 2),
        "duration_hours": round(total_time / 3600, 2),
        "elevation": {
            "ascent_m": total_ascend,
            "descent_m": total_descend,
        },
        "start_point": {"lon": coords[0][0], "lat": coords[0][1]} if coords else None,
        "end_point": {"lon": coords[-1][0], "lat": coords[-1][1]} if coords else None,
        "waypoints_count": len(coords),
    }
    
    # Only include full geometry if explicitly requested (for GPX export)
    if include_geometry:
        result["geometry"] = geometry
    
    return json.dumps(result)


async def _calculate_route_ors(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    bike_profile: str,
) -> str:
    """Calculate route using OpenRouteService (fallback)."""
    api_key = _get_ors_api_key()
    profile = ORS_PROFILES.get(bike_profile, "cycling-regular")
    
    body = {
        "coordinates": [
            [start_lon, start_lat],
            [end_lon, end_lat],
        ],
        "elevation": True,
        "instructions": False,
        "preference": "recommended",
        "units": "km",
        "geometry": False,  # Don't include geometry to save tokens
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ORS_BASE_URL}/v2/directions/{profile}",
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60.0,
        )
        
        if response.status_code != 200:
            return json.dumps({
                "error": f"ORS error: {response.status_code}",
                "details": response.text[:500],
            })
        
        data = response.json()
    
    if not data.get("routes"):
        return json.dumps({"error": "No route found"})
    
    route = data["routes"][0]
    summary = route["summary"]
    
    return json.dumps({
        "source": "openrouteservice",
        "profile": profile,
        "distance_km": round(summary["distance"], 2),
        "duration_hours": round(summary["duration"] / 3600, 2),
        "elevation": {
            "ascent_m": summary.get("ascent", 0),
            "descent_m": summary.get("descent", 0),
        },
    })


async def calculate_route_with_waypoints(
    waypoints: Annotated[list[tuple[float, float]], "List of (latitude, longitude) waypoints"],
    bike_profile: Annotated[str, "Bike profile: 'road', 'gravel', 'trekking', 'mountain'"] = "trekking",
) -> str:
    """
    Calculate a cycling route through multiple waypoints using BRouter.
    
    Use this when you need to route through specific intermediate points,
    such as planned camping locations or must-visit spots.
    
    Returns route details including total distance and segment information.
    """
    if len(waypoints) < 2:
        return json.dumps({"error": "At least 2 waypoints are required"})
    
    brouter_available = await _check_brouter_available()
    
    if not brouter_available:
        return json.dumps({
            "error": "BRouter is not available",
            "suggestion": "Start BRouter with 'docker compose up -d'"
        })
    
    profile = BROUTER_PROFILES.get(bike_profile, "trekking")
    
    # Build lonlats string for BRouter (lon,lat|lon,lat|...)
    lonlats = "|".join(f"{lon},{lat}" for lat, lon in waypoints)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BROUTER_BASE_URL}/brouter",
            params={
                "lonlats": lonlats,
                "profile": profile,
                "alternativeidx": 0,
                "format": "geojson",
            },
            timeout=120.0,  # Longer timeout for multi-waypoint routes
        )
        
        if response.status_code != 200:
            return json.dumps({
                "error": f"BRouter error: {response.status_code}",
                "details": response.text[:500],
            })
        
        geojson = response.json()
    
    if not geojson.get("features"):
        return json.dumps({"error": "No route found"})
    
    feature = geojson["features"][0]
    props = feature.get("properties", {})
    
    track_length = float(props.get("track-length", 0))
    total_time = float(props.get("total-time", 0))
    
    return json.dumps({
        "source": "brouter",
        "profile": profile,
        "waypoints_count": len(waypoints),
        "distance_km": round(track_length / 1000, 2),
        "duration_hours": round(total_time / 3600, 2),
        "elevation": {
            "ascent_m": float(props.get("filtered ascend", 0)),
            "descent_m": abs(float(props.get("filtered descend", 0))),
        },
    })


async def get_route_elevation(
    start_lat: Annotated[float, "Starting point latitude"],
    start_lon: Annotated[float, "Starting point longitude"],
    end_lat: Annotated[float, "End point latitude"],
    end_lon: Annotated[float, "End point longitude"],
) -> str:
    """
    Get elevation profile for a route.
    
    Returns elevation gain, loss, and profile data.
    Use this for detailed elevation analysis of a route segment.
    """
    # Use BRouter to get elevation data (it's included in route calculation)
    result = await calculate_route(start_lat, start_lon, end_lat, end_lon, "trekking")
    data = json.loads(result)
    
    if "error" in data:
        return result
    
    return json.dumps({
        "total_ascent_m": data.get("elevation", {}).get("ascent_m", 0),
        "total_descent_m": data.get("elevation", {}).get("descent_m", 0),
        "distance_km": data.get("distance_km", 0),
        "source": data.get("source", "unknown"),
    })


async def get_alternative_routes(
    start_lat: Annotated[float, "Starting point latitude"],
    start_lon: Annotated[float, "Starting point longitude"],
    end_lat: Annotated[float, "End point latitude"],
    end_lon: Annotated[float, "End point longitude"],
    num_alternatives: Annotated[int, "Number of alternative routes (1-3)"] = 2,
) -> str:
    """
    Get multiple alternative routes between two points.
    
    BRouter can calculate up to 3 alternative routes (indices 0, 1, 2).
    Use this to offer the user different route options.
    
    Returns a list of routes with their characteristics.
    """
    brouter_available = await _check_brouter_available()
    
    if not brouter_available:
        return json.dumps({
            "error": "BRouter is not available",
            "suggestion": "Start BRouter with 'docker compose up -d'"
        })
    
    lonlats = f"{start_lon},{start_lat}|{end_lon},{end_lat}"
    alternatives = []
    
    async with httpx.AsyncClient() as client:
        for idx in range(min(num_alternatives + 1, 4)):  # Max 4 alternatives (0-3)
            try:
                response = await client.get(
                    f"{BROUTER_BASE_URL}/brouter",
                    params={
                        "lonlats": lonlats,
                        "profile": "trekking",
                        "alternativeidx": idx,
                        "format": "geojson",
                    },
                    timeout=60.0,
                )
                
                if response.status_code == 200:
                    geojson = response.json()
                    if geojson.get("features"):
                        feature = geojson["features"][0]
                        props = feature.get("properties", {})
                        
                        alternatives.append({
                            "alternative_index": idx,
                            "distance_km": round(float(props.get("track-length", 0)) / 1000, 2),
                            "duration_hours": round(float(props.get("total-time", 0)) / 3600, 2),
                            "ascent_m": float(props.get("filtered ascend", 0)),
                            "descent_m": abs(float(props.get("filtered descend", 0))),
                        })
            except Exception:
                continue
    
    return json.dumps({
        "alternatives_count": len(alternatives),
        "alternatives": alternatives,
    })
