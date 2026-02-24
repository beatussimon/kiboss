"""
Payment Models for KIBOSS - Zenopay Integration

Implements a Zenopay placeholder that simulates:
- Authorization
- Escrow holding
- Release
- Partial refund
- Penalties
- Dispute freeze

NO real payment gateway calls - all simulated locally.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class PaymentStatus(models.TextChoices):
    """Payment status enumeration."""
    PENDING = 'PENDING', 'Pending'
    AUTHORIZED = 'AUTHORIZED', 'Authorized'
    ESCROW = 'ESCROW', 'In Escrow'
    RELEASED = 'RELEASED', 'Released to Owner'
    REFUNDED = 'REFUNDED', 'Refunded'
    PARTIAL_REFUND = 'PARTIAL_REFUND', 'Partially Refunded'
    FAILED = 'FAILED', 'Failed'
    DISPUTED = 'DISPUTED', 'Disputed'
    FROZEN = 'FROZEN', 'Frozen (Dispute)'


class PaymentMethod(models.TextChoices):
    """Payment method types including Zenopay supported providers."""
    # Cards
    CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
    DEBIT_CARD = 'DEBIT_CARD', 'Debit Card'
    
    # Mobile Money (East Africa)
    MPESA = 'MPESA', 'Vodacom M-Pesa'
    TIGO_PESA = 'TIGO_PESA', 'Tigo Pesa'
    AIRTEL_MONEY = 'AIRTEL_MONEY', 'Airtel Money'
    HALOPESA = 'HALOPESA', 'Halo Pesa'
    AZAM_PESA = 'AZAM_PESA', 'Azam Pesa'
    
    # Banking (Regional)
    CRDB = 'CRDB', 'CRDB Bank'
    NMB = 'NMB', 'NMB Bank'
    ABS_BANK = 'ABSA', 'Absa Bank'
    STANBIC = 'STANBIC', 'Stanbic Bank'
    NBC = 'NBC', 'NBC Bank'
    
    # Wallet
    ZENOPAY_WALLET = 'ZENOPAY_WALLET', 'Zenopay Wallet'


class Payment(models.Model):
    """
    Payment model for booking transactions.
    
    Simulates Zenopay payment processing with:
    - Authorization hold
    - Escrow during rental
    - Release upon completion
    - Refunds and penalties
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.PROTECT,
        related_name='payment_info',
        blank=True,
        null=True
    )
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    
    # Method
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CREDIT_CARD
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    
    # Zenopay reference (simulated)
    zenopay_transaction_id = models.CharField(max_length=100, blank=True)
    zenopay_authorization_code = models.CharField(max_length=100, blank=True)
    
    # Card details (last 4 digits only - simulated)
    card_last_four = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)
    
    # Escrow details
    escrow_held_at = models.DateTimeField(blank=True, null=True)
    escrow_released_at = models.DateTimeField(blank=True, null=True)
    escrow_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Refund details
    refunded_at = models.DateTimeField(blank=True, null=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    refund_reason = models.TextField(blank=True)
    
    # Penalty details
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    penalty_reason = models.TextField(blank=True)
    
    # Failure details
    failure_code = models.CharField(max_length=50, blank=True)
    failure_message = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['booking']),
            models.Index(fields=['zenopay_transaction_id']),
        ]
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency} ({self.status})"

    def save(self, *args, **kwargs):
        if self.booking_id:
            from kiboss.apps.bookings.models import Booking
            if not Booking.objects.filter(id=self.booking_id).exists():
                self.booking_id = None
        super().save(*args, **kwargs)
    
    # Zenopay Simulation Methods
    
    def authorize(self, amount, card_details):
        """
        Simulate Zenopay authorization.
        
        Args:
            amount: Amount to authorize
            card_details: Card information (simulated)
            
        Returns:
            bool: Whether authorization was successful
        """
        self.amount = amount
        self.status = PaymentStatus.AUTHORIZED
        self.zenopay_authorization_code = f"ZEN_AUTH_{uuid.uuid4().hex[:16]}"
        self.card_last_four = card_details.get('last_four', '4242')
        self.card_brand = card_details.get('brand', 'VISA')
        self.save()
        return True
    
    def hold_in_escrow(self, amount=None):
        """
        Move funds to escrow.
        
        Args:
            amount: Amount to hold (defaults to full amount)
        """
        hold_amount = amount or self.amount
        self.escrow_amount = hold_amount
        self.status = PaymentStatus.ESCROW
        self.escrow_held_at = timezone.now()
        self.zenopay_transaction_id = f"ZEN_ESCROW_{uuid.uuid4().hex[:16]}"
        self.save()
    
    def release_from_escrow(self, release_amount=None, deduct_fees=None):
        """
        Release escrow funds to owner.
        
        Args:
            release_amount: Amount to release (defaults to full escrow)
            deduct_fees: Fees to deduct from release
        """
        amount_to_release = release_amount or self.escrow_amount
        fees = deduct_fees or Decimal('0.00')
        
        self.escrow_amount -= amount_to_release
        self.metadata['release_details'] = {
            'released_amount': str(amount_to_release),
            'fees_deducted': str(fees),
            'released_at': str(timezone.now()),
            'zenopay_release_id': f"ZEN_RELEASE_{uuid.uuid4().hex[:16]}"
        }
        
        if self.escrow_amount <= Decimal('0.00'):
            self.status = PaymentStatus.RELEASED
            self.escrow_released_at = timezone.now()
        
        self.save()
    
    def refund(self, amount, reason=''):
        """
        Process refund to renter.
        
        Args:
            amount: Amount to refund
            reason: Reason for refund
        """
        self.refunded_amount += amount
        self.refund_reason = reason
        self.refunded_at = timezone.now()
        
        if self.refunded_amount >= self.amount:
            self.status = PaymentStatus.REFUNDED
        else:
            self.status = PaymentStatus.PARTIAL_REFUND
        
        self.metadata['refund_details'] = {
            'amount': str(amount),
            'reason': reason,
            'zenopay_refund_id': f"ZEN_REFUND_{uuid.uuid4().hex[:16]}"
        }
        self.save()
    
    def apply_penalty(self, amount, reason=''):
        """
        Apply penalty (deduct from escrow or charge card).
        
        Args:
            amount: Penalty amount
            reason: Reason for penalty
        """
        self.penalty_amount += amount
        self.penalty_reason = reason
        
        if self.escrow_amount >= amount:
            # Deduct from escrow
            self.escrow_amount -= amount
            self.metadata['penalty_deducted_from'] = 'escrow'
        else:
            # Charge remaining to card
            self.metadata['penalty_deducted_from'] = 'card'
        
        self.metadata['penalty_details'] = {
            'amount': str(amount),
            'reason': reason,
            'zenopay_penalty_id': f"ZEN_PENALTY_{uuid.uuid4().hex[:16]}"
        }
        self.save()
    
    def freeze_for_dispute(self):
        """Freeze payment during dispute."""
        self.status = PaymentStatus.FROZEN
        self.metadata['frozen_at'] = str(timezone.now())
        self.save()
    
    def unfreeze_after_dispute(self, resolution):
        """Unfreeze payment after dispute resolution."""
        self.metadata['dispute_resolution'] = resolution
        self.metadata['unfrozen_at'] = str(timezone.now())
        
        if resolution == 'refund':
            self.refund(self.amount, 'Dispute resolution - refund')
        elif resolution == 'release':
            self.release_from_escrow()
        
        self.save()


class Dispute(models.Model):
    """
    Payment dispute model.
    Handles disputes and their resolution.
    """
    
    DISPUTE_REASONS = [
        ('DAMAGE', 'Property Damage'),
        ('NO_SHOW', 'No Show'),
        ('LATE_RETURN', 'Late Return'),
        ('NOT_AS_DESCRIBED', 'Not As Described'),
        ('CANCELLATION', 'Unauthorized Cancellation'),
        ('REFUND_NOT_RECEIVED', 'Refund Not Received'),
        ('OTHER', 'Other'),
    ]
    
    DISPUTE_STATUS = [
        ('OPEN', 'Open'),
        ('UNDER_REVIEW', 'Under Review'),
        ('EVIDENCE_COLLECTION', 'Evidence Collection'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    RESOLUTION_TYPES = [
        ('REFUND_RENTER', 'Full Refund to Renter'),
        ('REFUND_PARTIAL', 'Partial Refund to Renter'),
        ('RELEASE_OWNER', 'Full Release to Owner'),
        ('RELEASE_PARTIAL', 'Partial Release to Owner'),
        ('NO_ACTION', 'No Action'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.PROTECT,
        related_name='dispute_info'
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name='dispute'
    )
    
    # Initiator
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='initiated_disputes'
    )
    
    # Details
    reason = models.CharField(max_length=30, choices=DISPUTE_REASONS)
    description = models.TextField()
    
    # Amount in dispute
    disputed_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=DISPUTE_STATUS,
        default='OPEN'
    )
    
    # Evidence
    evidence = models.JSONField(default=list, blank=True)
    
    # Resolution
    resolution = models.CharField(
        max_length=30,
        choices=RESOLUTION_TYPES,
        blank=True
    )
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='resolved_disputes'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'disputes'
        verbose_name = 'Dispute'
        verbose_name_plural = 'Disputes'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['booking']),
            models.Index(fields=['initiated_by']),
        ]
    
    def __str__(self):
        return f"Dispute {self.id} - {self.booking.id} ({self.status})"
    
    def resolve(self, resolution, notes, resolver):
        """Resolve the dispute."""
        self.resolution = resolution
        self.resolution_notes = notes
        self.resolved_by = resolver
        self.status = 'RESOLVED'
        self.resolved_at = timezone.now()
        
        # Update payment based on resolution
        if resolution == 'REFUND_RENTER':
            self.payment.refund(self.disputed_amount, 'Dispute resolution')
        elif resolution == 'REFUND_PARTIAL':
            self.payment.refund(self.disputed_amount * Decimal('0.5'), 'Partial refund')
        elif resolution == 'RELEASE_OWNER':
            self.payment.release_from_escrow()
        elif resolution == 'RELEASE_PARTIAL':
            self.payment.release_from_escrow(self.disputed_amount * Decimal('0.5'))
        
        self.save()
