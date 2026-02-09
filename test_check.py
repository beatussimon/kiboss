import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
import sys
sys.path.insert(0, '/home/bea/kiboss')
import django
django.setup()
from kiboss.apps.users.models import User
from kiboss.apps.users.models import UserManager

print(f"User._meta.managers: {User._meta.managers}")
print(f"User._default_manager: {User._default_manager}")
print(f"User._default_manager type: {type(User._default_manager)}")
print(f"User._default_manager.create_superuser: {User._default_manager.create_superuser}")
print(f"UserManager: {UserManager}")
print(f"User.objects: {User.objects}")
print(f"User.objects.__class__: {User.objects.__class__}")

# Check if they are the same
print(f"\nAre they the same instance? {User._default_manager is User.objects}")
