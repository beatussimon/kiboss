import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
import sys
sys.path.insert(0, '/home/bea/kiboss')
import django
django.setup()
from django.db import connection

# Check migration status
from django.db.migrations.loader import MigrationLoader
loader = MigrationLoader(connection, ignore_no_migrations=True)
print("Applied migrations:")
for app_name, migrations in sorted(loader.migrated_apps.items()):
    for mig in sorted(migrations):
        print(f"  {app_name}: {mig}")

# Check User model's manager
from kiboss.apps.users.models import User
print("\nUser model managers:")
for name, manager in User._meta.managers:
    print(f"  {name}: {type(manager).__name__}")

# Check the actual manager class
print(f"\nUser.objects type: {type(User.objects)}")
print(f"User.objects.create_superuser signature:")
import inspect
print(inspect.signature(User.objects.create_superuser))
