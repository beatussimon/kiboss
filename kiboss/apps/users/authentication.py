from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Check standard Authorization header first
        header = self.get_header(request)
        if header is None:
            # Fallback to HttpOnly cookie
            raw_token = request.COOKIES.get('access_token')
            if raw_token:
                validated_token = self.get_validated_token(raw_token)
                # SEC-03: Check blacklist — prevents logged-out tokens from authenticating
                try:
                    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
                    jti = validated_token.get('jti')
                    if jti and BlacklistedToken.objects.filter(token__jti=jti).exists():
                        return None
                except Exception:
                    # token_blacklist app may not be installed in all environments
                    pass
                return self.get_user(validated_token), validated_token
        return super().authenticate(request)
