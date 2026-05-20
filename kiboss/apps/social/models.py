"""
Social Models for KIBOSS - Controlled Social Features

Features:
- Likes (assets, rides, owners, reviews)
- Follows (users)
- Bookmarks (assets, rides)
- NO feeds
- NO algorithmic addiction
"""

import uuid
from django.db import models
from django.conf import settings


class Like(models.Model):
    """Like model for assets, rides, owners, and reviews."""
    
    ENTITY_TYPES = [
        ('ASSET', 'Asset'),
        ('RIDE', 'Ride'),
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
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'likes'
        unique_together = ['user', 'entity_type', 'entity_id']
    
    def __str__(self):
        return f"{self.user.email} liked {self.entity_type}:{self.entity_id}"


class Follow(models.Model):
    """Follow model for users."""
    
    ENTITY_TYPES = [
        ('USER', 'User'),
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
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'follows'
        unique_together = ['follower', 'following', 'entity_type']
    
    def __str__(self):
        return f"{self.follower.email} follows {self.following.email} ({self.entity_type})"


class Bookmark(models.Model):
    """Bookmark model for saving assets and rides."""
    
    ENTITY_TYPES = [
        ('ASSET', 'Asset'),
        ('RIDE', 'Ride'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookmarks'
    )
    
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id = models.UUIDField()
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'bookmarks'
        unique_together = ['user', 'entity_type', 'entity_id']
        indexes = [
            models.Index(fields=['user', 'entity_type']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} bookmarked {self.entity_type}:{self.entity_id}"
