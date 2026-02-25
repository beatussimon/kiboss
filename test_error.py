import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from django.test import Client
from kiboss.apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken
import json
import traceback

client = Client(raise_request_exception=False, SERVER_NAME='127.0.0.1')

user = User.objects.filter(is_superuser=True).first()
refresh = RefreshToken.for_user(user)
access_token = str(refresh.access_token)

try:
    response = client.post(
        '/api/v1/tasks/create_custom/',
        json.dumps({
            'title': 'Test Error Tracking',
            'description': '',
            'priority': 'MEDIUM',
            'attachments': [{'type': 'link', 'url': 'http://example.com'}]
        }),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {access_token}'
    )
    print(f"Status Code: {response.status_code}")
    print(f"Content: {response.content.decode()}")
except Exception as e:
    traceback.print_exc()
