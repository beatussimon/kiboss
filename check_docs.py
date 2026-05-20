import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.assets.models import Asset
for a in Asset.objects.filter(verification_status="PENDING", asset_type="VEHICLE"):
    docs = list(a.documents.values_list("document_type", flat=True))
    print(f"Vehicle: {a.name} (ID: {a.id})")
    print(f"Docs: {docs}")
