"""
URL Configuration for Users API
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import CustomTokenObtainPairSerializer
from .views import CurrentUserView, PublicUserView, RegisterView, CorporateRegistrationView, BusinessConfigView, VerifyEmailView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('corporate/register/', CorporateRegistrationView.as_view(), name='corporate-register'),
    path('business/config/', BusinessConfigView.as_view(), name='business-config'),
    # JWT endpoints with custom serializer for email authentication
    path('token/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Current user endpoints (must come before <uuid> routes)
    path('me/', CurrentUserView.as_view(), name='current-user'),
    
    # Public user profile endpoint (must come after /me/)
    path('<uuid:user_id>/public/', PublicUserView.as_view(), name='public-user'),
]
