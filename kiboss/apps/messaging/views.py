"""
Views for Messaging API - Context-Aware Messaging
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from kiboss.apps.messaging.models import (
    Thread, Message, MessageAttachment, ContextType, ThreadType
)
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
        from kiboss.apps.messaging.models import ThreadType
        from kiboss.apps.rbac.models import UserRole, Role
        
        # Check if user has SUPPORT role
        is_support_staff = False
        if request.user.is_authenticated:
            is_support_staff = request.user.is_superuser or UserRole.objects.filter(
                user=request.user, 
                role=Role.SUPPORT
            ).exists()

        # For thread-level permissions
        if isinstance(obj, Thread):
            if is_support_staff and obj.thread_type == ThreadType.SUPPORT:
                return True
            return request.user in obj.participants.all()
            
        # For message-level permissions
        if isinstance(obj, Message):
            if is_support_staff and obj.thread.thread_type == ThreadType.SUPPORT:
                return True
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
        
        # Base permissions logic:
        # A user can see threads they participate in.
        # If they are SUPPORT staff, they can ALSO see all SUPPORT threads.
        from kiboss.apps.rbac.models import UserRole, Role
        from kiboss.apps.messaging.models import ThreadType
        from django.db.models import Q
        
        is_support_staff = self.request.user.is_superuser or UserRole.objects.filter(
            user=self.request.user, role=Role.SUPPORT
        ).exists()

        participant_filter = Q(participants=self.request.user)
        
        # Add logic for Corporate Support Workers
        if hasattr(self.request.user, 'corporate_worker') and self.request.user.corporate_worker.status == 'ACTIVE':
            worker = self.request.user.corporate_worker
            if worker.role == 'SUPPORT':
                # Can see SUPPORT threads where their corporate profile is the owner
                # Since thread is linked to user currently, the business owner is `worker.corporate_profile.user`
                participant_filter |= Q(participants=worker.corporate_profile.user, thread_type=ThreadType.SUPPORT)

        if is_support_staff:
            queryset = queryset.filter(
                participant_filter | Q(thread_type=ThreadType.SUPPORT)
            ).distinct()
        else:
            queryset = queryset.filter(participant_filter).distinct()
        
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

    def create(self, request, *args, **kwargs):
        """Disallow non-contextual thread creation."""
        return Response(
            {
                'error': 'Free-form messaging is not allowed. Use create_contextual with valid context.',
                'code': 'CONTEXT_REQUIRED',
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get total unread message count for the user."""
        from kiboss.apps.messaging.models import Message
        count = Message.objects.filter(
            thread__participants=request.user
        ).exclude(
            sender=request.user
        ).exclude(
            read_receipts__user=request.user
        ).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def messages(self, request, pk=None):
        """Send a message to the thread."""
        thread = self.get_object()
        
        # Check if user is participant or support staff evaluating a support thread
        from kiboss.apps.messaging.models import ThreadType
        from kiboss.apps.rbac.models import UserRole, Role
        
        is_support_staff = request.user.is_superuser or UserRole.objects.filter(
            user=request.user, role=Role.SUPPORT
        ).exists()
        
        is_corporate_support = False
        if hasattr(request.user, 'corporate_worker') and request.user.corporate_worker.status == 'ACTIVE':
            worker = request.user.corporate_worker
            if worker.role == 'SUPPORT' and thread.thread_type == ThreadType.SUPPORT:
                if worker.corporate_profile.user in thread.participants.all():
                    is_corporate_support = True
        
        is_authorized = (request.user in thread.participants.all()) or (
            is_support_staff and thread.thread_type == ThreadType.SUPPORT
        ) or is_corporate_support
        
        if not is_authorized:
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
            
            # Check if this message should bump/create a StaffTask
            if thread.thread_type in [ThreadType.SUPPORT, ThreadType.DISPUTE]:
                from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
                from django.contrib.contenttypes.models import ContentType
                
                t_type = TaskType.SUPPORT_TICKET if thread.thread_type == ThreadType.SUPPORT else TaskType.DISPUTE_RESOLUTION
                role = 'SUPPORT'
                
                # Fetch target_user for task assignment context
                target_user = None
                for participant in thread.participants.all():
                    if not participant.is_superuser and participant != request.user:
                        target_user = participant
                        break
                
                if not target_user: target_user = request.user
                
                task, created = StaffTask.objects.get_or_create(
                    task_type=t_type,
                    content_type=ContentType.objects.get_for_model(thread.__class__),
                    object_id=thread.id,
                    defaults={
                        'title': f"{thread.get_thread_type_display()}: {thread.subject}",
                        'description': f"New message from {request.user.email}: {message.content[:100]}",
                        'status': TaskStatus.PENDING,
                        'priority': TaskPriority.HIGH if thread.thread_type == ThreadType.DISPUTE else TaskPriority.MEDIUM,
                        'assigned_role': role,
                        'created_by': target_user
                    }
                )
                
                if not created and task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                    # Re-open the task
                    task.status = TaskStatus.PENDING
                    task.description += f"\n[System Re-opened by message from {request.user.email}]"
                    task.save(update_fields=['status', 'description', 'updated_at'])
            
            # Broadcast via Channels to the specific thread
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            
            message_data = MessageSerializer(message).data
            
            # Convert UUID objects to strings for channel layer serialization
            import json
            from rest_framework.renderers import JSONRenderer
            message_data_json = json.loads(JSONRenderer().render(message_data))
            
            if channel_layer:
                try:
                    chat_group = f'chat_{str(thread.id)}'
                    async_to_sync(channel_layer.group_send)(
                        chat_group,
                        {
                            'type': 'chat_message',
                            'data': message_data_json
                        }
                    )
                    
                    # Also broadcast to other participants' notification groups for unread counts
                    for participant in thread.participants.all():
                        if participant.id != request.user.id:
                            participant_id_str = str(participant.id)
                            notif_group = f'notifications_{participant_id_str}'
                            async_to_sync(channel_layer.group_send)(
                                notif_group,
                                {
                                    'type': 'new_message',
                                    'data': message_data_json
                                }
                            )
                except Exception as e:
                    import logging
                    logger = logging.getLogger('kiboss')
                    logger.error(f"Failed to broadcast new message: {str(e)}")
            
            return Response(
                message_data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def message_list(self, request, pk=None):
        """Get all messages in the thread with pagination."""
        thread = self.get_object()
        
        # Check if user is participant or support staff
        from kiboss.apps.messaging.models import ThreadType
        from kiboss.apps.rbac.models import UserRole, Role
        
        is_support_staff = request.user.is_superuser or UserRole.objects.filter(
            user=request.user, role=Role.SUPPORT
        ).exists()
        
        is_corporate_support = False
        if hasattr(request.user, 'corporate_worker') and request.user.corporate_worker.status == 'ACTIVE':
            worker = request.user.corporate_worker
            if worker.role == 'SUPPORT' and thread.thread_type == ThreadType.SUPPORT:
                if worker.corporate_profile.user in thread.participants.all():
                    is_corporate_support = True
        
        is_authorized = (request.user in thread.participants.all()) or (
            is_support_staff and thread.thread_type == ThreadType.SUPPORT
        ) or is_corporate_support
        
        if not is_authorized:
            return Response(
                {'error': 'You are not a participant of this thread'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        messages = thread.messages.filter(is_deleted=False).order_by('-created_at')
        
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
            "thread_type": "INQUIRY|BOOKING|RIDE|DISPUTE|SUPPORT|DIRECT",
            "subject": "optional subject",
            "listing_id": "optional uuid (for asset)",
            "booking_id": "optional uuid",
            "ride_id": "optional uuid"
        }
        """
        target_user_id = request.data.get('target_user_id')
        # Map 'admin' to an actual superuser if requested
        if target_user_id == 'admin':
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                target_user_id = str(admin_user.id)
            else:
                return Response({'error': 'No administrator available'}, status=404)

        thread_type = request.data.get('thread_type', ThreadType.INQUIRY)
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
        
        # Context is required for everything EXCEPT DIRECT or SUPPORT threads
        is_context_optional = thread_type in [ThreadType.DIRECT, ThreadType.SUPPORT]
        
        provided_context_ids = [ctx for ctx in [listing_id, booking_id, ride_id] if ctx]
        if not is_context_optional and len(provided_context_ids) != 1:
            return Response(
                {
                    'error': 'Exactly one context is required (listing_id, booking_id, or ride_id)',
                    'code': 'INVALID_CONTEXT'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if is_context_optional and len(provided_context_ids) > 1:
             return Response(
                {
                    'error': 'Max one context allowed for direct/support messages',
                    'code': 'INVALID_CONTEXT'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate sender is not trying to contact themselves
        if str(request.user.id) == str(target_user_id):
            return Response(
                {'error': 'You cannot start a conversation with yourself', 'code': 'SELF_CONVERSATION'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if thread_type not in [choice[0] for choice in ThreadType.choices]:
            return Response(
                {'error': 'Invalid thread_type', 'code': 'INVALID_THREAD_TYPE'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Recipient user not found', 'code': 'USER_NOT_FOUND'},
                status=status.HTTP_404_NOT_FOUND
            )

        context_type = None
        context_id = None
        booking = None
        ride = None
        asset = None

        # Validate listing exists if provided
        if listing_id:
            from kiboss.apps.assets.models import Asset
            try:
                asset = Asset.objects.get(id=listing_id)
                # Check if sender is trying to contact the owner (Skip for support)
                if thread_type not in [ThreadType.SUPPORT, ThreadType.DIRECT]:
                    if str(asset.owner.id) != str(target_user_id):
                        return Response(
                            {'error': 'Target user is not the owner of this listing', 'code': 'INVALID_RECIPIENT'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
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
            context_type = ContextType.ASSET
            context_id = asset.id
        
        # Validate booking exists if provided
        if booking_id:
            from kiboss.apps.bookings.models import Booking
            try:
                booking = Booking.objects.get(id=booking_id)
                # Check if user is related to this booking (Skip for support)
                if thread_type not in [ThreadType.SUPPORT]:
                    is_renter = str(booking.renter.id) == str(request.user.id)
                    is_owner = str(booking.asset.owner.id) == str(request.user.id)
                    if str(booking.renter.id) == str(target_user_id):
                        if not is_owner:
                            return Response({'error': 'Permission denied', 'code': 'PERMISSION_DENIED'}, status=403)
                    elif str(booking.asset.owner.id) == str(target_user_id):
                        if not is_renter:
                            return Response({'error': 'Permission denied', 'code': 'PERMISSION_DENIED'}, status=403)
                    else:
                        return Response({'error': 'Invalid recipient', 'code': 'INVALID_RECIPIENT'}, status=400)
            except Booking.DoesNotExist:
                return Response({'error': 'Booking not found', 'code': 'BOOKING_NOT_FOUND'}, status=404)
            context_type = ContextType.BOOKING
            context_id = booking.id
        
        # Validate ride exists if provided
        if ride_id:
            from kiboss.apps.rides.models import Ride
            try:
                ride = Ride.objects.get(id=ride_id)
                if thread_type not in [ThreadType.SUPPORT]:
                    if str(ride.driver.id) == str(target_user_id):
                        if str(ride.driver.id) == str(request.user.id):
                            return Response({'error': 'Self conversation', 'code': 'SELF_CONVERSATION'}, status=400)
                    else:
                        return Response({'error': 'Invalid recipient', 'code': 'INVALID_RECIPIENT'}, status=400)
            except Ride.DoesNotExist:
                return Response({'error': 'Ride not found', 'code': 'RIDE_NOT_FOUND'}, status=404)
            context_type = ContextType.RIDE
            context_id = ride.id
        
        if not is_context_optional and (not context_type or not context_id):
            return Response(
                {'error': 'Context is required', 'code': 'MISSING_CONTEXT'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce context/thread type consistency.
        if context_type:
            expected_thread_type = {
                ContextType.ASSET: ThreadType.INQUIRY,
                ContextType.BOOKING: ThreadType.BOOKING,
                ContextType.RIDE: ThreadType.RIDE,
            }[context_type]
            if thread_type != expected_thread_type and thread_type not in [ThreadType.DISPUTE, ThreadType.SUPPORT]:
                return Response(
                    {'error': f'{context_type} context requires thread type {expected_thread_type}', 'code': 'THREAD_CONTEXT_MISMATCH'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        with transaction.atomic():
            # 1. Look for existing threads
            filter_kwargs = {
                'thread_type': thread_type,
                'participants': request.user,
            }
            if context_type:
                filter_kwargs['context_type'] = context_type
                filter_kwargs['context_id'] = context_id

            existing_threads = (
                Thread.objects.filter(**filter_kwargs)
                .filter(participants=target_user)
                .distinct()
                .order_by('-updated_at')
            )
            
            if existing_threads.exists():
                thread = existing_threads.first()
                save_required = False
                if booking and thread.booking != booking:
                    thread.booking = booking
                    save_required = True
                if ride and thread.ride != ride:
                    thread.ride = ride
                    save_required = True
                if save_required:
                    thread.save(update_fields=['booking', 'ride', 'updated_at'])
                
                # Check if we need to bump or create a StaffTask for existing support threads
                if thread_type in [ThreadType.SUPPORT, ThreadType.DISPUTE]:
                    from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
                    from django.contrib.contenttypes.models import ContentType
                    
                    t_type = TaskType.SUPPORT_TICKET if thread_type == ThreadType.SUPPORT else TaskType.DISPUTE_RESOLUTION
                    role = 'SUPPORT'
                    
                    task, created = StaffTask.objects.get_or_create(
                        task_type=t_type,
                        content_type=ContentType.objects.get_for_model(Thread),
                        object_id=thread.id,
                        defaults={
                            'title': f"{thread.get_thread_type_display()}: {thread.subject}",
                            'description': f"Re-opened {thread_type.lower()} thread by {request.user.email}.",
                            'status': TaskStatus.PENDING,
                            'priority': TaskPriority.HIGH if thread_type == ThreadType.DISPUTE else TaskPriority.MEDIUM,
                            'assigned_role': role,
                            'created_by': request.user
                        }
                    )
                    
                    if not created and task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                        # Re-open the task
                        task.status = TaskStatus.PENDING
                        task.description += "\n[System Re-opened by user reply]"
                        task.save(update_fields=['status', 'description', 'updated_at'])
                
                return Response(ThreadSerializer(thread, context={'request': request}).data)

            # 2. Create new contextual thread
            if not subject:
                if context_type == ContextType.ASSET and asset is not None:
                    subject = f'Inquiry about {asset.name}'
                elif context_type == ContextType.BOOKING and booking is not None:
                    subject = f'Inquiry about booking #{booking.id}'
                elif context_type == ContextType.RIDE and ride is not None:
                    subject = f'Inquiry about ride to {ride.destination}'
                else:
                    subject = f'Conversation about {thread_type.lower()}'

            thread = Thread.objects.create(
                thread_type=thread_type,
                subject=subject,
                context_type=context_type,
                context_id=context_id,
                booking=booking,
                ride=ride,
            )
            thread.participants.add(request.user, target_user)
            
            # Auto-create a StaffTask if it's a SUPPORT or DISPUTE thread
            if thread_type in [ThreadType.SUPPORT, ThreadType.DISPUTE]:
                from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
                from django.contrib.contenttypes.models import ContentType
                
                t_type = TaskType.SUPPORT_TICKET if thread_type == ThreadType.SUPPORT else TaskType.DISPUTE_RESOLUTION
                role = 'SUPPORT'
                
                StaffTask.objects.create(
                    title=f"{thread.get_thread_type_display()}: {subject}",
                    description=f"New {thread_type.lower()} thread started by {request.user.email}. Check Messaging center.",
                    task_type=t_type,
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.HIGH if thread_type == ThreadType.DISPUTE else TaskPriority.MEDIUM,
                    assigned_role=role,
                    content_type=ContentType.objects.get_for_model(Thread),
                    object_id=thread.id,
                    created_by=request.user
                )

        return Response(
            ThreadSerializer(thread, context={'request': request}).data,
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

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        """Mark all unread messages in a thread as read for the current user."""
        thread = self.get_object()
        
        # Determine authorization
        from kiboss.apps.messaging.models import ThreadType
        from kiboss.apps.rbac.models import UserRole, Role
        
        is_support_staff = request.user.is_superuser or UserRole.objects.filter(
            user=request.user, role=Role.SUPPORT
        ).exists()
        
        is_corporate_support = False
        if hasattr(request.user, 'corporate_worker') and request.user.corporate_worker.status == 'ACTIVE':
            worker = request.user.corporate_worker
            if worker.role == 'SUPPORT' and thread.thread_type == ThreadType.SUPPORT:
                if worker.corporate_profile.user in thread.participants.all():
                    is_corporate_support = True
                    
        is_authorized = (request.user in thread.participants.all()) or (
            is_support_staff and thread.thread_type == ThreadType.SUPPORT
        ) or is_corporate_support
        
        if not is_authorized:
            return Response(
                {'error': 'You are not authorized to view/read this thread'},
                status=status.HTTP_403_FORBIDDEN
            )

        from kiboss.apps.messaging.models import MessageReadReceipt
        from django.db import transaction

        # Find messages not sent by me and not already read by me
        unread_messages = thread.messages.exclude(sender=request.user).exclude(read_receipts__user=request.user)
        message_ids = list(unread_messages.values_list('id', flat=True))

        if not message_ids:
            return Response({'status': 'ok', 'count': 0})

        with transaction.atomic():
            # 1. Create receipts in bulk
            receipts = [
                MessageReadReceipt(message_id=m_id, user=request.user)
                for m_id in message_ids
            ]
            MessageReadReceipt.objects.bulk_create(receipts, ignore_conflicts=True)

            # 2. Update global status ONLY if it's not already READ
            # This is a shared state, so we only set it once (the first time someone reads it)
            thread.messages.filter(id__in=message_ids, status='SENT').update(
                status='READ',
                read_at=timezone.now(),
                updated_at=timezone.now()
            )

        # 3. Broadcast to others
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            try:
                chat_group = f'chat_{str(thread.id)}'
                async_to_sync(channel_layer.group_send)(
                    chat_group,
                    {
                        'type': 'chat_read_receipt',
                        'user_id': str(request.user.id),
                        'message_ids': [str(m_id) for m_id in message_ids]
                    }
                )
            except Exception as e:
                # Log but don't fail the request if broadcast fails
                import logging
                logger = logging.getLogger('kiboss')
                logger.error(f"Failed to broadcast read receipt: {str(e)}")

        return Response({'status': 'ok', 'count': len(message_ids)})


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
        
        from kiboss.apps.messaging.models import MessageReadReceipt
        from django.db import transaction

        # Don't mark our own messages as read by us
        if message.sender == request.user:
            return Response(MessageSerializer(message).data)

        with transaction.atomic():
            # Create receipt
            MessageReadReceipt.objects.get_or_create(message=message, user=request.user)
            
            # Update global status ONLY if it's not already READ
            if message.status != 'READ':
                message.status = 'READ'
                message.read_at = timezone.now()
                message.save(update_fields=['status', 'read_at', 'updated_at'])
                
                # Broadcast read receipt
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                if channel_layer:
                    try:
                        chat_group = f'chat_{str(message.thread.id)}'
                        async_to_sync(channel_layer.group_send)(
                            chat_group,
                            {
                                'type': 'chat_read_receipt',
                                'user_id': str(request.user.id),
                                'message_ids': [str(message.id)]
                            }
                        )
                    except Exception as e:
                        import logging
                        logger = logging.getLogger('kiboss')
                        logger.error(f"Failed to broadcast individual read receipt: {str(e)}")
            
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
