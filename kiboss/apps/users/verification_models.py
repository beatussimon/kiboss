"""
Verification Models for KIBOSS

Implements a structured verification workflow for users including:
- Email verification
- Phone verification  
- Identity verification (ID documents)
- Address verification
"""

import uuid
import os
from django.db import models
from django.conf import settings
from django.utils import timezone

from kiboss.apps.common.validators import validate_file_size, validate_image_extension


class VerificationType(models.TextChoices):
    """Types of verification."""
    EMAIL = 'EMAIL', 'Email Verification'
    PHONE = 'PHONE', 'Phone Verification'
    IDENTITY = 'IDENTITY', 'Identity Verification'
    ADDRESS = 'ADDRESS', 'Address Verification'
    BUSINESS = 'BUSINESS', 'Business Verification'


class VerificationStatus(models.TextChoices):
    """Status of verification requests."""
    PENDING = 'PENDING', 'Pending Review'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    EXPIRED = 'EXPIRED', 'Expired'


class VerificationRequest(models.Model):
    """
    Verification request model.
    
    Tracks the verification process for users including
    document uploads and review status.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_requests'
    )
    
    # Verification type
    verification_type = models.CharField(
        max_length=20,
        choices=VerificationType.choices
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )
    
    # Contact info being verified
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Identity documents
    document_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of ID document (passport, national_id, drivers_license)"
    )
    document_number = models.CharField(max_length=100, blank=True)
    document_country = models.CharField(max_length=100, blank=True)
    
    # Document images
    document_front = models.ImageField(
        upload_to='verification/%Y/%m/',
        validators=[validate_file_size, validate_image_extension],
        blank=True,
        null=True,
        help_text="Front of ID document"
    )
    document_back = models.ImageField(
        upload_to='verification/%Y/%m/',
        validators=[validate_file_size, validate_image_extension],
        blank=True,
        null=True,
        help_text="Back of ID document"
    )
    selfie = models.ImageField(
        upload_to='verification/%Y/%m/',
        validators=[validate_file_size, validate_image_extension],
        blank=True,
        null=True,
        help_text="Selfie with ID document"
    )
    
    # Address verification
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    proof_of_address = models.ImageField(
        upload_to='verification/%Y/%m/',
        validators=[validate_file_size, validate_image_extension],
        blank=True,
        null=True,
        help_text="Utility bill or bank statement"
    )
    
    # Verification codes (for email/phone)
    verification_code = models.CharField(max_length=10, blank=True)
    code_expires_at = models.DateTimeField(blank=True, null=True)
    code_attempts = models.PositiveIntegerField(default=0)
    
    # Review info
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_verifications'
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    review_notes = models.TextField(blank=True)
    
    # Timestamps
    submitted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'verification_requests'
        verbose_name = 'Verification Request'
        verbose_name_plural = 'Verification Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'verification_type']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.verification_type} ({self.status})"
    
    def generate_code(self):
        """Generate a verification code for email/phone verification."""
        import random
        import string
        self.verification_code = ''.join(random.choices(string.digits, k=6))
        self.code_expires_at = timezone.now() + timezone.timedelta(minutes=10)
        self.code_attempts = 0
        self.save()
        return self.verification_code
    
    def verify_code(self, code):
        """Verify the provided code."""
        if not self.verification_code or not self.code_expires_at:
            return False, "No verification code found"
        
        if timezone.now() > self.code_expires_at:
            return False, "Verification code has expired"
        
        if self.code_attempts >= 5:
            return False, "Too many attempts. Please request a new code."
        
        self.code_attempts += 1
        self.save()
        
        if self.verification_code == code:
            self.status = VerificationStatus.APPROVED
            self.reviewed_at = timezone.now()
            self.save()
            return True, "Verification successful"
        
        return False, "Invalid verification code"
    
    def submit(self):
        """Mark verification as submitted."""
        self.status = VerificationStatus.SUBMITTED
        self.submitted_at = timezone.now()
        self.save()
    
    def approve(self, reviewer=None, notes=''):
        """Approve the verification request."""
        self.status = VerificationStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Update user verification status
        if self.verification_type == VerificationType.EMAIL:
            self.user.is_email_verified = True
        elif self.verification_type == VerificationType.PHONE:
            self.user.is_phone_verified = True
        elif self.verification_type == VerificationType.IDENTITY:
            self.user.is_identity_verified = True
        self.user.save()
    
    def reject(self, reviewer=None, reason='', notes=''):
        """Reject the verification request."""
        self.status = VerificationStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.review_notes = notes
        self.save()
    
    def can_resubmit(self):
        """Check if user can resubmit after rejection."""
        if self.status != VerificationStatus.REJECTED:
            return False
        # Allow resubmission after 24 hours
        if self.reviewed_at:
            return timezone.now() > self.reviewed_at + timezone.timedelta(hours=24)
        return True


class VerificationDocument(models.Model):
    """
    Additional documents for verification.
    
    Allows multiple documents to be attached to a verification request.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    verification_request = models.ForeignKey(
        VerificationRequest,
        on_delete=models.CASCADE,
        related_name='additional_documents'
    )
    
    document_type = models.CharField(max_length=50)
    document = models.ImageField(upload_to='verification/%Y/%m/', validators=[validate_file_size, validate_image_extension])
    description = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'verification_documents'
        verbose_name = 'Verification Document'
        verbose_name_plural = 'Verification Documents'
    
    def __str__(self):
        return f"{self.verification_request.user.email} - {self.document_type}"


class VerificationLog(models.Model):
    """
    Audit log for verification events.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    verification_request = models.ForeignKey(
        VerificationRequest,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    
    action = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'verification_logs'
        verbose_name = 'Verification Log'
        verbose_name_plural = 'Verification Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.verification_request.user.email} - {self.action}"
