"""
Serializers for Messaging API
"""
from rest_framework import serializers
from kiboss.apps.messaging.models import Thread, Message, MessageAttachment
from kiboss.apps.users.models import User


class MessageAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for message attachments."""
    
    class Meta:
        model = MessageAttachment
        fields = [
            'id', 'file', 'file_type', 'file_name', 
            'file_size', 'is_safe', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'is_safe']


class CreateAttachmentSerializer(serializers.Serializer):
    """Serializer for uploading attachments."""
    message = serializers.UUIDField()
    file = serializers.FileField()
    file_type = serializers.ChoiceField(
        choices=MessageAttachment.ATTACHMENT_TYPES,
        required=False
    )
    
    def validate_file(self, value):
        """Validate file size."""
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 10MB")
        return value
    
    def validate(self, data):
        """Validate that the user is a participant in the thread."""
        from kiboss.apps.messaging.models import Message
        try:
            message = Message.objects.get(id=data['message'])
        except Message.DoesNotExist:
            raise serializers.ValidationError({"message": "Message not found"})
        
        request = self.context.get('request')
        if request and request.user not in message.thread.participants.all():
            raise serializers.ValidationError("You are not a participant of this thread")
        
        data['message_obj'] = message
        return data


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages."""
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    sender_name = serializers.SerializerMethodField()
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'thread', 'sender', 'sender_email', 'sender_name',
            'content', 'content_type', 'status',
            'read_at', 'attachments',
            'is_deleted', 'deleted_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'sender', 'status', 'read_at', 
            'is_deleted', 'deleted_at', 'created_at'
        ]
    
    def get_sender_name(self, obj):
        return f"{obj.sender.first_name} {obj.sender.last_name}"


class ThreadParticipantSerializer(serializers.ModelSerializer):
    """Serializer for thread participants (minimal info)."""
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    avatar = serializers.URLField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'avatar']


class ThreadSerializer(serializers.ModelSerializer):
    """Serializer for message threads."""
    participants = ThreadParticipantSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Thread
        fields = [
            'id', 'thread_type', 'subject', 'status',
            'participants', 'context_type', 'context_id', 'booking', 'ride',
            'message_count', 'last_message', 'unread_count',
            'is_flagged', 'flagged_reason',
            'auto_lock_after_completion', 'locked_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'message_count', 'is_flagged', 
            'locked_at', 'created_at', 'updated_at'
        ]
    
    def get_last_message(self, obj):
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return MessageSerializer(last_message).data
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and hasattr(request.user, 'id'):
            return obj.messages.exclude(
                sender=request.user,
                read_receipts__user=request.user
            ).exclude(status='READ').count()
        return 0


class ThreadDetailSerializer(ThreadSerializer):
    """Detailed serializer for thread with messages."""
    messages = serializers.SerializerMethodField()
    
    class Meta(ThreadSerializer.Meta):
        fields = ThreadSerializer.Meta.fields + ['messages']
    
    def get_messages(self, obj):
        """Get messages with optional pagination."""
        request = self.context.get('request')
        page = request.query_params.get('page') if request else None
        page_size = request.query_params.get('page_size', '20') if request else '20'
        
        try:
            page_size = int(page_size)
        except (ValueError, TypeError):
            page_size = 20
        
        # Get messages in chronological order (oldest first)
        messages = obj.messages.filter(is_deleted=False).order_by('created_at')
        
        # If page is specified, return paginated results
        if page:
            try:
                page_num = int(page)
                start = (page_num - 1) * page_size
                end = start + page_size
                messages = messages[start:end]
            except (ValueError, TypeError):
                messages = messages[:page_size]
        else:
            # Default: return last 50 messages for backward compatibility
            messages = messages[:50]
        
        return MessageSerializer(messages, many=True).data


class CreateMessageSerializer(serializers.ModelSerializer):
    """Serializer for creating messages."""
    
    class Meta:
        model = Message
        fields = ['content', 'content_type']
    
    def create(self, validated_data):
        validated_data['thread'] = self.context['thread']
        validated_data['sender'] = self.context['request'].user
        validated_data['status'] = 'SENT'
        return super().create(validated_data)


class CreateThreadSerializer(serializers.ModelSerializer):
    """Serializer for creating threads."""
    
    class Meta:
        model = Thread
        fields = ['thread_type', 'subject', 'booking', 'ride']
    
    def create(self, validated_data):
        validated_data['participants'] = [self.context['request'].user]
        return super().create(validated_data)
