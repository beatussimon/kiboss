"""
ZenoPay Payment Views for KIBOSS

Endpoints:
- POST /api/v1/payments/zenopay/create-order/ - Create a payment order
- POST /api/v1/payments/zenopay/webhook/ - Handle payment webhooks (no auth)
- GET /api/v1/payments/zenopay/status/<order_id>/ - Check payment status
"""

import logging
from decimal import Decimal
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from kiboss.apps.payments.zenopay_service import ZenoPayService, ZenoPayError

logger = logging.getLogger(__name__)


class CreateZenoPayOrderView(APIView):
    """Create a ZenoPay payment order."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        amount = request.data.get('amount')
        currency = request.data.get('currency', 'TZS')
        description = request.data.get('description', '')
        booking_id = request.data.get('booking_id')
        subscription_id = request.data.get('subscription_id')
        
        if not amount:
            return Response(
                {'error': 'amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount_decimal = Decimal(str(amount))
        except Exception:
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        profile = getattr(user, 'profile', None)
        
        metadata = {
            'user_id': str(user.id),
            'booking_id': booking_id or '',
            'subscription_id': subscription_id or '',
        }
        
        try:
            result = ZenoPayService.create_order(
                amount=amount_decimal,
                currency=currency,
                buyer_name=user.get_full_name(),
                buyer_email=user.email,
                buyer_phone=getattr(profile, 'phone', '') or '',
                description=description or f'Kiboss Payment by {user.get_full_name()}',
                metadata=metadata,
            )
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except ZenoPayError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_502_BAD_GATEWAY
            )


class ZenoPayWebhookView(APIView):
    """Handle ZenoPay payment webhooks (unauthenticated)."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        payload = request.data
        
        logger.info(f"ZenoPay webhook received: {payload}")
        
        result = ZenoPayService.handle_webhook(payload)
        
        if result['processed']:
            order_status = result['status']
            order_id = result['order_id']
            metadata = payload.get('metadata', {})
            
            # Update booking payment if applicable
            booking_id = metadata.get('booking_id')
            if booking_id and order_status == 'COMPLETED':
                try:
                    from kiboss.apps.payments.models import Payment
                    with transaction.atomic():
                        payment = Payment.objects.filter(
                            booking_id=booking_id
                        ).first()
                        if payment:
                            payment.status = 'ESCROW'
                            payment.payment_reference = order_id
                            payment.save()
                            logger.info(f"Payment {payment.id} moved to ESCROW for booking {booking_id}")
                except Exception as e:
                    logger.error(f"Error updating payment for booking {booking_id}: {e}")
            
            # Update subscription if applicable
            subscription_id = metadata.get('subscription_id')
            if subscription_id and order_status == 'COMPLETED':
                try:
                    from kiboss.apps.users.models import BusinessSubscription
                    with transaction.atomic():
                        subscription = BusinessSubscription.objects.get(id=subscription_id)
                        subscription.status = 'ACTIVE'
                        subscription.payment_reference = order_id
                        subscription.save()
                        
                        # Upgrade user tier
                        user = subscription.profile.user
                        user.account_tier = 'BUSINESS'
                        user.save(update_fields=['account_tier', 'updated_at'])
                        logger.info(f"Subscription {subscription_id} activated, user upgraded to BUSINESS")
                except Exception as e:
                    logger.error(f"Error updating subscription {subscription_id}: {e}")
        
        return Response({'status': 'ok'})


class ZenoPayStatusView(APIView):
    """Check payment status for an order."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, order_id):
        try:
            result = ZenoPayService.check_status(order_id)
            return Response(result)
        except ZenoPayError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_502_BAD_GATEWAY
            )
