# test_cache.py

import pytest
from redis_cache import RedisCache, cached
from unittest.mock import Mock, patch

@patch('redis.Redis') # This replaces the real Redis client with a mock for testing
def test_cache_set_get(mock_redis):
    """Tests that we can set a value in the cache and then get it back."""
    mock_client = Mock()
    mock_redis.return_value = mock_client
    
    # Simulate that the key doesn't exist yet
    mock_client.get.return_value = None
    
    cache = RedisCache()
    # Set a value
    cache.set('my_key', {'data': 'my_value'}, 3600)
    # Try to get it back
    cache.get('my_key')
    
    # Assert that the `setex` and `get` methods were called on the mock client
    mock_client.setex.assert_called_once()
    mock_client.get.assert_called_with('my_key')

@patch('redis_cache.cache') # This time, we patch the 'cache' instance directly
def test_cached_decorator_works(mock_cache):
    """Tests that the @cached decorator prevents a function from running twice."""
    # Simulate a cache miss on the first call
    mock_cache.get.return_value = None
    mock_cache.set.return_value = True
    
    # A global counter to track how many times the function actually runs
    call_count = 0
    
    @cached(key_pattern='my_test_function')
    def my_expensive_function():
        nonlocal call_count
        call_count += 1
        return "the result"

    # --- The Test ---
    # First call: should miss cache, run the function, and set the cache.
    result1 = my_expensive_function() 
    
    # Now, simulate a cache hit for the second call
    mock_cache.get.return_value = "the result" 
    
    # Second call: should hit the cache and return the cached value without running the function.
    result2 = my_expensive_function()
    
    # --- Assertions ---
    # The function should have only been executed ONCE.
    assert call_count == 1
    # Both results should be the same.
    assert result1 == result2
    # The cache's `set` method should have only been called ONCE.
    mock_cache.set.assert_called_once()
