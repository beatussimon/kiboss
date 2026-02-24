import os
import django
from django.core.files.uploadedfile import SimpleUploadedFile

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.users.models import User, CorporateProfile
from kiboss.apps.tasks.models import StaffTask, TaskType
from rest_framework.test import APIClient

def run_qa():
    print("Starting QA Tests for Business Registration Separation...\n")
    client = APIClient()
    
    # 1. Setup Test Users
    ride_user_email = 'ride.business@qa.com'
    asset_user_email = 'asset.business@qa.com'
    
    ride_user, _ = User.objects.get_or_create(email=ride_user_email)
    ride_user.set_password('qapassword123')
    ride_user.save()
    
    asset_user, _ = User.objects.get_or_create(email=asset_user_email)
    asset_user.set_password('qapassword123')
    asset_user.save()
    
    # Clean up previous state
    if hasattr(ride_user, 'corporate_profile'):
        ride_user.corporate_profile.delete()
    if hasattr(asset_user, 'corporate_profile'):
        asset_user.corporate_profile.delete()
    StaffTask.objects.filter(created_by__in=[ride_user, asset_user]).delete()

    dummy_file = SimpleUploadedFile("test_doc.pdf", b"file_content", content_type="application/pdf")

    # ---- TEST 1: RIDE BUSINESS REGISTRATION ----
    print("Test 1: Registering a Ride Business...")
    client.force_authenticate(user=ride_user)
    payload_ride = {
        'company_name': 'Kiboss Rides Ltd',
        'registration_number': 'REQ-100-R',
        'tax_id': 'TAX-RIDE-01',
        'business_category': 'RIDE',
        'plan_type': 'MONTHLY',
        'payment_reference': 'ZNP-QA-RIDE',
        'documents': dummy_file
    }
    
    res = client.post('/api/v1/users/corporate/register/', payload_ride, format='multipart', SERVER_NAME='localhost')
    assert res.status_code == 201, f"Failed to register Ride Business: {res.data}"
    
    # Verify DB State
    ride_profile = CorporateProfile.objects.get(user=ride_user)
    assert ride_profile.business_category == 'RIDE', "Business category mismatch!"
    
    # Verify Task Routing
    ride_task = StaffTask.objects.get(created_by=ride_user)
    assert ride_task.task_type == TaskType.CORPORATE_RIDE_VERIFICATION, f"Wrong TaskType: {ride_task.task_type}"
    assert ride_task.assigned_role == 'RIDE_BUSINESS_VERIFIER', f"Wrong assigned_role: {ride_task.assigned_role}"
    print("✅ Ride Business properly registered and routed to RIDE_BUSINESS_VERIFIER.")
    
    
    # ---- TEST 2: ASSET BUSINESS REGISTRATION ----
    print("\nTest 2: Registering an Asset Business...")
    dummy_file = SimpleUploadedFile("test_doc2.pdf", b"file_content", content_type="application/pdf")
    client.force_authenticate(user=asset_user)
    payload_asset = {
        'company_name': 'Kiboss Hotels Ltd',
        'registration_number': 'REQ-200-A',
        'tax_id': 'TAX-ASSET-01',
        'business_category': 'ASSET',
        'plan_type': 'MONTHLY',
        'payment_reference': 'ZNP-QA-ASSET',
        'documents': dummy_file
    }
    
    res = client.post('/api/v1/users/corporate/register/', payload_asset, format='multipart', SERVER_NAME='localhost')
    assert res.status_code == 201, f"Failed to register Asset Business: {res.data}"
    
    # Verify DB State
    asset_profile = CorporateProfile.objects.get(user=asset_user)
    assert asset_profile.business_category == 'ASSET', "Business category mismatch!"
    
    # Verify Task Routing
    asset_task = StaffTask.objects.get(created_by=asset_user)
    assert asset_task.task_type == TaskType.CORPORATE_ASSET_VERIFICATION, f"Wrong TaskType: {asset_task.task_type}"
    assert asset_task.assigned_role == 'ASSET_BUSINESS_VERIFIER', f"Wrong assigned_role: {asset_task.assigned_role}"
    print("✅ Asset Business properly registered and routed to ASSET_BUSINESS_VERIFIER.")
    
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY.")

if __name__ == '__main__':
    run_qa()
