"""
Serializers for Common API
"""

from rest_framework import serializers


class LocationQuerySerializer(serializers.Serializer):
    """Serializer for location-based queries"""
    
    latitude = serializers.FloatField(required=False, min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(required=False, min_value=-180.0, max_value=180.0)
    radius_km = serializers.FloatField(required=False, min_value=0.1, max_value=1000.0, default=50.0)
    query = serializers.CharField(required=False, allow_blank=True, max_length=255)
    
    def validate(self, data):
        """Validate that either coordinates or query is provided"""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        query = data.get('query')
        
        # At least one of coordinates or query must be provided
        if latitude is None or longitude is None:
            if not query:
                raise serializers.ValidationError(
                    'Either coordinates (latitude and longitude) or search query must be provided'
                )
        
        # Coordinates are validated by the field constraints (min_value/max_value)
        
        return data