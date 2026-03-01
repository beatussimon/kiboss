from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.social.views import LikeViewSet, FollowViewSet, BookmarkViewSet, EngagementView

router = DefaultRouter()
router.register(r'likes', LikeViewSet, basename='like')
router.register(r'follows', FollowViewSet, basename='follow')
router.register(r'bookmarks', BookmarkViewSet, basename='bookmark')
router.register(r'engagement', EngagementView, basename='engagement')

urlpatterns = [
    path('', include(router.urls)),
    path('following/', FollowViewSet.as_view({'get': 'following'}), name='user-following'),
    path('followers/', FollowViewSet.as_view({'get': 'followers'}), name='user-followers'),
]
