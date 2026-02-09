# Redis Locking Strategy for KIBOSS

This document describes the Redis-based distributed locking strategy for preventing race conditions in KIBOSS.

---

## 1. Lock Types

### 1.1 Asset Availability Lock
**Purpose**: Prevent double bookings for the same asset/time slot.

```
Lock Key: lock:asset:{asset_id}
TTL: 30 seconds
Retry: 3 times with exponential backoff (100ms, 200ms, 400ms)
```

### 1.2 Seat Booking Lock (Ride-Sharing)
**Purpose**: Prevent concurrent seat bookings on the same ride.

```
Lock Key: lock:seat:{ride_id}:{seat_number}
TTL: 30 seconds
Retry: 3 times with exponential backoff
```

### 1.3 Payment Processing Lock
**Purpose**: Prevent duplicate payment authorization.

```
Lock Key: lock:payment:{booking_id}
TTL: 60 seconds
Retry: 3 times
```

### 1.4 Booking State Transition Lock
**Purpose**: Prevent concurrent state changes on bookings.

```
Lock Key: lock:booking:{booking_id}
TTL: 15 seconds
Retry: 3 times
```

### 1.5 User Rate Limit Lock
**Purpose**: Implement rate limiting per user.

```
Lock Key: ratelimit:user:{user_id}:{action}
TTL: Per action window (e.g., 1 hour)
```

---

## 2. Lock Implementation

### 2.1 Redis Lock Manager

```python
# kiboss/apps/common/locking.py

import redis
import uuid
import time
from django.conf import settings
from typing import Optional, Callable
from contextlib import contextmanager


class RedisLockManager:
    """
    Redis-based distributed lock manager for KIBOSS.
    
    Features:
    - Atomic lock acquisition using SET NX EX
    - Automatic lock release using Lua script
    - Lock renewal for long operations
    - Retry with exponential backoff
    """
    
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.locks = {}
    
    def acquire_lock(
        self,
        lock_key: str,
        ttl: int = 30,
        max_retries: int = 3,
        retry_delay: float = 0.1
    ) -> Optional[str]:
        """
        Acquire a distributed lock.
        
        Args:
            lock_key: Unique lock identifier
            ttl: Lock time-to-live in seconds
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay (exponential backoff)
            
        Returns:
            Lock token if acquired, None otherwise
        """
        lock_token = str(uuid.uuid4())
        retry_count = 0
        
        while retry_count < max_retries:
            # Try to acquire lock atomically
            acquired = self.client.set(
                lock_key,
                lock_token,
                nx=True,  # Set only if not exists
                ex=ttl    # Expire after TTL
            )
            
            if acquired:
                self.locks[lock_key] = lock_token
                return lock_token
            
            # Exponential backoff
            retry_count += 1
            time.sleep(retry_delay * (2 ** (retry_count - 1)))
        
        return None
    
    def release_lock(self, lock_key: str, lock_token: str) -> bool:
        """
        Release a distributed lock atomically.
        
        Uses Lua script to ensure only the lock owner can release.
        
        Args:
            lock_key: Lock identifier
            lock_token: Token received when acquiring lock
            
        Returns:
            True if released, False otherwise
        """
        # Lua script for atomic release
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        result = self.client.eval(release_script, 1, lock_key, lock_token)
        
        if lock_key in self.locks:
            del self.locks[lock_key]
        
        return bool(result)
    
    def extend_lock(self, lock_key: str, lock_token: str, ttl: int) -> bool:
        """
        Extend lock TTL (for long operations).
        
        Args:
            lock_key: Lock identifier
            lock_token: Token received when acquiring lock
            ttl: New TTL in seconds
            
        Returns:
            True if extended, False otherwise
        """
        extend_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        result = self.client.eval(extend_script, 1, lock_key, lock_token, ttl)
        return bool(result)
    
    def is_locked(self, lock_key: str) -> bool:
        """Check if a lock exists."""
        return self.client.exists(lock_key) > 0
    
    def get_lock_owner(self, lock_key: str) -> Optional[str]:
        """Get the owner token of a lock."""
        return self.client.get(lock_key)
    
    @contextmanager
    def lock(
        self,
        lock_key: str,
        ttl: int = 30,
        max_retries: int = 3,
        retry_delay: float = 0.1
    ):
        """
        Context manager for acquiring and releasing locks.
        
        Usage:
            with lock_manager.lock("lock:asset:123", ttl=30):
                # Critical section
                ...
        """
        lock_token = self.acquire_lock(
            lock_key, ttl, max_retries, retry_delay
        )
        
        if not lock_token:
            raise LockAcquisitionError(
                f"Could not acquire lock: {lock_key}"
            )
        
        try:
            yield lock_token
        finally:
            self.release_lock(lock_key, lock_token)


class LockAcquisitionError(Exception):
    """Raised when lock acquisition fails."""
    pass


# Global lock manager instance
lock_manager = RedisLockManager()
```

---

## 3. Lock Usage Patterns

### 3.1 Asset Availability Check with Lock

```python
# kiboss/apps/bookings/services.py

from kiboss.apps.common.locking import lock_manager, LockAcquisitionError


class BookingLockService:
    """Service for booking-related locks."""
    
    ASSET_LOCK_PREFIX = "lock:asset:"
    BOOKING_LOCK_PREFIX = "lock:booking:"
    
    @classmethod
    def get_asset_lock_key(cls, asset_id: str) -> str:
        return f"{cls.ASSET_LOCK_PREFIX}{asset_id}"
    
    @classmethod
    def get_booking_lock_key(cls, booking_id: str) -> str:
        return f"{cls.BOOKING_LOCK_PREFIX}{booking_id}"
    
    @classmethod
    def with_asset_lock(cls, asset_id: str, callback: Callable, ttl: int = 30):
        """
        Execute callback with asset lock held.
        
        Args:
            asset_id: Asset UUID
            callback: Function to execute
            ttl: Lock TTL in seconds
            
        Returns:
            Callback return value
        """
        lock_key = cls.get_asset_lock_key(asset_id)
        
        with lock_manager.lock(lock_key, ttl=ttl):
            return callback()
    
    @classmethod
    def with_booking_lock(cls, booking_id: str, callback: Callable, ttl: int = 15):
        """
        Execute callback with booking lock held.
        
        Args:
            booking_id: Booking UUID
            callback: Function to execute
            ttl: Lock TTL in seconds
        """
        lock_key = cls.get_booking_lock_key(booking_id)
        
        with lock_manager.lock(lock_key, ttl=ttl):
            return callback()
```

### 3.2 Seat Booking with Lock

```python
# kiboss/apps/rides/services.py

from kiboss.apps.common.locking import lock_manager, LockAcquisitionError


class SeatBookingService:
    """Service for seat booking with locking."""
    
    SEAT_LOCK_PREFIX = "lock:seat:"
    
    @classmethod
    def get_seat_lock_key(cls, ride_id: str, seat_number: int) -> str:
        return f"{cls.SEAT_LOCK_PREFIX}{ride_id}:{seat_number}"
    
    @classmethod
    def book_seat(cls, ride_id: str, seat_number: int, passenger_id: str):
        """
        Book a seat with distributed locking.
        
        This ensures no two passengers can book the same seat simultaneously.
        """
        lock_key = cls.get_seat_lock_key(ride_id, seat_number)
        
        try:
            with lock_manager.lock(lock_key, ttl=30):
                # Verify seat is available
                seat_available = cls._check_seat_available(ride_id, seat_number)
                if not seat_available:
                    raise SeatNotAvailableError(
                        f"Seat {seat_number} on ride {ride_id} is not available"
                    )
                
                # Create seat booking
                booking = cls._create_seat_booking(
                    ride_id, seat_number, passenger_id
                )
                
                return booking
                
        except LockAcquisitionError:
            raise SeatLockError(
                "Unable to reserve seat. Please try again."
            )
    
    @classmethod
    def _check_seat_available(cls, ride_id: str, seat_number: int) -> bool:
        """Check if seat is available (within locked transaction)."""
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        
        return not SeatBooking.objects.filter(
            ride_id=ride_id,
            seat_number=seat_number,
            status__in=[
                SeatBookingStatus.RESERVED,
                SeatBookingStatus.CONFIRMED
            ]
        ).exists()
    
    @classmethod
    def _create_seat_booking(cls, ride_id: str, seat_number: int, passenger_id: str):
        """Create seat booking (caller must hold lock)."""
        from kiboss.apps.rides.models import SeatBooking, SeatBookingStatus
        from django.db import transaction
        
        with transaction.atomic():
            booking = SeatBooking.objects.create(
                ride_id=ride_id,
                passenger_id=passenger_id,
                seat_number=seat_number,
                status=SeatBookingStatus.RESERVED
            )
            
            # Update ride seat count
            from kiboss.apps.rides.models import Ride
            ride = Ride.objects.select_for_update().get(id=ride_id)
            ride.confirmed_seats += 1
            ride.save(update_fields=['confirmed_seats', 'updated_at'])
            
            return booking


class SeatNotAvailableError(Exception):
    pass


class SeatLockError(Exception):
    pass
```

---

## 4. Rate Limiting Implementation

### 4.1 Rate Limit Keys

```
# Per-action rate limits

Rate Limit Keys:
- ratelimit:anon:ip:{ip}:{action}  - Anonymous users by IP
- ratelimit:user:{user_id}:{action} - Authenticated users

Default Limits:
- API calls: 1000/hour per user
- Booking creation: 10/hour per user
- Messages: 100/hour per user
- Login attempts: 5/minute per IP
```

### 4.2 Rate Limiter

```python
# kiboss/apps/common/rate_limiting.py

import time
from django.conf import settings
from redis import Redis
from typing import Tuple, Optional


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.
    """
    
    def __init__(self):
        self.client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )
    
    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """
        Check if action is within rate limit.
        
        Args:
            key: Rate limit key
            limit: Maximum allowed actions
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Use pipeline for atomic operations
        pipe = self.client.pipeline()
        
        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set TTL on key
        pipe.expire(key, window_seconds)
        
        results = pipe.execute()
        current_count = results[1]
        
        is_allowed = current_count < limit
        remaining = max(0, limit - current_count)
        reset_time = results[2] if len(results) > 2 else current_time + window_seconds
        
        return is_allowed, remaining, reset_time
    
    def check_api_rate_limit(self, user_id: str = None, ip: str = None) -> Tuple[bool, int, int]:
        """Check API rate limit."""
        from django.conf import settings
        
        key = f"ratelimit:user:{user_id}" if user_id else f"ratelimit:anon:ip:{ip}"
        limit = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].get('user', '1000/hour')
        
        # Parse rate limit (format: 1000/hour)
        count, period = limit.split('/')
        window_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 3600)
        
        return self.check_rate_limit(key, int(count), window_seconds)
    
    def check_booking_rate_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Check booking creation rate limit."""
        return self.check_rate_limit(
            key=f"ratelimit:user:{user_id}:booking",
            limit=10,
            window_seconds=3600  # 10 bookings per hour
        )
    
    def check_messaging_rate_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Check messaging rate limit."""
        return self.check_rate_limit(
            key=f"ratelimit:user:{user_id}:message",
            limit=100,
            window_seconds=3600  # 100 messages per hour
        )
    
    def check_login_rate_limit(self, ip: str) -> Tuple[bool, int, int]:
        """Check login attempt rate limit."""
        return self.check_rate_limit(
            key=f"ratelimit:anon:ip:{ip}:login",
            limit=5,
            window_seconds=60  # 5 login attempts per minute
        )


# Global rate limiter
rate_limiter = RateLimiter()
```

---

## 5. Caching Strategy

### 5.1 Cache Keys

```
Cache Key Patterns:
- asset:{asset_id}           - Asset details
- asset:list:{filters}       - Asset list with filters
- booking:{booking_id}        - Booking details
- ride:{ride_id}              - Ride details
- ride:seats:{ride_id}        - Seat availability
- user:{user_id}:profile      - User profile
- user:{user_id}:trust        - Trust score
```

### 5.2 Cache Implementation

```python
# kiboss/apps/common/caching.py

import json
from typing import Optional, Any
from django.core.cache import cache
from django.conf import settings


class KibossCache:
    """
    KIBOSS caching layer with Redis backend.
    """
    
    DEFAULT_TIMEOUT = 300  # 5 minutes
    
    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Get value from cache."""
        value = cache.get(key)
        if value and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
    
    @classmethod
    def set(cls, key: str, value: Any, timeout: int = None) -> None:
        """Set value in cache."""
        if timeout is None:
            timeout = cls.DEFAULT_TIMEOUT
        
        # Serialize complex types
        if not isinstance(value, (str, int, float, bool, type(None))):
            value = json.dumps(value)
        
        cache.set(key, value, timeout)
    
    @classmethod
    def delete(cls, key: str) -> None:
        """Delete key from cache."""
        cache.delete(key)
    
    @classmethod
    def delete_pattern(cls, pattern: str) -> None:
        """Delete all keys matching pattern."""
        # Use Django's cache iterface with pattern
        # Note: This requires Redis cache backend with scan support
        keys = cache.keys(pattern)
        for key in keys:
            cache.delete(key)
    
    # Asset caching
    @classmethod
    def get_asset(cls, asset_id: str) -> Optional[dict]:
        return cls.get(f"asset:{asset_id}")
    
    @classmethod
    def set_asset(cls, asset_id: str, asset_data: dict, timeout: int = 300) -> None:
        cls.set(f"asset:{asset_id}", asset_data, timeout)
    
    @classmethod
    def invalidate_asset(cls, asset_id: str) -> None:
        cls.delete(f"asset:{asset_id}")
    
    # Booking caching
    @classmethod
    def get_booking(cls, booking_id: str) -> Optional[dict]:
        return cls.get(f"booking:{booking_id}")
    
    @classmethod
    def set_booking(cls, booking_id: str, booking_data: dict) -> None:
        cls.set(f"booking:{booking_id}", booking_data, 60)  # Short TTL for bookings
    
    @classmethod
    def invalidate_booking(cls, booking_id: str) -> None:
        cls.delete(f"booking:{booking_id}")
    
    # Seat availability caching
    @classmethod
    def get_seat_availability(cls, ride_id: str) -> Optional[dict]:
        return cls.get(f"ride:seats:{ride_id}")
    
    @classmethod
    def set_seat_availability(cls, ride_id: str, seat_data: dict, timeout: int = 30) -> None:
        cls.set(f"ride:seats:{ride_id}", seat_data, timeout)


# Global cache instance
kiboss_cache = KibossCache()
```

---

## 6. Graceful Fallback

### 6.1 Redis Failure Handling

```python
# kiboss/apps/common/redis_fallback.py

import logging
from django.conf import settings
from typing import Optional, Callable
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class RedisFallbackManager:
    """
    Manages graceful fallback when Redis is unavailable.
    """
    
    def __init__(self):
        self.redis_available = True
        self.fallback_mode = False
    
    def check_redis_status(self) -> bool:
        """Check if Redis is available."""
        try:
            from kiboss.apps.common.locking import lock_manager
            lock_manager.client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            self.redis_available = False
            return False
    
    @contextmanager
    def with_redis_fallback(self, fallback_enabled: bool = True):
        """
        Context manager that provides fallback when Redis is down.
        
        Usage:
            with fallback_manager.with_redis_fallback():
                # Redis operations here
                ...
        """
        original_mode = self.fallback_mode
        
        try:
            if not self.check_redis_status() and fallback_enabled:
                self.fallback_mode = True
                logger.warning("Operating in Redis fallback mode (locks disabled)")
            
            yield
        finally:
            self.fallback_mode = original_mode
    
    def acquire_lock_fallback(self, lock_key: str) -> str:
        """
        Fallback lock acquisition when Redis is down.
        
        Uses database-based locking as backup.
        """
        from kiboss.apps.bookings.models import BookingLock
        from django.utils import timezone
        from datetime import timedelta
        
        # Create database lock record
        lock = BookingLock.objects.create(
            lock_type='FALLBACK',
            resource_type='fallback',
            resource_id=lock_key,
            owner_id='fallback',
            owner_process='fallback',
            expires_at=timezone.now() + timedelta(seconds=30)
        )
        
        return str(lock.id)
    
    def release_lock_fallback(self, lock_id: str) -> None:
        """Release fallback lock."""
        try:
            BookingLock.objects.filter(id=lock_id).delete()
        except Exception as e:
            logger.error(f"Failed to release fallback lock: {e}")


# Global fallback manager
redis_fallback = RedisFallbackManager()
```

---

## 7. Lock Monitoring

### 7.1 Lock Statistics

```python
# kiboss/apps/common/monitoring.py

from kiboss.apps.common.locking import lock_manager


class LockMonitor:
    """Monitor lock statistics and health."""
    
    @classmethod
    def get_active_locks(cls) -> list:
        """Get all currently held locks."""
        return list(lock_manager.locks.keys())
    
    @classmethod
    def get_lock_info(cls, lock_key: str) -> dict:
        """Get information about a specific lock."""
        owner = lock_manager.get_lock_owner(lock_key)
        is_locked = lock_manager.is_locked(lock_key)
        
        return {
            'key': lock_key,
            'is_locked': is_locked,
            'owner': owner,
            'ttl': lock_manager.client.ttl(lock_key) if is_locked else None
        }
    
    @classmethod
    def get_redis_stats(cls) -> dict:
        """Get Redis server statistics."""
        info = lock_manager.client.info('stats')
        memory = lock_manager.client.info('memory')
        
        return {
            'connected_clients': info.get('connected_clients'),
            'total_connections_received': info.get('total_connections_received'),
            'total_commands_processed': info.get('total_commands_processed'),
            'keyspace_hits': info.get('keyspace_hits'),
            'keyspace_misses': info.get('keyspace_misses'),
            'used_memory_human': memory.get('used_memory_human'),
            'used_memory_peak_human': memory.get('used_memory_peak_human')
        }
    
    @classmethod
    def check_health(cls) -> dict:
        """Check overall lock system health."""
        try:
            redis_ok = lock_manager.client.ping()
            active_locks = len(cls.get_active_locks())
            
            return {
                'status': 'healthy' if redis_ok else 'degraded',
                'redis_available': redis_ok,
                'active_locks': active_locks,
                'timestamp': str(datetime.now())
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': str(datetime.now())
            }


from datetime import datetime
```

---

## 8. Security Considerations

### 8.1 Lock Security

1. **Lock Token**: Each lock is associated with a unique token to prevent accidental release
2. **Atomic Release**: Lua script ensures only the lock owner can release
3. **TTL Expiration**: Locks automatically expire to prevent deadlocks
4. **Audit Logging**: Lock acquisition/release is logged for security

### 8.2 Rate Limit Security

1. **IP-based Limits**: Anonymouse users are rate-limited by IP
2. **User-based Limits**: Authenticated users have higher limits
3. **Strict Enforcement**: Over-limit requests return 429 (Too Many Requests)
4. **Monitoring**: Suspicious rate limit patterns are logged

### 8.3 Cache Security

1. **TTL Limits**: Cached data has appropriate TTLs
2. **Sensitive Data**: User passwords, tokens are never cached
3. **Invalidation**: Automatic invalidation on data changes
4. **Encryption**: Redis connection uses password authentication
