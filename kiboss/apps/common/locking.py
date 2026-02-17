"""
Redis Locking Service for KIBOSS

This module implements Redis-based distributed locking to prevent race conditions
in booking and payment operations.
"""

import redis
import uuid
import time
from typing import Optional, Callable
from contextlib import contextmanager
from django.conf import settings
from django.core.exceptions import ValidationError


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
        self._mock_locks = {}
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            self.client.ping()
        except redis.ConnectionError:
            # Fallback for when Redis is not available
            self.client = None
    
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
        if self.client is None:
            existing = self._mock_locks.get(lock_key)
            now = time.time()
            if existing and existing['expires_at'] > now:
                return None
            token = f"mock_lock_{uuid.uuid4().hex[:8]}"
            self._mock_locks[lock_key] = {'token': token, 'expires_at': now + ttl}
            return token
        
        lock_token = str(uuid.uuid4())
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Try to acquire lock atomically
                acquired = self.client.set(
                    lock_key,
                    lock_token,
                    nx=True,  # Set only if not exists
                    ex=ttl    # Expire after TTL
                )
                
                if acquired:
                    return lock_token
                
                # Exponential backoff
                retry_count += 1
                time.sleep(retry_delay * (2 ** (retry_count - 1)))
                
            except redis.RedisError:
                # Log error and continue
                break
        
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
        if self.client is None:
            lock = self._mock_locks.get(lock_key)
            if not lock or lock['token'] != lock_token:
                return False
            del self._mock_locks[lock_key]
            return True
        
        # Lua script for atomic release
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            result = self.client.eval(release_script, 1, lock_key, lock_token)
            return bool(result)
        except redis.RedisError:
            return False
    
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
        if self.client is None:
            lock = self._mock_locks.get(lock_key)
            if not lock or lock['token'] != lock_token:
                return False
            lock['expires_at'] = time.time() + ttl
            return True
        
        extend_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        try:
            result = self.client.eval(extend_script, 1, lock_key, lock_token, ttl)
            return bool(result)
        except redis.RedisError:
            return False
    
    def is_locked(self, lock_key: str) -> bool:
        """Check if a lock exists."""
        if self.client is None:
            lock = self._mock_locks.get(lock_key)
            if not lock:
                return False
            if lock['expires_at'] <= time.time():
                del self._mock_locks[lock_key]
                return False
            return True
        
        try:
            return self.client.exists(lock_key) > 0
        except redis.RedisError:
            return False
    
    def get_lock_owner(self, lock_key: str) -> Optional[str]:
        """Get the owner token of a lock."""
        if self.client is None:
            lock = self._mock_locks.get(lock_key)
            if not lock or lock['expires_at'] <= time.time():
                return None
            return lock['token']
        
        try:
            return self.client.get(lock_key)
        except redis.RedisError:
            return None
    
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
        
        Raises:
            LockAcquisitionError: If lock cannot be acquired
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


class RedisRateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.
    """
    
    def __init__(self):
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
        except redis.ConnectionError:
            self.client = None
    
    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Check if action is within rate limit.
        
        Args:
            key: Rate limit key
            limit: Maximum allowed actions
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        if self.client is None:
            # No Redis - allow all requests
            return True, limit, int(time.time()) + window_seconds
        
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        try:
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
            reset_time = current_time + window_seconds
            
            return is_allowed, remaining, reset_time
            
        except redis.RedisError:
            # On error, allow the request
            return True, limit, int(time.time()) + window_seconds
    
    def check_booking_rate_limit(self, user_id: str) -> tuple[bool, int, int]:
        """Check booking creation rate limit (10/hour)."""
        return self.check_rate_limit(
            key=f"ratelimit:user:{user_id}:booking",
            limit=10,
            window_seconds=3600
        )
    
    def check_messaging_rate_limit(self, user_id: str) -> tuple[bool, int, int]:
        """Check messaging rate limit (100/hour)."""
        return self.check_rate_limit(
            key=f"ratelimit:user:{user_id}:message",
            limit=100,
            window_seconds=3600
        )
    
    def check_api_rate_limit(self, user_id: str = None, ip: str = None) -> tuple[bool, int, int]:
        """Check API rate limit (1000/hour per user, 100/hour per IP)."""
        from django.conf import settings
        
        if user_id:
            key = f"ratelimit:user:{user_id}"
            limit = 1000
        else:
            key = f"ratelimit:anon:ip:{ip}"
            limit = 100
        
        return self.check_rate_limit(
            key=key,
            limit=limit,
            window_seconds=3600
        )
    
    def check_login_rate_limit(self, ip: str) -> tuple[bool, int, int]:
        """Check login rate limit (5/minute per IP)."""
        return self.check_rate_limit(
            key=f"ratelimit:anon:ip:{ip}:login",
            limit=5,
            window_seconds=60
        )


# Global instances (lazily initialized)
_lock_manager = None
_rate_limiter = None

def get_lock_manager():
    """Get the RedisLockManager instance, creating it if necessary."""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = RedisLockManager()
    return _lock_manager

def get_rate_limiter():
    """Get the RedisRateLimiter instance, creating it if necessary."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RedisRateLimiter()
    return _rate_limiter


# Backward-compatible aliases used by legacy code/tests.
lock_manager = get_lock_manager()
rate_limiter = get_rate_limiter()
