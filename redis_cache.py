# redis_cache.py (Updated)

import redis
import pickle
import hashlib
from functools import wraps
import os
from urllib.parse import urlparse # Import urlparse

class RedisCache:
    def __init__(self):
        redis_url = os.environ.get('REDIS_URL')
        
        # Check if a full URL is provided (like from Render)
        if redis_url:
            # Parse the URL to get connection details
            url = urlparse(redis_url)
            self.redis_client = redis.Redis(
                host=url.hostname,
                port=url.port,
                password=url.password,
                ssl=url.scheme == 'rediss', # Enable SSL if scheme is 'rediss'
                decode_responses=False # Important: Set to False for pickle
            )
            print("Redis connected via URL.")
        else:
            # Fallback to individual environment variables for local development
            self.redis_client = redis.Redis(
                host=os.environ.get('REDIS_HOST', 'localhost'),
                port=int(os.environ.get('REDIS_PORT', 6379)),
                password=os.environ.get('REDIS_PASSWORD'),
                decode_responses=False # Important: Set to False for pickle
            )
            print("Redis connected via individual host/port variables.")
    
    def get(self, key):
        try:
            cached = self.redis_client.get(key)
            return pickle.loads(cached) if cached else None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def set(self, key, value, expire_seconds=3600):
        try:
            serialized = pickle.dumps(value)
            self.redis_client.setex(key, expire_seconds, serialized)
            return True
        except Exception as e:
            print(f"Redis set error: {e}")
            return False
    
    def delete(self, key):
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    def clear_pattern(self, pattern):
        try:
            # Note: decode_responses is False, so keys are bytes.
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            print(f"Redis clear pattern error: {e}")
            return False

cache = RedisCache()

def cached(key_pattern=None, expire_seconds=3600):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate cache key
            if key_pattern:
                cache_key = key_pattern
            else:
                key_parts = [f.__name__] + [str(arg) for arg in args] + [f"{k}:{v}" for k, v in kwargs.items()]
                key_string = "::".join(key_parts)
                cache_key = hashlib.md5(key_string.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                print(f"Cache HIT for key: {cache_key}")
                return cached_result
            
            print(f"Cache MISS for key: {cache_key}")
            # Execute function and cache result
            result = f(*args, **kwargs)
            cache.set(cache_key, result, expire_seconds)
            
            return result
        return decorated_function
    return decorator

def invalidate_cache(pattern):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            cache.clear_pattern(pattern)
            return result
        return decorated_function
    return decorator
