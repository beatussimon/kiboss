"""
ASGI config for kiboss project.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

print("DEBUG ASGI: Loading ASGI application configuration")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import websocket routing from apps
# Note: We'll need to define these in the respective apps
from kiboss.apps.messaging.routing import websocket_urlpatterns as messaging_urlpatterns
from kiboss.apps.notifications.routing import websocket_urlpatterns as notifications_urlpatterns
from kiboss.apps.core.middleware import JwtAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JwtAuthMiddleware(
        URLRouter(
            messaging_urlpatterns + notifications_urlpatterns
        )
    ),
})
