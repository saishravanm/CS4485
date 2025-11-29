"""
Test script for get_user_location()
Run: chainlit run test_location_request.py
Then type 'test' in browser chat
"""

import chainlit as cl
from location_request import get_user_location


@cl.on_chat_start
async def init():
    print("🧪 Test session ready")


@cl.on_message
async def handle(message: cl.Message):
    if message.content.lower() != "test":
        await cl.Message(content="Type 'test' to request location").send()
        return
    
    await cl.Message(content="🔄 Requesting location...").send()
    
    result = await get_user_location(timeout=30)
    
    if result:
        lat, lng = result
        await cl.Message(content=f"✅ Location: ({lat}, {lng})").send()
    else:
        await cl.Message(content="⚠️ Location request timed out").send()
