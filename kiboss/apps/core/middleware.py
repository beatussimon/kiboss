from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from kiboss.apps.users.models import User
from urllib.parse import parse_qs

@database_sync_to_async
def get_user(token_key):
    try:
        token = AccessToken(token_key)
        user_id = token['user_id']
        print(f"DEBUG: Token valid, user_id: {user_id}")
        user = User.objects.get(id=user_id)
        print(f"DEBUG: User found: {user.email}")
        return user
    except Exception as e:
        print(f"DEBUG: Auth error: {str(e)}")
        return AnonymousUser()

class JwtAuthMiddleware:
    """
    Custom middleware that takes a token from the query string and authenticates the user.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]
        
        print(f"DEBUG: WebSocket connection attempt, token present: {bool(token)}")
        
        if token:
            user = await get_user(token)
            scope["user"] = user
        else:
            scope["user"] = AnonymousUser()
            
        return await self.app(scope, receive, send)
