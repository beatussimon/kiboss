"""
Views for Contracts API
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from kiboss.apps.contracts.models import Contract, ContractVersion, ContractStatus
from kiboss.apps.contracts.serializers import (
    ContractSerializer, ContractDetailSerializer,
    ContractCreateSerializer, ContractAcceptSerializer, ContractVersionSerializer
)


class ContractViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing contracts.
    """
    queryset = Contract.objects.all().order_by('-generated_at')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractSerializer
        elif self.action == 'retrieve':
            return ContractDetailSerializer
        elif self.action == 'create':
            return ContractCreateSerializer
        return ContractSerializer
    
    def get_queryset(self):
        queryset = Contract.objects.select_related(
            'booking', 'booking__asset', 'booking__renter'
        ).order_by('-generated_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by booking
        booking_id = self.request.query_params.get('booking_id')
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        
        # Filter by party (user is renter or asset owner)
        user = self.request.user
        queryset = queryset.filter(
            booking__renter=user
        ) | queryset.filter(booking__asset__owner=user)
        
        return queryset.distinct()
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept a contract."""
        serializer = ContractAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        contract = self.get_object()
        
        # Check if user is party to the contract
        if contract.booking.renter != request.user and contract.booking.asset.owner != request.user:
            return Response(
                {'error': 'You are not a party to this contract'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Accept based on user role
        try:
            if request.user == contract.booking.renter:
                contract.accept_by_renter(serializer.validated_data.get('signature', {}))
            elif request.user == contract.booking.asset.owner:
                contract.accept_by_owner(serializer.validated_data.get('signature', {}))
            
            response_serializer = ContractDetailSerializer(contract)
            return Response(response_serializer.data)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get contract version history."""
        contract = self.get_object()
        versions = contract.versions.all().order_by('-version')
        serializer = ContractVersionSerializer(versions, many=True)
        return Response(serializer.data)
