"""
Views for Payments API
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from kiboss.apps.payments.models import (
    OfflinePaymentMethod, UserPaymentMethod, ManualPayment,
    Payment, PaymentStatus, Dispute
)
from kiboss.apps.payments.serializers import (
    PaymentSerializer, PaymentDetailSerializer,
    PaymentCreateSerializer, PaymentActionSerializer,
    DisputeSerializer, DisputeCreateSerializer,
    OfflinePaymentMethodSerializer,
    UserPaymentMethodSerializer, ManualPaymentSerializer
)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments.
    """
    queryset = Payment.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated]
    lookup_value_regex = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get payment summary for the current user."""
        user = request.user
        
        # Total paid (as renter)
        total_paid = Payment.objects.filter(
            booking__renter=user,
            status__in=[PaymentStatus.ESCROW, PaymentStatus.RELEASED]
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Total received (as owner)
        total_received = Payment.objects.filter(
            booking__asset__owner=user,
            status=PaymentStatus.RELEASED
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # In Escrow (as owner or renter)
        in_escrow = Payment.objects.filter(
            booking__asset__owner=user,
            status=PaymentStatus.ESCROW
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'total_paid': total_paid,
            'total_received': total_received,
            'in_escrow': in_escrow
        })
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PaymentSerializer
        elif self.action == 'retrieve':
            return PaymentDetailSerializer
        elif self.action == 'create':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'booking', 'booking__asset', 'booking__renter'
        ).order_by('-created_at')
        
        # Admins can see all payments
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            # Filter by user (renter or owner)
            user = self.request.user
            queryset = queryset.filter(
                booking__renter=user
            ) | queryset.filter(booking__asset__owner=user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by booking
        booking_id = self.request.query_params.get('booking_id')
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        
        return queryset.distinct()
    
    @action(detail=True, methods=['post'])
    def authorize(self, request, pk=None):
        """Authorize payment (simulate)."""
        payment = self.get_object()
        
        if payment.status != PaymentStatus.PENDING:
            return Response(
                {'error': 'Payment is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Simulate authorization
        card_details = {
            'last_four': request.data.get('card_last_four', '4242'),
            'brand': request.data.get('card_brand', 'VISA')
        }
        payment.authorize(payment.amount, card_details)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def hold_escrow(self, request, pk=None):
        """Move funds to escrow."""
        payment = self.get_object()
        
        if payment.status != PaymentStatus.AUTHORIZED:
            return Response(
                {'error': 'Payment must be authorized first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = request.data.get('amount')
        payment.hold_in_escrow(amount)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def release_escrow(self, request, pk=None):
        """Release escrow funds."""
        payment = self.get_object()
        
        if payment.status != PaymentStatus.ESCROW:
            return Response(
                {'error': 'Payment is not in escrow'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        release_amount = request.data.get('amount')
        deduct_fees = request.data.get('fees')
        payment.release_from_escrow(release_amount, deduct_fees)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Process refund."""
        payment = self.get_object()
        
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')
        
        payment.refund(amount, reason)
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def confirm_offline_payment(self, request, pk=None):
        """Confirm an offline payment (admin only)."""
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {'error': 'Only admins can confirm offline payments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        payment = self.get_object()
        
        if payment.status != PaymentStatus.PENDING:
            return Response(
                {'error': 'Payment is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update payment with offline confirmation details
        manual_confirmation = request.data.get('manual_confirmation', '')
        offline_method_id = request.data.get('offline_method_id')
        
        if manual_confirmation:
            payment.manual_confirmation = manual_confirmation
        
        if offline_method_id:
            try:
                offline_method = OfflinePaymentMethod.objects.get(id=offline_method_id)
                payment.offline_method = offline_method
            except OfflinePaymentMethod.DoesNotExist:
                return Response(
                    {'error': 'Offline payment method not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Move to escrow directly for offline payments (simulating bank transfer confirmation)
        payment.hold_in_escrow()
        
        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data)


class DisputeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing disputes.
    """
    queryset = Dispute.objects.all().order_by('-created_at')
    serializer_class = DisputeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Dispute.objects.select_related(
            'booking', 'payment', 'initiated_by'
        ).order_by('-created_at')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user
        user = self.request.user
        queryset = queryset.filter(
            initiated_by=user
        ) | queryset.filter(
            booking__renter=user
        ) | queryset.filter(
            booking__asset__owner=user
        )
        
        return queryset.distinct()
    
    def create(self, request, *args, **kwargs):
        """Create a new dispute."""
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from kiboss.apps.bookings.models import Booking
        
        booking_id = serializer.validated_data['booking_id']
        
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is party to the booking
        if request.user != booking.renter and request.user != booking.asset.owner:
            return Response(
                {'error': 'You are not a party to this booking'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if payment exists
        try:
            payment = booking.payment_info
        except Payment.DoesNotExist:
            return Response(
                {'error': 'No payment found for this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            dispute = Dispute.objects.create(
                booking=booking,
                payment=payment,
                initiated_by=request.user,
                reason=serializer.validated_data['reason'],
                description=serializer.validated_data['description'],
                disputed_amount=serializer.validated_data['disputed_amount']
            )
            
            # Freeze payment
            payment.freeze_for_dispute()
        
        response_serializer = DisputeSerializer(dispute)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a dispute (admin only).."""
        dispute = self.get_object()
        
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {'error': 'Only admins can resolve disputes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        resolution = request.data.get('resolution')
        notes = request.data.get('notes', '')
        
        dispute.resolve(resolution, notes, request.user)
        
        serializer = DisputeSerializer(dispute)
        return Response(serializer.data)


class OfflinePaymentMethodViewSet(viewsets.ModelViewSet):
    """ViewSet to list active offline payment methods and manage personal methods."""
    serializer_class = OfflinePaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return OfflinePaymentMethod.objects.all().order_by('-created_at')
        
        # Regular users see system-wide active methods AND their own methods
        from django.db.models import Q
        return OfflinePaymentMethod.objects.filter(
            Q(is_system_wide=True, is_active=True) | Q(owner=user)
        ).order_by('-created_at')

    def perform_create(self, serializer):
        # A regular user creating a method is automatically the owner
        # They cannot set is_system_wide to True unless staff
        is_system_wide = serializer.validated_data.get('is_system_wide', False)
        if is_system_wide and not (self.request.user.is_staff or self.request.user.is_superuser):
            is_system_wide = False
            
        serializer.save(
            owner=self.request.user,
            is_system_wide=is_system_wide
        )
        
    def perform_update(self, serializer):
        is_system_wide = serializer.validated_data.get('is_system_wide', getattr(serializer.instance, 'is_system_wide', False))
        if is_system_wide and not (self.request.user.is_staff or self.request.user.is_superuser):
            is_system_wide = False
            
        serializer.save(is_system_wide=is_system_wide)


class UserPaymentMethodViewSet(viewsets.ModelViewSet):
    """ViewSet for users to manage their own payment methods."""
    queryset = UserPaymentMethod.objects.all().order_by('-created_at')
    serializer_class = UserPaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Allow ?owner=<user_id> so checkout can load the asset/ride owner's methods
        owner_id = self.request.query_params.get('owner')
        if owner_id:
            # Public read: return active methods of the specified owner
            return UserPaymentMethod.objects.filter(
                user_id=owner_id, is_active=True
            ).order_by('-is_default', '-created_at')

        # Default: only the current user's own methods (full CRUD)
        return UserPaymentMethod.objects.filter(
            user=self.request.user
        ).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        if serializer.validated_data.get('is_default', False):
            UserPaymentMethod.objects.filter(
                user=self.request.user, is_default=True
            ).update(is_default=False)
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get('is_default', False):
            UserPaymentMethod.objects.filter(
                user=self.request.user, is_default=True
            ).exclude(pk=self.get_object().pk).update(is_default=False)
        serializer.save()


class ManualPaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for manual payment submissions for bookings."""
    queryset = ManualPayment.objects.all().order_by('-created_at')
    serializer_class = ManualPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Users can see their own submissions, admins can see all
        if self.request.user.is_staff or self.request.user.is_superuser:
            return ManualPayment.objects.all()
        
        # Get bookings where user is the renter/passenger/subscriber
        from kiboss.apps.bookings.models import Booking
        from kiboss.apps.rides.models import SeatBooking
        from kiboss.apps.users.models import UserSubscription, BusinessSubscription
        
        user_asset_bookings = Booking.objects.filter(renter=self.request.user).values_list('id', flat=True)
        user_ride_bookings = SeatBooking.objects.filter(passenger=self.request.user).values_list('id', flat=True)
        user_subscriptions = UserSubscription.objects.filter(user=self.request.user).values_list('id', flat=True)
        business_subscriptions = []
        if hasattr(self.request.user, 'corporate_profile'):
            business_subscriptions = BusinessSubscription.objects.filter(profile=self.request.user.corporate_profile).values_list('id', flat=True)
            
        return ManualPayment.objects.filter(
            booking_type='ASSET', booking_id__in=user_asset_bookings
        ) | ManualPayment.objects.filter(
            booking_type='RIDE', booking_id__in=user_ride_bookings
        ) | ManualPayment.objects.filter(
            booking_type='SUBSCRIPTION', booking_id__in=list(user_subscriptions) + list(business_subscriptions)
        )
    
    def create(self, request, *args, **kwargs):
        # 9. MANUAL PAYMENT VERIFICATION SCREENSHOT ENFORCEMENT
        if not request.FILES.get('receipt_image'):
            return Response(
                {'error': 'A screenshot of the payment receipt is strictly required. Your submission has been automatically rejected without it.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        data = request.data.copy()
        if data.get('booking_type') == 'SUBSCRIPTION' and not data.get('booking_id'):
            from kiboss.apps.users.models import UserSubscription
            plan_type = data.get('plan_type', 'PLUS')
            # Check if one already exists
            sub = UserSubscription.objects.filter(user=request.user, status='PENDING').first()
            if not sub:
                sub = UserSubscription.objects.create(
                    user=request.user,
                    plan_type=plan_type,
                    status='PENDING'
                )
            data['booking_id'] = str(sub.id)
            
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        
    def perform_create(self, serializer):
        payment = serializer.save(status=ManualPayment.Status.PENDING)
        
        # Create a StaffTask for subscription payments
        if payment.booking_type == 'SUBSCRIPTION':
            from kiboss.apps.tasks.models import StaffTask, TaskType
            from django.contrib.contenttypes.models import ContentType
            
            account_name = payment.user_payment_method.account_name if payment.user_payment_method else 'User'
            
            StaffTask.objects.create(
                title=f"Verify Subscription Payment for {account_name}",
                description=f"Manual payment submitted for subscription upgrade. Amount: {payment.amount} {payment.currency}. Please verify the transaction receipt.",
                task_type=TaskType.SUBSCRIPTION_VERIFICATION,
                content_type=ContentType.objects.get_for_model(payment),
                object_id=payment.id,
                priority='HIGH'
            )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a manual payment (admin only)."""
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {'error': 'Only admins can approve manual payments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        manual_payment = self.get_object()
        
        if manual_payment.status != ManualPayment.Status.PENDING:
            return Response(
                {'error': 'Manual payment is not pending approval'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        manual_payment.status = ManualPayment.Status.APPROVED
        manual_payment.admin_notes = request.data.get('admin_notes', '')
        manual_payment.reviewed_at = timezone.now()
        manual_payment.reviewed_by = request.user
        manual_payment.save()
        
        # Update the associated booking status if needed
        try:
            booking = manual_payment.booking
            if manual_payment.booking_type == 'ASSET':
                from kiboss.apps.bookings.services import BookingService
                BookingService.confirm_booking(booking.id, request.user)
            elif manual_payment.booking_type == 'RIDE':
                from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
                booking.status = SeatBookingStatus.CONFIRMED
                booking.save()
            elif manual_payment.booking_type == 'SUBSCRIPTION':
                from datetime import timedelta
                # Update subscription
                duration_days = 30
                if hasattr(booking, 'plan_type') and booking.plan_type == 'YEARLY':
                    duration_days = 365
                booking.status = 'ACTIVE'
                booking.start_date = timezone.now()
                booking.end_date = timezone.now() + timedelta(days=duration_days)
                booking.save()
                
                # Also upgrade the user's account tier
                if hasattr(booking, 'user'):
                    booking.user.account_tier = booking.plan_type
                    booking.user.save(update_fields=['account_tier', 'updated_at'])
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error updating booking status: {e}")
        
        # Send notification to user
        try:
            from kiboss.apps.notifications.services import NotificationService
            from kiboss.apps.notifications.models import NotificationCategory
            
            notification_user = None
            if manual_payment.booking_type == 'ASSET':
                notification_user = booking.renter
            elif manual_payment.booking_type == 'RIDE':
                notification_user = booking.passenger
            elif manual_payment.booking_type == 'SUBSCRIPTION':
                notification_user = booking.user if hasattr(booking, 'user') else (booking.profile.user if hasattr(booking, 'profile') else None)
            
            if notification_user:
                NotificationService.create_notification(
                    user=notification_user,
                    category=NotificationCategory.PAYMENT,
                    notification_type='MANUAL_PAYMENT_APPROVED',
                    title='Payment Approved',
                    message=f'Your manual payment of {manual_payment.amount} {manual_payment.currency} has been approved.',
                )
        except Exception:
            pass
        
        serializer = ManualPaymentSerializer(manual_payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a manual payment (admin only)."""
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {'error': 'Only admins can reject manual payments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        manual_payment = self.get_object()
        
        if manual_payment.status != ManualPayment.Status.PENDING:
            return Response(
                {'error': 'Manual payment is not pending approval'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        manual_payment.status = ManualPayment.Status.REJECTED
        manual_payment.admin_notes = request.data.get('admin_notes', '')
        manual_payment.reviewed_at = timezone.now()
        manual_payment.reviewed_by = request.user
        manual_payment.save()
        
        # Send notification to user
        try:
            booking = manual_payment.booking
            from kiboss.apps.notifications.services import NotificationService
            from kiboss.apps.notifications.models import NotificationCategory
            
            notification_user = None
            if manual_payment.booking_type == 'ASSET':
                notification_user = booking.renter
            elif manual_payment.booking_type == 'RIDE':
                notification_user = booking.passenger
            elif manual_payment.booking_type == 'SUBSCRIPTION':
                notification_user = booking.user if hasattr(booking, 'user') else (booking.profile.user if hasattr(booking, 'profile') else None)

            if notification_user:
                NotificationService.create_notification(
                    user=notification_user,
                    category=NotificationCategory.PAYMENT,
                    notification_type='MANUAL_PAYMENT_REJECTED',
                    title='Payment Rejected',
                    message=f'Your manual payment of {manual_payment.amount} {manual_payment.currency} has been rejected. Reason: {manual_payment.admin_notes}',
                )
        except Exception:
            pass
        
        serializer = ManualPaymentSerializer(manual_payment)
        return Response(serializer.data)
