"""Tests for route planning tools."""

import json
import pytest

from src.tools.routing import geocode_location, calculate_route
from src.tools.camping import find_camping_sites
from src.tools.poi import find_points_of_interest
from src.utils.geo import haversine_distance, calculate_bearing


class TestGeoUtils:
    """Test geospatial utility functions."""
    
    def test_haversine_distance_same_point(self):
        """Distance from a point to itself should be 0."""
        dist = haversine_distance(48.1351, 11.5820, 48.1351, 11.5820)
        assert dist == 0
    
    def test_haversine_distance_known_route(self):
        """Test distance calculation for a known route (Munich to Vienna ~400km)."""
        # Munich
        lat1, lon1 = 48.1351, 11.5820
        # Vienna
        lat2, lon2 = 48.2082, 16.3738
        
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        
        # Should be approximately 350-400 km (straight line)
        assert 300 < dist < 450
    
    def test_calculate_bearing(self):
        """Test bearing calculation."""
        # Munich to Vienna should be roughly east (90 degrees)
        bearing = calculate_bearing(48.1351, 11.5820, 48.2082, 16.3738)
        
        # Should be between 70-110 degrees (roughly east)
        assert 70 < bearing < 110


@pytest.mark.asyncio
class TestRoutingTools:
    """Test routing tools (requires API key)."""
    
    @pytest.mark.skip(reason="Requires API key")
    async def test_geocode_location(self):
        """Test geocoding a known location."""
        result = await geocode_location("Munich, Germany")
        data = json.loads(result)
        
        assert "latitude" in data
        assert "longitude" in data
        assert 48.0 < data["latitude"] < 48.3
        assert 11.4 < data["longitude"] < 11.8
    
    @pytest.mark.skip(reason="Requires API key")
    async def test_calculate_route(self):
        """Test route calculation."""
        result = await calculate_route(
            start_lat=48.1351,
            start_lon=11.5820,
            end_lat=48.2082,
            end_lon=16.3738,
            bike_profile="gravel",
        )
        data = json.loads(result)
        
        assert "distance_km" in data
        assert data["distance_km"] > 0


@pytest.mark.asyncio
class TestCampingTools:
    """Test camping finder tools."""
    
    @pytest.mark.skip(reason="Requires network access")
    async def test_find_camping_sites(self):
        """Test finding camping sites near a location."""
        result = await find_camping_sites(
            latitude=48.1351,
            longitude=11.5820,
            radius_km=20.0,
        )
        data = json.loads(result)
        
        assert "camping_sites" in data
        assert "results_count" in data


@pytest.mark.asyncio  
class TestPOITools:
    """Test POI finder tools."""
    
    @pytest.mark.skip(reason="Requires network access")
    async def test_find_pois(self):
        """Test finding points of interest."""
        result = await find_points_of_interest(
            latitude=48.1351,
            longitude=11.5820,
            radius_km=5.0,
            categories=["viewpoint", "water"],
        )
        data = json.loads(result)
        
        assert "pois" in data
        assert "total_results" in data
