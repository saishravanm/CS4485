# Location Integration Plan - OpenStreetMap Tool Implementation

## Overview

The goal is to integrate OpenStreetMap functionality from `lambda-function.py` to help users find shelters and resources near their location. The system uses a **two-tool approach**: `getLocation()` for location retrieval and `findSheltersNearLocation()` for shelter searching. The browser automatically tries to get GPS location first, and the LLM only asks the user if location is unavailable.

---

## Architecture Overview

### Core Design Principles

1. **Separation of Concerns**: Location retrieval (`getLocation()`) is separate from shelter searching (`findSheltersNearLocation()`)
2. **Browser-First Approach**: Browser automatically requests GPS on page load
3. **LLM Handles Fallback**: If GPS unavailable, LLM conversationally asks user for rough location
4. **Cache Once, Use Many**: Location checked once in `getLocation()`, then reused by other tools

### Location Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Browser (location.js) - Automatic on Page Load              │
├─────────────────────────────────────────────────────────────┤
│ 1. Requests GPS location via navigator.geolocation          │
│ 2. If successful:                                           │
│    → Sends to backend via Chainlit                          │
│    → Stored in cl.user_session["location"]                  │
│ 3. If failed:                                               │
│    → Location box shows error                               │
│    → Nothing stored in session                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ When LLM Needs Location                                     │
├─────────────────────────────────────────────────────────────┤
│ 1. LLM calls getLocation() tool                             │
│ 2. getLocation() checks cache:                              │
│    → If cached: Returns coordinates                         │
│    → If NOT cached: Returns LOCATION_REQUIRED error         │
│ 3. If LOCATION_REQUIRED:                                    │
│    → LLM asks user: "What city/neighborhood are you in?"    │
│    → User provides location                                 │
│    → LLM can use location for tools that need it            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ When LLM Needs to Find Shelters                             │
├─────────────────────────────────────────────────────────────┤
│ 1. LLM calls findSheltersNearLocation() with location       │
│ 2. Tool geocodes address if needed                          │
│ 3. Tool queries OSM for shelters                            │
│ 4. Returns formatted results                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Strategy

### Phase 1: Extract OSM Functions from lambda-function.py

**Location**: Add to `homefinder.py`

**Functions to Port**:

1. **HTTP Helpers**:
```python
def _http_get(url, params=None, headers=None, timeout=20):
    """HTTP GET request helper"""
    
def _http_post(url, data_str, headers=None, timeout=60):
    """HTTP POST request helper"""
```

2. **Geocoding Function**:
```python
def geocode_address(address: str) -> tuple[float, float] | tuple[None, None]:
    """
    Geocode an address to coordinates using OpenStreetMap Nominatim API.
    
    Args:
        address: Address string (e.g., "Dallas, TX" or "1201 E 9th St, Dallas")
    
    Returns:
        Tuple of (latitude, longitude) or (None, None) if geocoding fails
    """
    # Port from lambda-function.py _geocode_address()
    # Uses Nominatim API
    # Requires User-Agent header
    # Handles rate limiting (1 request/second)
```

3. **Shelter Query Function**:
```python
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
    """
    # Port from lambda-function.py _query_shelters()
    # Uses Overpass API
    # Queries for: amenity=shelter, social_facility=shelter, social_facility:for=homeless
    # Returns deduplicated list
```

**Key Implementation Details**:
- **User-Agent**: Required for Nominatim (use project identifier)
- **Rate Limiting**: 1 second delay between Nominatim requests
- **Timeouts**: 20-30 seconds for API calls
- **Error Handling**: Return None/empty list on failure, don't raise exceptions
- **Constants**: 
  - `NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"`
  - `OVERPASS_URL = "https://overpass-api.de/api/interpreter"`
  - `USER_AGENT = "HomeFinder/1.0 (contact: your-email@example.com)"`

---

### Phase 2: Location Storage & Browser Integration

**Location Storage Format**:
```python
cl.user_session["location"] = {
    "latitude": float,      # e.g., 32.776665
    "longitude": float,     # e.g., -96.796989
    "timestamp": datetime,  # When location was obtained
    "source": "browser_gps" # How location was obtained
}
```

**Browser Integration (location.js)**:
- Already requests GPS on page load
- **New**: When location is successfully obtained, send to backend
- **Method**: Research Chainlit's frontend-to-backend communication
  - Option A: Custom Chainlit action
  - Option B: Chainlit's built-in session API (if available)
  - Option C: Store in localStorage and read on first message

**Backend Handler**:
```python
# In homefinder.py
@cl.action_callback("set_location")  # If using actions
async def on_set_location(action):
    """Store location from browser in user session"""
    cl.user_session.set("location", {
        "latitude": action.payload["latitude"],
        "longitude": action.payload["longitude"],
        "timestamp": datetime.now(),
        "source": "browser_gps"
    })
```

---

### Phase 3: Create getLocation() Tool

**Tool Purpose**: Check for cached location. If unavailable, return error that prompts LLM to ask user.

**Tool Implementation**:
```python
from langchain_core.tools import tool
import json

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
    # Check cache
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
```

**Key Points**:
- **Single Responsibility**: Only checks cache, doesn't query APIs
- **Clear Error Format**: Structured JSON that LLM can parse
- **Suggestion Included**: Helps LLM know how to ask user
- **No Side Effects**: Doesn't modify session or make external calls

---

### Phase 4: Create findSheltersNearLocation() Tool

**Tool Purpose**: Find shelters near a location. Requires location as input (coordinates or address).

**Tool Implementation**:
```python
from langchain_core.tools import tool
import json
import time

@tool
def findSheltersNearLocation(
    latitude: float = None,
    longitude: float = None,
    address: str = None,
    radius_km: float = 5.0
) -> str:
    """
    Find homeless shelters near a location using OpenStreetMap data.
    
    This tool requires either coordinates (latitude/longitude) OR an address string.
    If an address is provided, it will be geocoded to coordinates first.
    The tool then searches OpenStreetMap for shelters within the specified radius.
    
    Use this tool when the user asks for shelters or resources "near me" or near a 
    specific location. You should call getLocation() first to check for cached location,
    or ask the user for their location if getLocation() returns LOCATION_REQUIRED.
    
    Args:
        latitude: Latitude coordinate (use with longitude, not address)
        longitude: Longitude coordinate (use with latitude, not address)
        address: Address string (e.g., "Dallas, TX", "1201 E 9th St, Dallas", "Oak Cliff")
        radius_km: Search radius in kilometers (default: 5.0)
    
    Returns:
        JSON string with list of shelters found, including name, coordinates, address, etc.
    """
    # Validate input
    if not address and (not latitude or not longitude):
        return json.dumps({
            "error": "INVALID_INPUT",
            "message": "Either address or both latitude and longitude must be provided."
        })
    
    # Geocode if address provided
    if address:
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
    
    # Query shelters
    radius_m = int(radius_km * 1000)
    shelters = query_shelters_near_location(lat, lon, radius_m)
    
    # Format results
    return json.dumps({
        "count": len(shelters),
        "shelters": shelters,
        "search_location": {
            "latitude": lat,
            "longitude": lon,
            "address": address if address else None
        },
        "radius_km": radius_km
    })
```

**Key Points**:
- **Requires Location Input**: Doesn't check cache itself - relies on LLM to get location first
- **Flexible Input**: Accepts coordinates OR address
- **Geocoding Built-in**: Handles address-to-coordinates conversion
- **Rate Limiting**: Includes delay between geocoding and shelter query
- **Structured Output**: Returns JSON that LLM can format for user

---

### Phase 5: Agent Integration

**Add Tools to Agent**:
```python
# In @cl.on_chat_start
tools = []
tools.append(kb_tool)
tools.append(search_tool)
tools.append(getLocation)  # Add location retrieval tool
tools.append(findSheltersNearLocation)  # Add shelter search tool
```

**Agent Prompt Modification**:
Add to system prompt:
```
You have access to location-based tools:

1. getLocation() - Check if user's location is cached from browser GPS. 
   - If location is available, returns coordinates
   - If not available, returns LOCATION_REQUIRED error
   - When you see LOCATION_REQUIRED, you MUST ask the user for their location

2. findSheltersNearLocation() - Find shelters near a location using OpenStreetMap.
   - Requires location as input (coordinates or address)
   - Call getLocation() first to check for cached location
   - If getLocation() returns LOCATION_REQUIRED, ask user for location first

When user asks for shelters/resources "near me" or location-based queries:
1. First call getLocation() to check for cached location
2. If getLocation() returns coordinates, use them with findSheltersNearLocation()
3. If getLocation() returns LOCATION_REQUIRED, ask user empathetically:
   "I'd like to help you find shelters nearby. Could you tell me what city or 
   neighborhood you're in? This helps me search for resources close to you."
4. After user provides location, call findSheltersNearLocation() with the location
5. Format results using the resource_format template

Be warm and empathetic when asking for location. Accept flexible input like city names, 
neighborhoods, or addresses. If geocoding fails, ask user to try a different format.
```

---

## Complete Data Flow Examples

### Scenario 1: User asks "Find shelters near me" (GPS location cached)

1. **Browser**: Already obtained GPS location, stored in `cl.user_session["location"]`
2. **User**: "Find shelters near me"
3. **LLM**: Calls `getLocation()`
4. **getLocation()**: Returns `{"latitude": 32.776665, "longitude": -96.796989, "source": "browser_gps"}`
5. **LLM**: Calls `findSheltersNearLocation(latitude=32.776665, longitude=-96.796989)`
6. **findSheltersNearLocation()**: 
   - Queries OSM for shelters within 5km
   - Returns list of shelters
7. **LLM**: Formats results using `resource_format` and responds to user

### Scenario 2: User asks "Find shelters near me" (NO GPS location)

1. **Browser**: GPS request failed or denied, nothing stored in session
2. **User**: "Find shelters near me"
3. **LLM**: Calls `getLocation()`
4. **getLocation()**: Returns `{"error": "LOCATION_REQUIRED", "message": "...", "suggestion": "..."}`
5. **LLM**: Detects LOCATION_REQUIRED error and asks user:
   - "I'd like to help you find shelters nearby. Could you tell me what city or neighborhood you're in? This helps me search for resources close to you."
6. **User**: "I'm in Dallas, near downtown"
7. **LLM**: Extracts location from user message and calls `findSheltersNearLocation(address="Dallas, near downtown")`
8. **findSheltersNearLocation()**:
   - Geocodes "Dallas, near downtown" → gets coordinates
   - Queries OSM for shelters
   - Returns list of shelters
9. **LLM**: Formats results and responds to user

### Scenario 3: User provides address in message

1. **User**: "Find shelters near 1201 E 9th St, Dallas"
2. **LLM**: Extracts address from message
3. **LLM**: Calls `findSheltersNearLocation(address="1201 E 9th St, Dallas")`
4. **findSheltersNearLocation()**:
   - Geocodes address → gets coordinates
   - Queries OSM for shelters
   - Returns results
5. **LLM**: Formats and responds

### Scenario 4: User asks general question, then location-based question

1. **User**: "What services do you provide?"
2. **LLM**: Responds about services (no location needed)
3. **User**: "Now find shelters near me"
4. **LLM**: Calls `getLocation()` (location still cached from page load)
5. **LLM**: Uses cached location with `findSheltersNearLocation()`
6. **LLM**: Returns results

---

## Error Handling & Edge Cases

### 1. **No Location Available (LOCATION_REQUIRED)**
- **Handled by**: `getLocation()` returns structured error
- **LLM Action**: Ask user for location empathetically
- **User Input Accepted**: City, neighborhood, address, area description
- **Follow-up**: LLM calls `findSheltersNearLocation()` with user's location

### 2. **Geocoding Failures**
- **Handled by**: `findSheltersNearLocation()` returns `GEOCODING_FAILED` error
- **LLM Action**: Ask user to try different format or be more specific
- **Example**: "I couldn't find that location. Could you try a different way to describe it, like a city name or street address?"

### 3. **No Shelters Found**
- **Handled by**: `findSheltersNearLocation()` returns empty list (count: 0)
- **LLM Action**: Inform user politely, suggest expanding radius or trying different location
- **Example**: "I didn't find any shelters within 5km of that location. Would you like me to search a wider area, or try a different location?"

### 4. **OSM API Rate Limiting**
- **Handled by**: Built-in delays (1 second between geocoding and shelter query)
- **Prevention**: Cache geocoding results in session if needed (future enhancement)
- **Error Handling**: Return user-friendly error if rate limited

### 5. **Network/Timeout Issues**
- **Handled by**: Timeout settings (20-30 seconds)
- **Error Handling**: Return structured error, LLM informs user to try again
- **User Experience**: Don't expose technical errors, keep messages friendly

### 6. **Invalid Tool Input**
- **Handled by**: `findSheltersNearLocation()` validates input
- **Error**: Returns `INVALID_INPUT` if neither address nor coordinates provided
- **LLM Action**: Should not happen if LLM follows tool description correctly

---

## Implementation Checklist

### Step 1: Extract OSM Functions
- [ ] Port `_http_get()` helper function
- [ ] Port `_http_post()` helper function
- [ ] Port `_geocode_address()` → `geocode_address()`
- [ ] Port `_query_shelters()` → `query_shelters_near_location()`
- [ ] Add proper error handling to all functions
- [ ] Add rate limiting delays
- [ ] Test functions independently with sample inputs

### Step 2: Browser-to-Backend Communication
- [ ] Research Chainlit frontend-to-backend communication methods
- [ ] Modify `location.js` to send location to backend when obtained
- [ ] Implement backend handler to receive location (e.g., `@cl.action_callback`)
- [ ] Test location storage in `cl.user_session`
- [ ] Verify location persists across messages in same session

### Step 3: Create getLocation() Tool
- [ ] Create `getLocation()` tool with proper description
- [ ] Implement cache checking logic
- [ ] Implement `LOCATION_REQUIRED` error return format
- [ ] Add tool to tools list in `@cl.on_chat_start`
- [ ] Test tool independently (with and without cached location)

### Step 4: Create findSheltersNearLocation() Tool
- [ ] Create `findSheltersNearLocation()` tool with proper description
- [ ] Implement input validation
- [ ] Integrate geocoding function
- [ ] Integrate shelter query function
- [ ] Implement result formatting
- [ ] Add tool to tools list
- [ ] Test tool independently with various inputs

### Step 5: Agent Integration
- [ ] Update agent system prompt with location tool instructions
- [ ] Add instructions for handling `LOCATION_REQUIRED` error
- [ ] Add example prompts for asking user for location
- [ ] Test agent calling `getLocation()` when needed
- [ ] Test agent handling `LOCATION_REQUIRED` and asking user
- [ ] Test agent calling `findSheltersNearLocation()` with location
- [ ] Verify agent maintains empathetic tone

### Step 6: End-to-End Testing
- [ ] Test complete flow: GPS cached → getLocation() → findSheltersNearLocation()
- [ ] Test complete flow: No GPS → getLocation() → LLM asks → user provides → findSheltersNearLocation()
- [ ] Test with various location formats (city, neighborhood, address)
- [ ] Test error cases (geocoding failure, no shelters found)
- [ ] Test rate limiting behavior
- [ ] Verify results format matches `resource_format`
- [ ] Test on different browsers/devices

---

## Key Design Decisions

### 1. **Two Separate Tools**
**Decision**: `getLocation()` and `findSheltersNearLocation()` are separate tools
**Rationale**: 
- Separation of concerns: location retrieval vs. shelter searching
- Reusability: `getLocation()` can be used by other tools that need location
- Clear responsibility: Each tool has one job
- LLM control: LLM explicitly decides when to check location

### 2. **Browser-First Approach**
**Decision**: Browser automatically requests GPS, LLM only asks if unavailable
**Rationale**:
- Better UX: No unnecessary prompts if GPS works
- Privacy: User grants permission once to browser
- Efficiency: GPS location is most accurate
- Fallback: LLM handles cases where GPS fails

### 3. **Cache Check in getLocation() Only**
**Decision**: Only `getLocation()` checks cache, `findSheltersNearLocation()` requires input
**Rationale**:
- Single source of truth: Cache checked once
- Clear flow: LLM gets location, then uses it
- Flexibility: `findSheltersNearLocation()` can use any location (cached or user-provided)
- No redundancy: Don't check cache in multiple places

### 4. **Structured Error Format**
**Decision**: Tools return JSON with structured errors (LOCATION_REQUIRED, GEOCODING_FAILED, etc.)
**Rationale**:
- LLM can parse and understand errors
- Consistent error handling
- Suggestions included for better LLM responses
- Not just strings - structured data

### 5. **Session-Scoped Cache**
**Decision**: Location cached for entire session, no time-based expiry initially
**Rationale**:
- Simpler implementation
- Location doesn't change much during a session
- Can add expiry later if needed
- Matches user's mental model (session = conversation)

### 6. **LLM Handles User Interaction**
**Decision**: LLM asks user for location when needed, not the tool
**Rationale**:
- Natural conversation flow
- LLM can be empathetic and contextual
- Matches HomeFinder's conversational tone
- Flexible: LLM can adapt question based on context

---

## Open Questions

1. **Frontend-to-Backend Communication**: What's the best method to send location from `location.js` to Python backend?
   - Need to research Chainlit's API
   - Options: Custom actions, session API, localStorage workaround
   - **Action**: Research Chainlit documentation

2. **Geocoding Cache**: Should we cache geocoding results in session?
   - Pros: Faster, fewer API calls
   - Cons: More memory, potential staleness
   - **Decision**: Start without caching, add if needed

3. **Location Privacy**: Should coordinates be considered PII?
   - Currently `remove_PII()` excludes ADDRESS type
   - Coordinates are sensitive location data
   - **Decision**: Don't store coordinates in message history, only in session

4. **Tool Description Clarity**: Are tool descriptions clear enough for LLM?
   - LLM needs to understand when to use each tool
   - LLM needs to understand error handling
   - **Action**: Test and refine based on LLM behavior

5. **Radius Default**: Is 5km appropriate default?
   - lambda-function.py uses 5000m (5km)
   - Should be configurable via tool parameter
   - **Decision**: 5km default, allow override

---

## Next Steps

1. **Research**: Chainlit frontend-to-backend communication methods
2. **Implement**: Extract OSM functions from lambda-function.py
3. **Implement**: Create `getLocation()` tool
4. **Implement**: Create `findSheltersNearLocation()` tool
5. **Implement**: Browser-to-backend location storage
6. **Integrate**: Add tools to agent and update prompt
7. **Test**: End-to-end testing with various scenarios
8. **Refine**: Based on testing, adjust tool descriptions and error handling

---

## Notes

- Consider mobile users: GPS may be more accurate on mobile devices
- Consider privacy: Location is sensitive data, handle with care
- Consider accessibility: Location box should be screen-reader friendly
- Consider internationalization: Location display should work in different languages
- Consider rate limiting: OSM APIs have usage policies, respect them
- Consider error messages: Keep them user-friendly, not technical
