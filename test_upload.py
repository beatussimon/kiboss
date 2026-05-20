import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from rest_framework.test import APIClient
from kiboss.apps.users.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

user = User.objects.filter(is_active=True).first()
client = APIClient(SERVER_NAME='localhost')
client.force_authenticate(user=user)

file1 = SimpleUploadedFile("reg.pdf", b"file_content", content_type="application/pdf")
file2 = SimpleUploadedFile("ins.pdf", b"file_content", content_type="application/pdf")
file3 = SimpleUploadedFile("own.pdf", b"file_content", content_type="application/pdf")

data = {
    'name': 'Test Vehicle ' + os.urandom(4).hex(),
    'description': 'A test vehicle',
    'country': 'Tanzania',
    'properties': '{"make": "Toyota", "model": "Corolla", "year": "2015", "vehicle_type": "CAR", "license_plate": "T111AA' + os.urandom(2).hex() + '"}',
    'documents': [file1, file2, file3],
    'document_types': ['REGISTRATION', 'INSURANCE', 'OWNERSHIP']
}

response = client.post('/api/v1/rides/vehicles/', data, format='multipart')
print(f"Status Code: {response.status_code}")
try:
    print(response.json())
except:
    pass

from kiboss.apps.assets.models import Asset
asset_id = response.json().get('id') if response.status_code == 201 else None
if asset_id:
    asset = Asset.objects.get(id=asset_id)
    print(f"Asset Created: {asset.name}")
    print("Documents saved:", list(asset.documents.values_list('document_type', flat=True)))
