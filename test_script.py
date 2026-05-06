import os, sys, traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from kiboss.apps.tasks.models import StaffTask
from kiboss.apps.common.services.verification import VerificationService

User = get_user_model()
try:
    task = StaffTask.objects.get(id='622269df-d6a6-4861-b2f1-626ddba79876')
    print('Task Type:', task.task_type)
    print('Content Object:', task.content_object)
    
    user = User.objects.first()
    VerificationService.process_verification(task, 'APPROVE', user, 'test notes')
    print('Verification processed successfully.')
except Exception as e:
    traceback.print_exc()
