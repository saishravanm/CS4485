"""
OpenStreetMap utility functions for geocoding and shelter queries.
Extracted from lambda-function.py for use in HomeFinder chatbot.
"""
import json
import time
import urllib.parse
import urllib.request

# OSM API endpoints
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT_BASE = "HomeFinder/1.0 (contact: homefinder@example.com)"


def _http_get(url, params=None, headers=None, timeout=20):
    """
    HTTP GET request helper.
    
    Args:
        url: URL to request
        params: Optional query parameters dict
        headers: Optional headers dict
        timeout: Request timeout in seconds
    
    Returns:
        Response body as bytes
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_post(url, data_str, headers=None, timeout=60):
    """
    HTTP POST request helper.
    
    Args:
        url: URL to request
        data_str: POST data as string
        headers: Optional headers dict
        timeout: Request timeout in seconds
    
    Returns:
        Response body as bytes
    """
    data = data_str.encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def geocode_address(address: str) -> tuple[float, float] | tuple[None, None]:
    """
    Geocode an address to coordinates using OpenStreetMap Nominatim API.
    
    Args:
        address: Address string (e.g., "Dallas, TX" or "1201 E 9th St, Dallas")
    
    Returns:
        Tuple of (latitude, longitude) or (None, None) if geocoding fails
    """
    headers = {"User-Agent": USER_AGENT_BASE}
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    }
    
    try:
        raw = _http_get(NOMINATIM_URL, params=params, headers=headers, timeout=25)
        data = json.loads(raw.decode("utf-8"))
        if not data:
            return None, None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Error geocoding address '{address}': {e}")
        return None, None


def execute_overpass_query(query: str) -> dict:
    """
    Execute an Overpass API query and return results.
    
    The query should already have coordinates filled in (no placeholders).
    This is a general-purpose function that executes any valid Overpass QL query.
    
    Args:
        query: Complete Overpass QL query string (should already have coordinates)
    
    Returns:
        Dictionary with Overpass API response, typically containing 'elements' list
        Returns empty dict on error
    """
    headers = {
        "User-Agent": USER_AGENT_BASE,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        raw = _http_post(
            OVERPASS_URL,
            f"data={urllib.parse.quote_plus(query)}",
            headers=headers,
            timeout=60
        )
        data = json.loads(raw.decode("utf-8"))
        return data
    except Exception as e:
        print(f"Error executing Overpass query: {e}")
        return {}

