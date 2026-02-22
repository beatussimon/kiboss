import os
import django
import sys
from django.core.files.uploadedfile import SimpleUploadedFile

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.assets.models import Asset, AssetPhoto, AssetDocument, AssetType, VerificationStatus
from kiboss.apps.users.models import User
from kiboss.apps.tasks.models import StaffTask
from django.contrib.contenttypes.models import ContentType

def test_asset_posting():
    print("Starting Asset Posting Integrity Test...")
    
    # 1. Get or create test user
    user, _ = User.objects.get_or_create(email='test_poster@example.com', defaults={'first_name': 'Test', 'last_name': 'Poster'})
    if not user.password:
        user.set_password('password123')
        user.save()
    
    # 2. Create Asset
    asset = Asset.objects.create(
        name="Test Posting Integrity",
        description="Testing photos and documents",
        asset_type=AssetType.VEHICLE,
        owner=user,
        verification_status=VerificationStatus.PENDING,
        country="Tanzania",
        city="Dar es Salaam"
    )
    print(f"Created Asset: {asset.id}")

    # 3. Add Photos
    small_gif = (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9'
        b'\x04\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00'
        b'\x00\x02\x02\x4c\x01\x00\x3b'
    )
    
    for i in range(3):
        photo_file = SimpleUploadedFile(f"test_photo_{i}.gif", small_gif, content_type="image/gif")
        photo = AssetPhoto.objects.create(
            asset=asset,
            image=photo_file,
            order=i,
            is_primary=(i == 0)
        )
        print(f"Added Photo {i}: {photo.id}")

    # 4. Add Documents
    for i in range(2):
        doc_file = SimpleUploadedFile(f"test_doc_{i}.pdf", b"test content", content_type="application/pdf")
        doc = AssetDocument.objects.create(
            asset=asset,
            document_type='REGISTRATION' if i == 0 else 'INSURANCE',
            file=doc_file,
            name=f"Document {i}"
        )
        print(f"Added Document {i}: {doc.id}")

    # 5. Verify StaffTask creation
    from kiboss.apps.common.services import VerificationService
    task = VerificationService.request_verification(asset, user)
    print(f"Created Verification Task: {task.id} for role: {task.assigned_role}")

    # 6. Final verification
    asset.refresh_from_db()
    assert asset.photos.count() == 3
    assert asset.documents.count() == 2
    assert StaffTask.objects.filter(object_id=asset.id).exists()
    
    print("Posting Integrity Test Passed Successfully!")

if __name__ == "__main__":
    try:
        test_asset_posting()
    except Exception as e:
        print(f"Test Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
