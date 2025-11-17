# Location Integration Plan - OpenStreetMap Tool Implementation

## Overview

The goal is to integrate the OpenStreetMap functionality from `lambda-function.py` as a LangChain tool that the LLM can use to find shelters and resources near the user's location. The tool should check for cached/stored location before making API calls.

---

## Architecture Approach

### 1. **Location Flow**

**Current (Chainlit-specific)**:
```
Frontend (location.js) 
  → Gets GPS coordinates via browser geolocation API
  → Sends to backend via Chainlit user session
  → Stored in cl.user_session["location"]
  → OSM Tool checks cache first
  → If cached, use it; if not, handle gracefully
```

**Future (React/Next.js compatible)**:
```
Frontend (React component)
  → Gets GPS coordinates via browser geolocation API
  → Sends to backend via REST API endpoint (POST /api/location)
  → Stored in session storage (database or server-side session)
  → OSM Tool checks cache first
  → If cached, use it; if not, handle gracefully
```

**Optimization**: Design backend API to be framework-agnostic from the start

### 2. **OSM Tool Structure**

The tool should be a LangChain tool that:
- **Checks location cache** via abstracted `get_user_location()` function (works with Chainlit sessions or database)
- **Accepts location input** in multiple formats:
  - Coordinates (lat, lon) from cache
  - Address string from user message
  - Explicit coordinates from user message
- **Uses OSM APIs** to:
  - Geocode addresses to coordinates (if needed)
  - Query resources near coordinates with natural language search terms
- **Returns structured results** that the LLM can format for the user

**Framework-Agnostic Design**: The tool uses abstracted session storage, so it works whether location comes from Chainlit session or REST API/database.

---

## Implementation Strategy

### Phase 1: Extract OSM Functions

**Location**: Create a new module or add to `homefinder.py`

**Extract from `lambda-function.py`**:
- `_geocode_address()` - Convert address to coordinates
- `_query_shelters()` - Query shelters near coordinates (as reference/example)
- HTTP helper functions (`_http_get`, `_http_post`)
- Keep the same OSM API endpoints (Nominatim, Overpass)

**Key Functions to Port**:
```python
def geocode_address(address: str) -> tuple[float, float]:
    """Geocode an address to lat/lon using Nominatim"""
    
def execute_overpass_query(query: str) -> dict:
    """
    Execute an Overpass API query and return results.
    The query should already have coordinates filled in (no placeholders).
    """
```

**Key Design Decision - LLM-Driven Query Construction**:
- **LLM constructs Overpass queries**: The LLM has full control over query construction based on its knowledge of OSM tags
- **Tool executes queries**: The tool simply executes whatever Overpass query the LLM provides
- **No regex/text matching**: No automatic matching - LLM decides how to search based on OSM tag structure
- **Simple and flexible**: LLM can construct any valid Overpass query for any use case

**Considerations**:
- Rate limiting: Nominatim requires 1 request/second, need polite delays
- User-Agent: Required for Nominatim (use project identifier)
- Error handling: Handle API failures gracefully
- Timeout handling: OSM APIs can be slow
- Query validation: Tool should validate Overpass query syntax before executing

---

### Phase 2: Location Storage & Caching

**Location Storage Strategy - Framework Agnostic Design**:

**Current Implementation (Chainlit)**:
- **Primary**: `cl.user_session["location"]` - stores coordinates from frontend
  - Format: `{"latitude": float, "longitude": float, "timestamp": datetime}`
  - Set when location is received from frontend
- **Cache validity**: Consider location valid for session duration (or X minutes)
- **Fallback**: If not in session, tool can't auto-use location

**Future Implementation (React/Next.js)**:
- **Primary**: Session storage via REST API endpoint
  - Same format: `{"latitude": float, "longitude": float, "timestamp": datetime}`
  - Stored via POST `/api/location` endpoint
  - Retrieved via GET `/api/location` endpoint
- **Session Management**: Use session ID from request (cookie or header)
- **Backend Storage**: Can use same DynamoDB table or separate session store

**Optimized Approach - Hybrid Design**:
- **Abstract the storage layer**: Create a `get_user_location(session_id)` function that works with both Chainlit sessions and REST API sessions
- **For Chainlit**: Use `cl.user_session.get("location")` internally
- **For React/Next.js**: Use session_id to query database/API
- **Location Storage Function**: 
  ```python
  def get_user_location(session_id: str = None) -> dict | None:
      """Get cached location - works with both Chainlit and REST API"""
      # If in Chainlit context, use cl.user_session
      if hasattr(cl, 'user_session') and cl.user_session:
          location = cl.user_session.get("location")
          if location:
              return {
                  "latitude": location["latitude"],
                  "longitude": location["longitude"]
              }
      
      # If session_id provided (REST API context), query from database
      if session_id:
          # Query from DynamoDB or session store
          location = get_location_from_db(session_id)
          if location:
              return {
                  "latitude": location["latitude"],
                  "longitude": location["longitude"]
              }
      
      return None
  ```

**Frontend Integration - Framework Agnostic**:

**Current (Chainlit)**:
- Modify `location.js` to send location via Chainlit action/callback
- OR: Store in localStorage and send with first message

**Future (React/Next.js)**:
- React component calls `fetch('/api/location', { method: 'POST', body: JSON.stringify({lat, lon}) })`
- Standard REST API - works with any frontend framework

**Recommended Implementation**:
1. **Create REST API endpoint** (works for both Chainlit and React):
   ```python
   @app.post("/api/location")  # FastAPI or Flask endpoint
   async def set_location(request: Request):
       session_id = get_session_id(request)  # From cookie/header
       data = await request.json()
       store_location(session_id, data["latitude"], data["longitude"])
       return {"status": "success"}
   ```

2. **Chainlit can use same endpoint** OR use `cl.user_session` as fallback
3. **React frontend** uses standard fetch/axios to POST location
4. **Both use same `get_user_location()` function** internally

---

### Phase 3: Create LangChain Tools

**Tool 1: `getLocation()` - Check and Retrieve Location**

```python
from langchain_core.tools import tool

@tool
def getLocation() -> str:
    """
    Get the user's current location. Checks for cached GPS location first.
    If no cached location is available, returns an error indicating the 
    agent should ask the user for their rough location (city, neighborhood, or address).
    
    Returns:
        JSON string with location coordinates if available, or error if not.
        Success: {"latitude": float, "longitude": float, "source": "browser_gps"}
        Error: {"error": "LOCATION_REQUIRED", "message": "..."}
    """
```

**Tool 2: `executeOverpassQuery()` - Execute OSM Overpass Query**

```python
@tool
def executeOverpassQuery(
    overpass_query: str,  # Full Overpass QL query string
    address: str = None,
    latitude: float = None,
    longitude: float = None,
) -> str:
    """
    Execute an Overpass API query to find resources near a location.
    The LLM constructs the Overpass query based on its knowledge of OSM tags.
    
    The tool handles geocoding if an address is provided, then executes the query.
    The LLM is responsible for constructing valid Overpass QL syntax.
    
    Args:
        overpass_query: Complete Overpass QL query string. Should use {lat} and {lon} 
                       placeholders for coordinates, which will be replaced by the tool.
                       Example: '[out:json][timeout:25];(node(around:5000,{lat},{lon})["amenity"="shelter"];);out center tags;'
        address: Optional address string (e.g., "1201 E 9th St, Dallas, TX")
                 If provided, will be geocoded to coordinates
        latitude: Optional latitude coordinate (use with longitude)
        longitude: Optional longitude coordinate (use with latitude)
    
    Note: If neither address nor coordinates are provided, the tool will check for 
          cached location. If no location is available, returns LOCATION_REQUIRED error.
    
    Returns:
        JSON string with query results from Overpass API
    """
```

**Tool Logic Flow for `executeOverpassQuery()`**:

1. **Check for cached location** if no explicit input provided
   ```python
   if not address and not latitude and not longitude:
       cached = get_user_location()
       if cached:
           latitude = cached["latitude"]
           longitude = cached["longitude"]
       else:
           # Return special indicator that prompts agent to ask user for location
           return json.dumps({
               "error": "LOCATION_REQUIRED",
               "message": "No location available. The agent should ask the user for their rough location (city, neighborhood, or address)."
           })
   ```

2. **Geocode if address provided**
   ```python
   if address:
       lat, lon = geocode_address(address)
       if not lat or not lon:
           return json.dumps({
               "error": "GEOCODING_FAILED",
               "message": f"Could not geocode address: {address}"
           })
   else:
       lat, lon = latitude, longitude
   ```

3. **Replace coordinate placeholders in query**
   ```python
   # Replace {lat} and {lon} placeholders with actual coordinates
   query = overpass_query.replace("{lat}", str(lat)).replace("{lon}", str(lon))
   ```

4. **Execute Overpass query**
   ```python
   # Execute the query via Overpass API
   results = execute_overpass_query(query)
   ```

5. **Return results**
   ```python
   # Return raw Overpass API response (JSON)
   return json.dumps(results)
   ```

**Overpass Query Construction - LLM Responsibility**:

The LLM constructs Overpass queries directly based on its knowledge of OSM tags and structure.

**Example Query Construction**:
```python
# Example: User wants "halal food near me"
# LLM constructs Overpass query based on OSM tag knowledge:
# - Uses amenity tags for food places
# - Uses diet:halal tag or cuisine matching
# - Uses around() for proximity search

overpass_query = """
[out:json][timeout:25];
(
  node(around:5000,{lat},{lon})[
    "amenity"~"restaurant|fast_food|cafe"
  ][
    "diet:halal"="yes" | 
    "cuisine"~"halal",i
  ];
  way(around:5000,{lat},{lon})[
    "amenity"~"restaurant|fast_food|cafe"
  ][
    "diet:halal"="yes" | 
    "cuisine"~"halal",i
  ];
);
out center tags;
"""
```

**Tool Description for LLM** (important):
- LLM must construct valid Overpass QL syntax
- LLM should use its knowledge of OSM tags (amenity, shop, etc.)
- Use {lat} and {lon} placeholders for coordinates (tool will replace them)
- Tool handles geocoding and query execution only
- LLM has full control over query structure and tag matching

---

### Phase 4: Frontend-to-Backend Communication

**Challenge**: Getting location from frontend to Python backend in a framework-agnostic way

**Critical Optimization for React/Next.js Migration**:

**❌ Chainlit-Specific Approach (NOT recommended)**:
- Chainlit actions/callbacks won't work in React
- `cl.user_session` is Chainlit-specific
- DOM manipulation in `location.js` is not React-friendly

**✅ Framework-Agnostic Approach (Recommended)**:

**Option A: REST API Endpoint (Best for React/Next.js)**
```python
# In homefinder.py - Add FastAPI/Flask endpoint
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

@app.post("/api/location")
async def set_location(request: Request):
    """Store location - works with any frontend"""
    session_id = get_session_id_from_request(request)  # From cookie/header
    data = await request.json()
    
    # Store in session (Chainlit or database)
    if hasattr(cl, 'user_session') and cl.user_session:
        # Chainlit context
        cl.user_session.set("location", {
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "timestamp": datetime.now()
        })
    else:
        # REST API context - store in database
        store_location_in_db(session_id, data["latitude"], data["longitude"])
    
    return {"status": "success"}
```

```javascript
// Works in both Chainlit location.js AND React components
async function sendLocationToBackend(lat, lon) {
    const response = await fetch('/api/location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            latitude: lat,
            longitude: lon
        })
    });
    return response.json();
}

// In location.js (current)
if (position) {
    sendLocationToBackend(
        position.coords.latitude,
        position.coords.longitude
    );
}

// In React component (future)
const LocationComponent = () => {
    useEffect(() => {
        navigator.geolocation.getCurrentPosition((position) => {
            sendLocationToBackend(
                position.coords.latitude,
                position.coords.longitude
            );
        });
    }, []);
    // ...
};
```

**Option B: Hybrid Approach (Chainlit + REST API)**
- **For Chainlit**: Use `cl.user_session` as primary, REST API as fallback
- **For React**: Use REST API exclusively
- **Backend**: Check Chainlit session first, fall back to database if not available

**Implementation Strategy**:
1. **Create REST API endpoint** that works in both contexts
2. **Abstract session storage** - function that checks Chainlit session OR database
3. **Frontend sends to REST API** - same code works in Chainlit JS and React
4. **Backend handles both** - Chainlit session for now, database for React later

**Benefits**:
- ✅ Works with current Chainlit setup
- ✅ Ready for React/Next.js migration
- ✅ No code changes needed when migrating frontend
- ✅ Standard HTTP API - easy to test and debug
- ✅ Can use same endpoint for both frameworks

**Recommendation**: Implement REST API endpoint from the start, even if Chainlit can use `cl.user_session` directly. This makes migration seamless.

---

### Phase 5: Integration with Agent

**Add Tools to Agent**:
```python
# In @cl.on_chat_start
tools = []
tools.append(kb_tool)
tools.append(search_tool)
tools.append(getLocation)  # Add location retrieval tool
tools.append(executeOverpassQuery)  # Add OSM Overpass query execution tool
```

**Agent Prompt Modification**:
- Update system prompt to mention location-aware tools and Overpass query construction
- Guide agent to use `getLocation()` first when user asks for "near me" or location-based queries
- **Critical**: When `getLocation()` returns `LOCATION_REQUIRED` error, agent MUST ask user for location
- **Key**: Agent constructs Overpass queries directly using its knowledge of OSM tags and structure

- Example prompt addition: 
  ```
  "When the user asks for resources 'near me' or location-based queries:
  1. First call getLocation() to check for cached GPS location
  2. If getLocation() returns LOCATION_REQUIRED, ask the user for their rough location 
     (city, neighborhood, or street address) empathetically
  3. Once you have location (cached or from user), construct an Overpass query and 
     call executeOverpassQuery() to search for resources
  
  For executeOverpassQuery():
  - You must construct valid Overpass QL syntax based on your knowledge of OSM tags
  - Use {lat} and {lon} placeholders in your query - the tool will replace them with coordinates
  - Construct queries based on what the user is looking for:
    * Shelters: amenity=shelter, amenity=social_facility
    * Food: amenity=restaurant, amenity=fast_food, amenity=cafe
    * Healthcare: amenity=hospital, amenity=clinic, amenity=pharmacy
    * Dietary restrictions: diet:halal=yes, diet:kosher=yes, diet:vegetarian=yes
    * Accessibility: wheelchair=yes, wheelchair=designated
  - Use around(radius_meters, lat, lon) for proximity searches
  - Query both nodes and ways for complete results
  
  Examples:
  - User: 'I need halal food near me' 
    → getLocation() → executeOverpassQuery(overpass_query='[out:json][timeout:25];(node(around:5000,{lat},{lon})["amenity"~"restaurant|fast_food"]["diet:halal"="yes"];);out center tags;', ...)
  - User: 'Find shelters nearby'
    → getLocation() → executeOverpassQuery(overpass_query='[out:json][timeout:25];(node(around:5000,{lat},{lon})["amenity"~"shelter|social_facility"];);out center tags;', ...)
  - User: 'Wheelchair accessible shelters'
    → getLocation() → executeOverpassQuery(overpass_query='[out:json][timeout:25];(node(around:5000,{lat},{lon})["amenity"~"shelter|social_facility"]["wheelchair"~"yes|designated"];);out center tags;', ...)
  "

**Tool Priority & Location Request Flow**:
- When user asks for resources near them:
  1. **Call `getLocation()`** to check for cached GPS location
  2. **If `getLocation()` returns LOCATION_REQUIRED**:
     - Agent asks user: "I'd like to help you find resources nearby. Could you tell me what city, neighborhood, or area you're in? This helps me search for resources close to you."
     - Wait for user response with location information
     - Extract location from user's response (city name, neighborhood, address, etc.)
  3. **Construct Overpass query** based on user's request:
     - Determine resource type and requirements from user's message
     - Build valid Overpass QL query using OSM tag knowledge
     - Use {lat} and {lon} placeholders for coordinates
  4. **Call `executeOverpassQuery()`** with:
     - Overpass query string
     - Location (from cache or user as address/coordinates)
  5. **Fall back to Knowledge Base search** if OSM fails or returns no results

---

## Error Handling & Edge Cases

### 1. **No Location Available - Location Request Flow**
- Tool returns structured error: `{"error": "LOCATION_REQUIRED", "message": "..."}`
- Agent detects `LOCATION_REQUIRED` error and proactively asks user for location
- Agent asks empathetically: "I'd like to help you find shelters nearby. Could you tell me what city or neighborhood you're in?"
- Agent accepts flexible input:
  - City name (e.g., "Dallas", "Fort Worth")
  - Neighborhood (e.g., "Deep Ellum", "Oak Cliff")
  - Street address (e.g., "1201 E 9th St, Dallas")
  - Area description (e.g., "near downtown Dallas")
- After user provides location, agent calls tool again with the location
- Don't fail silently - always ask if location is needed

### 2. **Geocoding Failures**
- Handle invalid addresses gracefully
- Return helpful error message
- Suggest user try different format

### 3. **OSM API Rate Limiting**
- Implement delays between requests (1 second for Nominatim)
- Cache geocoding results if possible (session-scoped)
- Handle rate limit errors gracefully

### 4. **No Shelters Found**
- Return empty list, not error
- Let LLM inform user politely
- Suggest expanding radius or trying different location

### 5. **Network/Timeout Issues**
- Set reasonable timeouts (20-30 seconds)
- Handle exceptions gracefully
- Return user-friendly error messages

---

## Data Flow Example

### Scenario: User asks "Find shelters near me" (with cached location)

1. **User sends message**: "Find shelters near me"
2. **Agent calls `getLocation()`**: Checks for cached GPS location
3. **`getLocation()` returns**: `{"latitude": 32.776665, "longitude": -96.796989, "source": "browser_gps"}`
4. **Agent constructs Overpass query** for shelters:
   ```
   [out:json][timeout:25];
   (node(around:5000,{lat},{lon})["amenity"~"shelter|social_facility"];);
   out center tags;
   ```
5. **Agent calls**: `executeOverpassQuery(overpass_query="...", latitude=32.776665, longitude=-96.796989)`
6. **Tool replaces placeholders** and executes query
7. **OSM returns results**: List of shelters with names, coordinates, addresses
8. **Tool returns results**: Raw JSON from Overpass API
9. **Agent receives results**: Formats for user using resource_format
10. **User sees response**: Formatted list of shelters with addresses

### Scenario: User asks "I need halal food near me" (NO cached location)

1. **User sends message**: "I need halal food near me"
2. **Agent calls `getLocation()`**: Checks for cached GPS location
3. **`getLocation()` returns**: `{"error": "LOCATION_REQUIRED", "message": "..."}`
4. **Agent detects LOCATION_REQUIRED error** and asks user for location:
   - Agent: "I'd like to help you find halal food nearby. Could you tell me what city or neighborhood you're in? This helps me search for resources close to you."
5. **User responds**: "I'm in Dallas, near downtown"
6. **Agent constructs Overpass query** for halal food:
   ```
   [out:json][timeout:25];
   (node(around:5000,{lat},{lon})["amenity"~"restaurant|fast_food"]["diet:halal"="yes"];);
   out center tags;
   ```
7. **Agent calls**: `executeOverpassQuery(overpass_query="...", address="Dallas, near downtown")`
8. **Tool geocodes address**: Calls `geocode_address()` → gets lat/lon for downtown Dallas
9. **Tool replaces placeholders** and executes query
10. **OSM returns results**: List of halal food options
11. **Agent formats response**: Shows user formatted list of halal food locations

### Scenario: User asks "Find kosher restaurants nearby"

1. **User sends**: "Find kosher restaurants nearby"
2. **Agent calls `getLocation()`**: Gets cached location (or asks user if not available)
3. **Agent constructs Overpass query** for kosher restaurants:
   ```
   [out:json][timeout:25];
   (node(around:5000,{lat},{lon})["amenity"~"restaurant|fast_food"]["diet:kosher"="yes"];);
   out center tags;
   ```
4. **Agent calls**: `executeOverpassQuery(overpass_query="...", latitude=X, longitude=Y)`
5. **Tool executes query**: Returns kosher restaurants near location
6. **Agent formats results**: Shows user formatted list

### Scenario: User asks "Wheelchair accessible shelters"

1. **User sends**: "I need wheelchair accessible shelters near me"
2. **Agent calls `getLocation()`**: Gets location
3. **Agent constructs Overpass query** for accessible shelters:
   ```
   [out:json][timeout:25];
   (node(around:5000,{lat},{lon})["amenity"~"shelter|social_facility"]["wheelchair"~"yes|designated"];);
   out center tags;
   ```
4. **Agent calls**: `executeOverpassQuery(overpass_query="...", ...)`
5. **Tool executes query**: Returns accessible shelters
6. **Agent formats results**: Shows user formatted list

### Key Point: LLM Constructs Queries

The LLM has full control and responsibility:
- Constructs valid Overpass QL queries based on OSM tag knowledge
- Uses {lat} and {lon} placeholders for coordinates
- Tool only handles geocoding, coordinate replacement, and query execution
- LLM decides query structure, tag matching, and filtering logic

---

## Implementation Checklist

### Step 1: Extract OSM Functions
- [ ] Port `_geocode_address()` to `homefinder.py`
- [ ] Port HTTP helper functions (`_http_get`, `_http_post`)
- [ ] Create `execute_overpass_query()` function
  - [ ] Implement Overpass API HTTP request
  - [ ] Handle query execution and response parsing
  - [ ] Add proper error handling and timeout handling
- [ ] Add proper error handling
- [ ] Test function independently with various Overpass queries

### Step 2: Location Caching
- [ ] Create `get_user_location()` helper function
- [ ] Research Chainlit frontend-to-backend communication
- [ ] Implement location storage in `cl.user_session`
- [ ] Test location caching

### Step 3: Create LangChain Tools
- [ ] Create `getLocation()` tool
  - [ ] Implement cache checking logic
  - [ ] Implement `LOCATION_REQUIRED` error return format
  - [ ] Add proper tool description for LLM
- [ ] Create `executeOverpassQuery()` tool
  - [ ] Accept overpass_query string parameter
  - [ ] Accept optional address, latitude, longitude parameters
  - [ ] Implement cache checking logic if no location provided
  - [ ] Implement geocoding fallback for addresses
  - [ ] Replace {lat} and {lon} placeholders in query
  - [ ] Execute Overpass query via API
  - [ ] Add proper tool description emphasizing LLM constructs queries
- [ ] Test tools independently:
  - [ ] Test with cached location
  - [ ] Test with various Overpass queries (shelters, food, healthcare)
  - [ ] Test with different OSM tag combinations
  - [ ] Test error cases (invalid query syntax, geocoding failures)

### Step 4: Frontend Integration
- [ ] Modify `location.js` to send location to backend
- [ ] Implement backend handler to receive location
- [ ] Test end-to-end location flow

### Step 5: Agent Integration
- [ ] Add both tools to tools list in `@cl.on_chat_start`
- [ ] Update agent prompt to mention:
  - [ ] Location retrieval flow (getLocation() first)
  - [ ] Overpass query construction (executeOverpassQuery())
  - [ ] OSM tag knowledge and query syntax
  - [ ] Examples of Overpass queries for common resource types
- [ ] Add instructions for agent to detect `LOCATION_REQUIRED` and ask user for location
- [ ] Add example prompts for how agent should ask for location
- [ ] Test agent with various scenarios:
  - [ ] Cached location + simple resource request
  - [ ] No cached location + resource request (LOCATION_REQUIRED flow)
  - [ ] Resource request with dietary restrictions ("halal food", "kosher restaurant")
  - [ ] Resource request with accessibility needs ("wheelchair accessible")
  - [ ] Resource request with multiple criteria
- [ ] Verify agent constructs valid Overpass queries
- [ ] Verify agent asks empathetically and handles user's location response
- [ ] Verify tools are called appropriately

### Step 6: Testing & Refinement
- [ ] Test with cached location (happy path)
- [ ] Test location request flow (no cached location)
  - [ ] Verify agent asks for location when getLocation() returns LOCATION_REQUIRED
  - [ ] Test agent parsing various location formats from user
  - [ ] Test agent calling executeOverpassQuery() after receiving location
- [ ] Test Overpass query construction:
  - [ ] Dietary restrictions: halal, kosher, vegetarian queries
  - [ ] Accessibility: wheelchair accessible queries
  - [ ] Different resource types: shelter, food, healthcare, clothing
  - [ ] Complex queries with multiple criteria
- [ ] Test with address input in user message
- [ ] Test with coordinates input
- [ ] Test error cases:
  - [ ] Geocoding failure
  - [ ] No resources found
  - [ ] Invalid Overpass query syntax
  - [ ] Query timeout
- [ ] Test rate limiting behavior
- [ ] Verify results format matches `resource_format`
- [ ] Verify agent maintains empathetic tone when asking for location
- [ ] Verify agent constructs valid Overpass queries for various use cases

---

## Key Design Decisions

### 1. **LLM-Driven Query Construction**
**Decision**: LLM constructs Overpass queries directly, tool only executes them
**Rationale**: 
- Full control in LLM's hands - can construct any valid Overpass query
- No need for regex/text matching logic in tool
- LLM uses its knowledge of OSM tags and structure
- Simple tool implementation - just handles geocoding, coordinate replacement, and execution
- Can add regex/text matching later if needed

### 2. **Two Separate Tools**
**Decision**: Separate `getLocation()` and `executeOverpassQuery()` tools
**Rationale**: 
- Separation of concerns: location retrieval vs. query execution
- `getLocation()` is reusable by other tools that need location
- `executeOverpassQuery()` is a simple query executor
- LLM has explicit control over when to check location and what query to construct

### 3. **Tool Input Flexibility**
**Decision**: `executeOverpassQuery()` accepts address OR coordinates OR uses cache, plus Overpass query string
**Rationale**: Maximum flexibility - agent can use cached location, extract address from message, use explicit coordinates, and construct any Overpass query

### 4. **Cache Validity**
**Decision**: Session-scoped (valid for entire session)
**Rationale**: Simpler implementation, location doesn't change much during a session. Can add time-based expiry later if needed.

### 5. **Return Format**
**Decision**: JSON string (not structured object)
**Rationale**: LangChain tools typically return strings. LLM can parse JSON and format for user.

### 6. **Error Handling**
**Decision**: Return user-friendly error messages, don't raise exceptions
**Rationale**: Agent can handle error messages and respond appropriately to user

### 7. **Tool Priority**
**Decision**: Use OSM tool as primary for location-based queries, Knowledge Base as fallback
**Rationale**: OSM provides real-time, proximity-based results. Knowledge Base has structured data but may not have location proximity matching.

### 8. **Location Request Flow**
**Decision**: When location unavailable, tool returns structured error and agent proactively asks user
**Rationale**: Better UX - user doesn't need to figure out what went wrong. Agent conversationally asks for what's needed. Matches the empathetic, conversational tone of HomeFinder.

---

## Open Questions

1. **Frontend-to-Backend Communication**: What's the best way to send location from frontend to Python backend?
   - ✅ **Decision**: Use REST API endpoint (`/api/location`) - framework-agnostic
   - Works with Chainlit (current) and React/Next.js (future)
   - Standard HTTP POST request - no framework-specific APIs needed
   - Backend can use Chainlit session OR database depending on context

2. **Geocoding Caching**: Should we cache geocoding results?
   - Pros: Faster, fewer API calls
   - Cons: More memory, potential staleness
   - Decision: Start without caching, add if needed

3. **Location Privacy**: Should location be included in PII redaction?
   - Currently `remove_PII()` excludes ADDRESS type
   - Should coordinates be considered PII?
   - Decision: Coordinates are PII, but needed for functionality. Don't store in message history.

4. **Tool vs. Direct Function**: Should this be a tool or called directly?
   - Tool approach: LLM decides when to use it (flexible)
   - Direct approach: Always use when location available (simpler)
   - Decision: Tool approach (current plan) - gives LLM control

5. **Radius Default**: What should default radius be?
   - lambda-function.py uses 5000m (5km)
   - Should tool allow user to specify?
   - Decision: Default 5km, allow override via tool parameter

6. **Query Construction Approach**: Should LLM construct queries or tool handle matching?
   - LLM constructs queries: Full control, uses OSM tag knowledge, simple tool implementation
   - Tool handles matching: More complex tool, but could add regex/text matching later if needed
   - Decision: LLM constructs Overpass queries directly - simple tool, full flexibility, can add matching later if needed

---

## Location Request Flow - Detailed Implementation

### How Agent Should Ask for Location

**When tool returns LOCATION_REQUIRED**, agent should:

1. **Acknowledge the request**: "I'd like to help you find shelters nearby"
2. **Explain why location is needed**: "To find resources close to you, I need to know your location"
3. **Ask specifically**: "Could you tell me what city or neighborhood you're in?"
4. **Provide examples** (if helpful): "For example, you could say 'Dallas', 'Oak Cliff', or 'near downtown'"
5. **Be empathetic**: Match the warm, understanding tone of HomeFinder

**Example Agent Responses**:

**Option A (Concise)**:
```
I'd like to help you find shelters nearby. Could you tell me what city or 
neighborhood you're in? This helps me search for resources close to you.
```

**Option B (More Detailed)**:
```
I'd like to help you find shelters near you. To do that, I need to know 
your location. Could you share what city or area you're in? You can give me 
a city name like "Dallas", a neighborhood like "Deep Ellum", or even a 
street address if you're comfortable sharing that.
```

**Option C (Most Empathetic)**:
```
I understand you're looking for shelters nearby. To help you find resources 
close to where you are, could you tell me what city or neighborhood you're 
in? You can share as much or as little detail as you're comfortable with - 
just a city name works great!
```

### Parsing User's Location Response

After agent asks for location, user might respond with various formats:

- **City name**: "Dallas", "Fort Worth", "Arlington"
- **Neighborhood**: "Deep Ellum", "Oak Cliff", "downtown"
- **Address**: "1201 E 9th St, Dallas, TX"
- **Area description**: "near downtown Dallas", "in the Oak Cliff area"
- **Combination**: "I'm in Dallas, near Deep Ellum"

**Agent should**:
- Extract location information from user's response
- Use natural language understanding to identify the location
- Call OSM tool with the extracted location
- If geocoding fails, ask for clarification: "I couldn't find that location. Could you try a different way to describe it, like a city name or street address?"

### Tool Return Format for LOCATION_REQUIRED

```python
# When location is unavailable
return json.dumps({
    "error": "LOCATION_REQUIRED",
    "message": "No location available. The agent should ask the user for their rough location (city, neighborhood, or address).",
    "suggestion": "Ask the user: 'Could you tell me what city or neighborhood you're in? This helps me search for resources close to you.'"
})
```

This structured format helps the agent:
- Detect that location is needed (check for `error == "LOCATION_REQUIRED"`)
- Use the suggestion as a template for asking
- Understand this is a normal flow, not an error condition

---

## Next Steps

1. **✅ Decision Made**: Use REST API endpoint for location storage (framework-agnostic)
2. **Prototype**: Extract OSM functions and test independently
3. **Implement**: 
   - Create REST API endpoint `/api/location` (works with Chainlit and React)
   - Create tool with cache checking (uses abstracted session storage)
4. **Integrate**: Add to agent and test
5. **Refine**: Based on testing, adjust as needed

## React/Next.js Migration Considerations

### Key Optimizations Made:

1. **✅ REST API Endpoint**: Instead of Chainlit-specific actions, use standard HTTP POST
   - Works with any frontend framework
   - Easy to test with curl/Postman
   - Standard HTTP - no framework lock-in

2. **✅ Abstracted Session Storage**: `get_user_location()` function works with both:
   - Chainlit sessions (current)
   - Database/API sessions (React/Next.js)

3. **✅ Frontend Code Reusable**: Same JavaScript function works in:
   - Chainlit's `location.js` (current)
   - React components (future)
   - Any JavaScript frontend

4. **✅ Location Display**: Current `location.js` uses DOM manipulation
   - **For React**: Will need to convert to React component
   - **Location logic**: Can reuse (geolocation API calls)
   - **UI**: Will be React component instead of DOM manipulation

### Migration Checklist (When Moving to React):

- [ ] Convert `location.js` to React component (`LocationDisplay.tsx`)
- [ ] Replace DOM manipulation with React state/hooks
- [ ] Keep same REST API endpoint (no backend changes needed)
- [ ] Update session storage to use database instead of Chainlit session
- [ ] Test location flow end-to-end in React app

### What Stays the Same:

- ✅ REST API endpoint (`/api/location`)
- ✅ OSM functions (framework-agnostic)
- ✅ LangChain tools (backend-only)
- ✅ Location storage format
- ✅ Error handling logic

