"""
Rate Limiting Middleware for Flask APIs (Standalone Version)

Limits request rate by IP address and API key to prevent abuse and DoS attacks.

Features:
- In-memory request tracking (suitable for single-instance deployments)
- Configurable limits per endpoint
- Standard rate limit headers (X-RateLimit-*)
- Support for both IP-based and API key-based limiting
- Thread-safe implementation using locks

For production with multiple instances, use Redis or database-backed storage.
"""
import time
import logging
from functools import wraps
from collections import defaultdict
from threading import Lock
from typing import Tuple, Dict, Any

from flask import request, jsonify, g

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Thread-safe rate limiter using in-memory storage.

    Tracks requests by key (IP address or API key) and enforces limits
    within a sliding time window.
    """

    def __init__(self):
        # In-memory store: {key: [timestamp1, timestamp2, ...]}
        self.requests: Dict[str, list] = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, key: str, limit: int, period: int) -> bool:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Identifier (IP address or API key)
            limit: Max requests allowed in time period
            period: Time period in seconds

        Returns:
            bool: True if request is allowed, False if limit exceeded
        """
        with self.lock:
            now = time.time()

            # Remove old requests outside time window
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if now - req_time < period
            ]

            # Check if under limit
            if len(self.requests[key]) < limit:
                self.requests[key].append(now)
                return True
            else:
                return False

    def get_request_count(self, key: str, period: int) -> int:
        """
        Get current request count for a key within the period.

        Args:
            key: Identifier (IP address or API key)
            period: Time period in seconds

        Returns:
            int: Number of requests made within the period
        """
        with self.lock:
            now = time.time()

            # Clean old requests first
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if now - req_time < period
            ]

            return len(self.requests[key])

    def get_retry_after(self, key: str, period: int) -> int:
        """
        Get seconds until next request is allowed.

        Args:
            key: Identifier (IP address or API key)
            period: Time period in seconds

        Returns:
            int: Seconds until next request allowed (0 if allowed now)
        """
        with self.lock:
            if not self.requests[key]:
                return 0

            now = time.time()
            # Find oldest request within period
            oldest_valid = None
            for req_time in self.requests[key]:
                if now - req_time < period:
                    oldest_valid = req_time
                    break

            if oldest_valid is None:
                return 0

            retry_after = int(oldest_valid + period - now)
            return max(0, retry_after)

    def get_reset_time(self, key: str, period: int) -> int:
        """
        Get Unix timestamp when rate limit window resets.

        Args:
            key: Identifier (IP address or API key)
            period: Time period in seconds

        Returns:
            int: Unix timestamp of window reset
        """
        with self.lock:
            if not self.requests[key]:
                return int(time.time() + period)

            now = time.time()
            oldest = min(self.requests[key])
            return int(oldest + period)


# Global rate limiter instance
rate_limiter = RateLimiter()


# Rate limit configurations
RATE_LIMITS = {
    'default': (100, 3600),      # 100 requests per hour (default)
    'strict': (10, 60),          # 10 requests per minute (strict)
    'medium': (1000, 3600),      # 1000 requests per hour (medium)
    'high': (10000, 3600),       # 10000 requests per hour (high)
    'health': (1000, 60),        # 1000 requests per minute (health checks)
    'write': (20, 3600),         # 20 requests per hour (write operations)
}


def rate_limit(
    limit: int = None,
    period: int = None,
    key_type: str = 'ip',
    limit_name: str = None
):
    """
    Decorator for rate limiting Flask endpoints.

    Args:
        limit: Max requests allowed (optional, uses default if not specified)
        period: Time period in seconds (optional)
        key_type: 'ip', 'api_key', or 'both' (default: 'ip')
        limit_name: Name of limit from RATE_LIMITS config (optional)

    Returns:
        Decorated function with rate limiting

    Example:
        @app.route('/api/data')
        @rate_limit(limit=100, period=3600)  # 100 requests/hour by IP
        def get_data():
            return jsonify(data)

        @app.route('/api/data/critical')
        @rate_limit(limit_name='strict')  # Use predefined limit
        def get_critical():
            return jsonify(data)

        @app.route('/api/v1/items', methods=['POST'])
        @rate_limit(limit=20, period=3600, key_type='api_key')  # By API key
        def create_item():
            return jsonify(created=True)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            nonlocal limit, period

            # Determine limit/period
            if limit_name and limit_name in RATE_LIMITS:
                limit, period = RATE_LIMITS[limit_name]
            elif limit is None:
                limit, period = RATE_LIMITS['default']

            # Determine key for rate limiting
            if key_type == 'api_key':
                # Use API key if available, fallback to IP
                key = g.get('api_key', request.remote_addr)
            elif key_type == 'both':
                # Combine IP and API key for more granular control
                api_key = g.get('api_key', 'none')
                key = f"{request.remote_addr}:{api_key}"
            else:
                # Default to IP address
                key = request.remote_addr

            # Check if allowed
            if rate_limiter.is_allowed(key, limit, period):
                # Execute the endpoint function
                response = f(*args, **kwargs)

                # Add rate limit headers to response
                if isinstance(response, tuple):
                    # Handle responses with status codes
                    response_data, status_code = response[0], response[1]
                    if hasattr(response_data, 'headers'):
                        _add_rate_limit_headers(
                            response_data.headers,
                            key,
                            limit,
                            period
                        )
                    return response
                else:
                    # Handle normal responses
                    if hasattr(response, 'headers'):
                        _add_rate_limit_headers(
                            response.headers,
                            key,
                            limit,
                            period
                        )
                    return response
            else:
                # Rate limit exceeded
                retry_after = rate_limiter.get_retry_after(key, period)
                logger.warning(
                    f"Rate limit exceeded for {key_type}={key[:20]}... "
                    f"from {request.remote_addr}"
                )

                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Try again in {retry_after} seconds.',
                    'retry_after': retry_after,
                    'limit': limit,
                    'period': period
                }), 429  # HTTP 429 Too Many Requests

        return decorated_function
    return decorator


def _add_rate_limit_headers(headers: Dict, key: str, limit: int, period: int):
    """
    Add standard rate limit headers to response.

    Headers added:
        X-RateLimit-Limit: Max requests allowed in period
        X-RateLimit-Remaining: Requests remaining in period
        X-RateLimit-Reset: Unix timestamp when limit resets

    Args:
        headers: Response headers dictionary
        key: Rate limit key (IP or API key)
        limit: Max requests allowed
        period: Time period in seconds
    """
    current_count = rate_limiter.get_request_count(key, period)
    remaining = max(0, limit - current_count)
    reset_time = rate_limiter.get_reset_time(key, period)

    headers['X-RateLimit-Limit'] = str(limit)
    headers['X-RateLimit-Remaining'] = str(remaining)
    headers['X-RateLimit-Reset'] = str(reset_time)


def get_rate_limit_status(key: str, limit: int, period: int) -> Dict[str, Any]:
    """
    Get current rate limit status for a key.

    Args:
        key: Rate limit key (IP or API key)
        limit: Max requests allowed
        period: Time period in seconds

    Returns:
        Dictionary with rate limit status:
            - limit: Max requests allowed
            - remaining: Requests remaining
            - reset: Unix timestamp when limit resets
            - current: Current request count
    """
    current = rate_limiter.get_request_count(key, period)
    remaining = max(0, limit - current)
    reset = rate_limiter.get_reset_time(key, period)

    return {
        'limit': limit,
        'remaining': remaining,
        'reset': reset,
        'current': current
    }


def clear_rate_limits(key: str = None):
    """
    Clear rate limit history for a key or all keys.

    Useful for testing or administrative resets.

    Args:
        key: Key to clear (optional, clears all if None)
    """
    with rate_limiter.lock:
        if key:
            rate_limiter.requests[key] = []
            logger.info(f"Cleared rate limits for {key[:20]}...")
        else:
            rate_limiter.requests.clear()
            logger.info("Cleared all rate limits")


def get_rate_limit_stats() -> Dict[str, Any]:
    """
    Get statistics about rate limiter usage.

    Returns:
        Dictionary with rate limit statistics:
            - total_keys: Number of unique keys being tracked
            - total_requests: Total requests tracked
            - top_keys: List of (key, request_count) tuples
    """
    with rate_limiter.lock:
        total_keys = len(rate_limiter.requests)
        total_requests = sum(len(reqs) for reqs in rate_limiter.requests.values())

        # Get top 5 keys by request count
        top_keys = sorted(
            rate_limiter.requests.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:5]

        return {
            'total_keys': total_keys,
            'total_requests': total_requests,
            'top_keys': [(k[:20], len(v)) for k, v in top_keys]
        }
