from django.test import TestCase
from django.contrib.auth import get_user_model
from kiboss.apps.assets.models import Asset, AssetType, VerificationStatus
from kiboss.apps.tasks.models import StaffTask, TaskStatus, TaskType
from kiboss.apps.rbac.models import UserRole, Role
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APITestCase
from rest_framework import status
import uuid

User = get_user_model()

class TaskWorkflowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            password='password123',
            first_name='Regular',
            last_name='User'
        )
        self.verifier = User.objects.create_user(
            email='verifier@example.com',
            password='password123',
            first_name='Staff',
            last_name='Verifier'
        )
        # Assign Verifier role and permissions
        from kiboss.apps.rbac.models import Permission, RolePermission
        UserRole.objects.create(user=self.verifier, role='CAR_VERIFIER')
        RolePermission.objects.get_or_create(role='CAR_VERIFIER', permission=Permission.ASSET_VERIFY)
        RolePermission.objects.get_or_create(role='CAR_VERIFIER', permission=Permission.ASSET_VIEW)
        
        self.client.force_authenticate(user=self.user)

    def test_vehicle_registration_creates_task(self):
        """Test that registering a vehicle creates a staff task."""
        url = '/api/v1/rides/vehicles/'
        data = {
            'name': 'Test Car',
            'description': 'A nice test car',
            'properties': {
                'make': 'Toyota',
                'model': 'Corolla',
                'year': '2020',
                'license_plate': 'KCA123X',
                'vehicle_type': 'SEDAN'
            }
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        
        # Check Asset created
        asset = Asset.objects.get(name='Test Car')
        self.assertEqual(asset.verification_status, VerificationStatus.PENDING)
        
        # Check Task created
        task = StaffTask.objects.get(object_id=asset.id)
        self.assertEqual(task.task_type, TaskType.VE_VERIFICATION if hasattr(TaskType, 'VE_VERIFICATION') else TaskType.VEHICLE_VERIFICATION)
        self.assertEqual(task.assigned_role, 'CAR_VERIFIER')
        self.assertEqual(task.status, TaskStatus.PENDING)

    def test_verifier_can_approve_task(self):
        """Test that a verifier can approve a task and verify the vehicle."""
        # Create asset and task
        asset = Asset.objects.create(
            name='Car to Verify',
            asset_type=AssetType.VEHICLE,
            owner=self.user,
            verification_status=VerificationStatus.PENDING,
            properties={
                'make': 'Toyota',
                'model': 'Corolla',
                'year': '2020',
                'license_plate': 'KCA123Y',
                'vehicle_type': 'SEDAN'
            }
        )
        # Add required documents
        from kiboss.apps.assets.models import AssetDocument
        for doc_type in ['REGISTRATION', 'INSURANCE', 'OWNERSHIP']:
             AssetDocument.objects.create(
                 asset=asset,
                 document_type=doc_type,
                 file='test.pdf',
                 name=f'Test {doc_type}'
             )
        task = StaffTask.objects.create(
            title='Verify Car',
            task_type=TaskType.VEHICLE_VERIFICATION,
            content_type=ContentType.objects.get_for_model(Asset),
            object_id=asset.id,
            assigned_role='CAR_VERIFIER',
            status=TaskStatus.PENDING
        )
        
        # Authenticate as verifier
        self.client.force_authenticate(user=self.verifier)
        
        url = f'/api/v1/tasks/{task.id}/process/'
        data = {
            'action': 'APPROVE',
            'notes': 'Everything looks good!'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check task completed
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.assigned_to, self.verifier)
        
        # Check asset verified
        asset.refresh_from_db()
        self.assertEqual(asset.verification_status, VerificationStatus.VERIFIED)
        self.assertEqual(asset.verified_by, self.verifier)
