import os
import django
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.users.models import User, CorporateProfile
from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus
from kiboss.apps.common.services.verification import VerificationService
from rest_framework.test import APIClient

def run_e2e():
    print("--- Starting End-to-End Testing of Business Scenarios ---\n")
    client = APIClient()
    
    # --- SETUP ---
    # Clean previous data
    User.objects.filter(email__in=['john.ride@test.com', 'mary.asset@test.com', 'staff.verifier@test.com']).delete()
    
    # Create Staff Verifier
    staff_user = User.objects.create_superuser(
        email='staff.verifier@test.com',
        password='staffpassword123',
        first_name='Admin',
        last_name='Verifier'
    )
    
    # Add necessary roles to staff if testing pure RBAC, but superuser bypasses most checks.
    
    # Create Users
    john_ride = User.objects.create_user(email='john.ride@test.com', password='password123')
    mary_asset = User.objects.create_user(email='mary.asset@test.com', password='password123')
    
    dummy_file = SimpleUploadedFile("test_proof.pdf", b"legal document content", content_type="application/pdf")
    
    # =========================================================================
    # SCENARIO 1: The Ride Business Workflow
    # =========================================================================
    print(">>> SCENARIO 1: The Ride Business Workflow (John's Metro Shuttles)")
    
    # 1. Registration via API (simulating frontend)
    print("  -> John submits Corporate Registration...")
    client.force_authenticate(user=john_ride)
    res = client.post('/api/v1/users/corporate/register/', {
        'company_name': 'Metro Shuttles Ltd',
        'registration_number': 'RIDE-12345',
        'tax_id': 'TIN-999',
        'business_category': 'RIDE',
        'plan_type': 'MONTHLY',
        'payment_reference': 'ZENOPAY-RIDE-01',
        'documents': dummy_file
    }, format='multipart', SERVER_NAME='localhost')
    assert res.status_code == 201, f"Failed: {res.data}"
    
    # 2. System Verification (Checking Task Routing)
    print("  -> System processes request and routes to specialized verifier...")
    task_ride = StaffTask.objects.get(created_by=john_ride)
    assert task_ride.task_type == TaskType.CORPORATE_RIDE_VERIFICATION
    assert task_ride.assigned_role == 'RIDE_BUSINESS_VERIFIER'
    assert task_ride.status == TaskStatus.PENDING
    
    # 3. Specialized Review (Staff Action)
    print("  -> Staff Verifier reviews documents and Approves...")
    # Simulate staff processing the task
    VerificationService.process_verification(task_ride, 'APPROVE', staff_user, "Documents are legit. License valid.")
    
    # Service doesn't inherently mark the task complete, let's just mark it
    task_ride.status = TaskStatus.COMPLETED
    task_ride.save()
    
    # 4. Usage & Benefits Check
    print("  -> Verifying John's account benefits are unlocked...")
    john_ride.refresh_from_db()
    assert john_ride.verification_tier == 'business', "John didn't get the business badge!"
    assert hasattr(john_ride, 'corporate_profile')
    assert john_ride.corporate_profile.verification_status == 'VERIFIED'
    assert john_ride.corporate_profile.business_category == 'RIDE'
    print("  ✅ Scenario 1 (Ride Business) Passed E2E successfully!\n")
    

    # =========================================================================
    # SCENARIO 2: The Asset Business Workflow
    # =========================================================================
    print(">>> SCENARIO 2: The Asset Business Workflow (Mary's Grand Plaza Hotels)")
    
    dummy_file_2 = SimpleUploadedFile("test_proof_asset.pdf", b"legal document content", content_type="application/pdf")
    
    # 1. Registration via API
    print("  -> Mary submits Corporate Registration...")
    client.force_authenticate(user=mary_asset)
    res = client.post('/api/v1/users/corporate/register/', {
        'company_name': 'Grand Plaza Hotels',
        'registration_number': 'ASSET-98765',
        'tax_id': 'TIN-888',
        'business_category': 'ASSET',
        'plan_type': 'YEARLY',
        'payment_reference': 'ZENOPAY-ASSET-02',
        'documents': dummy_file_2
    }, format='multipart', SERVER_NAME='localhost')
    assert res.status_code == 201, f"Failed: {res.data}"
    
    # 2. System Verification (Checking Task Routing)
    print("  -> System processes request and routes to specialized verifier...")
    task_asset = StaffTask.objects.get(created_by=mary_asset)
    assert task_asset.task_type == TaskType.CORPORATE_ASSET_VERIFICATION
    assert task_asset.assigned_role == 'ASSET_BUSINESS_VERIFIER'
    assert task_asset.status == TaskStatus.PENDING
    
    # 3. Specialized Review (Staff Action)
    print("  -> Staff Verifier reviews documents and Approves...")
    VerificationService.process_verification(task_asset, 'APPROVE', staff_user, "Real estate deeds verified.")
    task_asset.status = TaskStatus.COMPLETED
    task_asset.save()
    
    # 4. Usage & Benefits Check
    print("  -> Verifying Mary's account benefits are unlocked...")
    mary_asset.refresh_from_db()
    assert mary_asset.verification_tier == 'business', "Mary didn't get the business badge!"
    assert hasattr(mary_asset, 'corporate_profile')
    assert mary_asset.corporate_profile.verification_status == 'VERIFIED'
    assert mary_asset.corporate_profile.business_category == 'ASSET'
    print("  ✅ Scenario 2 (Asset Business) Passed E2E successfully!\n")
    
    
    print("🎉 ALL END-TO-END SCENARIOS COMPLETED AND VALIDATED!")


if __name__ == '__main__':
    run_e2e()
