"""
LangChain tool wrappers for location functionality.
- get_user_location_tool: Get GPS from browser
- geocode_address_tool: Convert address text to coordinates
- search_nearby_tool: Search for places near coordinates
"""

from langchain.tools import tool
from location_request import get_user_location
from location_tools import geocode_address_google, search_nearby_places
import json
from typing import Optional, List

# Cache to prevent repeated calls in same session
# None = not called yet, dict with status = cached result
_last_location_result = None
_location_success = False  # Track if we got a successful result

# Geocode cache: address -> result (to avoid repeated API calls)
_geocode_cache: dict[str, str] = {}

# Nearby search cache: (lat, lng, radius, types_tuple, rank_by) -> result
_nearby_cache: dict[tuple, str] = {}


_GPS_FAILED_USER_MESSAGE = """I wasn't able to access your GPS location - no worries though! 

Could you share a rough location so I can find resources near you? It doesn't have to be exact - any of these work:
- A neighborhood (like "Oak Cliff" or "Deep Ellum")
- A nearby intersection (like "Main and Elm")
- A landmark (like "near the library" or "by Fair Park")

Just let me know the general area and I'll help you find what you need!"""

@tool
async def get_user_location_tool() -> str:
    """
    Get the user's current GPS coordinates from their browser.
    Use this ONCE when the user asks for resources 'near me', 'nearby', 'closest', 
    or needs location-based results. Returns JSON with latitude and longitude.
    After receiving coordinates, DO NOT call this tool again - use the coordinates 
    to search for resources or respond to the user.
    """
    global _last_location_result, _location_success
    
    # If we already got a successful result, tell LLM to stop calling
    if _last_location_result is not None and _location_success:
        coords = json.loads(_last_location_result)
        return f"SUCCESS. Coordinates: Latitude {coords['latitude']}, Longitude {coords['longitude']}. DO NOT call this tool again."
    
    # If previous call failed (denied/timeout), return the hardcoded user message
    if _last_location_result is not None and not _location_success:
        return f"ALREADY_FAILED. Display this message to user exactly:\n\n{_GPS_FAILED_USER_MESSAGE}"
    
    result = await get_user_location(timeout=15)
    
    if result:
        lat, lng = result
        _last_location_result = json.dumps({"status": "success", "latitude": lat, "longitude": lng})
        _location_success = True
        return f"SUCCESS. Coordinates: Latitude {lat}, Longitude {lng}. Use these to search for resources."
    else:
        _last_location_result = "failed"
        _location_success = False
        return f"GPS_FAILED. Display this message to user exactly:\n\n{_GPS_FAILED_USER_MESSAGE}"


def reset_location_cache():
    """Call this at start of new chat session to reset the cache."""
    global _last_location_result, _location_success, _geocode_cache, _nearby_cache
    _last_location_result = None
    _location_success = False
    _geocode_cache = {}
    _nearby_cache = {}


@tool
def geocode_address_tool(address: str) -> str:
    """
    Convert a street address or location name to GPS coordinates.
    Use this ONCE when the user provides an address, city name, or landmark.
    Example inputs: "123 Main St, Dallas, TX", "downtown Fort Worth", "Love Field Airport"
    Returns JSON with latitude, longitude, and formatted address.
    After receiving coordinates, DO NOT call this tool again - use the coordinates to search.
    """
    global _geocode_cache
    
    if not address or not address.strip():
        return json.dumps({"status": "error", "message": "No address provided"})
    
    # Normalize address for cache lookup
    cache_key = address.strip().lower()
    
    # Check cache first
    if cache_key in _geocode_cache:
        cached = _geocode_cache[cache_key]
        # Return with a clear "already have this" message
        return f"ADDRESS ALREADY GEOCODED. STOP CALLING THIS TOOL. Use these coordinates: {cached}"
    
    try:
        result = geocode_address_google(address.strip())
        
        if result:
            response = json.dumps({
                "status": "success",
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "formatted_address": result.get("formatted_address", address)
            })
            # Cache the successful result
            _geocode_cache[cache_key] = response
            return response
        else:
            error_response = json.dumps({
                "status": "error",
                "message": f"Could not find coordinates for '{address}'. Ask user to provide a more specific address."
            })
            # Cache errors too to prevent repeated failed lookups
            _geocode_cache[cache_key] = error_response
            return error_response
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Geocoding error: {str(e)}"
        })


@tool
def search_nearby_tool(
    latitude: float,
    longitude: float,
    place_types: Optional[str] = None,
    radius: int = 5000,
    max_results: int = 10
) -> str:
    """
    Search for places near a location using Google Places API.
    
    Args:
        latitude: Center latitude (required)
        longitude: Center longitude (required)
        place_types: Comma-separated place types to search for (e.g. "shelter,food_bank,hospital")
                    Common types: shelter, food_bank, hospital, pharmacy, social_services, church
                    If not provided, returns all nearby places.
        radius: Search radius in meters (default 5000, max 50000)
        max_results: Maximum results to return (default 10, max 20)
    
    Returns JSON with list of places including name, address, phone, website, rating.
    """
    global _nearby_cache
    
    # Parse place_types string to list
    types_list = None
    if place_types:
        types_list = [t.strip() for t in place_types.split(",") if t.strip()]
    
    # Create cache key - round lat/lng to 4 decimals (~11m precision) to catch near-identical queries
    cache_key = (
        round(latitude, 4),
        round(longitude, 4),
        radius,
        tuple(sorted(types_list)) if types_list else None,
    )
    
    # Check cache
    if cache_key in _nearby_cache:
        return f"SEARCH ALREADY PERFORMED. Use these results: {_nearby_cache[cache_key]}"
    
    try:
        results = search_nearby_places(
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            included_types=types_list,
            max_results=max_results,
            rank_by="DISTANCE"
        )
        
        if results:
            # Format results for LLM
            places = []
            for place in results:
                places.append({
                    "name": place.get("name"),
                    "address": place.get("address"),
                    "phone": place.get("phone"),
                    "website": place.get("website"),
                    "rating": place.get("rating"),
                    "types": place.get("types", [])[:3],  # Limit types shown
                    "status": place.get("business_status")
                })
            
            response = json.dumps({
                "status": "success",
                "count": len(places),
                "places": places
            })
            _nearby_cache[cache_key] = response
            return response
        else:
            error_response = json.dumps({
                "status": "error",
                "message": f"No places found near ({latitude}, {longitude}) with the specified filters."
            })
            _nearby_cache[cache_key] = error_response
            return error_response
            
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Nearby search error: {str(e)}"
        })
