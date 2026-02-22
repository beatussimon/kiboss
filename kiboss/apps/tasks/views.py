"""
Views for Tasks API - Custom Internal Staff Workflow
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction, models
from django.utils import timezone
from kiboss.apps.tasks.models import StaffTask, TaskStatus, TaskType
from kiboss.apps.tasks.serializers import StaffTaskSerializer, TaskActionSerializer, TaskAssignmentSerializer
from kiboss.apps.rbac.models import UserRole, Role
from kiboss.apps.assets.models import VerificationStatus, Asset
from kiboss.apps.users.serializers import UserSerializer


class StaffTaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for internal staff tasks.
    Provides the core logic for the custom admin-like dashboard.
    """
    queryset = StaffTask.objects.all()
    serializer_class = StaffTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter tasks based on user roles, permissions, and assignments.
        This implements dynamic role-based access to internal tasks.
        """
        user = self.request.user
        queryset = StaffTask.objects.all()

        # Support task_type filtering via query params (e.g., ?task_type=VEHICLE_VERIFICATION,IDENTITY_VERIFICATION)
        task_type_filter = self.request.query_params.get('task_type')
        if task_type_filter:
            types = task_type_filter.split(',')
            queryset = queryset.filter(task_type__in=types)
        
        # Get user's staff roles and permissions
        from kiboss.apps.rbac.models import UserRole, RolePermission, Permission, Role
        roles = UserRole.objects.filter(user=user).values_list('role', flat=True)
        user_permissions = RolePermission.objects.filter(role__in=roles).values_list('permission', flat=True)
        
        # Super admin sees everything (via is_superuser flag or SUPER_ADMIN role)
        if user.is_superuser or Role.SUPER_ADMIN in roles:
            return queryset.order_by('-priority', 'created_at')
            
        if not roles and not user.is_staff:
            # Regular users can only see tasks they created (submissions)
            return queryset.filter(created_by=user).order_by('created_at')
            
        # Dynamically map permissions to task types
        permission_task_map = {
            Permission.USER_VERIFY: [TaskType.IDENTITY_VERIFICATION, TaskType.CORPORATE_VERIFICATION],
            Permission.ASSET_VERIFY: [TaskType.VEHICLE_VERIFICATION, TaskType.ASSET_AUDIT],
            Permission.DISPUTE_VIEW: [TaskType.DISPUTE_RESOLUTION],
            Permission.SUPPORT_TICKET: [TaskType.SUPPORT_TICKET], 
        }
        
        allowed_types = []
        for perm in user_permissions:
            if perm in permission_task_map:
                allowed_types.extend(permission_task_map[perm])
            
        # Staff see tasks STRICTLY according to their permissions:
        # 1. Specifically assigned to their individual ID
        # 2. Specifically assigned to one of their roles
        # 3. Tasks assigned to general 'VERIFIER' role (if they have verifier permissions)
        # 4. Of a type that their permissions allow them to handle (unassigned pool)
        
        is_any_verifier = any(p in user_permissions for p in [Permission.USER_VERIFY, Permission.ASSET_VERIFY])
        
        return queryset.filter(
            models.Q(assigned_to=user) |
            models.Q(assigned_role__in=roles) |
            (models.Q(assigned_role='VERIFIER') if is_any_verifier else models.Q(pk__in=[])) |
            models.Q(task_type__in=allowed_types)
        ).distinct().order_by('-priority', 'created_at')

    def destroy(self, request, *args, **kwargs):
        """Only superusers can delete tasks."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can delete tasks.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign a task to a user or role. Only for superusers.
        """
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can assign tasks.'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        task = self.get_object()
        serializer = TaskAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            if 'assigned_to' in serializer.validated_data:
                task.assigned_to_id = serializer.validated_data['assigned_to']
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.ASSIGNED
            
            if 'assigned_role' in serializer.validated_data:
                task.assigned_role = serializer.validated_data['assigned_role']
                
            if 'priority' in serializer.validated_data:
                task.priority = serializer.validated_data['priority']
                
            task.save()
            
        return Response(self.get_serializer(task).data)

    @action(detail=False, methods=['get'])
    def staff_users(self, request):
        """
        List all users who have staff roles or are superusers.
        """
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can list staff users.'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Users with any role assigned or is_staff/is_superuser
        staff_ids = UserRole.objects.values_list('user_id', flat=True)
        from kiboss.apps.users.models import User
        users = User.objects.filter(
            models.Q(id__in=staff_ids) | 
            models.Q(is_staff=True) | 
            models.Q(is_superuser=True)
        ).distinct()
        
        return Response(UserSerializer(users, many=True).data)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """
        Handle Approve, Reject, or Request Changes for a task.
        This logic drives the verification workflow.
        """
        task = self.get_object()
        serializer = TaskActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action_type = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')
        
        # Verify the user has the role required for this task
        if not request.user.is_superuser:
            role_required = task.assigned_role
            if role_required and not UserRole.objects.filter(user=request.user, role=role_required).exists():
                return Response(
                    {'error': f'Only users with the {role_required} role can process this task.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        with transaction.atomic():
            # Update the task status
            task.reviewer_notes = notes
            task.assigned_to = request.user
            
            from kiboss.apps.common.services import VerificationService
            VerificationService.process_verification(task, action_type, request.user, notes)
            
            if action_type == 'APPROVE':
                task.status = TaskStatus.COMPLETED
                task.completion_date = timezone.now()
                
                # Activate latest pending subscription if it's a corporate verification
                if task.task_type == TaskType.CORPORATE_VERIFICATION:
                    profile = task.content_object
                    if profile:
                        latest_sub = profile.subscriptions.filter(status='PENDING').first()
                        if latest_sub:
                            latest_sub.status = 'ACTIVE'
                            latest_sub.save()
                        
            elif action_type == 'REJECT':
                task.status = TaskStatus.REJECTED
                        
            elif action_type == 'REQUEST_CHANGES':
                task.status = TaskStatus.CHANGES_REQUESTED

            elif action_type == 'REVOKE':
                task.status = TaskStatus.PENDING
                task.completion_date = None
            
            task.save()
            
        return Response(self.get_serializer(task).data)

    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get summary statistics for the staff dashboard."""
        tasks = self.get_queryset()
        
        return Response({
            'total_pending': tasks.filter(status=TaskStatus.PENDING).count(),
            'my_assigned': tasks.filter(assigned_to=request.user, status=TaskStatus.ASSIGNED).count(),
            'my_completed': tasks.filter(assigned_to=request.user, status=TaskStatus.COMPLETED).count(),
            'recent_requests': StaffTaskSerializer(tasks.filter(status=TaskStatus.PENDING)[:5], many=True).data
        })

    @action(detail=False, methods=['get'])
    def super_analytics(self, request):
        """
        Advanced 'supercharged' analytics for superusers.
        Aggregates high-level metrics across the entire platform.
        """
        if not request.user.is_superuser:
            return Response(
                {'error': 'Unauthorized access to advanced analytics.'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        from kiboss.apps.users.models import User
        from kiboss.apps.assets.models import Asset, AssetType
        from kiboss.apps.bookings.models import Booking
        from kiboss.apps.rides.models import Ride
        from kiboss.apps.payments.models import Payment
        from django.db.models import Sum, Count, Q
        from datetime import timedelta
        
        # 1. Financial Overview
        payments = Payment.objects.all()
        total_volume = payments.aggregate(total=Sum('amount'))['total'] or 0
        escrow_volume = payments.filter(status='ESCROW').aggregate(total=Sum('amount'))['total'] or 0
        released_volume = payments.filter(status='RELEASED').aggregate(total=Sum('amount'))['total'] or 0
        
        # 2. User Stats
        users = User.objects.all()
        total_users = users.count()
        verified_users = users.filter(is_identity_verified=True).count()
        new_users_today = users.filter(date_joined__date=timezone.now().date()).count()
        
        # 3. Asset Distribution
        assets = Asset.objects.all()
        total_assets = assets.count()
        assets_by_type = dict(assets.values('asset_type').annotate(count=Count('id')).values_list('asset_type', 'count'))
        
        # 4. Booking Performance
        bookings = Booking.objects.all()
        total_bookings = bookings.count()
        active_bookings = bookings.filter(status='ACTIVE').count()
        completed_bookings = bookings.filter(status='COMPLETED').count()
        cancelled_bookings = bookings.filter(status='CANCELLED').count()
        
        # 5. Ride Stats
        rides = Ride.objects.all()
        total_rides = rides.count()
        upcoming_rides = rides.filter(departure_time__gte=timezone.now()).count()
        
        # 6. Growth Chart Data (Last 7 days)
        growth_data = []
        for i in range(6, -1, -1):
            day = timezone.now().date() - timedelta(days=i)
            growth_data.append({
                'day': day.strftime('%a'),
                'users': users.filter(date_joined__date=day).count(),
                'bookings': bookings.filter(created_at__date=day).count(),
                'revenue': float(payments.filter(created_at__date=day).aggregate(s=Sum('amount'))['s'] or 0)
            })

        return Response({
            'financials': {
                'total_volume': float(total_volume),
                'escrow_volume': float(escrow_volume),
                'released_volume': float(released_volume),
            },
            'users': {
                'total': total_users,
                'verified': verified_users,
                'new_today': new_users_today,
            },
            'assets': {
                'total': total_assets,
                'by_type': assets_by_type,
            },
            'performance': {
                'total_bookings': total_bookings,
                'active_bookings': active_bookings,
                'completed_bookings': completed_bookings,
                'cancelled_bookings': cancelled_bookings,
                'total_rides': total_rides,
                'upcoming_rides': upcoming_rides,
            },
            'growth': growth_data
        })
