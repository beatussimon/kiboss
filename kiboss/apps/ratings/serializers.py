"""
Serializers for Ratings API
"""
from rest_framework import serializers
from kiboss.apps.ratings.models import Rating, RatingCategory, RatingStatus


class RatingSerializer(serializers.ModelSerializer):
    """Serializer for Rating model."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Rating
        fields = [
            'id', 'booking', 'ride', 'reviewer', 'reviewee',
            'category', 'category_display',
            'overall_rating', 'reliability_rating', 'communication_rating',
            'cleanliness_rating', 'timeliness_rating',
            'title', 'comment', 'private_feedback',
            'status', 'status_display',
            'is_mutually_revealed', 'revealed_at',
            'asset_rating',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RatingCreateSerializer(serializers.Serializer):
    """Serializer for creating ratings."""
    booking_id = serializers.UUIDField(required=False)
    ride_id = serializers.UUIDField(required=False)
    category = serializers.ChoiceField(choices=RatingCategory.choices)
    overall_rating = serializers.IntegerField(min_value=1, max_value=5)
    reliability_rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    communication_rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    cleanliness_rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    timeliness_rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    title = serializers.CharField(max_length=100, required=False, allow_blank=True)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    private_feedback = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    asset_rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
