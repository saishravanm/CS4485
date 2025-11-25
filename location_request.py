"""
Location request - gets user GPS via browser.
Token-based: generates UUID, frontend POSTs to /api/set_location, polls LOCATION_STORE.
"""

import chainlit as cl
import asyncio
import uuid
from typing import Optional
from fastapi import Body

from location_store import LOCATION_STORE
from chainlit.server import app


@app.post("/api/set_location")
async def set_location(payload: dict = Body(...)):
    """Receives {latitude, longitude, token} or {error, message, token} from frontend JS."""
    token = payload.get("token")
    
    if token is None:
        return {"status": "error", "message": "Missing token"}
    
    # Check if this is an error response (user denied permission)
    if "error" in payload:
        error_code = payload.get("error")
        error_msg = payload.get("message", "Unknown error")
        LOCATION_STORE[token] = {"error": error_code, "message": error_msg}
        print(f"❌ Location denied for {token}: {error_msg}")
        return {"status": "ok", "token": token}
    
    # Normal location response
    lat = payload.get("latitude")
    lng = payload.get("longitude")
    
    if lat is None or lng is None:
        return {"status": "error", "message": "Missing latitude or longitude"}
    
    LOCATION_STORE[token] = {"lat": float(lat), "lng": float(lng)}
    print(f"📍 Stored location for {token}: ({lat}, {lng})")
    return {"status": "ok", "token": token}


async def get_user_location(timeout: int = 30) -> Optional[tuple[float, float]]:
    """
    Request user location from browser. Returns (lat, lng) or None on timeout.
    """
    token = str(uuid.uuid4())
    
    # Send trigger to frontend
    await cl.Message(
        content=f'<location_request_trigger token="{token}">REQUEST_LOCATION</location_request_trigger>',
        author="System"
    ).send()
    
    # Poll for response
    waited = 0.0
    while waited < timeout:
        if token in LOCATION_STORE:
            data = LOCATION_STORE.pop(token)
            
            # Check if user denied permission
            if "error" in data:
                print(f"❌ Location denied: {data.get('message')}")
                return None
            
            print(f"✅ Location received: ({data['lat']}, {data['lng']})")
            return (data["lat"], data["lng"])
        await asyncio.sleep(0.5)
        waited += 0.5
    
    print(f"⚠️ Location timeout after {timeout}s")
    return None
