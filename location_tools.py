"""
LangChain tools for location-based resource searching using OpenStreetMap.

These tools allow the LLM to:
1. Get cached user location from browser GPS
2. Execute Overpass queries to find resources near a location
"""
import json
import time
import chainlit as cl
from langchain_core.tools import tool
from osm_utils import geocode_address, execute_overpass_query


@tool
def getLocation() -> str:
    """
    Get the user's current location. Checks for cached GPS location from browser first.
    If no cached location is available, returns an error indicating the agent should 
    ask the user for their rough location (city, neighborhood, or address).
    
    Use this tool when you need the user's location for location-based searches.
    If this tool returns a LOCATION_REQUIRED error, you must ask the user for their 
    location before proceeding with location-based queries.
    
    Returns:
        JSON string with location coordinates if available, or error if not.
        Format if available: {"latitude": float, "longitude": float, "source": "browser_gps"}
        Format if unavailable: {"error": "LOCATION_REQUIRED", "message": "...", "suggestion": "..."}
    """
    # Check cache for location
    location = cl.user_session.get("location")
    
    if location:
        return json.dumps({
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "source": location.get("source", "browser_gps")
        })
    else:
        return json.dumps({
            "error": "LOCATION_REQUIRED",
            "message": "No cached location available. The agent should ask the user for their rough location.",
            "suggestion": "Ask the user: 'I'd like to help you find resources nearby. Could you tell me what city or neighborhood you're in? This helps me search for resources close to you.'"
        })


@tool
def executeOverpassQuery(
    overpass_query: str,
    address: str = None,
    latitude: float = None,
    longitude: float = None,
) -> str:
    """
    Execute an Overpass API query to find resources near a location.
    The LLM constructs the Overpass query based on its knowledge of OSM tags.
    
    CRITICAL: You MUST provide location information in one of these ways:
    1. If user provides location in their message (e.g., "Frisco, Texas" or "corner of Main and 1st St"), 
       extract it and pass as the 'address' parameter. The tool will geocode it automatically.
    2. If you have coordinates from getLocation(), pass them as 'latitude' and 'longitude' parameters.
    3. If neither is provided, the tool will check for cached GPS location (may not be available).
    
    The tool handles geocoding if an address is provided, then executes the query.
    The LLM is responsible for constructing valid Overpass QL syntax.
    
    Args:
        overpass_query: Complete Overpass QL query string. Should use {lat} and {lon} 
                       placeholders for coordinates, which will be replaced by the tool.
                       Example: '[out:json][timeout:25];(node(around:5000,{lat},{lon})["amenity"="shelter"];);out center tags;'
        address: REQUIRED if user provided location in their message. Extract location from user's message 
                 and pass here (e.g., "Frisco, TX", "Dallas, Texas", "corner of Main St and 1st Ave, Dallas").
                 The tool will geocode this address to coordinates automatically.
        latitude: Optional latitude coordinate (use with longitude, typically from getLocation())
        longitude: Optional longitude coordinate (use with latitude, typically from getLocation())
    
    IMPORTANT: When user mentions a location in their message (city, address, intersection, etc.), 
               you MUST extract it and pass it as the 'address' parameter. Do NOT just pass the query 
               with placeholders - the tool needs the actual location to work!
    
    Returns:
        JSON string with query results from Overpass API
    """
    # Determine coordinates
    lat = None
    lon = None
    
    # Check for cached location if no explicit input provided
    if not address and not latitude and not longitude:
        location = cl.user_session.get("location")
        if location:
            lat = location["latitude"]
            lon = location["longitude"]
        else:
            return json.dumps({
                "error": "LOCATION_REQUIRED",
                "message": "No location available. The agent should ask the user for their rough location (city, neighborhood, or address).",
                "suggestion": "Ask the user: 'I'd like to help you find resources nearby. Could you tell me what city or neighborhood you're in? This helps me search for resources close to you.'"
            })
    elif address:
        # Geocode address
        lat, lon = geocode_address(address)
        if not lat or not lon:
            return json.dumps({
                "error": "GEOCODING_FAILED",
                "message": f"Could not geocode address: {address}. Please try a different format or be more specific."
            })
        # Polite delay for OSM rate limiting
        time.sleep(1)
    else:
        lat, lon = latitude, longitude
    
    # Replace coordinate placeholders in query
    query = overpass_query.replace("{lat}", str(lat)).replace("{lon}", str(lon))
    
    # Execute Overpass query
    results = execute_overpass_query(query)
    
    # Return results as JSON string
    return json.dumps(results)

