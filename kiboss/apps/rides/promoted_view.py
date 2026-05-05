from rest_framework import viewsets, permissions
from rest_framework.response import Response
from kiboss.apps.rides.models import Ride
from kiboss.apps.rides.serializers import RideListSerializer

class PromotedRideViewSet(viewsets.ModelViewSet):
    queryset = Ride.objects.none()
    serializer_class = RideListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def list(self, request, *args, **kwargs):
        # Temporary mock implementation to return empty list and avoid 404
        return Response({"count": 0, "next": None, "previous": None, "results": []})
