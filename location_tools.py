"""
Location tools for HomeFinder
Handles geocoding (address -> coordinates) using Google Geocoding API
and nearby place search using Google Places API (New)
"""

import os
import json
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try importing googlemaps, fallback to requests if not available
try:
    import googlemaps
    GOOGLEMAPS_AVAILABLE = True
except ImportError:
    GOOGLEMAPS_AVAILABLE = False

# Always import requests for Places API (New) calls
import requests

# Text search cache: (query, lat_rounded, lng_rounded, radius) -> results
# Rounds lat/lng to 3 decimals (~111m precision) for cache hits on nearby locations
_text_search_cache: dict[tuple, list] = {}


def clear_text_search_cache():
    """Clear the text search cache. Call at start of new session if needed."""
    global _text_search_cache
    _text_search_cache = {}


def get_google_api_key() -> Optional[str]:
    """
    Get Google API key from environment variable
    Returns None if not found
    """
    # First try environment variable
    api_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    
    if api_key:
        return api_key
    return None


def geocode_address_google(address: str, api_key: Optional[str] = None) -> Optional[Dict]:
    """
    Convert an address to latitude and longitude using Google Geocoding API
    
    Args:
        address: Full address string (e.g., "123 Main St, Dallas, TX 75201")
        api_key: Google API key (if None, will try to get from env/secrets)
    
    Returns:
        Dictionary with keys: 'latitude', 'longitude', 'formatted_address', 'place_id'
        Returns None if geocoding fails
    """
    if api_key is None:
        api_key = get_google_api_key()
    
    if not api_key:
        raise ValueError("Google API key not found. Set GOOGLE_PLACES_API_KEY or GOOGLE_MAPS_API_KEY in .env")
    
    if GOOGLEMAPS_AVAILABLE:
        # Use googlemaps library (cleaner, but requires: pip install googlemaps)
        try:
            gmaps = googlemaps.Client(key=api_key)
            geocode_result = gmaps.geocode(address)
            
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                return {
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'formatted_address': geocode_result[0]['formatted_address'],
                    'place_id': geocode_result[0].get('place_id'),
                    'address_components': geocode_result[0].get('address_components', [])
                }
        except Exception as e:
            print(f"Error geocoding with googlemaps library: {e}")
            return None
    else:
        # Fallback to direct API call using requests
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': address,
                'key': api_key
            }
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                location = data['results'][0]['geometry']['location']
                return {
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'formatted_address': data['results'][0]['formatted_address'],
                    'place_id': data['results'][0].get('place_id'),
                    'address_components': data['results'][0].get('address_components', [])
                }
            else:
                print(f"Geocoding failed: {data.get('status')} - {data.get('error_message', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"Error geocoding with requests: {e}")
            return None
    
    return None


def text_search_places(
    query: str,
    latitude: float,
    longitude: float,
    radius: int = 5000,
    max_results: int = 10,
    api_key: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Search for places using natural language query near a location.
    Uses Google Places Text Search (New) API - accepts queries like "goodwill", "food bank", etc.
    Results are cached to avoid redundant API calls.
    
    Args:
        query: Natural language search query (e.g., "goodwill", "food bank", "homeless shelter")
        latitude: Center latitude for the search
        longitude: Center longitude for the search
        radius: Search radius in meters (default: 5000)
        max_results: Maximum number of results to return (default: 10, max: 20)
        api_key: Google API key (if None, will try to get from env)
    
    Returns:
        List of place dictionaries, or None if search fails
    """
    global _text_search_cache
    
    if api_key is None:
        api_key = get_google_api_key()
    
    if not api_key:
        raise ValueError("Google API key not found")
    
    # Cap max_results at 20
    if max_results > 20:
        max_results = 20
    
    # Create cache key - normalize query and round coordinates
    cache_key = (
        query.lower().strip(),
        round(latitude, 3),  # ~111m precision
        round(longitude, 3),
        radius,
        max_results
    )
    
    # Check cache first
    if cache_key in _text_search_cache:
        cached = _text_search_cache[cache_key]
        print(f"Cache hit for '{query}' - returning {len(cached)} cached results")
        return cached
    
    # Build the request
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types,places.rating,places.userRatingCount,places.nationalPhoneNumber,places.websiteUri,places.businessStatus"
    }
    
    # Request body with location bias
    body = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": float(radius)
            }
        },
        "maxResultCount": max_results
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if "places" not in data:
            print(f"No places found for query: {query}")
            # Cache empty results to avoid repeated API calls
            _text_search_cache[cache_key] = []
            return []
        
        # Format results
        places = []
        for place in data["places"]:
            place_info = {
                "name": place.get("displayName", {}).get("text"),
                "address": place.get("formattedAddress"),
                "location": place.get("location"),
                "types": place.get("types", []),
                "rating": place.get("rating"),
                "user_rating_count": place.get("userRatingCount"),
                "phone": place.get("nationalPhoneNumber"),
                "website": place.get("websiteUri"),
                "business_status": place.get("businessStatus")
            }
            places.append(place_info)
        
        # Cache successful results
        _text_search_cache[cache_key] = places
        print(f"Text search found {len(places)} places for '{query}' (cached)")
        return places
        
    except requests.exceptions.RequestException as e:
        print(f"Error in text search (network/request error): {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   API Error: {error_data}")
            except:
                print(f"   Response status: {e.response.status_code}")
        return None
    except Exception as e:
        print(f"Error in text search: {e}")
        return None


