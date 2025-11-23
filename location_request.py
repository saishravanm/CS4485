"""
Location request functionality for HomeFinder
Handles requesting user location from browser via Chainlit frontend
"""

import chainlit as cl
import asyncio


async def get_user_location(timeout: int = 30) -> tuple[float, float] | None:
    """
    Requests the user's current location from their browser.
    This function sends a trigger to the frontend JavaScript to request location,
    then waits for the location to be received and stored in the session.
    
    Args:
        timeout: Maximum seconds to wait for location (default: 30)
    
    Returns:
        Tuple of (latitude, longitude) if location is received, None if timeout or error
    """
    # Check if location is already available in session
    lat = cl.user_session.get("user_latitude")
    lng = cl.user_session.get("user_longitude")
    
    if lat is not None and lng is not None:
        print(f"✅ Location already available: ({lat}, {lng})")
        return (float(lat), float(lng))
    
    # Send a message with a special marker to trigger location request in JavaScript
    # The JavaScript will detect this and request location
    await cl.Message(
        content="<location_request_trigger>REQUEST_LOCATION</location_request_trigger>",
        author="System"
    ).send()
    
    # Wait for location to be received (poll session)
    wait_interval = 0.5  # Check every 500ms
    waited = 0
    
    while waited < timeout:
        lat = cl.user_session.get("user_latitude")
        lng = cl.user_session.get("user_longitude")
        
        if lat is not None and lng is not None:
            print(f"✅ Location received: ({lat}, {lng})")
            return (float(lat), float(lng))
        
        await asyncio.sleep(wait_interval)
        waited += wait_interval
    
    print(f"⚠️ Location request timed out after {timeout} seconds")
    return None

