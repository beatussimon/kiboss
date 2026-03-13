"""
URL Configuration for Users API
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import CustomTokenObtainPairSerializer
from .views import CurrentUserView, PublicUserView, RegisterView, CorporateRegistrationView, BusinessConfigView, VerifyEmailView, CorporateWorkerViewSet, TierListView, UpgradeView, WorkerPasswordResetView, CurrentUserAnalyticsView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('corporate/register/', CorporateRegistrationView.as_view(), name='corporate-register'),
    path('corporate/workers/', CorporateWorkerViewSet.as_view(), name='corporate-workers'),
    path('corporate/workers/reset-password/', WorkerPasswordResetView.as_view(), name='corporate-workers-reset-password'),
    path('business/config/', BusinessConfigView.as_view(), name='business-config'),
    path('tiers/', TierListView.as_view(), name='tier-list'),
    path('upgrade/', UpgradeView.as_view(), name='upgrade'),
    # JWT endpoints with custom serializer for email authentication
    path('token/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Current user endpoints (must come before <uuid> routes)
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/analytics/', CurrentUserAnalyticsView.as_view(), name='current-user-analytics'),
    
    # Public user profile endpoint (must come after /me/)
    path('<uuid:user_id>/public/', PublicUserView.as_view(), name='public-user'),
]
