import os
import django
import asyncio
from channels.layers import get_channel_layer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

async def test_redis():
    channel_layer = get_channel_layer()
    print(f"Channel layer: {channel_layer}")
    try:
        await channel_layer.send('test_channel', {'type': 'test.message'})
        print("Successfully sent message to Redis")
    except Exception as e:
        print(f"Error connecting to Redis: {e}")

if __name__ == "__main__":
    asyncio.run(test_redis())
