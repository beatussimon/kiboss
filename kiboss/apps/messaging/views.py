"""
Views for Messaging API - Context-Aware Messaging
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from kiboss.apps.messaging.models import Thread, Message, MessageAttachment
from kiboss.apps.messaging.serializers import (
    ThreadSerializer, ThreadDetailSerializer, MessageSerializer,
    CreateThreadSerializer, CreateMessageSerializer, MessageAttachmentSerializer,
    CreateAttachmentSerializer
)
from kiboss.apps.users.models import User


class MessagePagination(PageNumberPagination):
    """Pagination for messages."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class IsThreadParticipant(permissions.BasePermission):
    """
    Permission check: only thread participants can access the thread.
    """
    def has_object_permission(self, request, view, obj):
        # For thread-level permissions
        if isinstance(obj, Thread):
            return request.user in obj.participants.all()
        # For message-level permissions
        if isinstance(obj, Message):
            return request.user in obj.thread.participants.all()
        return False


class ThreadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing message threads.
    
    Provides CRUD operations for messaging threads.
    """
    queryset = Thread.objects.all().order_by('-updated_at')
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ThreadDetailSerializer
        return ThreadSerializer
    
    def get_queryset(self):
        """Filter threads to only show user's threads."""
        queryset = Thread.objects.prefetch_related('participants').order_by('-updated_at')
        
        # Filter by participant (current user)
        queryset = queryset.filter(participants=self.request.user)
        
        # Filter by thread type
        thread_type = self.request.query_params.get('thread_type')
        if thread_type:
            queryset = queryset.filter(thread_type=thread_type)
        
        # Filter by status
        thread_status = self.request.query_params.get('status')
        if thread_status:
            queryset = queryset.filter(status=thread_status)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create thread and add participant."""
        thread = serializer.save()
        thread.participants.add(self.request.user)
    
    @action(detail=True, methods=['post'])
    def messages(self, request, pk=None):
        """Send a message to the thread."""
        thread = self.get_object()
        
        # Check if user is participant
        if request.user not in thread.participants.all():
            return Response(
                {'error': 'You are not a participant of this thread'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if thread is locked
        if thread.status == 'LOCKED':
            return Response(
                {'error': 'Thread is locked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = CreateMessageSerializer(
            data=request.data,
            context={'thread': thread, 'request': request}
        )
        
        if serializer.is_valid():
            message = serializer.save()
            
            # Update thread message count
            thread.message_count += 1
            thread.save()
            
            return Response(
                MessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def message_list(self, request, pk=None):
        """Get all messages in the thread with pagination."""
        thread = self.get_object()
        
        # Check if user is participant
        if request.user not in thread.participants.all():
            return Response(
                {'error': 'You are not a participant of this thread'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        messages = thread.messages.filter(is_deleted=False).order_by('created_at')
        
        # Pagination
        paginator = MessagePagination()
        page = paginator.paginate_queryset(messages, request)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """Add a participant to the thread."""
        thread = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from kiboss.apps.users.models import User
        try:
            user = User.objects.get(id=user_id)
            if user not in thread.participants.all():
                thread.participants.add(user)
            return Response(ThreadSerializer(thread).data)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def create_direct(self, request):
        """
        DEPRECATED: Use create_contextual instead.
        Direct messages are no longer allowed without context.
        """
        return Response(
            {'error': 'Free-form messaging is not allowed. Use create_contextual endpoint with proper context.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['post'])
    def create_contextual(self, request):
        """
        Create or get a contextual thread based on listing/booking/ride.
        
        Request body:
        {
            "target_user_id": "uuid",
            "thread_type": "INQUIRY|BOOKING|RIDE|DISPUTE",
            "subject": "optional subject",
            "listing_id": "optional uuid (for asset)",
            "booking_id": "optional uuid",
            "ride_id": "optional uuid"
        }
        
        At least one context (listing_id, booking_id, or ride_id) OR thread_type must be provided.
        
        Validation:
        - Sender and recipient must exist
        - At least one context must be provided
        - Context must exist (listing, booking, or ride)
        - Sender must have permission to contact recipient (owner/driver)
        """
        target_user_id = request.data.get('target_user_id')
        thread_type = request.data.get('thread_type', 'INQUIRY')
        subject = request.data.get('subject', '')
        listing_id = request.data.get('listing_id')
        booking_id = request.data.get('booking_id')
        ride_id = request.data.get('ride_id')
        
        # Validate target_user_id is provided
        if not target_user_id:
            return Response(
                {'error': 'target_user_id is required', 'code': 'MISSING_TARGET_USER'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that context is provided
        if not (listing_id or booking_id or ride_id):
            return Response(
                {'error': 'At least one context (listing_id, booking_id, or ride_id) is required', 'code': 'MISSING_CONTEXT'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate sender is not trying to contact themselves
        if str(request.user.id) == str(target_user_id):
            return Response(
                {'error': 'You cannot start a conversation with yourself', 'code': 'SELF_CONVERSATION'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Recipient user not found', 'code': 'USER_NOT_FOUND'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate listing exists if provided
        if listing_id:
            from kiboss.apps.assets.models import Asset
            try:
                asset = Asset.objects.get(id=listing_id)
                # Check if sender is trying to contact the owner
                if str(asset.owner.id) != str(target_user_id):
                    return Response(
                        {'error': 'Target user is not the owner of this listing', 'code': 'INVALID_RECIPIENT'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # Check if user is trying to contact themselves
                if str(asset.owner.id) == str(request.user.id):
                    return Response(
                        {'error': 'You cannot contact yourself about your own listing', 'code': 'SELF_CONVERSATION'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Asset.DoesNotExist:
                return Response(
                    {'error': 'Listing not found', 'code': 'LISTING_NOT_FOUND'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Validate booking exists if provided
        if booking_id:
            from kiboss.apps.bookings.models import Booking
            try:
                booking = Booking.objects.get(id=booking_id)
                # Check if user is related to this booking (either renter or owner)
                is_renter = str(booking.renter.id) == str(request.user.id)
                is_owner = str(booking.owner.id) == str(request.user.id)
                
                # Check if target user is the other party in the booking
                if str(booking.renter.id) == str(target_user_id):
                    # Contacting renter - only owner can do this
                    if not is_owner:
                        return Response(
                            {'error': 'You can only contact the renter if you are the booking owner', 'code': 'PERMISSION_DENIED'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                elif str(booking.owner.id) == str(target_user_id):
                    # Contacting owner - only renter can do this
                    if not is_renter:
                        return Response(
                            {'error': 'You can only contact the owner if you are the renter', 'code': 'PERMISSION_DENIED'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                else:
                    return Response(
                        {'error': 'Target user is not a party to this booking', 'code': 'INVALID_RECIPIENT'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Booking.DoesNotExist:
                return Response(
                    {'error': 'Booking not found', 'code': 'BOOKING_NOT_FOUND'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Validate ride exists if provided
        if ride_id:
            from kiboss.apps.rides.models import Ride
            try:
                ride = Ride.objects.get(id=ride_id)
                # Check if user is trying to contact the driver
                if str(ride.driver.id) == str(target_user_id):
                    # Contacting driver - must not be the driver themselves
                    if str(ride.driver.id) == str(request.user.id):
                        return Response(
                            {'error': 'You cannot contact yourself about your own ride', 'code': 'SELF_CONVERSATION'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    return Response(
                        {'error': 'Target user is not the driver of this ride', 'code': 'INVALID_RECIPIENT'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Ride.DoesNotExist:
                return Response(
                    {'error': 'Ride not found', 'code': 'RIDE_NOT_FOUND'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Build filter for existing thread
        filter_kwargs = {
            'thread_type': thread_type,
            'participants': request.user,
        }
        
        # Add context to filter if provided
        if booking_id:
            filter_kwargs['booking_id'] = booking_id
        if ride_id:
            filter_kwargs['ride_id'] = ride_id
        
        # Check if thread already exists
        existing_threads = Thread.objects.filter(**filter_kwargs)
        
        if booking_id or ride_id:
            # For booking/ride threads, also check for target user
            existing_threads = existing_threads.filter(participants=target_user)
        
        if existing_threads.exists():
            thread = existing_threads.first()
            return Response(ThreadSerializer(thread).data)
        
        # Create new contextual thread
        thread = Thread.objects.create(
            thread_type=thread_type,
            subject=subject or f'Conversation about {thread_type.lower()}'
        )
        thread.participants.add(request.user, target_user)
        
        # Link to context if provided
        if booking_id:
            from kiboss.apps.bookings.models import Booking
            try:
                booking = Booking.objects.get(id=booking_id)
                thread.booking = booking
                if not subject:
                    thread.subject = f'Inquiry about booking #{booking.id}'
            except Booking.DoesNotExist:
                pass
        
        if ride_id:
            from kiboss.apps.rides.models import Ride
            try:
                ride = Ride.objects.get(id=ride_id)
                thread.ride = ride
                if not subject:
                    thread.subject = f'Inquiry about ride to {ride.destination}'
            except Ride.DoesNotExist:
                pass
        
        # Also link listing if provided (for INQUIRY type threads)
        if listing_id and thread_type == 'INQUIRY':
            from kiboss.apps.assets.models import Asset
            try:
                asset = Asset.objects.get(id=listing_id)
                if not subject:
                    thread.subject = f'Inquiry about {asset.name}'
            except Asset.DoesNotExist:
                pass
        
        thread.save()
        
        return Response(
            ThreadSerializer(thread).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """Leave the thread."""
        thread = self.get_object()
        thread.participants.remove(request.user)
        return Response({'status': 'left thread'})
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Lock the thread (admin only)."""
        thread = self.get_object()
        thread.lock(request.user)
        return Response(ThreadSerializer(thread).data)
    
    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """Unlock the thread (admin only)."""
        thread = self.get_object()
        thread.unlock(request.user)
        return Response(ThreadSerializer(thread).data)


class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual messages.
    """
    queryset = Message.objects.all().order_by('-created_at')
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter messages to only show user's threads."""
        queryset = Message.objects.all().order_by('-created_at')
        
        # Filter by thread
        thread_id = self.request.query_params.get('thread')
        if thread_id:
            queryset = queryset.filter(thread_id=thread_id)
        
        # Only show messages from threads user participates in
        queryset = queryset.filter(thread__participants=self.request.user)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark message as read."""
        message = self.get_object()
        
        # Check if user is participant
        if request.user not in message.thread.participants.all():
            return Response(
                {'error': 'You are not a participant of this thread'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message.status = 'READ'
        message.read_at = timezone.now()
        message.save()
        return Response(MessageSerializer(message).data)
    
    @action(detail=True, methods=['post'])
    def delete(self, request, pk=None):
        """Soft delete a message."""
        message = self.get_object()
        
        # Only allow sender to delete
        if message.sender != request.user:
            return Response(
                {'error': 'You can only delete your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message.soft_delete()
        return Response({'status': 'deleted'})


class AttachmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing message attachments.
    """
    queryset = MessageAttachment.objects.all()
    serializer_class = MessageAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateAttachmentSerializer
        return MessageAttachmentSerializer
    
    def get_queryset(self):
        """Filter attachments to only show user's thread attachments."""
        queryset = MessageAttachment.objects.all()
        
        # Filter by message thread
        message_id = self.request.query_params.get('message')
        if message_id:
            queryset = queryset.filter(message__thread_id=message_id)
        
        # Only show attachments from threads user participates in
        queryset = queryset.filter(message__thread__participants=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create attachment - requires message_id and file."""
        validated_data = serializer.validated_data
        message_obj = validated_data.pop('message_obj')
        file = validated_data['file']
        
        # Auto-detect file type
        file_type = validated_data.get('file_type', 'DOCUMENT')
        if file.content_type and file.content_type.startswith('image/'):
            file_type = 'IMAGE'
        elif file.content_type and file.content_type.startswith('video/'):
            file_type = 'VIDEO'
        elif file.content_type and file.content_type.startswith('audio/'):
            file_type = 'AUDIO'
        
        attachment = MessageAttachment.objects.create(
            message=message_obj,
            file=file,
            file_type=file_type,
            file_name=file.name,
            file_size=file.size,
            is_safe=True
        )
        return attachment


from django.utils import timezone
