import uuid
from django.db import models
from django.conf import settings

class Feedback(models.Model):
    """
    Model to store user feedback, inquiries, and issues.
    """
    class Category(models.TextChoices):
        VERIFICATION = 'VERIFICATION', 'Verification Issue'
        TECHNICAL = 'TECHNICAL', 'Technical Problem'
        BILLING = 'BILLING', 'Billing/Payment'
        SUGGESTION = 'SUGGESTION', 'Suggestion'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedbacks'
    )
    
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )
    subject = models.CharField(max_length=255)
    message = models.TextField()
    
    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'feedbacks'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.category}: {self.subject} ({self.user.email})"
