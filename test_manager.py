import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
import sys
sys.path.insert(0, '/home/bea/kiboss')
import django
django.setup()
from kiboss.apps.users.models import UserManager
import inspect
print("UserManager.create_superuser signature:")
print(inspect.signature(UserManager.create_superuser))
