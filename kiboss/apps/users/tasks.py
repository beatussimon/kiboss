"""
Celery Tasks for Users App
"""

from celery import shared_task
from django.utils import timezone
from kiboss.apps.users.models import UserSubscription, BusinessSubscription
from kiboss.apps.assets.models import Asset

@shared_task
def expire_subscriptions():
    """
    [T2-11] Comprehensive subscription expiry task.
    Handles tier downgrades and asset delisting.
    """
    expired_user_subs = UserSubscription.objects.filter(status='ACTIVE', end_date__lt=timezone.now())
    count = expired_user_subs.count()
    for sub in expired_user_subs:
        sub.status = 'EXPIRED'
        sub.save()
        sub.user.account_tier = 'FREE'
        sub.user.save(update_fields=['account_tier', 'updated_at'])
        
        # Delist excess assets (keep only first 3)
        excess_assets = Asset.objects.filter(owner=sub.user, is_listed=True).order_by('-created_at')[3:]
        for asset in excess_assets:
            asset.is_listed = False
            asset.save(update_fields=['is_listed'])
            
    return f"Processed {count} expired subscriptions."

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_worker_invite_email(self, email, raw_password, company_name):
    """
    Send an email to an invited worker with their temporary password.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    import logging
    
    logger = logging.getLogger(__name__)
    
    subject = f"You have been invited to join {company_name} on KIBOSS"
    message = f"""
    Hello,
    
    You have been invited to join the corporate profile for {company_name} on KIBOSS.
    
    Your account has been created. Here are your temporary credentials:
    Email: {email}
    Password: {raw_password}
    
    Please log in and change your password immediately.
    
    Regards,
    The KIBOSS Team
    """
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return f"Invite email sent to {email}"
    except Exception as e:
        logger.error(f"Failed to send invite email to {email}: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, email, raw_password):
    """
    Send an email with a newly generated password (for worker password resets).
    """
    from django.core.mail import send_mail
    from django.conf import settings
    import logging
    
    logger = logging.getLogger(__name__)
    
    subject = "Your KIBOSS Password has been reset"
    message = f"""
    Hello,
    
    Your password has been reset by your corporate administrator.
    
    Here are your new temporary credentials:
    Email: {email}
    Password: {raw_password}
    
    Please log in and change your password immediately.
    
    Regards,
    The KIBOSS Team
    """
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return f"Password reset email sent to {email}"
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, email, code):
    """
    Send a verification code for email registration.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    import logging
    
    logger = logging.getLogger(__name__)
    
    subject = "Verify your KIBOSS account"
    message = f"""
    Hello,
    
    Your verification code is: {code}
    
    Enter this code to verify your email address.
    
    Regards,
    The KIBOSS Team
    """
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return f"Verification email sent to {email}"
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def delete_user_background(self, user_id):
    """
    Perform cascading deletes for a user in the background.
    """
    from django.contrib.auth import get_user_model
    import logging
    
    logger = logging.getLogger(__name__)
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.info(f"User {user_id} already deleted or does not exist.")
        return
        
    try:
        from django.db.models import Q
        from kiboss.apps.bookings.models import Booking
        from kiboss.apps.rides.models import Ride, SeatBooking, RideSchedule
        from kiboss.apps.payments.models import Payment, Dispute
        
        # Check active bookings (double check just in case)
        active = Booking.objects.filter(
            Q(renter=user) | Q(asset__owner=user),
            status__in=['ACTIVE', 'CONFIRMED']
        ).exists()
        if active:
            logger.warning(f"Cannot delete user {user.email}: has active or confirmed bookings")
            return
            
        SeatBooking.objects.filter(passenger=user).delete()
        RideSchedule.objects.filter(driver=user).delete()
        Ride.objects.filter(driver=user).delete()

        impacted_bookings = Booking.objects.filter(Q(renter=user) | Q(asset__owner=user))
        Dispute.objects.filter(booking__in=impacted_bookings).delete()
        Payment.objects.filter(booking__in=impacted_bookings).delete()
        impacted_bookings.delete()
        
        # Finally delete user (this triggers standard cascading on remaining simple objects like Profile, TrustScore)
        # Call super().delete to avoid loop if we override User.delete
        User.objects.filter(id=user_id).delete()
        
        return f"Successfully deleted user {user_id}"
    except Exception as e:
        logger.error(f"Error during background deletion of user {user_id}: {e}")
        raise self.retry(exc=e)
