import logging

logger = logging.getLogger(__name__)

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
            logger.debug(f"DEBUG AUTH: UntypedToken validation failed: {str(e)}")
            return AnonymousUser()

        # 2. Decode, check blacklist, and get user ID
        try:
            token = AccessToken(token_key)
            user_id = token['user_id']

            # SEC-07: Check token blacklist for logged-out tokens
            try:
                from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
                jti = token.get('jti')
                if jti and BlacklistedToken.objects.filter(token__jti=jti).exists():
                    logger.debug(f"DEBUG AUTH: Token {jti} is blacklisted")
                    return AnonymousUser()
            except Exception:
                pass

            user = User.objects.get(id=user_id)
            if not user.is_active:
                logger.debug(f"DEBUG AUTH: User {user.email} is inactive")
                return AnonymousUser()
            logger.debug(f"DEBUG AUTH: Success for user {user.email} (ID: {user_id})")
            return user
        except (InvalidToken, TokenError) as e:
            logger.debug(f"DEBUG AUTH: AccessToken validation failed: {str(e)}")
            return AnonymousUser()
        except User.DoesNotExist:
            logger.debug(f"DEBUG AUTH: User ID {user_id} not found")
            return AnonymousUser()
            
    except Exception as e:
        logger.debug(f"DEBUG AUTH: Unexpected error in get_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return AnonymousUser()

class JwtAuthMiddleware:
    """
    Custom middleware that takes a token from the query string or cookies and authenticates the user.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        logger.debug(f"DEBUG ASGI: WebSocket request to {scope.get('path')}")
        try:
            token = None
            
            # 1. Try to extract token from query string
            query_string = scope.get("query_string", b"").decode("utf-8")
            from urllib.parse import parse_qs
            query_params = parse_qs(query_string)
            token = query_params.get("token", [None])[0]
            
            # 2. Try to extract token from cookies if not in query string
            if not token:
                headers = dict(scope.get("headers", []))
                if b"cookie" in headers:
                    from http.cookies import SimpleCookie
                    cookies = SimpleCookie(headers[b"cookie"].decode("utf-8"))
                    if "access_token" in cookies:
                        token = cookies["access_token"].value
            
            if token:
                user = await get_user(token)
                scope["user"] = user
            else:
                logger.debug("DEBUG AUTH: No token provided in query string or cookies")
                scope["user"] = AnonymousUser()
        except Exception as e:
            logger.debug(f"DEBUG AUTH: Exception in middleware __call__: {str(e)}")
            import traceback
            traceback.print_exc()
            scope["user"] = AnonymousUser()
            
        return await self.app(scope, receive, send)
