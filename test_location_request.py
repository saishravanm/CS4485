"""
Test script for get_user_location() function
This can be run to test the location request functionality without the LLM

Usage:
    Option 1: Run with Chainlit (recommended)
        chainlit run test_location_request.py
    
    Option 2: Manual test - set location in session first, then call function
        python test_location_request.py
"""

import chainlit as cl
import asyncio
from location_request import get_user_location


@cl.on_chat_start
async def test_init():
    """
    Initialize test session
    """
    print("🧪 Test session initialized")
    
    # Option 1: Pre-set location to test the "already available" path
    # Uncomment to test this scenario:
    # cl.user_session.set("user_latitude", 32.7767)
    # cl.user_session.set("user_longitude", -96.7970)
    # print("✅ Pre-set location in session for testing")


@cl.on_message
async def test_location_request(message: cl.Message):
    """
    Test the get_user_location() function
    """
    print("\n" + "=" * 60)
    print("🧪 Testing get_user_location() function")
    print("=" * 60)
    
    # Check if user wants to test with pre-set location
    if message.content.lower() == "test preset":
        # Set a test location
        cl.user_session.set("user_latitude", 32.7767)
        cl.user_session.set("user_longitude", -96.7970)
        await cl.Message(content="✅ Test location set in session. Now type 'test' to test the function.").send()
        return
    
    if message.content.lower() == "test":
        await cl.Message(content="🔄 Calling get_user_location()... This will request location from browser if not already available.").send()
        
        try:
            # Call the function
            result = await get_user_location(timeout=30)
            
            if result:
                lat, lng = result
                await cl.Message(
                    content=f"✅ **Test Successful!**\n\nLocation received:\n- Latitude: {lat}\n- Longitude: {lng}"
                ).send()
                print(f"✅ Test passed: Location = ({lat}, {lng})")
            else:
                await cl.Message(
                    content="⚠️ **Test Result:** Location request timed out or failed. Check browser console and location permissions."
                ).send()
                print("⚠️ Test: Location request timed out")
                
        except Exception as e:
            error_msg = f"❌ **Test Failed:** {str(e)}"
            await cl.Message(content=error_msg).send()
            print(f"❌ Test error: {e}")
    
    elif message.content.lower() == "help":
        help_text = """
**Location Request Test Commands:**

- `test` - Test the get_user_location() function
- `test preset` - Pre-set a test location in session (tests the "already available" path)
- `help` - Show this help message

**How it works:**
1. Type 'test' to trigger the location request
2. The function will check if location is already in session
3. If not, it sends a trigger message that JavaScript will detect
4. JavaScript requests location from browser
5. Location is sent back and stored in session
6. Function returns the coordinates
        """
        await cl.Message(content=help_text).send()
    
    else:
        await cl.Message(
            content="Type 'test' to test get_user_location(), 'test preset' to set a test location, or 'help' for more info."
        ).send()


# Standalone test function (can be called without Chainlit)
async def standalone_test():
    """
    Standalone test that simulates the function behavior
    This can be run with: python test_location_request.py
    """
    print("=" * 60)
    print("🧪 Standalone Test for get_user_location()")
    print("=" * 60)
    print("\n⚠️  Note: This function requires Chainlit's session context.")
    print("    For full testing, run: chainlit run test_location_request.py")
    print("\n" + "=" * 60)
    print("\nTo test manually:")
    print("1. Start Chainlit: chainlit run test_location_request.py")
    print("2. Open the app in browser")
    print("3. Type 'test' in the chat")
    print("4. Allow location access when prompted")
    print("5. Check the result")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # If run directly, show instructions
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "standalone":
        asyncio.run(standalone_test())
    else:
        print("=" * 60)
        print("Location Request Test Script")
        print("=" * 60)
        print("\nTo test get_user_location():")
        print("  chainlit run test_location_request.py")
        print("\nThen in the browser:")
        print("  - Type 'test' to test the function")
        print("  - Type 'test preset' to set a test location first")
        print("  - Type 'help' for more info")
        print("\n" + "=" * 60)

