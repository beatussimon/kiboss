"""
Verification Services for KIBOSS.
"""
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from kiboss.apps.tasks.models import StaffTask, TaskType, TaskStatus, TaskPriority
from kiboss.apps.assets.models import Asset, VerificationStatus, AssetType
from kiboss.apps.users.models import CorporateProfile, User

class VerificationService:
    """
    Service to handle verification workflows for various entities (Assets, Users, Corporate).
    """

    @staticmethod
    def request_verification(entity, user, notes=""):
        """
        Submit an entity for verification.
        Creates a StaffTask and updates the entity's status if applicable.
        """
        content_type = ContentType.objects.get_for_model(entity)
        task_type = None
        assigned_role = None
        title = ""
        description = ""

        # Determine Task Type and Role based on Entity
        if isinstance(entity, Asset):
            entity.verification_status = VerificationStatus.PENDING
            entity.verification_notes = notes
            entity.save()

            if entity.asset_type == AssetType.VEHICLE:
                task_type = TaskType.VEHICLE_VERIFICATION
                assigned_role = 'CAR_VERIFIER'
                title = f"Verify Vehicle: {entity.name}"
                description = f"Vehicle verification request from {user.email}. {notes}"
            elif entity.asset_type in [AssetType.HOTEL, AssetType.RESTAURANT]:
                task_type = TaskType.ASSET_AUDIT
                assigned_role = 'OPS'
                title = f"Verify Property: {entity.name}"
                description = f"Property verification request from {user.email}. {notes}"
            else:
                # Default asset verification
                task_type = TaskType.ASSET_AUDIT
                assigned_role = 'VERIFIER'
                title = f"Verify Asset: {entity.name}"
                description = f"Asset verification request from {user.email}. {notes}"

        elif isinstance(entity, CorporateProfile):
            entity.verification_status = 'PENDING'
            entity.save()
            
            task_type = TaskType.CORPORATE_VERIFICATION
            assigned_role = 'BUSINESS_VERIFIER'
            title = f"Verify Business: {entity.company_name}"
            description = f"Corporate verification request from {user.email}. {notes}"
            
        elif isinstance(entity, User):
            # Identity verification
            task_type = TaskType.IDENTITY_VERIFICATION
            assigned_role = 'VERIFIER' # Or IDENTITY_VERIFIER
            title = f"Verify User Identity: {entity.email}"
            description = f"Identity verification request. {notes}"

        else:
            raise ValueError(f"Verification not supported for {type(entity)}")

        # Create the Task
        task = StaffTask.objects.create(
            title=title,
            description=description,
            task_type=task_type,
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            assigned_role=assigned_role,
            content_type=content_type,
            object_id=entity.id,
            created_by=user
        )
        
        return task

    @staticmethod
    def process_verification(task, action, reviewer, notes=""):
        """
        Process a verification task (Approve/Reject).
        Updates the task and the linked entity.
        """
        # This logic should ideally be called by the StaffTaskViewSet.process action
        # separating it here allows for re-use and cleaner view logic.
        
        entity = task.content_object
        
        if action == 'APPROVE':
            if isinstance(entity, Asset):
                entity.verification_status = VerificationStatus.VERIFIED
                entity.verified_at = timezone.now()
                entity.verified_by = reviewer
                entity.verification_notes = notes
                entity.is_listed = True
                entity.save()
            elif isinstance(entity, CorporateProfile):
                entity.verification_status = 'VERIFIED'
                entity.save()
                # Update User Tier
                user = entity.user
                user.verification_tier = 'business'
                user.is_identity_verified = True
                user.save()
                
            elif isinstance(entity, User):
                entity.is_identity_verified = True
                entity.save()

        elif action == 'REJECT':
            if isinstance(entity, Asset):
                entity.verification_status = VerificationStatus.REJECTED
                entity.verification_notes = notes
                entity.is_listed = False
                entity.save()
            elif isinstance(entity, CorporateProfile):
                entity.verification_status = 'REJECTED'
                entity.save()
            elif isinstance(entity, User):
                entity.is_identity_verified = False
                entity.save()

        elif action == 'REQUEST_CHANGES':
             if isinstance(entity, Asset):
                entity.verification_status = VerificationStatus.UNVERIFIED # Or keep PENDING with notes?
                entity.verification_notes = f"Changes Requested: {notes}"
                entity.save()

        elif action == 'REVOKE':
            if isinstance(entity, Asset):
                entity.verification_status = VerificationStatus.PENDING
                entity.verification_notes = f"Verification Revoked: {notes}"
                entity.is_listed = False
                entity.save()
            elif isinstance(entity, CorporateProfile):
                entity.verification_status = 'PENDING'
                entity.save()
                user = entity.user
                user.verification_tier = 'none'
                # Also revoke identity verified status if it was granted via this profile
                user.is_identity_verified = False
                user.save()
            elif isinstance(entity, User):
                # Only revoke if they don't have a verified corporate profile
                if not hasattr(entity, 'corporate_profile') or entity.corporate_profile.verification_status != 'VERIFIED':
                    entity.is_identity_verified = False
                    entity.save()
