import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.users.models import User
from kiboss.apps.assets.models import Asset

halima = User.objects.get(email="halima@kiboss.com")
print("User:", halima)
vehicles = Asset.objects.filter(owner=halima, asset_type='VEHICLE')
print("Total vehicles:", vehicles.count())
for v in vehicles:
    print(v.id, v.name, v.is_active, v.is_listed, v.verification_status, v.is_corporate)

