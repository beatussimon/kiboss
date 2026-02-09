# Edge Case Handling Matrix for KIBOSS

This document describes how KIBOSS handles various edge cases and failure scenarios.

---

## 1. Concurrency & Race Conditions

### 1.1 Double Booking Prevention

| Scenario | Probability | Impact | Mitigation |
|----------|-------------|--------|------------|
| Two users book same time slot | Medium | High | Redis distributed lock |
| Payment race condition | Medium | High | Atomic payment processing |
| Seat booking conflict | High | High | Seat-level locking + DB constraint |
| Rating double submission | Low | Medium | Unique constraint + status check |

### 1.2 Double Booking Scenario

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DOUBLE BOOKING SCENARIO                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User A                          User B                                     │
│      │                               │                                       │
│      │  1. Check availability         │                                       │
│      │◄───────────────────────────────│                                       │
│      │  (Available)                   │                                       │
│      │                               │ 2. Check availability                  │
│      │                               │◄──────────────────────────────────────│
│      │                               │  (Available)                          │
│      │                               │                                       │
│      │  3. Acquire Redis lock        │                                       │
│      │◄───────────────────────────────│                                       │
│      │  (LOCKED)                     │                                       │
│      │                               │ 4. Try to acquire Redis lock          │
│      │                               │◄──────────────────────────────────────│
│      │                               │  (WAITING - Retry with backoff)       │
│      │                               │                                       │
│      │  5. Create booking            │                                       │
│      │◄───────────────────────────────│                                       │
│      │  (BOOKING_CREATED)            │                                       │
│      │                               │                                       │
│      │  6. Release lock              │                                       │
│      │◄───────────────────────────────│                                       │
│      │                               │                                       │
│      │                               │ 7. Acquire Redis lock (now succeeds)  │
│      │                               │◄──────────────────────────────────────│
│      │                               │                                       │
│      │                               │ 8. Check availability                 │
│      │                               │◄──────────────────────────────────────│
│      │                               │  (NOT AVAILABLE - Return error)      │
│      │                               │                                       │
│      │                               │ 9. Release lock                       │
│      │                               │◄──────────────────────────────────────│
│                                                                              │
│   Result: User A gets booking, User B gets "not available" error            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Seat Booking Concurrency

```python
# Concurrent seat booking implementation

class SeatBookingService:
    @classmethod
    def book_seat_concurrent(cls, ride_id, seat_number, passenger_id):
        """
        Book a seat with full concurrency control.
        
        Implements:
        1. Redis lock for the specific seat
        2. DB constraint check
        3. Atomic seat count update
        """
        lock_key = f"lock:seat:{ride_id}:{seat_number}"
        
        # Acquire seat lock
        lock_token = lock_manager.acquire_lock(lock_key, ttl=30, max_retries=3)
        if not lock_token:
            raise SeatLockError("Seat is currently being booked")
        
        try:
            with transaction.atomic():
                # Use SELECT FOR UPDATE to lock the ride row
                ride = Ride.objects.select_for_update().get(id=ride_id)
                
                # Check seat availability at DB level
                existing_booking = SeatBooking.objects.filter(
                    ride=ride,
                    seat_number=seat_number,
                    status__in=[SeatBookingStatus.RESERVED, SeatBookingStatus.CONFIRMED]
                ).select_for_update().first()
                
                if existing_booking:
                    raise SeatNotAvailableError("Seat is already booked")
                
                # Check ride capacity
                if ride.confirmed_seats >= ride.total_seats:
                    raise RideFullError("Ride is full")
                
                # Create booking
                booking = SeatBooking.objects.create(
                    ride=ride,
                    passenger_id=passenger_id,
                    seat_number=seat_number,
                    status=SeatBookingStatus.RESERVED
                )
                
                # Update seat count atomically
                ride.confirmed_seats += 1
                ride.save(update_fields=['confirmed_seats', 'updated_at'])
                
                return booking
                
        finally:
            lock_manager.release_lock(lock_key, lock_token)
```

---

## 2. Time-Related Edge Cases

### 2.1 Timezone Handling

| Scenario | Issue | Solution |
|----------|-------|----------|
| User in different timezone | Confusion about booking times | Store all times in UTC, display in user's timezone |
| Day boundary crossing | Booking spans midnight | Explicit end time, no implicit day boundaries |
| Daylight saving time | Hour skipped or repeated | Use timezone-aware datetimes, avoid hour-based logic |
| Asset in different tz | Availability rules | Asset timezone for availability, user timezone for display |

```python
# Timezone handling implementation

from django.utils import timezone as django_timezone
from datetime import datetime
import pytz


class TimezoneService:
    """Service for handling timezone conversions."""
    
    @classmethod
    def utc_to_user_local(cls, utc_time, user):
        """Convert UTC time to user's local timezone."""
        user_tz = pytz.timezone(user.profile.timezone)
        return utc_time.astimezone(user_tz)
    
    @classmethod
    def user_local_to_utc(cls, local_time, user):
        """Convert user's local time to UTC."""
        user_tz = pytz.timezone(user.profile.timezone)
        return user_tz.localize(local_time).astimezone(pytz.UTC)
    
    @classmethod
    def format_for_user(cls, utc_time, user, format='%B %d at %I:%M %p'):
        """Format UTC time for user's locale."""
        local_time = cls.utc_to_user_local(utc_time, user)
        return local_time.strftime(format)
    
    @classmethod
    def validate_booking_time(cls, start_time, end_time, asset):
        """
        Validate booking time considering timezones.
        
        All times are stored and processed in UTC internally.
        """
        # Ensure times are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=pytz.UTC)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=pytz.UTC)
        
        # Basic validation
        if start_time >= end_time:
            raise ValidationError("End time must be after start time")
        
        # Check against asset's timezone rules
        asset_tz = pytz.timezone(asset.timezone)
        
        # Get local times in asset timezone
        local_start = start_time.astimezone(asset_tz)
        local_end = end_time.astimezone(asset_tz)
        
        # Check if within operating hours
        availability = asset.availability_rules.first()
        if availability:
            if local_start.time() < availability.available_from:
                raise ValidationError("Booking starts before operating hours")
            if local_end.time() > availability.available_to:
                raise ValidationError("Booking ends after operating hours")
        
        return True
```

### 2.2 Grace Period Handling

| Scenario | Grace Period | Action |
|----------|--------------|--------|
| Late return | 15 minutes | No penalty, notification only |
| Payment timeout | 15 minutes | Booking expires |
| Check-in grace | 10 minutes | Can still check in |
| No-show cutoff | 10 minutes after departure | Mark as no-show |
| Cancellation | 48 hours | Full refund |

```python
# Grace period implementation

class GracePeriodService:
    """Service for handling grace periods."""
    
    @classmethod
    def check_late_return(cls, booking, actual_return_time):
        """Check if return is late and calculate fees."""
        grace_end = booking.end_time + timedelta(minutes=booking.grace_period_minutes)
        
        if actual_return_time <= grace_end:
            return {
                'is_late': False,
                'late_minutes': 0,
                'fee': Decimal('0.00')
            }
        
        late_minutes = (actual_return_time - grace_end).total_seconds() / 60
        late_fee = booking.calculate_late_fee(actual_return_time)
        
        return {
            'is_late': True,
            'late_minutes': int(late_minutes),
            'fee': late_fee
        }
    
    @classmethod
    def check_payment_timeout(cls, booking):
        """Check if payment has timed out."""
        timeout = booking.created_at + timedelta(minutes=15)
        
        if timezone.now() > timeout:
            return True
        return False
    
    @classmethod
    def get_countdown_seconds(cls, booking):
        """Get seconds until booking expires."""
        timeout = booking.created_at + timedelta(minutes=15)
        remaining = timeout - timezone.now()
        return max(0, remaining.total_seconds())
```

---

## 3. Payment Failure Scenarios

### 3.1 Payment Failure Handling

| Failure Type | Response | User Action |
|--------------|----------|-------------|
| Card declined | Show error, keep booking pending | Retry with different card |
| Insufficient funds | Show error, keep booking pending | Retry with different payment |
| Payment timeout | Auto-cancel booking, release slot | Create new booking |
| Gateway error | Retry 3 times, then alert admin | Retry later |
| Network error | Show error, preserve booking state | Retry connection |

```python
# Payment failure handling

class PaymentFailureHandler:
    """Handler for various payment failure scenarios."""
    
    FAILURE_RESPONSES = {
        'card_declined': {
            'message': 'Your card was declined. Please try a different payment method.',
            'user_action': 'Retry with different card',
            'booking_action': 'KEEP_PENDING',
            'notification': False
        },
        'insufficient_funds': {
            'message': 'Insufficient funds. Please try a different payment method.',
            'user_action': 'Retry with different card',
            'booking_action': 'KEEP_PENDING',
            'notification': False
        },
        'expired_card': {
            'message': 'Your card has expired. Please update your payment method.',
            'user_action': 'Update payment method',
            'booking_action': 'KEEP_PENDING',
            'notification': False
        },
        'payment_timeout': {
            'message': 'Payment timed out. Please try again.',
            'user_action': 'Retry payment',
            'booking_action': 'EXPIRE_BOOKING',
            'notification': True
        },
        'gateway_error': {
            'message': 'Payment service temporarily unavailable. Please try again.',
            'user_action': 'Retry later',
            'booking_action': 'KEEP_PENDING',
            'notification': False
        },
        'network_error': {
            'message': 'Network error. Please check your connection and retry.',
            'user_action': 'Check connection',
            'booking_action': 'KEEP_PENDING',
            'notification': False
        }
    }
    
    @classmethod
    def handle_failure(cls, payment, failure_type, error_details):
        """Handle payment failure based on type."""
        response = cls.FAILURE_RESPONSES.get(failure_type, cls.FAILURE_RESPONSES['gateway_error'])
        
        # Update payment record
        payment.status = PaymentStatus.FAILED
        payment.failure_code = failure_type
        payment.failure_message = error_details.get('message', 'Unknown error')
        payment.save()
        
        # Create audit log
        AuditLog.log(
            actor=payment.booking.renter,
            action=AuditAction.PAYMENT_FAILED,
            description=f"Payment failed: {failure_type}",
            resource_type='Payment',
            resource_id=payment.id,
            metadata={
                'booking_id': str(payment.booking.id),
                'failure_type': failure_type,
                'error_details': error_details
            }
        )
        
        # Handle booking based on response
        if response['booking_action'] == 'EXPIRE_BOOKING':
            from kiboss.apps.bookings.models import BookingStatus
            payment.booking.transition_to(
                BookingStatus.EXPIRED,
                actor_type='SYSTEM',
                reason='Payment timeout'
            )
        
        # Send notification if required
        if response['notification']:
            NotificationService.create_notification(
                event_type='payment.failed',
                recipient=payment.booking.renter,
                context={
                    'booking_id': str(payment.booking.id),
                    'error_message': response['message']
                }
            )
        
        return response
```

### 3.2 Partial Cancellation

| Scenario | Refund Amount | Penalty | Notes |
|----------|---------------|---------|-------|
| 48+ hours before | 100% | 0% | Full refund |
| 24-48 hours | 75% | 25% | Owner gets 25% |
| 12-24 hours | 50% | 50% | Owner gets 50% |
| 2-12 hours | 25% | 75% | Owner gets 75% |
| < 2 hours | 0% | 100% | Full penalty |
| No-show | 0% | 25% | Penalty + no refund |

```python
# Partial cancellation implementation

class CancellationPolicyService:
    """Service for calculating cancellation fees."""
    
    POLICY_TIERS = [
        (timedelta(hours=48), Decimal('1.00'), Decimal('0.00')),  # 100% refund, 0% penalty
        (timedelta(hours=24), Decimal('0.75'), Decimal('0.25')),
        (timedelta(hours=12), Decimal('0.50'), Decimal('0.50')),
        (timedelta(hours=2), Decimal('0.25'), Decimal('0.75')),
        (timedelta(hours=0), Decimal('0.00'), Decimal('1.00')),
    ]
    
    @classmethod
    def calculate_refund(cls, booking, cancel_time):
        """
        Calculate refund amount based on cancellation timing.
        
        Args:
            booking: Booking object
            cancel_time: Time of cancellation
            
        Returns:
            dict with refund_amount, penalty_amount, policy_tier
        """
        time_until_start = booking.start_time - cancel_time
        
        for hours_threshold, refund_pct, penalty_pct in cls.POLICY_TIERS:
            if time_until_start >= hours_threshold:
                refund_amount = booking.total_price * refund_pct
                penalty_amount = booking.total_price * penalty_pct
                
                return {
                    'refund_amount': refund_amount,
                    'penalty_amount': penalty_amount,
                    'policy_tier': f'{hours_threshold.days * 24 + hours_threshold.seconds // 3600}h+',
                    'refund_pct': float(refund_pct) * 100,
                    'penalty_pct': float(penalty_pct) * 100
                }
        
        # No-show case
        return {
            'refund_amount': Decimal('0.00'),
            'penalty_amount': booking.total_price * Decimal('0.25'),
            'policy_tier': 'no_show',
            'refund_pct': 0,
            'penalty_pct': 25
        }
```

---

## 4. System Failure Scenarios

### 4.1 Redis Failure

| Scenario | Impact | Fallback |
|----------|--------|----------|
| Redis unavailable | Lock acquisition fails | Use DB-based locks |
| Redis slow | Operations timeout | Increased timeout, circuit breaker |
| Redis data loss | Cache invalid | Rebuild from DB |
| Redis memory full | New keys fail | Eviction policy, alerts |

```python
# Redis fallback implementation

class RedisFailoverService:
    """Service for handling Redis failures."""
    
    def __init__(self):
        self.redis_available = True
        self.fallback_mode = False
    
    def check_health(self):
        """Check Redis health."""
        try:
            from kiboss.apps.common.locking import lock_manager
            lock_manager.client.ping()
            self.redis_available = True
            self.fallback_mode = False
            return True
        except Exception as e:
            self.redis_available = False
            return False
    
    def get_lock_strategy(self, lock_type):
        """
        Get appropriate lock strategy based on Redis availability.
        """
        if self.redis_available and not self.fallback_mode:
            return 'redis'
        else:
            return 'database'
    
    @contextmanager
    def adaptive_lock(self, lock_key, lock_type='booking', ttl=30):
        """
        Context manager that adapts lock strategy based on availability.
        """
        strategy = self.get_lock)
        
        if_strategy(lock_type strategy == 'redis':
            with lock_manager.lock(lock_key, ttl=ttl):
                yield
        else:
            # Use DB-based lock
            with self.database_lock(lock_key, ttl=ttl):
                yield
    
    def database_lock(self, lock_key, ttl=30):
        """Database-based lock context manager."""
        from kiboss.apps.bookings.models import BookingLock
        from django.utils import timezone
        from datetime import timedelta
        
        lock = BookingLock.objects.create(
            lock_type=lock_type,
            resource_type='fallback',
            resource_id=lock_key,
            owner_id='fallback',
            owner_process='system',
            expires_at=timezone.now() + timedelta(seconds=ttl)
        )
        
        try:
            yield lock
        finally:
            lock.delete()
```

### 4.2 Celery Task Failure

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Worker crash | Task lost | Retry with exponential backoff |
| Task timeout | Incomplete processing | Re-queue, max retries |
| Database error | Partial completion | Rollback, retry |
| Memory overflow | Process killed | Chunk processing |

```python
# Celery task retry implementation

from celery.exceptions import MaxRetriesExceededError


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def resilient_booking_task(self, booking_id):
    """
    Celery task with comprehensive retry logic.
    """
    try:
        # Process booking
        booking = Booking.objects.get(id=booking_id)
        # ... task logic ...
        
        return {'status': 'success', 'booking_id': booking_id}
    
    except Exception as e:
        # Log failure
        logger.error(f"Task failed for booking {booking_id}: {e}")
        
        # Check if should retry
        if self.request.retries >= self.max_retries:
            # Final failure - alert admin
            self.send_alert_email(booking_id, e)
            raise MaxRetriesExceededError(f"Max retries exceeded: {e}")
        
        # Retry with exponential backoff
        raise self.retry(exc=e)
```

---

## 5. User Behavior Edge Cases

### 5.1 Rating Manipulation Prevention

| Scenario | Prevention |
|----------|------------|
| Multiple ratings for same booking | Unique constraint on (booking, reviewer) |
| Rating before completion | Status check - only COMPLETED |
| Fake accounts for boost | Trust score weighted average |
| Revenge ratings | Moderation workflow |
| Rating spamming | One rating per transaction |

```python
# Rating validation

class RatingValidationService:
    """Service for validating rating submissions."""
    
    @classmethod
    def validate_rating_submission(cls, booking, reviewer):
        """Validate that rating can be submitted."""
        
        # Check booking is completed
        if booking.status != BookingStatus.COMPLETED:
            raise ValidationError("Can only rate completed bookings")
        
        # Check rating doesn't exist
        if Rating.objects.filter(booking=booking, reviewer=reviewer).exists():
            raise ValidationError("You have already submitted a rating for this booking")
        
        # Check time window (within 14 days of completion)
        rating_window = timedelta(days=14)
        if timezone.now() - booking.completed_at > rating_window:
            raise ValidationError("Rating window has expired")
        
        # Check mutual rating
        mutual_booking = Rating.objects.filter(
            booking=booking,
            reviewer=booking.renter if reviewer == booking.asset.owner else booking.asset.owner
        ).exists()
        
        return True
```

### 5.2 Messaging Abuse Prevention

| Scenario | Prevention |
|----------|------------|
| Spam messages | Rate limiting, content filtering |
| Harassment | Report feature, moderation |
| Excessive attachments | Size limits, type restrictions |
| Message flooding | Rate limits per thread |
| Fake reports | Report validation, penalty for abuse |

```python
# Messaging abuse prevention

class AbusePreventionService:
    """Service for preventing messaging abuse."""
    
    RATE_LIMITS = {
        'messages_per_hour': 100,
        'messages_per_day': 1000,
        'threads_per_day': 50,
        'reports_per_day': 10
    }
    
    CONTENT_LIMITS = {
        'max_message_length': 10000,
        'max_attachments': 5,
        'max_attachment_size': 10 * 1024 * 1024,  # 10MB
        'allowed_attachment_types': ['IMAGE', 'DOCUMENT']
    }
    
    @classmethod
    def check_rate_limit(cls, user, action):
        """Check if user has exceeded rate limits."""
        from kiboss.apps.common.rate_limiting import rate_limiter
        
        key = f"ratelimit:user:{user.id}:{action}"
        is_allowed, remaining, _ = rate_limiter.check_rate_limit(
            key=key,
            limit=cls.RATE_LIMITS.get(action, 100),
            window_seconds=3600
        )
        
        return is_allowed
    
    @classmethod
    def validate_content(cls, content, attachments=None):
        """Validate message content."""
        errors = []
        
        # Check length
        if len(content) > cls.CONTENT_LIMITS['max_message_length']:
            errors.append(f"Message exceeds {cls.CONTENT_LIMITS['max_message_length']} characters")
        
        # Check for spam patterns
        if cls._is_spam_content(content):
            errors.append("Message appears to be spam")
        
        # Check attachments
        if attachments and len(attachments) > cls.CONTENT_LIMITS['max_attachments']:
            errors.append(f"Maximum {cls.CONTENT_LIMITS['max_attachments']} attachments allowed")
        
        return errors
    
    @classmethod
    def _is_spam_content(cls, content):
        """Detect spam content."""
        # Check for excessive URLs
        url_count = content.count('http://') + content.count('https://')
        if url_count > 3:
            return True
        
        # Check for spam keywords
        spam_keywords = ['buy now', 'click here', 'free money', 'make money fast']
        if any(kw in content.lower() for kw in spam_keywords):
            return True
        
        return False
```

---

## 6. Data Consistency Edge Cases

### 6.1 Contract Version Mismatch

| Scenario | Prevention |
|----------|------------|
| Asset price changes after booking | Store price snapshot in booking |
| Terms changed after booking | Store terms snapshot in contract |
| User data changes | Store user data snapshot in contract |
| Old contract accessed | Version tracking, immutable snapshots |

```python
# Contract versioning

class ContractVersioningService:
    """Service for handling contract versions."""
    
    @classmethod
    def create_contract_snapshot(cls, booking):
        """Create immutable snapshot for contract."""
        from kiboss.apps.contracts.models import Contract, ContractVersion
        
        # Get current asset state
        asset = booking.asset
        
        snapshot = {
            'booking': {
                'id': str(booking.id),
                'start_time': booking.start_time.isoformat(),
                'end_time': booking.end_time.isoformat(),
                'quantity': booking.quantity,
                'unit_price': str(booking.unit_price),
                'subtotal': str(booking.subtotal),
                'total_price': str(booking.total_price),
                'currency': booking.currency
            },
            'asset': {
                'id': str(asset.id),
                'name': asset.name,
                'description': asset.description,
                'address': asset.address,
                'owner_id': str(asset.owner_id)
            },
            'renter': {
                'id': str(booking.renter.id),
                'name': booking.renter.get_full_name(),
                'email': booking.renter.email
            },
            'owner': {
                'id': str(asset.owner.id),
                'name': asset.owner.get_full_name(),
                'email': asset.owner.email
            },
            'created_at': timezone.now().isoformat()
        }
        
        # Create contract with snapshot
        contract = Contract.objects.create(
            booking=booking,
            version=1,
            status=ContractStatus.PENDING,
            snapshot=snapshot,
            jurisdiction=asset.jurisdiction,
            cancellation_policy=asset.get_property('cancellation_policy', ''),
            late_return_policy=asset.get_property('late_return_policy', ''),
            damage_policy=asset.get_property('damage_policy', '')
        )
        
        # Create version record
        ContractVersion.objects.create(
            contract=contract,
            version=1,
            snapshot=snapshot,
            changes='Initial contract generation'
        )
        
        return contract
```

### 6.2 Orphaned Records

| Scenario | Prevention | Cleanup |
|----------|-------------|---------|
| Deleted user with bookings | PROTECT on delete | Soft delete, archive |
| Deleted asset with bookings | PROTECT on delete | Complete with refund |
| Deleted payment for booking | PROTECT on delete | Prevent deletion |
| Deleted thread with messages | CASCADE | Archive thread |

---

## 7. Edge Case Summary Table

| Edge Case | Probability | Impact | Mitigation | Fallback |
|-----------|-------------|--------|------------|----------|
| Double booking | Medium | High | Redis lock + DB constraint | Error response |
| Payment failure | Medium | Medium | Retry + graceful error | Alternative payment |
| Late return | Medium | Low | Grace period + fee | Fee calculation |
| No-show | Low | Medium | Penalty + notification | Standby upgrade |
| Redis failure | Low | High | Fallback to DB | Degraded mode |
| Celery failure | Low | Medium | Retry + alerts | Manual intervention |
| Contract mismatch | Low | High | Version snapshots | Original terms |
| Rating fraud | Low | Medium | Validation + moderation | Rejection |
| Messaging abuse | Medium | Medium | Rate limits + filters | Account suspension |
| Timezone confusion | Medium | Low | Clear formatting | Timezone selector |
