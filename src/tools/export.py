"""Route export tools for visualization and GPS devices."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import httpx

BROUTER_BASE_URL = os.getenv("BROUTER_URL", "http://localhost:17777")
# Self-hosted brouter-web instance
BROUTER_WEB_URL = os.getenv("BROUTER_WEB_URL", "http://localhost:8080")


def generate_brouter_web_url(
    waypoints: Annotated[str, "Waypoints as 'lat,lon|lat,lon|...' string (e.g. '48.1351,11.5820|47.8095,13.0550')"],
    profile: Annotated[str, "Routing profile: 'trekking', 'fastbike', 'mtb', 'safety'"] = "trekking",
    zoom: Annotated[int, "Map zoom level (8-15)"] = 10,
    pois: Annotated[str, "Optional POI markers as 'lat,lon,name|lat,lon,name|...' (e.g. '56.17,24.05,Camp Day1|54.68,25.30,Vilnius')"] = "",
) -> str:
    """
    Generate a brouter-web URL to visualize a route with optional POI markers.
    
    Creates a URL that opens brouter-web with the specified waypoints and POIs pre-loaded.
    The user can then view, modify, and export the route.
    
    Use this after planning a route to give the user a visual map with marked points.
    
    waypoints format: "lat,lon|lat,lon|lat,lon" (pipe-separated coordinate pairs)
    pois format: "lat,lon,name|lat,lon,name" (pipe-separated, each with lat,lon,name)
    
    POI examples:
    - Camping sites: "56.17,24.05,Camp Day1|55.50,24.80,Camp Day2"
    - Points of interest: "56.90,24.10,Viewpoint|56.50,24.30,Water Source"
    """
    # Parse waypoints string into list of (lat, lon) tuples
    try:
        parsed_waypoints = []
        for wp in waypoints.split("|"):
            lat, lon = map(float, wp.strip().split(","))
            parsed_waypoints.append((lat, lon))
    except (ValueError, AttributeError):
        return json.dumps({"error": "Invalid waypoints format. Use 'lat,lon|lat,lon|...'"})
    
    if len(parsed_waypoints) < 2:
        return json.dumps({"error": "At least 2 waypoints required"})
    
    # Calculate center point for map view
    avg_lat = sum(wp[0] for wp in parsed_waypoints) / len(parsed_waypoints)
    avg_lon = sum(wp[1] for wp in parsed_waypoints) / len(parsed_waypoints)
    
    # Format waypoints as lon,lat;lon,lat (brouter-web uses lon,lat order)
    lonlats = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in parsed_waypoints)
    
    # Build URL with hash parameters
    # Format: #map=zoom/lat/lon/layer&lonlats=...&profile=...
    url = f"{BROUTER_WEB_URL}/#map={zoom}/{avg_lat:.4f}/{avg_lon:.4f}/standard&lonlats={lonlats}&profile={profile}"
    
    # Add POIs if provided
    poi_count = 0
    if pois and pois.strip():
        try:
            poi_parts = []
            for poi in pois.split("|"):
                parts = poi.strip().split(",", 2)  # Split into max 3 parts: lat, lon, name
                if len(parts) >= 3:
                    lat, lon = float(parts[0]), float(parts[1])
                    name = quote(parts[2].strip())  # URL-encode the name
                    poi_parts.append(f"{lon:.5f},{lat:.5f},{name}")
                    poi_count += 1
            if poi_parts:
                pois_str = "|".join(poi_parts)
                url += f"&pois={pois_str}"
        except (ValueError, IndexError):
            # Invalid POI format, skip but continue
            pass
    
    return json.dumps({
        "map_url": url,
        "display_text": f"🗺️ View Interactive Map: {url}",
        "waypoints_count": len(parsed_waypoints),
        "pois_count": poi_count,
        "note": "Click the link to view the route with marked camping sites and POIs"
    })


async def export_route_gpx(
    waypoints: Annotated[str, "Waypoints as 'lat,lon|lat,lon|...' string (e.g. '48.1351,11.5820|47.8095,13.0550')"],
    route_name: Annotated[str, "Name for the GPX file and route"] = "bikepacking_route",
    profile: Annotated[str, "Routing profile: 'trekking', 'fastbike', 'mtb'"] = "trekking",
) -> str:
    """
    Export a route as a GPX file for GPS devices.
    
    Calculates the full route through all waypoints using BRouter,
    then saves it as a GPX file that can be loaded into GPS devices,
    Komoot, Strava, or other cycling apps.
    
    Returns the path to the saved GPX file.
    
    waypoints format: "lat,lon|lat,lon|lat,lon" (pipe-separated coordinate pairs)
    """
    # Parse waypoints string into list of (lat, lon) tuples
    try:
        parsed_waypoints = []
        for wp in waypoints.split("|"):
            lat, lon = map(float, wp.strip().split(","))
            parsed_waypoints.append((lat, lon))
    except (ValueError, AttributeError):
        return json.dumps({"error": "Invalid waypoints format. Use 'lat,lon|lat,lon|...'"})
    
    if len(parsed_waypoints) < 2:
        return json.dumps({"error": "At least 2 waypoints required"})
    
    # Build lonlats string for BRouter (lon,lat order)
    lonlats = "|".join(f"{lon},{lat}" for lat, lon in parsed_waypoints)
    
    # Request GPX format directly from BRouter
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BROUTER_BASE_URL}/brouter",
                params={
                    "lonlats": lonlats,
                    "profile": profile,
                    "alternativeidx": 0,
                    "format": "gpx",
                },
                timeout=120.0,
            )
            
            if response.status_code != 200:
                return json.dumps({
                    "error": f"BRouter error: {response.status_code}",
                    "details": response.text[:200]
                })
            
            gpx_content = response.text
            
        except httpx.ConnectError:
            return json.dumps({
                "error": "Cannot connect to BRouter",
                "suggestion": "Start BRouter with 'docker compose up -d'"
            })
        except Exception as e:
            return json.dumps({"error": f"Failed to generate GPX: {str(e)}"})
    
    # Save to output directory
    output_dir = Path(__file__).parent.parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in route_name)
    filename = f"{safe_name}_{timestamp}.gpx"
    filepath = output_dir / filename
    
    # Write GPX file
    filepath.write_text(gpx_content)
    
    return json.dumps({
        "success": True,
        "filepath": str(filepath),
        "filename": filename,
        "waypoints_count": len(waypoints),
        "instructions": f"GPX file saved. You can load it into GPS devices, Komoot, Strava, or brouter-web."
    })


def generate_daily_waypoints_summary(
    daily_segments: Annotated[list[dict], "List of daily segments with start/end coordinates"],
) -> str:
    """
    Generate a summary of waypoints for a multi-day route.
    
    Takes the planned daily segments and creates:
    - A list of all waypoints (overnight stops)
    - A brouter-web URL for the full route
    - Individual URLs for each day
    
    Use this to provide the user with visual route links.
    """
    if not daily_segments:
        return json.dumps({"error": "No daily segments provided"})
    
    all_waypoints = []
    daily_urls = []
    
    for i, segment in enumerate(daily_segments):
        start = segment.get("start", {})
        end = segment.get("end", {})
        
        # Add start point (only for first segment)
        if i == 0 and start:
            all_waypoints.append((start.get("lat"), start.get("lon")))
        
        # Add end point
        if end:
            all_waypoints.append((end.get("lat"), end.get("lon")))
        
        # Generate URL for this day's segment
        if start and end:
            day_waypoints = [
                (start.get("lat"), start.get("lon")),
                (end.get("lat"), end.get("lon"))
            ]
            lonlats = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in day_waypoints)
            center_lat = (start.get("lat") + end.get("lat")) / 2
            center_lon = (start.get("lon") + end.get("lon")) / 2
            
            day_url = f"{BROUTER_WEB_URL}/#map=11/{center_lat:.4f}/{center_lon:.4f}/standard&lonlats={lonlats}&profile=trekking"
            daily_urls.append({
                "day": i + 1,
                "name": segment.get("name", f"Day {i + 1}"),
                "url": day_url
            })
    
    # Generate full route URL
    if len(all_waypoints) >= 2:
        lonlats = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in all_waypoints)
        avg_lat = sum(wp[0] for wp in all_waypoints) / len(all_waypoints)
        avg_lon = sum(wp[1] for wp in all_waypoints) / len(all_waypoints)
        full_url = f"{BROUTER_WEB_URL}/#map=9/{avg_lat:.4f}/{avg_lon:.4f}/standard&lonlats={lonlats}&profile=trekking"
    else:
        full_url = None
    
    return json.dumps({
        "total_waypoints": len(all_waypoints),
        "waypoints": [{"lat": lat, "lon": lon} for lat, lon in all_waypoints],
        "full_route_url": full_url,
        "daily_urls": daily_urls,
        "instructions": "Click the full_route_url to see the entire trip, or daily URLs for individual segments"
    })
