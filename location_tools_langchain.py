"""
Simplified location handling - AI only extracts resource type.
Location, geocoding, and Places API calls are handled automatically.
"""

from typing import Optional
import chainlit as cl
from location_store import (
    get_session_location,
    store_session_location,
    geocode_and_store,
    search_near_session
)
from location_request import get_user_location

# Session state tracking: session_id -> {"gps_requested": bool, "gps_failed": bool, "pending_query": str}
_session_state: dict[str, dict] = {}


def get_session_state(session_id: str) -> dict:
    """Get or create session state."""
    if session_id not in _session_state:
        _session_state[session_id] = {
            "gps_requested": False,
            "gps_failed": False,
            "pending_query": None  # Store the original query when waiting for address
        }
    return _session_state[session_id]


def reset_location_state(session_id: Optional[str] = None):
    """Reset location state. If session_id provided, reset just that session."""
    global _session_state
    if session_id:
        if session_id in _session_state:
            del _session_state[session_id]
    else:
        _session_state = {}


async def ensure_location(session_id: str, user_address: Optional[str] = None) -> dict:
    """
    Ensure we have a location for the session.
    - If user provided address, geocode it
    - If no location stored, request GPS
    - Returns {"status": "success/error/need_address", "lat": ..., "lng": ..., "message": ...}
    """
    state = get_session_state(session_id)
    
    # If user provided an address, geocode it
    if user_address:
        result = geocode_and_store(session_id, user_address)
        if result:
            # Clear the pending query since we now have location
            state["pending_query"] = None
            return {
                "status": "success",
                "lat": result[0],
                "lng": result[1],
                "source": "geocoded"
            }
        else:
            return {
                "status": "error",
                "message": f"Couldn't find location for '{user_address}'. Try a more specific address."
            }
    
    # Check if we already have a location stored
    existing = get_session_location(session_id)
    if existing:
        return {
            "status": "success",
            "lat": existing[0],
            "lng": existing[1],
            "source": "stored"
        }
    
    # If GPS already failed, don't try again
    if state["gps_failed"]:
        return {
            "status": "need_address",
            "message": "I couldn't access your GPS. Could you share a rough location like a neighborhood, intersection, or landmark?"
        }
    
    # Try to get GPS location
    if not state["gps_requested"]:
        state["gps_requested"] = True
        result = await get_user_location(timeout=15)
        if result:
            lat, lng = result
            store_session_location(session_id, lat, lng, source="gps")
            return {
                "status": "success",
                "lat": lat,
                "lng": lng,
                "source": "gps"
            }
        else:
            state["gps_failed"] = True
            return {
                "status": "need_address",
                "message": "I couldn't access your GPS - no worries! Could you share a rough location like a neighborhood, intersection, or landmark?"
            }
    
    # GPS was requested but we don't have a result yet
    return {
        "status": "need_address",
        "message": "I need a location to search. Could you share a rough location like a neighborhood, intersection, or landmark?"
    }


def set_pending_query(session_id: str, query: str):
    """Store the pending search query while waiting for address."""
    state = get_session_state(session_id)
    state["pending_query"] = query


def get_pending_query(session_id: str) -> Optional[str]:
    """Get the pending search query (if waiting for address)."""
    state = get_session_state(session_id)
    return state.get("pending_query")


def is_waiting_for_address(session_id: str) -> bool:
    """Check if we're waiting for the user to provide an address."""
    state = get_session_state(session_id)
    return state["gps_failed"] and state["pending_query"] is not None


def search_resources(
    session_id: str,
    query: str,
    radius: int = 5000,
    max_results: int = 10
) -> dict:
    """
    Search for resources near the session's stored location using natural language.
    Uses Google Text Search API - no type mapping needed, just pass the query directly.
    
    Args:
        session_id: Session ID to get location for
        query: Natural language query (e.g., "goodwill", "food bank", "homeless shelter")
        radius: Search radius in meters
        max_results: Max results to return
    
    Returns:
        Formatted results dict with status, count, places
    """
    if not query:
        query = "resources"  # Default fallback
    
    # Search using natural language query - no mapping needed!
    results = search_near_session(
        session_id=session_id,
        query=query,
        radius=radius,
        max_results=max_results
    )
    
    if results is None:
        return {
            "status": "error",
            "message": "No location stored. Please share your location first."
        }
    
    if not results:
        return {
            "status": "no_results",
            "message": f"No results found for '{query}' nearby. Try a different search term or expand your search area."
        }
    
    # Format results
    places = []
    for place in results:
        places.append({
            "name": place.get("name"),
            "address": place.get("address"),
            "phone": place.get("phone"),
            "website": place.get("website"),
            "rating": place.get("rating"),
            "types": place.get("types", [])[:3],
            "status": place.get("business_status")
        })
    
    return {
        "status": "success",
        "count": len(places),
        "query": query,
        "places": places
    }


def format_results_for_user(results: dict) -> str:
    """Format search results as a readable string for the AI to present."""
    if results["status"] == "error":
        return results["message"]
    
    if results["status"] == "no_results":
        return results["message"]
    
    if results["status"] != "success":
        return "Something went wrong with the search."
    
    places = results["places"]
    query = results.get("query", "places")
    
    output = f"Found {len(places)} results for '{query}' nearby:\n\n"
    
    for i, place in enumerate(places, 1):
        output += f"**{i}. {place['name']}**\n"
        if place.get('address'):
            output += f"   📍 {place['address']}\n"
        if place.get('phone'):
            output += f"   📞 {place['phone']}\n"
        if place.get('website'):
            output += f"   🌐 {place['website']}\n"
        if place.get('rating'):
            output += f"   ⭐ {place['rating']}/5\n"
        output += "\n"
    
    return output
