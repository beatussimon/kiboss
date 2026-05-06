from rest_framework import viewsets, permissions
from .models import Feedback, FAQ
from .serializers import FeedbackSerializer, FAQSerializer

class FeedbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling user feedback.
    """
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Users see their own feedback, staff see all.
        """
        if self.request.user.is_staff or self.request.user.is_superuser:
            return Feedback.objects.all()
        return Feedback.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        feedback = serializer.save(user=self.request.user)
        
        # Auto-create Support Ticket StaffTask and Messaging Thread
        from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
        from kiboss.apps.messaging.models import Thread, ThreadType, Message
        from django.contrib.contenttypes.models import ContentType
        
        # 1. Create a Thread for this support request
        thread = Thread.objects.create(
            thread_type=ThreadType.SUPPORT,
            subject=f"Support: {feedback.subject}"
        )
        thread.participants.add(feedback.user)
        
        # 2. Add the user's initial message
        Message.objects.create(
            thread=thread,
            sender=feedback.user,
            content=feedback.message
        )
        
        # 3. Create the Staff Task pointing to the Thread
        StaffTask.objects.create(
            title=f"Support: {feedback.subject}",
            description=feedback.message[:200] + ("..." if len(feedback.message) > 200 else ""),
            task_type=TaskType.SUPPORT_TICKET,
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            assigned_role='SUPPORT',
            content_type=ContentType.objects.get_for_model(Thread),
            object_id=thread.id,
            created_by=feedback.user
        )


class FAQViewSet(viewsets.ModelViewSet):
    """
    ViewSet for FAQs. Admins can create/edit/delete.
    """
    queryset = FAQ.objects.all().order_by('order', '-created_at')
    serializer_class = FAQSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return FAQ.objects.all().order_by('order', '-created_at')
        return FAQ.objects.filter(is_active=True).order_by('order', '-created_at')
