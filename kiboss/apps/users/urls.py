"""
URL Configuration for Users API
"""

from django.urls import path
from .serializers import CustomTokenObtainPairSerializer
from .views import (
    CurrentUserView, PublicUserView, RegisterView, CorporateRegistrationView, BusinessConfigView,
    BusinessCategoryListView, VerifyEmailView, CorporateWorkerViewSet, TierListView, UpgradeView,
    WorkerPasswordResetView, CurrentUserAnalyticsView, CookieTokenObtainPairView, CookieTokenRefreshView,
    LogoutView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('corporate/register/', CorporateRegistrationView.as_view(), name='corporate-register'),
    path('corporate/workers/', CorporateWorkerViewSet.as_view(), name='corporate-workers'),
    path('corporate/workers/reset-password/', WorkerPasswordResetView.as_view(), name='corporate-workers-reset-password'),
    path('business/config/', BusinessConfigView.as_view(), name='business-config'),
    path('business/categories/', BusinessCategoryListView.as_view(), name='business-categories'),
    path('tiers/', TierListView.as_view(), name='tier-list'),
    path('upgrade/', UpgradeView.as_view(), name='upgrade'),
    # JWT endpoints using HttpOnly cookies
    path('token/', CookieTokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Current user endpoints (must come before <uuid> routes)
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/analytics/', CurrentUserAnalyticsView.as_view(), name='current-user-analytics'),
    
    # Public user profile endpoint (must come after /me/)
    path('<uuid:user_id>/public/', PublicUserView.as_view(), name='public-user'),
]
