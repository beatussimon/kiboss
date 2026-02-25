import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from django.test import Client
from kiboss.apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken
import json

client = Client()

user = User.objects.filter(is_superuser=True).first()
print(f"User: {user}")

refresh = RefreshToken.for_user(user)
access_token = str(refresh.access_token)

response = client.post(
    '/api/v1/tasks/create_custom/',
    json.dumps({
        'title': 'Test REST Request',
        'description': '',
        'priority': 'MEDIUM'
    }),
    content_type='application/json',
    HTTP_AUTHORIZATION=f'Bearer {access_token}'
)

print(f"Status Code: {response.status_code}")
try:
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Failed to parse JSON: {e}")
    print(response.content)

