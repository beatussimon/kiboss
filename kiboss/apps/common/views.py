from rest_framework import viewsets, permissions
from .models import Feedback
from .serializers import FeedbackSerializer

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
        if self.request.user.is_staff:
            return Feedback.objects.all()
        return Feedback.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        feedback = serializer.save(user=self.request.user)
        
        # Auto-create Support Ticket StaffTask
        from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
        from django.contrib.contenttypes.models import ContentType
        from .models import Feedback
        
        StaffTask.objects.create(
            title=f"Feedback: {feedback.subject}",
            description=feedback.message[:200] + ("..." if len(feedback.message) > 200 else ""),
            task_type=TaskType.SUPPORT_TICKET,
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM,
            assigned_role='SUPPORT',
            content_type=ContentType.objects.get_for_model(Feedback),
            object_id=feedback.id,
            created_by=feedback.user
        )
