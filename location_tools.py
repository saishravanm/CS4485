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


def search_nearby_places(
    latitude: float,
    longitude: float,
    radius: int = 5000,
    included_types: Optional[List[str]] = None,
    max_results: int = 20,
    rank_by: str = "DISTANCE",
    api_key: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    Search for places near a location using Google Places API (New) nearby search endpoint.
    
    Args:
        latitude: Center latitude for the search
        longitude: Center longitude for the search
        radius: Search radius in meters (max 50,000, default: 5000)
        included_types: Optional list of place types to filter (e.g., ["shelter", "food_bank"])
                       If None, returns all types. See: https://developers.google.com/maps/documentation/places/web-service/place-types
        max_results: Maximum number of results to return (default: 20, max: 20)
        rank_by: How to rank results - "DISTANCE" or "POPULARITY" (default: "DISTANCE")
        api_key: Google API key (if None, will try to get from env)
    
    Returns:
        List of dictionaries, each containing:
        - place_id: Google place ID
        - name: Place name
        - address: Formatted address
        - location: Dict with 'latitude' and 'longitude'
        - types: List of place types
        - rating: Rating (if available)
        - user_rating_count: Number of ratings (if available)
        - phone: Phone number (if available)
        - website: Website URL (if available)
        - business_status: Business status (OPERATIONAL, CLOSED_PERMANENTLY, etc.)
        Returns None if search fails
    """
    if api_key is None:
        api_key = get_google_api_key()
    
    if not api_key:
        raise ValueError("Google API key not found. Set GOOGLE_PLACES_API_KEY or GOOGLE_MAPS_API_KEY in .env")
    
    # Validate radius
    if radius > 50000:
        radius = 50000
        print(f"⚠️ Radius capped at 50,000 meters (max allowed)")
    
    # Validate max_results
    if max_results > 20:
        max_results = 20
        print(f"⚠️ Max results capped at 20 (max allowed)")
    
    # Validate rank_by
    if rank_by not in ["DISTANCE", "POPULARITY"]:
        rank_by = "DISTANCE"
        print(f"⚠️ Invalid rank_by, using 'DISTANCE'")
    
    url = "https://places.googleapis.com/v1/places:searchNearby"
    
    # Field mask specifies which fields to return (required by Places API New)
    # Using '*' for all fields, or specify specific fields like:
    # "places.id,places.displayName,places.formattedAddress,places.location,places.types,places.rating,places.userRatingCount,places.nationalPhoneNumber,places.websiteUri,places.businessStatus,places.priceLevel"
    field_mask = "places.id,places.displayName,places.formattedAddress,places.location,places.types,places.rating,places.userRatingCount,places.nationalPhoneNumber,places.websiteUri,places.businessStatus,places.priceLevel"
    
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
        "Content-Type": "application/json"
    }
    
    # Build request body
    body = {
        "maxResultCount": max_results,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": float(radius)
            }
        },
        "rankPreference": rank_by
    }
    
    # Add included types if provided
    if included_types:
        body["includedTypes"] = included_types
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        places = []
        for place in data.get("places", []):
            # Extract location
            location_data = place.get("location", {})
            location = None
            if location_data:
                location = {
                    "latitude": location_data.get("latitude"),
                    "longitude": location_data.get("longitude")
                }
            
            # Extract display name
            display_name = place.get("displayName", {})
            name = display_name.get("text") if isinstance(display_name, dict) else str(display_name) if display_name else None
            
            place_dict = {
                "place_id": place.get("id"),
                "name": name,
                "address": place.get("formattedAddress"),
                "location": location,
                "types": place.get("types", []),
                "rating": place.get("rating"),
                "user_rating_count": place.get("userRatingCount"),
                "phone": place.get("nationalPhoneNumber"),
                "website": place.get("websiteUri"),
                "business_status": place.get("businessStatus"),
                "price_level": place.get("priceLevel")  # PRICE_LEVEL_FREE, PRICE_LEVEL_INEXPENSIVE, etc.
            }
            
            places.append(place_dict)
        
        return places
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error searching nearby places (network/request error): {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   API Error: {error_data}")
            except:
                print(f"   Response status: {e.response.status_code}")
        return None
    except Exception as e:
        print(f"❌ Error searching nearby places: {e}")
        return None


if __name__ == "__main__":
    """
    Test script for location_tools functions
    """
    print("=" * 60)
    print("Testing location_tools.py functions")
    print("=" * 60)
    
    # Test 1: Check API key
    print("\n[Test 1] Checking API key...")
    api_key = get_google_api_key()
    if api_key:
        print(f"✅ API key found: {api_key[:10]}...")
    else:
        print("❌ API key not found!")
        print("   Set GOOGLE_PLACES_API_KEY or GOOGLE_MAPS_API_KEY in .env")
        exit(1)
    
    # Test 2: Geocode an address
    print("\n[Test 2] Testing geocode_address_google...")
    test_address = "Dallas, TX"
    print(f"   Geocoding: {test_address}")
    geocode_result = geocode_address_google(test_address)
    if geocode_result:
        print(f"✅ Geocoding successful:")
        print(f"   Address: {geocode_result.get('formatted_address')}")
        print(f"   Location: ({geocode_result.get('latitude')}, {geocode_result.get('longitude')})")
        test_lat = geocode_result.get('latitude')
        test_lng = geocode_result.get('longitude')
    else:
        print("❌ Geocoding failed!")
        # Use default Dallas coordinates for nearby search test
        test_lat = 32.7767
        test_lng = -96.7970
        print(f"   Using default coordinates: ({test_lat}, {test_lng})")
    
    # Test 3: Nearby search - all types
    print("\n[Test 3] Testing search_nearby_places (all types, 1km radius)...")
    print(f"   Searching near: ({test_lat}, {test_lng})")
    nearby_results = search_nearby_places(
        latitude=test_lat,
        longitude=test_lng,
        radius=1000,  # 1km
        max_results=5
    )
    if nearby_results:
        print(f"✅ Found {len(nearby_results)} places:")
        for i, place in enumerate(nearby_results[:3], 1):  # Show first 3
            print(f"   {i}. {place.get('name')} - {place.get('address', 'No address')}")
            if place.get('types'):
                print(f"      Types: {', '.join(place.get('types', [])[:3])}")
    else:
        print("❌ Nearby search failed!")
    
    # Test 4: Nearby search - filtered by type
    print("\n[Test 4] Testing search_nearby_places (filtered by type: 'hospital')...")
    nearby_hospitals = search_nearby_places(
        latitude=test_lat,
        longitude=test_lng,
        radius=5000,  # 5km
        included_types=["hospital"],
        max_results=5
    )
    if nearby_hospitals:
        print(f"✅ Found {len(nearby_hospitals)} hospitals:")
        for i, place in enumerate(nearby_hospitals[:3], 1):
            print(f"   {i}. {place.get('name')} - {place.get('address', 'No address')}")
    else:
        print("❌ Hospital search failed!")
    
    # Test 5: Nearby search - ranked by popularity
    print("\n[Test 5] Testing search_nearby_places (ranked by popularity)...")
    popular_places = search_nearby_places(
        latitude=test_lat,
        longitude=test_lng,
        radius=2000,
        max_results=5,
        rank_by="POPULARITY"
    )
    if popular_places:
        print(f"✅ Found {len(popular_places)} popular places:")
        for i, place in enumerate(popular_places[:3], 1):
            rating = place.get('rating', 'N/A')
            print(f"   {i}. {place.get('name')} (Rating: {rating})")
    else:
        print("❌ Popular places search failed!")
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)

