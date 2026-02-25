from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from kiboss.apps.assets.views import AssetViewSet
from kiboss.apps.assets.models import Asset, AssetType

User = get_user_model()
factory = APIRequestFactory()

user = User.objects.filter(is_superuser=False).first()
print(f"Testing with user: {user.email}")

Asset.objects.filter(owner=user, asset_type=AssetType.VEHICLE).delete()

view = AssetViewSet.as_view({'post': 'create'})

# 1. Create first vehicle
request1 = factory.post('/assets/', {'name': 'Car 1', 'asset_type': 'VEHICLE'})
force_authenticate(request1, user=user)
response1 = view(request1)
print(f"First vehicle creation status: {response1.status_code}")

# 2. Attempt to create second vehicle
request2 = factory.post('/assets/', {'name': 'Car 2', 'asset_type': 'VEHICLE'})
force_authenticate(request2, user=user)
response2 = view(request2)
print(f"Second vehicle creation status: {response2.status_code}")
if response2.status_code == 403:
    print(f"Error message: {response2.data['detail']}")
