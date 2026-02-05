"""Points of Interest finder using OpenStreetMap Overpass API."""

import json
from typing import Annotated

import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def find_points_of_interest(
    latitude: Annotated[float, "Center point latitude"],
    longitude: Annotated[float, "Center point longitude"],
    radius_km: Annotated[float, "Search radius in kilometers"] = 5.0,
    categories: Annotated[list[str] | None, "POI categories: 'viewpoint', 'water', 'food', 'bike_shop', 'supermarket'"] = None,
) -> str:
    """
    Find points of interest near a location.
    
    Searches for viewpoints, water sources, restaurants, bike shops, and other
    useful stops for cyclists. Use this to find nice pause spots along the route.
    
    Returns categorized POIs with coordinates and details.
    """
    radius_m = radius_km * 1000
    
    # Default to all categories if none specified
    if not categories:
        categories = ["viewpoint", "water", "food", "bike_shop", "supermarket"]
    
    # Build query based on requested categories
    query_parts = []
    
    if "viewpoint" in categories:
        query_parts.extend([
            f'node["tourism"="viewpoint"](around:{radius_m},{latitude},{longitude});',
            f'node["natural"="peak"](around:{radius_m},{latitude},{longitude});',
        ])
    
    if "water" in categories:
        query_parts.extend([
            f'node["amenity"="drinking_water"](around:{radius_m},{latitude},{longitude});',
            f'node["natural"="spring"]["drinking_water"="yes"](around:{radius_m},{latitude},{longitude});',
            f'node["man_made"="water_tap"](around:{radius_m},{latitude},{longitude});',
        ])
    
    if "food" in categories:
        query_parts.extend([
            f'node["amenity"="restaurant"](around:{radius_m},{latitude},{longitude});',
            f'node["amenity"="cafe"](around:{radius_m},{latitude},{longitude});',
            f'node["amenity"="pub"](around:{radius_m},{latitude},{longitude});',
            f'node["amenity"="fast_food"](around:{radius_m},{latitude},{longitude});',
        ])
    
    if "bike_shop" in categories:
        query_parts.extend([
            f'node["shop"="bicycle"](around:{radius_m},{latitude},{longitude});',
            f'node["amenity"="bicycle_repair_station"](around:{radius_m},{latitude},{longitude});',
        ])
    
    if "supermarket" in categories:
        query_parts.extend([
            f'node["shop"="supermarket"](around:{radius_m},{latitude},{longitude});',
            f'node["shop"="convenience"](around:{radius_m},{latitude},{longitude});',
        ])
    
    if "rest_area" in categories:
        query_parts.extend([
            f'node["amenity"="bench"](around:{radius_m},{latitude},{longitude});',
            f'node["tourism"="picnic_site"](around:{radius_m},{latitude},{longitude});',
            f'node["leisure"="picnic_table"](around:{radius_m},{latitude},{longitude});',
        ])
    
    if not query_parts:
        return json.dumps({"error": "No valid categories specified"})
    
    query = f"""
    [out:json][timeout:25];
    (
        {' '.join(query_parts)}
    );
    out body;
    """
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return json.dumps({
                "error": f"Failed to search for POIs: {str(e)}"
            })
    
    # Categorize results
    results = {
        "viewpoints": [],
        "water_sources": [],
        "food": [],
        "bike_shops": [],
        "supermarkets": [],
        "rest_areas": [],
    }
    
    for element in data.get("elements", []):
        if element.get("type") != "node":
            continue
            
        tags = element.get("tags", {})
        lat = element.get("lat")
        lon = element.get("lon")
        
        if not lat or not lon:
            continue
        
        poi = {
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "name": tags.get("name", "Unnamed"),
        }
        
        # Calculate distance from search center
        from math import radians, sin, cos, sqrt, atan2
        R = 6371
        lat1, lon1 = radians(latitude), radians(longitude)
        lat2, lon2 = radians(lat), radians(lon)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        poi["dist_km"] = round(R * c, 1)
        
        # Categorize
        if tags.get("tourism") == "viewpoint" or tags.get("natural") == "peak":
            if tags.get("ele"):
                poi["elevation"] = tags.get("ele")
            results["viewpoints"].append(poi)
        
        elif tags.get("amenity") == "drinking_water" or tags.get("man_made") == "water_tap":
            results["water_sources"].append(poi)
        
        elif tags.get("amenity") in ["restaurant", "cafe", "pub", "fast_food"]:
            poi["type"] = tags.get("amenity")
            results["food"].append(poi)
        
        elif tags.get("shop") == "bicycle" or tags.get("amenity") == "bicycle_repair_station":
            results["bike_shops"].append(poi)
        
        elif tags.get("shop") in ["supermarket", "convenience"]:
            results["supermarkets"].append(poi)
        
        elif tags.get("amenity") == "bench" or tags.get("tourism") == "picnic_site":
            results["rest_areas"].append(poi)
    
    # Sort each category by distance and limit
    for category in results:
        results[category].sort(key=lambda x: x["dist_km"])
        results[category] = results[category][:5]  # Limit to 5 per category
    
    # Remove empty categories
    results = {k: v for k, v in results.items() if v}
    
    return json.dumps(results)


async def find_scenic_route_spots(
    start_lat: Annotated[float, "Route start latitude"],
    start_lon: Annotated[float, "Route start longitude"],
    end_lat: Annotated[float, "Route end latitude"],
    end_lon: Annotated[float, "Route end longitude"],
) -> str:
    """
    Find scenic spots along a route corridor.
    
    Searches for viewpoints, natural features, and historic sites
    along the general path between two points.
    
    Returns notable spots that would make good pause locations.
    """
    # Calculate bounding box with some padding
    min_lat = min(start_lat, end_lat) - 0.1
    max_lat = max(start_lat, end_lat) + 0.1
    min_lon = min(start_lon, end_lon) - 0.1
    max_lon = max(start_lon, end_lon) + 0.1
    
    query = f"""
    [out:json][timeout:30];
    (
        node["tourism"="viewpoint"]({min_lat},{min_lon},{max_lat},{max_lon});
        node["natural"="peak"]({min_lat},{min_lon},{max_lat},{max_lon});
        node["historic"]({min_lat},{min_lon},{max_lat},{max_lon});
        node["natural"="waterfall"]({min_lat},{min_lon},{max_lat},{max_lon});
        node["tourism"="attraction"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out body;
    """
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=35.0,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return json.dumps({
                "error": f"Failed to search scenic spots: {str(e)}"
            })
    
    spots = []
    
    for element in data.get("elements", []):
        if element.get("type") != "node":
            continue
            
        tags = element.get("tags", {})
        lat = element.get("lat")
        lon = element.get("lon")
        
        if not lat or not lon:
            continue
        
        # Determine category
        category = "attraction"
        if tags.get("tourism") == "viewpoint":
            category = "viewpoint"
        elif tags.get("natural") == "peak":
            category = "peak"
        elif tags.get("historic"):
            category = "historic"
        elif tags.get("natural") == "waterfall":
            category = "waterfall"
        
        spot = {
            "coords": {"latitude": lat, "longitude": lon},
            "name": tags.get("name", f"Unnamed {category}"),
            "category": category,
            "description": tags.get("description"),
            "elevation": tags.get("ele"),
            "wikipedia": tags.get("wikipedia"),
        }
        
        spots.append(spot)
    
    return json.dumps({
        "route_corridor": {
            "start": {"latitude": start_lat, "longitude": start_lon},
            "end": {"latitude": end_lat, "longitude": end_lon},
        },
        "scenic_spots_count": len(spots),
        "scenic_spots": spots[:25],  # Limit results
    })
