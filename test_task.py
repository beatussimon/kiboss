import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.users.models import User
from kiboss.apps.tasks.serializers import CustomTaskCreateSerializer
from django.contrib.contenttypes.models import ContentType
from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
from rest_framework.request import Request
from django.test import RequestFactory

user = User.objects.filter(is_superuser=True).first()
print(f"User: {user}")

data = {
    'title': 'Test Task',
    'description': 'Test description',
    'priority': 'MEDIUM',
    'attachments': []
}

serializer = CustomTaskCreateSerializer(data=data)
if not serializer.is_valid():
    print(f"Validation Error: {serializer.errors}")
else:
    print("Serializer valid")
    data = serializer.validated_data
    
    try:
        content_type = ContentType.objects.get_for_model(user)
        
        task = StaffTask.objects.create(
            title=data['title'],
            description=data.get('description', ''),
            task_type=TaskType.CUSTOM_TASK,
            status=TaskStatus.ASSIGNED if data.get('assigned_to') else TaskStatus.PENDING,
            priority=data.get('priority', TaskPriority.MEDIUM),
            assigned_to_id=data.get('assigned_to'),
            assigned_role=data.get('assigned_role', ''),
            content_type=content_type,
            object_id=user.id,
            created_by=user,
            extra_data={'custom_attachments': data.get('attachments', [])}
        )
        print(f"Created task: {task.id}")
    except Exception as e:
        import traceback
        traceback.print_exc()
