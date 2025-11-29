"""
In-memory location store for token-based location requests.
Maps token (UUID string) -> {"lat": float, "lng": float}

This can be swapped for Redis or a database for scaling later.
"""
from typing import Optional, Tuple
from location_tools import geocode_address_google, text_search_places, clear_text_search_cache

# Global in-memory store: token -> {"lat": ..., "lng": ...}
LOCATION_STORE: dict[str, dict[str, float]] = {}

# Session-based location store: session_id -> {"lat": float, "lng": float, "source": str}
SESSION_LOCATIONS: dict[str, dict] = {}


def store_session_location(session_id: str, lat: float, lng: float, source: str = "gps") -> None:
    """Store location for a session (from GPS or geocoding)."""
    SESSION_LOCATIONS[session_id] = {
        "lat": lat,
        "lng": lng,
        "source": source  # "gps" or "geocoded"
    }
    print(f"Stored session location for {session_id}: ({lat}, {lng}) via {source}")


def get_session_location(session_id: str) -> Optional[Tuple[float, float]]:
    """Get stored location for a session. Returns (lat, lng) or None."""
    if session_id in SESSION_LOCATIONS:
        loc = SESSION_LOCATIONS[session_id]
        return (loc["lat"], loc["lng"])
    return None


def clear_session_location(session_id: str) -> None:
    """Clear location for a session (on chat end). Also clears search cache."""
    if session_id in SESSION_LOCATIONS:
        del SESSION_LOCATIONS[session_id]
        print(f"Cleared session location for {session_id}")
    # Clear text search cache when session ends
    clear_text_search_cache()


def geocode_and_store(session_id: str, address: str) -> Optional[Tuple[float, float]]:
    """Geocode an address and store it for the session. Returns (lat, lng) or None."""
    result = geocode_address_google(address)
    if result:
        lat = result["latitude"]
        lng = result["longitude"]
        store_session_location(session_id, lat, lng, source="geocoded")
        return (lat, lng)
    return None


def search_near_session(
    session_id: str,
    query: str,
    radius: int = 5000,
    max_results: int = 10
) -> Optional[list[dict]]:
    """
    Search for places near the session's stored location using natural language query.
    Uses Google Text Search API - accepts queries like "goodwill", "food bank", etc.
    
    Args:
        session_id: The session ID to get location for
        query: Natural language search query (e.g., "goodwill", "food bank")
        radius: Search radius in meters (default 5000)
        max_results: Max results to return (default 10)
    
    Returns:
        List of places or None if no location stored.
    """
    location = get_session_location(session_id)
    if not location:
        return None
    
    lat, lng = location
    results = text_search_places(
        query=query,
        latitude=lat,
        longitude=lng,
        radius=radius,
        max_results=max_results
    )
    return results

