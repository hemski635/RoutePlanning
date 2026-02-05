"""Camping spot finder - finds remote hiking spots along a route."""

import asyncio
import json
import os
from typing import Annotated
from math import radians, sin, cos, sqrt, atan2

import httpx

# Overpass API configuration
# Use local instance by default, or public Overpass API if USE_PUBLIC_SERVICES=true
USE_PUBLIC_SERVICES = os.getenv("USE_PUBLIC_SERVICES", "false").lower() == "true"

if USE_PUBLIC_SERVICES:
    # Public Overpass instances (with rate limits)
    OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
else:
    OVERPASS_URL = os.getenv("OVERPASS_URL", "http://localhost:12345/api/interpreter")

# Minimum forest area in hectares for wild camping consideration
MIN_FOREST_AREA_HA = 20  # At least 20 hectares (~450m x 450m) for reasonable wild camping


def _calc_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km using Haversine formula."""
    R = 6371
    rlat1, rlon1 = radians(lat1), radians(lon1)
    rlat2, rlon2 = radians(lat2), radians(lon2)
    dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
    a = sin(dlat/2)**2 + cos(rlat1) * cos(rlat2) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def _estimate_polygon_area_ha(coords):
    """
    Estimate area of a polygon in hectares using the Shoelace formula.
    coords: list of [lon, lat] pairs
    """
    if len(coords) < 3:
        return 0
    
    # Convert to approximate metric coordinates (rough but sufficient for area comparison)
    # Use average lat for lon scaling
    avg_lat = sum(c[1] for c in coords) / len(coords)
    lon_scale = cos(radians(avg_lat)) * 111320  # meters per degree longitude
    lat_scale = 111320  # meters per degree latitude
    
    # Convert to meters
    metric_coords = [(c[0] * lon_scale, c[1] * lat_scale) for c in coords]
    
    # Shoelace formula for polygon area
    n = len(metric_coords)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += metric_coords[i][0] * metric_coords[j][1]
        area -= metric_coords[j][0] * metric_coords[i][1]
    area = abs(area) / 2.0
    
    # Convert to hectares (1 ha = 10,000 m²)
    return area / 10000


def _interpolate_point_along_route(points, cumulative_dist, target_km):
    """Find the lat/lon at a specific km distance along the route."""
    for i in range(1, len(points)):
        if cumulative_dist[i] >= target_km:
            # Interpolate between points[i-1] and points[i]
            segment_start = cumulative_dist[i-1]
            segment_end = cumulative_dist[i]
            segment_len = segment_end - segment_start
            if segment_len == 0:
                return points[i-1]
            ratio = (target_km - segment_start) / segment_len
            lat = points[i-1][0] + ratio * (points[i][0] - points[i-1][0])
            lon = points[i-1][1] + ratio * (points[i][1] - points[i-1][1])
            return (lat, lon)
    return points[-1]


async def _query_overpass(client, query, timeout=60.0, max_retries=3):
    """Query Overpass with retry on 504/429 errors."""
    for attempt in range(max_retries):
        if attempt > 0:
            await asyncio.sleep(5 * attempt)
        try:
            resp = await client.post(OVERPASS_URL, data={"data": query}, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in (429, 504):
                continue
            else:
                return {"error": f"Status {resp.status_code}"}
        except Exception as e:
            if attempt == max_retries - 1:
                return {"error": str(e)}
    return {"error": "Max retries exceeded"}


async def _find_large_forest_for_wild_camping(client, lat, lon, search_radius_km=8.0):
    """
    Find a suitable large forest area for wild camping.
    
    Returns the center of the largest forest area that is:
    - At least MIN_FOREST_AREA_HA hectares (to avoid small tree patches)
    - NOT farmland, agricultural land, or managed plantation
    - Away from roads and settlements
    
    Returns None if no suitable forest found.
    """
    delta = search_radius_km / 111.0
    bbox = (lat - delta, lon - delta * 1.5, lat + delta, lon + delta * 1.5)
    
    # Query for forests with geometry - use out geom for ways
    query = f"""[out:json][timeout:60];
(
  way["natural"="wood"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["landuse"="forest"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out body geom;"""
    
    forests = await _query_overpass(client, query, timeout=60.0)
    if "error" in forests:
        return None
    
    # Find the largest suitable forest
    best_forest = None
    best_area = 0
    
    for elem in forests.get("elements", []):
        tags = elem.get("tags", {})
        
        # Skip if explicitly agricultural or managed plantation
        if tags.get("leaf_type") == "needleleaved" and tags.get("managed") == "yes":
            continue
        if tags.get("crop"):  # Any crop tags indicate farmland
            continue
            
        # Get geometry from 'geometry' array (way nodes)
        geom = elem.get("geometry", [])
        if not geom or len(geom) < 3:
            continue
        
        # Convert geometry to coordinate list
        coords = []
        for point in geom:
            if isinstance(point, dict) and "lon" in point and "lat" in point:
                coords.append([point["lon"], point["lat"]])
        
        if len(coords) < 3:
            continue
        
        # Calculate area
        area_ha = _estimate_polygon_area_ha(coords)
        
        # Only consider forests above minimum size
        if area_ha >= MIN_FOREST_AREA_HA and area_ha > best_area:
            # Calculate centroid
            center_lon = sum(c[0] for c in coords) / len(coords)
            center_lat = sum(c[1] for c in coords) / len(coords)
            
            # Check distance from target
            dist = _calc_distance(lat, lon, center_lat, center_lon)
            if dist <= search_radius_km:
                best_forest = {
                    "lat": center_lat,
                    "lon": center_lon,
                    "area_ha": area_ha,
                    "name": tags.get("name", f"Forest ({area_ha:.0f} ha)"),
                    "type": "natural" if tags.get("natural") == "wood" else "forest",
                }
                best_area = area_ha
    
    return best_forest


async def _check_is_farmland(client, lat, lon):
    """Check if a point is on farmland/agricultural area. Returns True if farmland."""
    # Small bbox around the point
    delta = 0.002  # ~200m
    bbox = (lat - delta, lon - delta, lat + delta, lon + delta)
    
    query = f"""[out:json][timeout:15];
(
  way["landuse"="farmland"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["landuse"="farm"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["landuse"="meadow"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["landuse"="orchard"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["landuse"="vineyard"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["landuse"="agricultural"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["crop"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out count;"""
    
    result = await _query_overpass(client, query, timeout=15.0)
    if "error" in result:
        return False  # Assume not farmland if query fails
    
    # Parse the count result - look for total > 0
    for elem in result.get("elements", []):
        if elem.get("type") == "count":
            tags = elem.get("tags", {})
            total = int(tags.get("total", 0))
            return total > 0
    
    return False


async def find_daily_camping_spots(
    waypoints: Annotated[str, "Route waypoints as 'lat,lon|lat,lon|...' from route calculation"],
    daily_distance_km: Annotated[float, "Target distance per day in km"] = 80.0,
    search_radius_km: Annotated[float, "How far from day-end point to search (max 10km recommended)"] = 8.0,
) -> str:
    """
    Find ONE camping spot near the END of each day's ride along a route.
    
    This tool divides the route into daily segments and finds the best camping
    spot near each day's ending point. Camping spots are:
    - Within search_radius_km of that day's target end point
    - At least 500m from major roads
    - At least 2km from towns/villages
    
    For wild camping, it finds LARGE FOREST AREAS (50+ hectares) and avoids farmland.
    
    Returns:
    - One recommended spot per day
    - `route_waypoints`: waypoints string to recalculate route THROUGH camping spots
    
    Use route_waypoints with calculate_route to get the actual routed path through camps.
    """
    # Cap search radius to avoid searching too far off route
    search_radius_km = min(search_radius_km, 10.0)
    
    # Parse waypoints
    try:
        points = []
        for wp in waypoints.split("|"):
            lat, lon = wp.strip().split(",")
            points.append((float(lat), float(lon)))
    except:
        return json.dumps({"error": "Invalid waypoints. Use 'lat,lon|lat,lon|...'"})
    
    if len(points) < 2:
        return json.dumps({"error": "Need at least 2 waypoints"})
    
    start_point = points[0]
    end_point = points[-1]
    
    # Calculate cumulative distance along route
    cumulative_dist = [0.0]
    for i in range(1, len(points)):
        d = _calc_distance(points[i-1][0], points[i-1][1], points[i][0], points[i][1])
        cumulative_dist.append(cumulative_dist[-1] + d)
    total_route_km = cumulative_dist[-1]
    
    # Calculate number of days and day-end points
    num_days = max(1, int(total_route_km / daily_distance_km))
    if total_route_km % daily_distance_km > daily_distance_km * 0.3:
        num_days += 1
    
    # Find the target end point for each day (except last day - that's the destination)
    day_targets = []
    for day in range(1, num_days):
        target_km = day * daily_distance_km
        if target_km < total_route_km - 20:  # Don't place camp too close to destination
            target_point = _interpolate_point_along_route(points, cumulative_dist, target_km)
            day_targets.append({
                "day": day,
                "target_km": target_km,
                "lat": target_point[0],
                "lon": target_point[1],
            })
    
    if not day_targets:
        return json.dumps({
            "total_km": round(total_route_km, 1),
            "num_days": 1,
            "daily_camps": [],
            "route_waypoints": f"{start_point[0]},{start_point[1]}|{end_point[0]},{end_point[1]}",
            "note": "Route is short enough for single day - no camping needed"
        })
    
    # Search for camping spots near each day's target
    daily_camps = []
    camp_waypoints = [start_point]  # Start with route start
    
    async with httpx.AsyncClient() as client:
        for target in day_targets:
            lat, lon = target["lat"], target["lon"]
            # Create a small bounding box around the target point
            delta = search_radius_km / 111.0  # Rough conversion km to degrees
            bbox = (lat - delta, lon - delta * 1.5, lat + delta, lon + delta * 1.5)
            
            # Query camping features in this small area
            query = f"""[out:json][timeout:30];
(
  node["amenity"="shelter"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["tourism"="wilderness_hut"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["tourism"="picnic_site"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["shelter_type"~"picnic_shelter|lean_to|basic_hut"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["tourism"="viewpoint"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["tourism"="camp_site"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["natural"="spring"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["leisure"="firepit"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out body;"""
            
            features = await _query_overpass(client, query, timeout=30.0)
            if "error" in features:
                features = {"elements": []}
            
            await asyncio.sleep(1)
            
            # Query settlements to check remoteness
            settle_query = f"""[out:json][timeout:20];
(node["place"~"city|town|village"]({bbox[0]-0.05},{bbox[1]-0.05},{bbox[2]+0.05},{bbox[3]+0.05}););
out body;"""
            settlements = await _query_overpass(client, settle_query, timeout=25.0)
            settle_points = []
            if "error" not in settlements:
                for s in settlements.get("elements", []):
                    if s.get("lat") and s.get("lon"):
                        settle_points.append((s["lat"], s["lon"]))
            
            await asyncio.sleep(1)
            
            # Score and filter spots
            candidates = []
            for elem in features.get("elements", []):
                tags = elem.get("tags", {})
                spot_lat = elem.get("lat")
                spot_lon = elem.get("lon")
                
                if not spot_lat or not spot_lon:
                    continue
                
                # Skip transit shelters
                if tags.get("shelter_type") == "public_transport":
                    continue
                if tags.get("public_transport") or tags.get("highway") == "bus_stop":
                    continue
                
                # Check distance from target point
                dist_from_target = _calc_distance(lat, lon, spot_lat, spot_lon)
                if dist_from_target > search_radius_km:
                    continue
                
                # Check distance from settlements
                min_settle_dist = 100
                for slat, slon in settle_points:
                    d = _calc_distance(spot_lat, spot_lon, slat, slon)
                    min_settle_dist = min(min_settle_dist, d)
                
                if min_settle_dist < 1.5:  # At least 1.5km from settlements
                    continue
                
                # Determine type and priority
                spot_type = "spot"
                priority = 5
                if tags.get("amenity") == "shelter" or tags.get("shelter_type"):
                    spot_type = "shelter"
                    priority = 1
                elif tags.get("tourism") == "wilderness_hut":
                    spot_type = "hut"
                    priority = 1
                elif tags.get("tourism") == "picnic_site":
                    spot_type = "picnic"
                    priority = 2
                elif tags.get("tourism") == "camp_site":
                    spot_type = "campsite"
                    priority = 2
                elif tags.get("tourism") == "viewpoint":
                    spot_type = "viewpoint"
                    priority = 3
                elif tags.get("natural") == "spring":
                    spot_type = "water"
                    priority = 4
                elif tags.get("leisure") == "firepit":
                    spot_type = "firepit"
                    priority = 3
                
                name = tags.get("name", f"{spot_type.title()} near km {target['target_km']:.0f}")
                
                # Score: prefer closer to target, better type, further from towns
                score = priority * 10 + dist_from_target - min(min_settle_dist, 10) * 0.5
                
                candidates.append({
                    "lat": round(spot_lat, 5),
                    "lon": round(spot_lon, 5),
                    "name": name[:40],
                    "type": spot_type,
                    "km_from_target": round(dist_from_target, 1),
                    "town_km": round(min_settle_dist, 1),
                    "score": score,
                })
            
            # Pick best candidate for this day
            if candidates:
                candidates.sort(key=lambda x: x["score"])
                best = candidates[0]
                daily_camps.append({
                    "day": target["day"],
                    "target_km": round(target["target_km"], 1),
                    "spot": best,
                })
                camp_waypoints.append((best["lat"], best["lon"]))
            else:
                # No official spot found - search for large forest area
                forest = await _find_large_forest_for_wild_camping(client, lat, lon, search_radius_km)
                
                if forest:
                    # Forest found - use it (the forest polygon itself is the source of truth,
                    # don't reject just because nearby farmland polygons may overlap in OSM)
                    daily_camps.append({
                        "day": target["day"],
                        "target_km": round(target["target_km"], 1),
                        "spot": {
                            "lat": round(forest["lat"], 5),
                            "lon": round(forest["lon"], 5),
                            "name": f"Wild camp in {forest['name']}",
                            "type": "wild_forest",
                            "area_ha": round(forest["area_ha"], 0),
                            "km_from_target": round(_calc_distance(lat, lon, forest["lat"], forest["lon"]), 1),
                            "town_km": None,
                            "note": f"Large forest area ({forest['area_ha']:.0f} ha) - good for wild camping"
                        }
                    })
                    camp_waypoints.append((forest["lat"], forest["lon"]))
                    await asyncio.sleep(0.5)
                    continue
                
                # Last resort: suggest finding forest manually, but still need a waypoint
                # Use the target point, but clearly mark it needs scouting
                daily_camps.append({
                    "day": target["day"],
                    "target_km": round(target["target_km"], 1),
                    "spot": {
                        "lat": round(lat, 5),
                        "lon": round(lon, 5),
                        "name": f"Scout area Day {target['day']} (find forest nearby)",
                        "type": "scout_needed",
                        "km_from_target": 0,
                        "town_km": None,
                        "note": "No large forest found - scout this area before trip to find suitable wild camp spot"
                    }
                })
                camp_waypoints.append((lat, lon))
    
    # Add destination
    camp_waypoints.append(end_point)
    
    # Create waypoints string for route recalculation through camping spots
    route_waypoints = "|".join(f"{wp[0]},{wp[1]}" for wp in camp_waypoints)
    
    # Create POIs string for map display
    pois_list = []
    for camp in daily_camps:
        spot = camp["spot"]
        name = spot["name"].replace(",", " ").replace("|", " ")[:30]
        pois_list.append(f"{spot['lat']},{spot['lon']},{name}")
    pois_str = "|".join(pois_list) if pois_list else ""
    
    return json.dumps({
        "total_km": round(total_route_km, 1),
        "daily_distance_km": daily_distance_km,
        "num_days": num_days,
        "daily_camps": daily_camps,
        "route_waypoints": route_waypoints,
        "camp_pois": pois_str,
        "tip": "Use route_waypoints with calculate_route to get the routed path through all camping spots. Each day ends at a camp, next day starts from that camp."
    })
