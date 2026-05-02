"""
Contract Models for KIBOSS - Contract Engine

Every booking generates a contract snapshot that requires explicit acceptance.
Contracts are immutable after acceptance and jurisdiction-aware.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings


class ContractStatus(models.TextChoices):
    """Contract status enumeration."""
    PENDING = 'PENDING', 'Pending Acceptance'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    EXECUTED = 'EXECUTED', 'Executed'
    COMPLETED = 'COMPLETED', 'Completed'
    ARCHIVED = 'ARCHIVED', 'Archived'
    VOIDED = 'VOIDED', 'Voided'


class Contract(models.Model):
    """
    Contract model for booking agreements.
    
    Contracts are:
    - Generated per booking
    - Require explicit acceptance by both parties
    - Immutable after acceptance
    - Jurisdiction-aware
    - Support admin override with audit log
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.PROTECT,
        related_name='contract_info'
    )
    
    # Version control
    version = models.PositiveIntegerField(default=1)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.PENDING
    )
    
    # Contract snapshot (immutable JSON)
    snapshot = models.JSONField(
        default=dict,
        help_text="Complete contract terms at time of generation"
    )
    
    # Jurisdiction
    jurisdiction = models.CharField(max_length=100, default='TZ')
    governing_law = models.CharField(max_length=255, blank=True)
    
    # Terms (JSON)
    terms = models.JSONField(default=dict, blank=True)
    cancellation_policy = models.TextField(blank=True)
    late_return_policy = models.TextField(blank=True)
    damage_policy = models.TextField(blank=True)
    
    # Signatures
    owner_signature = models.JSONField(default=dict, blank=True)
    renter_signature = models.JSONField(default=dict, blank=True)
    
    # Acceptance timestamps
    owner_accepted_at = models.DateTimeField(blank=True, null=True)
    renter_accepted_at = models.DateTimeField(blank=True, null=True)
    
    # Admin override (if contract needs modification)
    admin_override = models.BooleanField(default=False)
    admin_override_reason = models.TextField(blank=True)
    admin_override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='admin_contracts'
    )
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contracts'
        verbose_name = 'Contract'
        verbose_name_plural = 'Contracts'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['booking']),
            models.Index(fields=['jurisdiction']),
        ]
    
    def __str__(self):
        return f"Contract {self.id} for Booking {self.booking.id} ({self.status})"
    
    def accept_by_owner(self, signature_data):
        """Accept contract by asset owner."""
        if self.status not in [ContractStatus.PENDING, ContractStatus.ACCEPTED]:
            raise ValueError("Contract cannot be signed in its current state")
        
        self.owner_signature = signature_data
        self.owner_accepted_at = timezone.now()
        
        if self.renter_signature:
            self.status = ContractStatus.EXECUTED
        else:
            self.status = ContractStatus.ACCEPTED
        
        self.save()
    
    def accept_by_renter(self, signature_data):
        """Accept contract by renter."""
        if self.status not in [ContractStatus.PENDING, ContractStatus.ACCEPTED]:
            raise ValueError("Contract cannot be signed in its current state")
        
        self.renter_signature = signature_data
        self.renter_accepted_at = timezone.now()
        
        if self.owner_signature:
            self.status = ContractStatus.EXECUTED
        else:
            self.status = ContractStatus.ACCEPTED
        
        self.save()
    
    def is_fully_executed(self):
        """Check if both parties have accepted."""
        return bool(self.owner_signature and self.renter_signature)


class ContractVersion(models.Model):
    """Version history for contracts (for audit purposes)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    
    version = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict)
    changes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_contract_versions'
    )
    
    class Meta:
        db_table = 'contract_versions'
        verbose_name = 'Contract Version'
        verbose_name_plural = 'Contract Versions'
    
    def __str__(self):
        return f"Contract {self.contract.id} v{self.version}"


# Import timezone at module level
from django.utils import timezone
