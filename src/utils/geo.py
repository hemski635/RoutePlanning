"""Geospatial utility functions."""

from math import radians, sin, cos, sqrt, atan2, degrees


def haversine_distance(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    
    Args:
        lat1, lon1: First point coordinates in degrees
        lat2, lon2: Second point coordinates in degrees
    
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


def calculate_bearing(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """
    Calculate the initial bearing from point 1 to point 2.
    
    Args:
        lat1, lon1: Starting point coordinates in degrees
        lat2, lon2: End point coordinates in degrees
    
    Returns:
        Bearing in degrees (0-360)
    """
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    
    x = sin(dlon) * cos(lat2_rad)
    y = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(dlon)
    
    bearing = atan2(x, y)
    bearing = degrees(bearing)
    
    # Normalize to 0-360
    return (bearing + 360) % 360


def point_along_route(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    fraction: float,
) -> tuple[float, float]:
    """
    Calculate a point along the great circle between two points.
    
    Args:
        lat1, lon1: Starting point coordinates in degrees
        lat2, lon2: End point coordinates in degrees
        fraction: Fraction of the distance (0.0 to 1.0)
    
    Returns:
        (latitude, longitude) of the intermediate point
    """
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)
    
    d = haversine_distance(lat1, lon1, lat2, lon2) / 6371  # Angular distance
    
    a = sin((1-fraction) * d) / sin(d)
    b = sin(fraction * d) / sin(d)
    
    x = a * cos(lat1_rad) * cos(lon1_rad) + b * cos(lat2_rad) * cos(lon2_rad)
    y = a * cos(lat1_rad) * sin(lon1_rad) + b * cos(lat2_rad) * sin(lon2_rad)
    z = a * sin(lat1_rad) + b * sin(lat2_rad)
    
    lat = atan2(z, sqrt(x**2 + y**2))
    lon = atan2(y, x)
    
    return (degrees(lat), degrees(lon))


def estimate_cycling_time(
    distance_km: float,
    elevation_gain_m: float = 0,
    average_speed_kmh: float = 20.0,
) -> float:
    """
    Estimate cycling time based on distance and elevation.
    
    Args:
        distance_km: Route distance in kilometers
        elevation_gain_m: Total elevation gain in meters
        average_speed_kmh: Base average speed on flat terrain
    
    Returns:
        Estimated time in hours
    """
    # Base time from distance
    base_time = distance_km / average_speed_kmh
    
    # Add time for climbing (rule of thumb: ~10 min per 100m climbing)
    climbing_time = (elevation_gain_m / 100) * (10 / 60)
    
    return base_time + climbing_time
