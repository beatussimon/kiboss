import os
import django
from django.test import Client
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

User = get_user_model()
user, created = User.objects.get_or_create(email='admin@test.com', defaults={'is_staff': True, 'is_superuser': True})
if created:
    user.set_password('password')
    user.save()

client = Client()
client.force_login(user)

print("Calling client.get('/admin/')...")
try:
    response = client.get('/admin/')
    print("Response status:", response.status_code)
except Exception as e:
    print("Exception:", type(e), e)
