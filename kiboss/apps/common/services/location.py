"""
Location Service for KIBOSS - Handles location-based queries and operations

Uses Haversine formula for distance calculations instead of GDAL.
"""

import math
from django.db.models import Q
from rest_framework import status, views, response
from rest_framework.permissions import AllowAny
from kiboss.apps.common.serializers import LocationQuerySerializer


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points
    on the Earth using the Haversine formula.
    
    Args:
        lat1: Latitude of point 1 in degrees
        lon1: Longitude of point 1 in degrees
        lat2: Latitude of point 2 in degrees
        lon2: Longitude of point 2 in degrees
    
    Returns:
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Earth's radius in kilometers
    earth_radius_km = 6371.0
    
    return earth_radius_km * c


class LocationService:
    """Service for handling location-based operations"""
    
    @staticmethod
    def get_nearby_rides(latitude: float, longitude: float, radius_km: float = 50.0):
        """
        Get rides near a specific location
        
        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            radius_km: Search radius in kilometers (default: 50km)
            
        Returns:
            List of rides within the specified radius, sorted by distance
        """
        from kiboss.apps.rides.models import Ride, RideStatus
        from django.utils import timezone
        
        # Get rides that are available
        rides = Ride.objects.filter(
            status__in=[RideStatus.OPEN, RideStatus.SCHEDULED],
            departure_time__gte=timezone.now()
        ).select_related('driver', 'vehicle_asset').prefetch_related('stops')
        
        # Calculate distances and filter by radius
        nearby_rides = []
        for ride in rides:
            # Check ride stops for proximity
            min_distance = None
            for stop in ride.stops.all():
                dist = haversine_distance(
                    latitude, longitude,
                    float(stop.latitude), float(stop.longitude)
                )
                if min_distance is None or dist < min_distance:
                    min_distance = dist
            
            # If no stops, skip this ride
            if min_distance is not None and min_distance <= radius_km:
                nearby_rides.append((ride, min_distance))
        
        # Sort by distance
        nearby_rides.sort(key=lambda x: x[1])
        
        return [ride for ride, _ in nearby_rides]
    
    @staticmethod
    def get_nearby_assets(latitude: float, longitude: float, radius_km: float = 50.0):
        """
        Get assets near a specific location
        """
        from kiboss.apps.assets.models import Asset, VerificationStatus
        
        # Get assets that are available with location data
        assets = Asset.objects.filter(
            is_active=True,
            is_listed=True
        ).exclude(
            latitude__isnull=True, longitude__isnull=True
        )
        
        # Calculate distances and filter by radius
        nearby_assets = []
        for asset in assets:
            if asset.latitude and asset.longitude:
                dist = haversine_distance(
                    latitude, longitude,
                    float(asset.latitude), float(asset.longitude)
                )
                if dist <= radius_km:
                    nearby_assets.append((asset, dist))
        
        # Sort by distance
        nearby_assets.sort(key=lambda x: x[1])
        
        return [asset for asset, _ in nearby_assets]
    
    @staticmethod
    def search_by_location(query: str, latitude: float = None, longitude: float = None, radius_km: float = 50.0):
        """
        Search for rides and assets by location query
        """
        from kiboss.apps.rides.models import Ride, RideStatus
        from kiboss.apps.assets.models import Asset
        from django.utils import timezone
        
        results = {
            'rides': [],
            'assets': []
        }
        
        # Search by text query
        text_query_rides = Q(origin__icontains=query) | Q(destination__icontains=query) | \
                           Q(route_name__icontains=query)
        
        rides = Ride.objects.filter(
            text_query_rides,
            status__in=[RideStatus.OPEN, RideStatus.SCHEDULED],
            departure_time__gte=timezone.now()
        ).select_related('driver', 'vehicle_asset').prefetch_related('stops').order_by('-departure_time')[:20]
        
        text_query_assets = Q(name__icontains=query) | Q(description__icontains=query) | \
                           Q(asset_type__icontains=query)
        
        assets = Asset.objects.filter(
            text_query_assets,
            is_active=True,
            is_listed=True
        ).order_by('-created_at')[:20]
        
        # If coordinates provided, filter by proximity
        if latitude is not None and longitude is not None:
            # Filter rides by proximity to stops
            nearby_rides = []
            for ride in rides:
                min_distance = None
                for stop in ride.stops.all():
                    dist = haversine_distance(
                        latitude, longitude,
                        float(stop.latitude), float(stop.longitude)
                    )
                    if min_distance is None or dist < min_distance:
                        min_distance = dist
                if min_distance is not None and min_distance <= radius_km:
                    nearby_rides.append((ride, min_distance))
            nearby_rides.sort(key=lambda x: x[1])
            rides = [r for r, _ in nearby_rides]
            
            # Filter assets by proximity
            nearby_assets = []
            for asset in assets:
                if asset.latitude and asset.longitude:
                    dist = haversine_distance(
                        latitude, longitude,
                        float(asset.latitude), float(asset.longitude)
                    )
                    if dist <= radius_km:
                        nearby_assets.append((asset, dist))
            nearby_assets.sort(key=lambda x: x[1])
            assets = [a for a, _ in nearby_assets]
        
        results['rides'] = rides
        results['assets'] = assets
        
        return results


class LocationView(views.APIView):
    """API view for location-based queries"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Handle GET requests for location-based searches"""
        serializer = LocationQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return response.Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get validated data
        latitude = serializer.validated_data.get('latitude')
        longitude = serializer.validated_data.get('longitude')
        radius_km = serializer.validated_data.get('radius_km', 50.0)
        query = serializer.validated_data.get('query', '')
        
        # Get search results
        results = LocationService.search_by_location(
            query=query,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km
        )
        
        # Serialize results
        from kiboss.apps.rides.serializers import RideListSerializer
        from kiboss.apps.assets.serializers import AssetListSerializer
        
        results_data = {
            'rides': RideListSerializer(results['rides'], many=True).data,
            'assets': AssetListSerializer(results['assets'], many=True).data,
            'query': query,
            'latitude': latitude,
            'longitude': longitude,
            'radius_km': radius_km
        }
        
        return response.Response(results_data, status=status.HTTP_200_OK)