"""
Views for Notifications API - Event-Driven Notifications
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from kiboss.apps.notifications.models import Notification, NotificationPreference
from kiboss.apps.notifications.serializers import (
    NotificationSerializer, NotificationPreferenceSerializer
)


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications.
    
    Provides CRUD operations for user notifications.
    """
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter notifications to only show user's notifications."""
        queryset = Notification.objects.all().order_by('-created_at')
        
        # Filter by user (current user)
        queryset = queryset.filter(user=self.request.user)
        
        # Filter by status
        notif_status = self.request.query_params.get('status')
        if notif_status:
            queryset = queryset.filter(status=notif_status)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Only unread
        unread_only = self.request.query_params.get('unread')
        if unread_only and unread_only.lower() == 'true':
            queryset = queryset.exclude(status='READ')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.mark_read()
        return Response(NotificationSerializer(notification).data)
    
    @action(detail=False, methods=['post'])
    def read_all(self, request):
        """Mark all user notifications as read."""
        updated = Notification.objects.filter(
            user=request.user
        ).exclude(
            status='READ'
        ).update(
            status='READ',
            read_at=timezone.now()
        )
        return Response({'status': 'success', 'updated_count': updated})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications."""
        count = Notification.objects.filter(
            user=request.user
        ).exclude(
            status='READ'
        ).count()
        return Response({'unread_count': count})


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification preferences.
    """
    queryset = NotificationPreference.objects.all()
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Only show current user's preferences."""
        return NotificationPreference.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get or create preferences for current user."""
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj
    
    def list(self, request, *args, **kwargs):
        """Get preferences (get or create if not exists)."""
        try:
            preference = self.get_object()
            return Response(NotificationPreferenceSerializer(preference).data)
        except NotificationPreference.DoesNotExist:
            return Response({
                'email_enabled': True,
                'push_enabled': True,
                'sms_enabled': False,
                'categories': {},
                'quiet_hours_enabled': False,
                'quiet_hours_start': None,
                'quiet_hours_end': None
            })
    
    def create(self, request, *args, **kwargs):
        """Create preferences."""
        try:
            preference = NotificationPreference.objects.get(user=request.user)
            return Response(
                {'error': 'Preferences already exist'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except NotificationPreference.DoesNotExist:
            preference = NotificationPreference.objects.create(
                user=request.user,
                email_enabled=request.data.get('email_enabled', True),
                push_enabled=request.data.get('push_enabled', True),
                sms_enabled=request.data.get('sms_enabled', False),
                categories=request.data.get('categories', {}),
                quiet_hours_enabled=request.data.get('quiet_hours_enabled', False),
            )
            return Response(
                NotificationPreferenceSerializer(preference).data,
                status=status.HTTP_201_CREATED
            )
    
    def update(self, request, *args, **kwargs):
        """Update preferences."""
        preference = self.get_object()
        for key, value in request.data.items():
            if key in ['email_enabled', 'push_enabled', 'sms_enabled',
                      'categories', 'quiet_hours_enabled',
                      'quiet_hours_start', 'quiet_hours_end']:
                setattr(preference, key, value)
        preference.save()
        return Response(NotificationPreferenceSerializer(preference).data)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update preferences."""
        return self.update(request, *args, **kwargs)


from django.utils import timezone
