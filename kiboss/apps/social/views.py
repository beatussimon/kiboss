from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from kiboss.apps.social.models import Like, Follow, Bookmark
from kiboss.apps.social.serializers import (
    LikeSerializer, FollowSerializer, BookmarkSerializer, EngagementSerializer
)
from kiboss.apps.assets.models import Asset


class LikeViewSet(viewsets.ModelViewSet):
    queryset = Like.objects.all()
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='assets/(?P<asset_id>[^/.]+)')
    def like_asset(self, request, asset_id=None):
        asset = get_object_or_404(Asset, id=asset_id)
        like, created = Like.objects.get_or_create(
            user=request.user,
            entity_type='ASSET',
            entity_id=asset.id
        )
        serializer = self.get_serializer(like)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='assets/(?P<asset_id>[^/.]+)')
    def unlike_asset(self, request, asset_id=None):
        Like.objects.filter(
            user=request.user,
            entity_type='ASSET',
            entity_id=asset_id
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='rides/(?P<ride_id>[^/.]+)')
    def like_ride(self, request, ride_id=None):
        from kiboss.apps.rides.models import Ride
        ride = get_object_or_404(Ride, id=ride_id)
        like, created = Like.objects.get_or_create(
            user=request.user,
            entity_type='RIDE',
            entity_id=ride.id
        )
        serializer = self.get_serializer(like)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='rides/(?P<ride_id>[^/.]+)')
    def unlike_ride(self, request, ride_id=None):
        Like.objects.filter(
            user=request.user,
            entity_type='RIDE',
            entity_id=ride_id
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowViewSet(viewsets.ModelViewSet):
    queryset = Follow.objects.all()
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.action == 'list':
            return self.queryset.filter(follower=self.request.user)
        return self.queryset

    @action(detail=False, methods=['get'])
    def following(self, request):
        follows = Follow.objects.filter(follower=request.user)
        serializer = self.get_serializer(follows, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def followers(self, request):
        follows = Follow.objects.filter(following=request.user)
        serializer = self.get_serializer(follows, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='users/(?P<user_id>[^/.]+)')
    def follow_user(self, request, user_id=None):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target_user = get_object_or_404(User, id=user_id)
        
        if target_user == request.user:
            return Response({"detail": "You cannot follow yourself"}, status=status.HTTP_400_BAD_REQUEST)

        follow, created = Follow.objects.get_or_create(
            follower=request.user,
            following=target_user,
            entity_type=request.data.get('entity_type', 'USER')
        )
        serializer = self.get_serializer(follow)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='users/(?P<user_id>[^/.]+)')
    def unfollow_user(self, request, user_id=None):
        Follow.objects.filter(
            follower=request.user,
            following_id=user_id
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookmarkViewSet(viewsets.ModelViewSet):
    queryset = Bookmark.objects.all()
    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='assets/(?P<asset_id>[^/.]+)')
    def bookmark_asset(self, request, asset_id=None):
        asset = get_object_or_404(Asset, id=asset_id)
        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user,
            entity_type='ASSET',
            entity_id=asset.id
        )
        serializer = self.get_serializer(bookmark)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='assets/(?P<asset_id>[^/.]+)')
    def unbookmark_asset(self, request, asset_id=None):
        Bookmark.objects.filter(
            user=request.user,
            entity_type='ASSET',
            entity_id=asset_id
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='rides/(?P<ride_id>[^/.]+)')
    def bookmark_ride(self, request, ride_id=None):
        from kiboss.apps.rides.models import Ride
        ride = get_object_or_404(Ride, id=ride_id)
        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user,
            entity_type='RIDE',
            entity_id=ride.id
        )
        serializer = self.get_serializer(bookmark)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='rides/(?P<ride_id>[^/.]+)')
    def unbookmark_ride(self, request, ride_id=None):
        Bookmark.objects.filter(
            user=request.user,
            entity_type='RIDE',
            entity_id=ride_id
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EngagementView(viewsets.ViewSet):
    """Get engagement metrics for an entity (asset or ride)."""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['get'], url_path='(?P<entity_type>ASSET|RIDE)/(?P<entity_id>[^/.]+)')
    def get_engagement(self, request, entity_type=None, entity_id=None):
        like_count = Like.objects.filter(entity_type=entity_type, entity_id=entity_id).count()
        bookmark_count = Bookmark.objects.filter(entity_type=entity_type, entity_id=entity_id).count()
        
        # For follower count, get the owner's follower count
        follower_count = 0
        if entity_type == 'ASSET':
            try:
                asset = Asset.objects.get(id=entity_id)
                follower_count = Follow.objects.filter(following=asset.owner).count()
            except Asset.DoesNotExist:
                pass
        elif entity_type == 'RIDE':
            from kiboss.apps.rides.models import Ride
            try:
                ride = Ride.objects.get(id=entity_id)
                follower_count = Follow.objects.filter(following=ride.driver).count()
            except Ride.DoesNotExist:
                pass

        is_liked = False
        is_bookmarked = False
        is_following = False
        
        if request.user.is_authenticated:
            is_liked = Like.objects.filter(
                user=request.user, entity_type=entity_type, entity_id=entity_id
            ).exists()
            is_bookmarked = Bookmark.objects.filter(
                user=request.user, entity_type=entity_type, entity_id=entity_id
            ).exists()
            # Check if following the entity owner
            if entity_type == 'ASSET':
                try:
                    asset = Asset.objects.get(id=entity_id)
                    is_following = Follow.objects.filter(
                        follower=request.user, following=asset.owner
                    ).exists()
                except Asset.DoesNotExist:
                    pass
            elif entity_type == 'RIDE':
                from kiboss.apps.rides.models import Ride
                try:
                    ride = Ride.objects.get(id=entity_id)
                    is_following = Follow.objects.filter(
                        follower=request.user, following=ride.driver
                    ).exists()
                except Ride.DoesNotExist:
                    pass

        data = {
            'like_count': like_count,
            'bookmark_count': bookmark_count,
            'follower_count': follower_count,
            'is_liked': is_liked,
            'is_bookmarked': is_bookmarked,
            'is_following': is_following,
        }
        serializer = EngagementSerializer(data)
        return Response(serializer.data)
