"""
Social Models for KIBOSS - Controlled Social Features

Features:
- Likes (assets, owners, reviews)
- Follows (owners, drivers)
- NO feeds
- NO algorithmic addiction
"""

import uuid
from django.db import models
from django.conf import settings


class Like(models.Model):
    """Like model for assets, owners, and reviews."""
    
    ENTITY_TYPES = [
        ('ASSET', 'Asset'),
        ('OWNER', 'Owner'),
        ('REVIEW', 'Review'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id = models.UUIDField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'likes'
        unique_together = ['user', 'entity_type', 'entity_id']
    
    def __str__(self):
        return f"{self.user.email} liked {self.entity_type}:{self.entity_id}"


class Follow(models.Model):
    """Follow model for owners and drivers."""
    
    ENTITY_TYPES = [
        ('OWNER', 'Owner'),
        ('DRIVER', 'Driver'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='following'
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'follows'
        unique_together = ['follower', 'following', 'entity_type']
    
    def __str__(self):
        return f"{self.follower.email} follows {self.following.email} ({self.entity_type})"
