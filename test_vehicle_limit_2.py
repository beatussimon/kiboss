from django.contrib.auth import get_user_model
from kiboss.apps.assets.models import Asset, AssetType

User = get_user_model()
user = User.objects.filter(is_superuser=False).first()

count = Asset.objects.filter(owner=user, asset_type=AssetType.VEHICLE).exclude(is_active=False, is_listed=False).count()
print(f"Current count: {count}")

