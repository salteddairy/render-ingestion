"""
Idempotency Middleware for Render Ingestion Service
Prevents duplicate processing of requests with same idempotency key

Protocol:
1. Client provides X-Idempotency-Key header (optional)
2. If key exists in cache and not expired, return cached response
3. If key is new, process request and cache response
4. Keys expire after 24 hours

Created: 2026-01-31
Author: Distributed Systems Reliability Engineer
"""

import hashlib
import json
import logging
from functools import wraps
from typing import Callable, Optional, Tuple, Any
from flask import Request, jsonify
import psycopg2
from psycopg2.extras import Json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IdempotencyMiddleware:
    """
    Middleware for handling idempotency keys in API requests.

    Usage:
        middleware = IdempotencyMiddleware(get_db_connection)

        @app.route('/api/ingest', methods=['POST'])
        @middleware.check_idempotency
        def ingest_data():
            # Your handler code
            pass
    """

    def __init__(self, db_connection_func: Callable):
        """
        Initialize idempotency middleware.

        Args:
            db_connection_func: Function that returns database connection
        """
        self.get_db_connection = db_connection_func
        logger.info("Idempotency middleware initialized")

    def _hash_request(self, data: dict) -> str:
        """
        Generate SHA-256 hash of request data.

        Args:
            data: Request data dictionary

        Returns:
            Hexadecimal hash string
        """
        # Normalize JSON for consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _get_cached_response(self, idempotency_key: str) -> Optional[dict]:
        """
        Check if idempotency key exists and return cached response.

        Args:
            idempotency_key: Unique idempotency key

        Returns:
            Cached response dict if exists and not expired, None otherwise
        """
        conn = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Query for non-expired idempotency key
            cursor.execute("""
                SELECT response, status, response_code, created_at
                FROM idempotency_keys
                WHERE key = %s
                  AND expires_at > NOW()
                ORDER BY created_at DESC
                LIMIT 1
            """, (idempotency_key,))

            result = cursor.fetchone()

            if result:
                response, status, response_code, created_at = result
                logger.info(f"Idempotency cache hit for key: {idempotency_key} (created: {created_at})")
                return {
                    'response': response,
                    'status': status,
                    'response_code': response_code
                }

            return None

        except Exception as e:
            logger.error(f"Error checking idempotency cache: {str(e)}")
            # On error, allow request to proceed (fail open)
            return None

        finally:
            if conn is not None:
                conn.close()

    def _store_response(
        self,
        idempotency_key: str,
        endpoint: str,
        request_data: dict,
        response_data: dict,
        status_code: int
    ) -> None:
        """
        Store idempotency key and response in database.

        Args:
            idempotency_key: Unique idempotency key
            endpoint: API endpoint path
            request_data: Original request data
            response_data: Response data to cache
            status_code: HTTP status code
        """
        conn = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            request_hash = self._hash_request(request_data)

            # Insert with conflict handling - if key already exists, don't overwrite
            # This prevents race conditions where two requests with same key arrive simultaneously
            cursor.execute("""
                INSERT INTO idempotency_keys (
                    key, endpoint, request_hash, response, status, response_code, expires_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, NOW() + INTERVAL '24 hours'
                )
                ON CONFLICT (key) DO NOTHING
            """, (
                idempotency_key,
                endpoint,
                request_hash,
                Json(response_data),
                'completed' if 200 <= status_code < 300 else 'failed',
                status_code
            ))

            conn.commit()
            logger.debug(f"Stored idempotency key: {idempotency_key}")

        except Exception as e:
            logger.error(f"Error storing idempotency key: {str(e)}")
            if conn:
                conn.rollback()

        finally:
            if conn is not None:
                conn.close()

    def check_idempotency(self, func: Callable) -> Callable:
        """
        Decorator to check idempotency before processing request.

        Usage:
            @middleware.check_idempotency
            def my_handler():
                return jsonify({"success": True}), 200
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request

            # Get idempotency key from header
            idempotency_key = request.headers.get('X-Idempotency-Key')

            # If no idempotency key, proceed with normal processing
            if not idempotency_key:
                logger.debug("No idempotency key provided, processing request normally")
                return func(*args, **kwargs)

            # Validate idempotency key format (should be non-empty string)
            if not isinstance(idempotency_key, str) or len(idempotency_key.strip()) == 0:
                logger.warning("Invalid idempotency key format")
                return jsonify({
                    "success": False,
                    "error": "Invalid idempotency key format"
                }), 400

            idempotency_key = idempotency_key.strip()

            # Check if key exists in cache
            cached = self._get_cached_response(idempotency_key)
            if cached:
                # Return cached response
                logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
                return jsonify(cached['response']), cached['response_code']

            # Key doesn't exist, process request
            logger.info(f"Processing new request with idempotency key: {idempotency_key}")

            try:
                # Execute the original function
                response = func(*args, **kwargs)

                # Extract response data and status code
                if isinstance(response, tuple):
                    response_data, status_code = response[0], response[1]
                    # If response_data is a Flask response object, get JSON
                    if hasattr(response_data, 'get_json'):
                        response_data = response_data.get_json()
                    elif hasattr(response_data, 'json'):
                        response_data = response_data.json
                else:
                    response_data = response
                    status_code = 200

                # Get JSON response data
                if hasattr(response_data, 'get_json'):
                    json_response = response_data.get_json()
                elif isinstance(response_data, dict):
                    json_response = response_data
                else:
                    json_response = {"data": str(response_data)}

                # Store the response for future requests with same key
                endpoint = request.path
                request_data = request.get_json() or {}

                self._store_response(
                    idempotency_key=idempotency_key,
                    endpoint=endpoint,
                    request_data=request_data,
                    response_data=json_response,
                    status_code=status_code
                )

                return response

            except Exception as e:
                logger.error(f"Error in idempotency wrapper: {str(e)}")
                # On error, re-raise to be handled by error handlers
                raise

        return wrapper


def cleanup_expired_keys(db_connection_func: Callable, days_old: int = 1) -> int:
    """
    Cleanup expired idempotency keys older than specified days.

    Args:
        db_connection_func: Function that returns database connection
        days_old: Delete keys older than this many days (default: 1)

    Returns:
        Number of keys deleted
    """
    conn = None
    try:
        conn = db_connection_func()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM idempotency_keys
            WHERE expires_at < NOW() - INTERVAL '%s days'
        """, (days_old,))

        deleted_count = cursor.rowcount
        conn.commit()

        logger.info(f"Cleaned up {deleted_count} expired idempotency keys")
        return deleted_count

    except Exception as e:
        logger.error(f"Error cleaning up expired keys: {str(e)}")
        if conn:
            conn.rollback()
        return 0

    finally:
        if conn is not None:
            conn.close()


def get_idempotency_stats(db_connection_func: Callable) -> dict:
    """
    Get statistics about idempotency keys.

    Args:
        db_connection_func: Function that returns database connection

    Returns:
        Dictionary with statistics
    """
    conn = None
    try:
        conn = db_connection_func()
        cursor = conn.cursor()

        # Get total keys, active keys, failed requests
        cursor.execute("""
            SELECT
                COUNT(*) as total_keys,
                COUNT(*) FILTER (WHERE expires_at > NOW()) as active_keys,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM idempotency_keys
        """)

        row = cursor.fetchone()
        if row:
            return {
                'total_keys': row[0],
                'active_keys': row[1],
                'completed': row[2],
                'failed': row[3]
            }

        return {}

    except Exception as e:
        logger.error(f"Error getting idempotency stats: {str(e)}")
        return {}

    finally:
        if conn is not None:
            conn.close()
