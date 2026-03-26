import os
import base64
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('kiboss')

# Keys for Redis
CHECKMARK_VERIFIED_KEY = 'asset:checkmark:verified'
CHECKMARK_BUSINESS_KEY = 'asset:checkmark:business'

# Map filenames to Redis keys
# plus.png is used for standard verification (Plus/Premium/Gold/Basic)
# business.png is used for Business tier verification
CHECKMARK_MAPPING = {
    'plus.png': CHECKMARK_VERIFIED_KEY,
    'business.png': CHECKMARK_BUSINESS_KEY,
}

def warm_checkmark_cache():
    """
    Load checkmark images from disk into Redis as Base64 strings.
    This is called on startup to ensures "hot-load" availability.
    """
    checkmarks_dir = os.path.join(settings.MEDIA_ROOT, 'checkmarks')
    
    if not os.path.exists(checkmarks_dir):
        logger.warning(f"Checkmarks directory not found: {checkmarks_dir}")
        return False

    success = True
    for filename, redis_key in CHECKMARK_MAPPING.items():
        file_path = os.path.join(checkmarks_dir, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as f:
                    # Encode to Base64
                    encoded_string = base64.b64encode(f.read()).decode('utf-8')
                    # Prepend data URI prefix for direct <img> src injection
                    data_uri = f"data:image/png;base64,{encoded_string}"
                    # Store in Redis indefinitely (timeout=None)
                    cache.set(redis_key, data_uri, timeout=None)
                    logger.info(f"Successfully cached checkmark: {filename} -> {redis_key}")
            except Exception as e:
                logger.error(f"Failed to cache checkmark {filename}: {e}")
                success = False
        else:
            logger.warning(f"Checkmark file not found during warming: {file_path}")
            success = False
    return success

def get_checkmark_data(tier):
    """
    Retrieve checkmark Base64 data from Redis based on user tier.
    Automatically warms cache if data is missing.
    """
    if not tier or tier == 'none':
        return None

    if tier == 'business':
        key = CHECKMARK_BUSINESS_KEY
    else:
        # standard verified (basic, premium, gold, plus)
        key = CHECKMARK_VERIFIED_KEY

    data = cache.get(key)
    if not data:
        # Cache miss - perform hot-load
        logger.info(f"Cache miss for {key}, performing hot-load...")
        warm_checkmark_cache()
        data = cache.get(key)
    
    return data
