from django.urls import re_path
from kiboss.apps.messaging import consumers

websocket_urlpatterns = [
    re_path(r'^/?ws/chat/(?P<thread_id>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
]
