import asyncio
import websockets

async def test_ws():
    uri = "ws://localhost:8000/ws/notifications/"
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            message = await websocket.recv()
            print(f"Received: {message}")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"Handshake failed with status code: {e.status_code}")
    except Exception as e:
        print(f"Connection failed: {str(e)}")

asyncio.run(test_ws())
