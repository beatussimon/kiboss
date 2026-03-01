"""
ZenoPay Payment Integration for KIBOSS

Provides:
- create_order: Creates a payment order with ZenoPay
- check_status: Checks payment status
- handle_webhook: Processes payment status callbacks
"""

import logging
import requests
import uuid
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ZenoPay API settings (read from Django settings or env)
ZENOPAY_API_URL = getattr(settings, 'ZENOPAY_API_URL', 'https://api.zfricopay.com/v1')
ZENOPAY_ACCOUNT_ID = getattr(settings, 'ZENOPAY_ACCOUNT_ID', '')
ZENOPAY_API_KEY = getattr(settings, 'ZENOPAY_API_KEY', '')
ZENOPAY_SECRET_KEY = getattr(settings, 'ZENOPAY_SECRET_KEY', '')


class ZenoPayError(Exception):
    """Raised when a ZenoPay API call fails."""
    pass


class ZenoPayService:
    """Service for interacting with ZenoPay payment API."""
    
    @staticmethod
    def _headers():
        return {
            'Authorization': f'Bearer {ZENOPAY_API_KEY}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    @classmethod
    def create_order(cls, amount: Decimal, currency: str = 'TZS',
                     buyer_name: str = '', buyer_email: str = '',
                     buyer_phone: str = '', description: str = '',
                     metadata: dict = None) -> dict:
        """
        Create a payment order with ZenoPay.
        
        Args:
            amount: Payment amount
            currency: Currency code (default TZS)
            buyer_name: Customer name
            buyer_email: Customer email
            buyer_phone: Customer phone (for mobile money)
            description: Payment description
            metadata: Additional metadata to store
            
        Returns:
            dict with order_id, payment_url, status
        """
        order_ref = f"KIBOSS-{uuid.uuid4().hex[:12].upper()}"
        
        payload = {
            'account_id': ZENOPAY_ACCOUNT_ID,
            'amount': str(amount),
            'currency': currency,
            'buyer_name': buyer_name,
            'buyer_email': buyer_email,
            'buyer_phone': buyer_phone,
            'description': description or f'Kiboss Payment {order_ref}',
            'order_id': order_ref,
            'webhook_url': getattr(settings, 'ZENOPAY_WEBHOOK_URL', ''),
            'redirect_url': getattr(settings, 'ZENOPAY_REDIRECT_URL', ''),
            'metadata': metadata or {},
        }
        
        try:
            response = requests.post(
                f'{ZENOPAY_API_URL}/orders',
                json=payload,
                headers=cls._headers(),
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"ZenoPay order created: {order_ref}")
            return {
                'order_id': data.get('order_id', order_ref),
                'payment_url': data.get('payment_url', ''),
                'status': data.get('status', 'PENDING'),
                'reference': order_ref,
                'raw': data,
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"ZenoPay order creation failed: {e}")
            raise ZenoPayError(f"Payment service unavailable: {str(e)}")
    
    @classmethod
    def check_status(cls, order_id: str) -> dict:
        """Check payment status for an order."""
        try:
            response = requests.get(
                f'{ZENOPAY_API_URL}/orders/{order_id}',
                headers=cls._headers(),
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"ZenoPay status check failed for {order_id}: {e}")
            raise ZenoPayError(f"Could not check payment status: {str(e)}")
    
    @classmethod
    def handle_webhook(cls, payload: dict) -> dict:
        """
        Process a ZenoPay webhook callback.
        
        Expected payload keys:
            - order_id: The order reference
            - status: Payment status (COMPLETED, FAILED, CANCELLED)
            - amount: Payment amount
            - metadata: Any metadata we sent
            
        Returns:
            dict with processed result
        """
        order_id = payload.get('order_id', '')
        status = payload.get('status', '').upper()
        amount = payload.get('amount', '0')
        
        logger.info(f"ZenoPay webhook received: order={order_id}, status={status}")
        
        result = {
            'order_id': order_id,
            'status': status,
            'amount': amount,
            'processed': False,
            'message': '',
        }
        
        if not order_id:
            result['message'] = 'Missing order_id'
            return result
        
        # Process based on status
        if status == 'COMPLETED':
            result['processed'] = True
            result['message'] = 'Payment completed successfully'
            # The caller (view) should update the booking/subscription status
        elif status == 'FAILED':
            result['processed'] = True
            result['message'] = 'Payment failed'
        elif status == 'CANCELLED':
            result['processed'] = True
            result['message'] = 'Payment cancelled'
        else:
            result['message'] = f'Unknown status: {status}'
        
        return result
