import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
User = get_user_model()

# Get the superuser
user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.first()

client = Client()
client.force_login(user)
response = client.post('/api/v1/tasks/622269df-d6a6-4861-b2f1-626ddba79876/process/', {'action': 'APPROVE', 'notes': 'testing error handler'}, content_type='application/json')
print('Status Code:', response.status_code)
print('Response JSON:', response.json())
