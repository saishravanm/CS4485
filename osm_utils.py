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


def query_shelters_near_location(
    lat: float, 
    lon: float, 
    radius_m: int = 5000
) -> list[dict]:
    """
    Query homeless shelters near coordinates using OpenStreetMap Overpass API.
    
    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate
        radius_m: Search radius in meters (default: 5000 = 5km)
    
    Returns:
        List of shelter dictionaries with name, coordinates, address, etc.
        Each dict contains: name, latitude, longitude, address, osm_url
    """
    # Build Overpass query for shelters
    query = f"""
    [out:json][timeout:25];
    (
      node(around:{radius_m},{lat},{lon})["amenity"="shelter"];
      way(around:{radius_m},{lat},{lon})["amenity"="shelter"];
      relation(around:{radius_m},{lat},{lon})["amenity"="shelter"];

      node(around:{radius_m},{lat},{lon})["amenity"="social_facility"]["social_facility"="shelter"];
      way(around:{radius_m},{lat},{lon})["amenity"="social_facility"]["social_facility"="shelter"];
      relation(around:{radius_m},{lat},{lon})["amenity"="social_facility"]["social_facility"="shelter"];

      node(around:{radius_m},{lat},{lon})["social_facility:for"="homeless"];
      way(around:{radius_m},{lat},{lon})["social_facility:for"="homeless"];
      relation(around:{radius_m},{lat},{lon})["social_facility:for"="homeless"];
    );
    out center tags;
    """.strip()

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

        results = []
        for el in data.get("elements", []):
            tags = el.get("tags", {}) or {}

            # Get coordinates for node vs way/relation
            if "lat" in el and "lon" in el:
                el_lat, el_lon = el["lat"], el["lon"]
            else:
                center = el.get("center")
                if not center:
                    continue
                el_lat, el_lon = center["lat"], center["lon"]

            # Build address string from address components
            addr_parts = []
            for k in ("addr:housenumber", "addr:street", "addr:city", "addr:state", "addr:postcode"):
                if k in tags:
                    addr_parts.append(tags[k])
            addr_str = ", ".join(addr_parts) if addr_parts else None

            results.append({
                "name": tags.get("name", "Unnamed Shelter"),
                "latitude": el_lat,
                "longitude": el_lon,
                "address": addr_str,
                "osm_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
            })

        # Deduplicate shelters based on name and coordinates
        seen = set()
        unique = []
        for r in results:
            key = (r["name"], round(float(r["latitude"]), 6), round(float(r["longitude"]), 6))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique
    except Exception as e:
        print(f"Error querying shelters near ({lat}, {lon}): {e}")
        return []

