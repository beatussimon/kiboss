"""
Serializers for Tasks API
"""

from rest_framework import serializers
from kiboss.apps.tasks.models import StaffTask, TaskStatus, TaskPriority, TaskType
from kiboss.apps.assets.serializers import AssetDetailSerializer, AssetDocumentSerializer
from kiboss.apps.assets.models import Asset


class StaffTaskSerializer(serializers.ModelSerializer):
    """Serializer for staff tasks."""
    
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True)
    
    # Nested resource detail for easier review
    resource_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffTask
        fields = [
            'id', 'title', 'description', 'task_type', 
            'status', 'priority', 'assigned_role', 
            'assigned_to', 'assigned_to_email',
            'reviewer_notes', 'completion_date',
            'resource_detail',
            'created_at', 'updated_at', 'created_by_email'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_email']

    def get_resource_detail(self, obj):
        """Get the detail of the related resource (e.g., Asset)."""
        if obj.task_type == TaskType.CUSTOM_TASK:
            return obj.extra_data
            
        content_object = obj.content_object
        if isinstance(content_object, Asset):
            # Include documents for verification
            data = AssetDetailSerializer(content_object).data
            data['documents'] = AssetDocumentSerializer(content_object.documents.all(), many=True).data
            return data
        
        from kiboss.apps.users.models import User, CorporateProfile
        if isinstance(content_object, User):
            from kiboss.apps.users.serializers import UserWithProfileSerializer
            return UserWithProfileSerializer(content_object).data
        
        if type(content_object).__name__ == 'CorporateProfile' or isinstance(content_object, CorporateProfile):
            from kiboss.apps.users.serializers import CorporateProfileSerializer
            data = CorporateProfileSerializer(content_object).data
            data['user_email'] = getattr(content_object, 'user', None) and content_object.user.email
            data['verification_documents'] = getattr(content_object, 'verification_documents', [])
            
            # Add latest subscription info if available
            if hasattr(content_object, 'subscriptions'):
                latest_sub = content_object.subscriptions.all().first()
                if latest_sub:
                    data['plan_type'] = latest_sub.plan_type
                    data['amount_paid'] = float(latest_sub.amount_paid)
                    data['payment_reference'] = latest_sub.payment_reference
            return data
            
        from kiboss.apps.messaging.models import Thread
        if isinstance(content_object, Thread):
            from kiboss.apps.messaging.serializers import ThreadSerializer
            # We don't have request context here, so some ThreadSerializer fields might fail if they need it.
            # Usually ThreadSerializer handles it gracefully or we pass an empty context.
            return ThreadSerializer(content_object, context={}).data
            
        from kiboss.apps.common.models import Feedback
        if isinstance(content_object, Feedback):
            from kiboss.apps.common.serializers import FeedbackSerializer
            return FeedbackSerializer(content_object).data

        from kiboss.apps.assets.models import PromotedListing
        if isinstance(content_object, PromotedListing):
            return {
                'id': str(content_object.id),
                'asset_name': content_object.asset.name,
                'promotion_type': content_object.promotion_type,
                'amount_paid': float(content_object.amount_paid),
                'payment_reference': content_object.payment_reference,
                'starts_at': content_object.starts_at.isoformat(),
                'ends_at': content_object.ends_at.isoformat(),
                'user_email': content_object.asset.owner.email,
            }
            
        # Handle other types if needed later
        return None


class TaskActionSerializer(serializers.Serializer):
    """Serializer for taking actions on tasks (Approve, Reject, etc.)."""
    
    action = serializers.ChoiceField(choices=['APPROVE', 'REJECT', 'REQUEST_CHANGES', 'REVOKE', 'SUBMIT_COMPLETION'])
    notes = serializers.CharField(required=False, allow_blank=True)
    attachment = serializers.CharField(required=False, allow_blank=True)


class TaskAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning tasks to users or roles."""
    
    assigned_to = serializers.UUIDField(required=False, allow_null=True)
    assigned_role = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=TaskPriority.choices, required=False)


class CustomTaskCreateSerializer(serializers.Serializer):
    """Serializer for creating custom administrative tasks."""
    
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=TaskPriority.choices, default=TaskPriority.MEDIUM)
    assigned_to = serializers.UUIDField(required=False, allow_null=True)
    assigned_role = serializers.CharField(required=False, allow_blank=True)
    attachments = serializers.ListField(
        child=serializers.DictField(), 
        required=False, 
        default=list
    )
