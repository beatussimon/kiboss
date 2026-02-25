import requests
import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken

user = User.objects.filter(is_superuser=True).first()
refresh = RefreshToken.for_user(user)
access_token = str(refresh.access_token)

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

payload = {
    'title': 'Test title',
    'description': 'Test desc',
    'priority': 'URGENT', # It might fail on 'Urgent' if frontend sends title case!
    'attachments': {'external_link': 'http://test'}
}

response = requests.post('http://127.0.0.1:8000/api/v1/tasks/create_custom/', json=payload, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
