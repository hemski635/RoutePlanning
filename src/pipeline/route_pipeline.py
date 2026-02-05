"""Deterministic route planning pipeline.

This executes the route planning steps WITHOUT needing an LLM for each step.
The LLM only parses the initial intent, then this pipeline runs deterministically.

Pipeline steps:
1. Geocode start/end locations
2. Calculate initial route
3. Find camping spots along route
4. Recalculate route through camping spots
5. Generate output (map URL, summary)
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.tools.routing import geocode_location, calculate_route, calculate_route_with_waypoints
from src.tools.camping import find_daily_camping_spots
from src.tools.export import generate_brouter_web_url

from .intent_parser import RouteIntent


console = Console()


@dataclass
class DayCamp:
    """A single day's camping information."""
    day: int
    target_km: float
    name: str
    type: str
    lat: float
    lon: float
    area_ha: Optional[float] = None
    note: Optional[str] = None


@dataclass
class RoutePlanResult:
    """Complete route planning result."""
    success: bool
    error: Optional[str] = None
    
    # Locations
    start_name: str = ""
    start_coords: tuple[float, float] = None
    end_name: str = ""
    end_coords: tuple[float, float] = None
    
    # Route info
    total_km: float = 0
    num_days: int = 0
    daily_distance_km: float = 0
    profile: str = "trekking"
    
    # Camping
    camps: list[DayCamp] = None
    
    # Output
    map_url: str = ""
    waypoints: str = ""
    
    def __post_init__(self):
        if self.camps is None:
            self.camps = []
    
    def format_summary(self) -> str:
        """Format a human-readable summary of the route."""
        if not self.success:
            return f"❌ Route planning failed: {self.error}"
        
        lines = [
            f"## 🚴 Bike Route: {self.start_name} → {self.end_name}",
            f"",
            f"**Total distance:** {self.total_km:.0f} km over {self.num_days} days",
            f"**Daily target:** ~{self.daily_distance_km:.0f} km/day",
            f"**Profile:** {self.profile}",
            f"",
            "### Daily Itinerary",
            "",
        ]
        
        prev_name = self.start_name
        cumulative_km = 0
        
        for camp in self.camps:
            day_km = camp.target_km - cumulative_km
            lines.append(f"**Day {camp.day}:** {prev_name} → {camp.name}")
            lines.append(f"  - Distance: ~{day_km:.0f} km")
            lines.append(f"  - Camping: {camp.type}")
            if camp.area_ha:
                lines.append(f"  - Forest area: {camp.area_ha:.0f} ha")
            if camp.note:
                lines.append(f"  - Note: {camp.note}")
            lines.append("")
            prev_name = camp.name
            cumulative_km = camp.target_km
        
        # Final day
        final_km = self.total_km - cumulative_km
        lines.append(f"**Day {self.num_days}:** {prev_name} → {self.end_name}")
        lines.append(f"  - Distance: ~{final_km:.0f} km")
        lines.append(f"  - 🏁 Finish!")
        lines.append("")
        
        lines.append("### 🗺️ Interactive Map")
        lines.append(f"[View route with camping spots]({self.map_url})")
        lines.append("")
        lines.append(f"**Direct link:** {self.map_url}")
        
        return "\n".join(lines)


class RoutePlanningPipeline:
    """
    Deterministic pipeline for route planning.
    
    This class executes all route planning steps without needing
    an LLM for reasoning - just direct tool calls in sequence.
    """
    
    def __init__(self, show_progress: bool = True):
        self.show_progress = show_progress
    
    async def execute(self, intent: RouteIntent) -> RoutePlanResult:
        """
        Execute the full route planning pipeline.
        
        Args:
            intent: Parsed route intent with start, end, daily_km, etc.
            
        Returns:
            RoutePlanResult with all route information
        """
        result = RoutePlanResult(
            success=False,
            daily_distance_km=intent.daily_distance_km,
            profile=intent.profile,
        )
        
        if self.show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                return await self._execute_with_progress(intent, result, progress)
        else:
            return await self._execute_steps(intent, result)
    
    async def _execute_with_progress(
        self, 
        intent: RouteIntent, 
        result: RoutePlanResult,
        progress: Progress
    ) -> RoutePlanResult:
        """Execute pipeline with progress display."""
        
        # Step 1: Geocode start
        task = progress.add_task(f"📍 Finding {intent.start_location}...", total=None)
        start_result = await self._geocode(intent.start_location)
        if not start_result:
            result.error = f"Could not find location: {intent.start_location}"
            return result
        result.start_name = start_result["name"]
        result.start_coords = (start_result["lat"], start_result["lon"])
        progress.remove_task(task)
        
        # Step 2: Geocode end
        task = progress.add_task(f"📍 Finding {intent.end_location}...", total=None)
        end_result = await self._geocode(intent.end_location)
        if not end_result:
            result.error = f"Could not find location: {intent.end_location}"
            return result
        result.end_name = end_result["name"]
        result.end_coords = (end_result["lat"], end_result["lon"])
        progress.remove_task(task)
        
        # Step 3: Calculate initial route
        task = progress.add_task("🛤️ Calculating route...", total=None)
        route_result = await self._calculate_route(
            result.start_coords, 
            result.end_coords,
            intent.profile
        )
        if not route_result:
            result.error = "Could not calculate route"
            return result
        progress.remove_task(task)
        
        # Step 4: Find camping spots
        task = progress.add_task("⛺ Finding camping spots...", total=None)
        camping_result = await self._find_camping(
            route_result["waypoints"],
            intent.daily_distance_km
        )
        if not camping_result:
            result.error = "Could not find camping spots"
            return result
        progress.remove_task(task)
        
        # Parse camping results
        result.total_km = camping_result.get("total_km", 0)
        result.num_days = camping_result.get("num_days", 1)
        
        for camp_data in camping_result.get("daily_camps", []):
            spot = camp_data.get("spot", {})
            camp = DayCamp(
                day=camp_data.get("day", 0),
                target_km=camp_data.get("target_km", 0),
                name=spot.get("name", "Unknown"),
                type=spot.get("type", "unknown"),
                lat=spot.get("lat", 0),
                lon=spot.get("lon", 0),
                area_ha=spot.get("area_ha"),
                note=spot.get("note"),
            )
            result.camps.append(camp)
        
        # Step 5: Get final route waypoints (through camps)
        task = progress.add_task("🔄 Finalizing route through camps...", total=None)
        final_waypoints = camping_result.get("route_waypoints", "")
        result.waypoints = final_waypoints
        progress.remove_task(task)
        
        # Step 6: Generate map URL
        task = progress.add_task("🗺️ Generating map...", total=None)
        camp_pois = camping_result.get("camp_pois", "")
        map_result = self._generate_map_url(final_waypoints, intent.profile, camp_pois)
        if map_result:
            result.map_url = map_result.get("map_url", "")
        progress.remove_task(task)
        
        result.success = True
        return result
    
    async def _execute_steps(self, intent: RouteIntent, result: RoutePlanResult) -> RoutePlanResult:
        """Execute pipeline steps without progress display."""
        
        # Step 1-2: Geocode
        start_result = await self._geocode(intent.start_location)
        if not start_result:
            result.error = f"Could not find: {intent.start_location}"
            return result
        result.start_name = start_result["name"]
        result.start_coords = (start_result["lat"], start_result["lon"])
        
        end_result = await self._geocode(intent.end_location)
        if not end_result:
            result.error = f"Could not find: {intent.end_location}"
            return result
        result.end_name = end_result["name"]
        result.end_coords = (end_result["lat"], end_result["lon"])
        
        # Step 3: Route
        route_result = await self._calculate_route(
            result.start_coords, result.end_coords, intent.profile
        )
        if not route_result:
            result.error = "Could not calculate route"
            return result
        
        # Step 4: Camping
        camping_result = await self._find_camping(
            route_result["waypoints"], intent.daily_distance_km
        )
        if not camping_result:
            result.error = "Could not find camping spots"
            return result
        
        result.total_km = camping_result.get("total_km", 0)
        result.num_days = camping_result.get("num_days", 1)
        
        for camp_data in camping_result.get("daily_camps", []):
            spot = camp_data.get("spot", {})
            result.camps.append(DayCamp(
                day=camp_data.get("day", 0),
                target_km=camp_data.get("target_km", 0),
                name=spot.get("name", "Unknown"),
                type=spot.get("type", "unknown"),
                lat=spot.get("lat", 0),
                lon=spot.get("lon", 0),
                area_ha=spot.get("area_ha"),
                note=spot.get("note"),
            ))
        
        # Step 5-6: Final route and map
        result.waypoints = camping_result.get("route_waypoints", "")
        camp_pois = camping_result.get("camp_pois", "")
        map_result = self._generate_map_url(result.waypoints, intent.profile, camp_pois)
        if map_result:
            result.map_url = map_result.get("map_url", "")
        
        result.success = True
        return result
    
    async def _geocode(self, location: str) -> Optional[dict]:
        """Geocode a location name."""
        try:
            result_json = await geocode_location(location)
            result = json.loads(result_json)
            if "error" in result:
                return None
            return result
        except Exception:
            return None
    
    async def _calculate_route(
        self, 
        start: tuple[float, float], 
        end: tuple[float, float],
        profile: str
    ) -> Optional[dict]:
        """Calculate route between two points."""
        try:
            result_json = await calculate_route(
                start_lat=start[0],
                start_lon=start[1],
                end_lat=end[0],
                end_lon=end[1],
                bike_profile=profile,
                include_geometry=True,  # Need geometry for camping spots
            )
            result = json.loads(result_json)
            if "error" in result:
                return None
            
            # Convert geometry to waypoints string for camping function
            # Geometry is in [lon, lat, elevation] format, we need "lat,lon|lat,lon|..."
            geometry = result.get("geometry", {})
            coords = geometry.get("coordinates", [])
            
            if coords:
                # Sample every Nth point to keep waypoints manageable
                # Full routes can have thousands of points
                step = max(1, len(coords) // 100)  # ~100 points max
                sampled = coords[::step]
                if coords[-1] not in sampled:
                    sampled.append(coords[-1])  # Always include endpoint
                
                # coords are [lon, lat, elevation] - we need lat,lon
                waypoints = "|".join(f"{c[1]},{c[0]}" for c in sampled)
                result["waypoints"] = waypoints
            
            return result
        except Exception as e:
            print(f"Route calculation error: {e}")
            return None
    
    async def _find_camping(self, waypoints: str, daily_km: float) -> Optional[dict]:
        """Find camping spots along route."""
        try:
            result_json = await find_daily_camping_spots(waypoints, daily_km)
            result = json.loads(result_json)
            if "error" in result:
                return None
            return result
        except Exception:
            return None
    
    def _generate_map_url(self, waypoints: str, profile: str, pois: str) -> Optional[dict]:
        """Generate brouter-web map URL."""
        try:
            result_json = generate_brouter_web_url(waypoints, profile, 10, pois)
            result = json.loads(result_json)
            if "error" in result:
                return None
            return result
        except Exception:
            return None
