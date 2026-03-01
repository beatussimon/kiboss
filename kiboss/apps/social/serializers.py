from rest_framework import serializers
from django.contrib.auth import get_user_model
from kiboss.apps.social.models import Like, Follow, Bookmark
from kiboss.apps.assets.models import Asset

User = get_user_model()

class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']

class AssetMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'name', 'asset_type']

class LikeSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    asset = serializers.SerializerMethodField()
    
    class Meta:
        model = Like
        fields = ['id', 'user', 'entity_type', 'entity_id', 'asset', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

    def get_asset(self, obj):
        if obj.entity_type == 'ASSET':
            try:
                asset = Asset.objects.get(id=obj.entity_id)
                return AssetMinimalSerializer(asset).data
            except Asset.DoesNotExist:
                return None
        return None

class FollowSerializer(serializers.ModelSerializer):
    follower = UserMinimalSerializer(read_only=True)
    following = UserMinimalSerializer(read_only=True)
    following_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = Follow
        fields = ['id', 'follower', 'following', 'following_id', 'entity_type', 'created_at']
        read_only_fields = ['id', 'follower', 'following', 'created_at']

    def create(self, validated_data):
        following_id = validated_data.pop('following_id', None)
        if following_id:
            try:
                following_user = User.objects.get(id=following_id)
                validated_data['following'] = following_user
                return super().create(validated_data)
            except User.DoesNotExist:
                raise serializers.ValidationError({"following_id": "User does not exist"})
        return super().create(validated_data)


class BookmarkSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    asset = serializers.SerializerMethodField()
    
    class Meta:
        model = Bookmark
        fields = ['id', 'user', 'entity_type', 'entity_id', 'asset', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

    def get_asset(self, obj):
        if obj.entity_type == 'ASSET':
            try:
                asset = Asset.objects.get(id=obj.entity_id)
                return AssetMinimalSerializer(asset).data
            except Asset.DoesNotExist:
                return None
        return None


class EngagementSerializer(serializers.Serializer):
    """Serializer for engagement counts on an entity."""
    like_count = serializers.IntegerField()
    bookmark_count = serializers.IntegerField()
    follower_count = serializers.IntegerField()
    is_liked = serializers.BooleanField()
    is_bookmarked = serializers.BooleanField()
    is_following = serializers.BooleanField()
