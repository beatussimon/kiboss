from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from kiboss.apps.users.models import User
from urllib.parse import parse_qs

@database_sync_to_async
def get_user(token_key):
    try:
        from rest_framework_simplejwt.tokens import AccessToken, UntypedToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        
        # 1. Basic validation of the token string
        try:
            UntypedToken(token_key)
        except (InvalidToken, TokenError) as e:
            print(f"DEBUG AUTH: UntypedToken validation failed: {str(e)}")
            return AnonymousUser()

        # 2. Decode and get user ID
        try:
            token = AccessToken(token_key)
            user_id = token['user_id']
            user = User.objects.get(id=user_id)
            if not user.is_active:
                print(f"DEBUG AUTH: User {user.email} is inactive")
                return AnonymousUser()
            print(f"DEBUG AUTH: Success for user {user.email} (ID: {user_id})")
            return user
        except (InvalidToken, TokenError) as e:
            print(f"DEBUG AUTH: AccessToken validation failed: {str(e)}")
            return AnonymousUser()
        except User.DoesNotExist:
            print(f"DEBUG AUTH: User ID {user_id} not found")
            return AnonymousUser()
            
    except Exception as e:
        print(f"DEBUG AUTH: Unexpected error in get_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return AnonymousUser()

class JwtAuthMiddleware:
    """
    Custom middleware that takes a token from the query string and authenticates the user.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        print(f"DEBUG ASGI: WebSocket request to {scope.get('path')}")
        try:
            # Extract token from query string
            query_string = scope.get("query_string", b"").decode("utf-8")
            from urllib.parse import parse_qs
            query_params = parse_qs(query_string)
            token = query_params.get("token", [None])[0]
            
            if token:
                user = await get_user(token)
                scope["user"] = user
            else:
                print("DEBUG AUTH: No token provided in query string")
                scope["user"] = AnonymousUser()
        except Exception as e:
            print(f"DEBUG AUTH: Exception in middleware __call__: {str(e)}")
            import traceback
            traceback.print_exc()
            scope["user"] = AnonymousUser()
            
        return await self.app(scope, receive, send)
