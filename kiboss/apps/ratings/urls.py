"""URL Configuration for Ratings API"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.ratings.views import RatingViewSet, TrustDetailsViewSet

router = DefaultRouter()
router.register(r'', RatingViewSet, basename='rating')
router.register(r'trust', TrustDetailsViewSet, basename='trust')

urlpatterns = [
    path('', include(router.urls)),
]
