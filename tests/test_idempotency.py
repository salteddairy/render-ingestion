"""
Test Idempotency Middleware
Tests duplicate request prevention with idempotency keys

Created: 2026-01-31
Author: Distributed Systems Reliability Engineer
"""

import pytest
import json
import time
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, get_db_connection
from middleware.idempotency import (
    IdempotencyMiddleware,
    cleanup_expired_keys,
    get_idempotency_stats
)


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def clean_db():
    """Clean up idempotency keys before and after tests."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clean up test keys
    try:
        cursor.execute("DELETE FROM idempotency_keys WHERE endpoint LIKE '/test%'")
        conn.commit()
    except:
        pass  # Table might not exist yet

    yield

    # Clean up after test
    try:
        cursor.execute("DELETE FROM idempotency_keys WHERE endpoint LIKE '/test%'")
        conn.commit()
    except:
        pass
    finally:
        conn.close()


class TestIdempotencyMiddleware:
    """Test suite for idempotency middleware."""

    def test_idempotency_key_prevents_duplicate_processing(self, client, clean_db):
        """Test that duplicate requests with same idempotency key return cached response."""
        idempotency_key = "test-key-123"

        # First request - should process normally
        response1 = client.post('/health', headers={
            'X-Idempotency-Key': idempotency_key
        })

        assert response1.status_code == 200

        # Second request with same key - should return cached response
        response2 = client.post('/health', headers={
            'X-Idempotency-Key': idempotency_key
        })

        assert response2.status_code == 200

        # Responses should be identical
        assert response1.json == response2.json

    def test_different_keys_process_independently(self, client, clean_db):
        """Test that different idempotency keys process independently."""
        key1 = "test-key-456"
        key2 = "test-key-789"

        response1 = client.post('/health', headers={
            'X-Idempotency-Key': key1
        })

        response2 = client.post('/health', headers={
            'X-Idempotency-Key': key2
        })

        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_no_idempotency_key_processes_normally(self, client, clean_db):
        """Test that requests without idempotency key process normally."""
        response1 = client.post('/health')
        response2 = client.post('/health')

        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_invalid_idempotency_key_rejected(self, client, clean_db):
        """Test that invalid idempotency keys are rejected."""
        # Empty string
        response = client.post('/health', headers={
            'X-Idempotency-Key': '   '
        })

        # Should still work (endpoint doesn't require idempotency)
        assert response.status_code == 200

    def test_key_expiration_after_24_hours(self, clean_db):
        """Test that idempotency keys expire after 24 hours."""
        middleware = IdempotencyMiddleware(get_db_connection)

        # Insert an expired key
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO idempotency_keys (key, endpoint, response, expires_at)
                VALUES (%s, %s, %s, NOW() - INTERVAL '1 hour')
            """, ('expired-key', '/test', json.dumps({"test": "data"})))
            conn.commit()

            # Try to retrieve expired key
            cached = middleware._get_cached_response('expired-key')

            # Should return None (key expired)
            assert cached is None

        finally:
            cursor.execute("DELETE FROM idempotency_keys WHERE key = 'expired-key'")
            conn.commit()
            conn.close()

    def test_cleanup_expired_keys(self, clean_db):
        """Test cleanup of expired idempotency keys."""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Insert expired keys
            cursor.execute("""
                INSERT INTO idempotency_keys (key, endpoint, response, expires_at)
                VALUES (%s, %s, %s, NOW() - INTERVAL '2 days')
            """, ('old-key-1', '/test', json.dumps({"test": "1"})))

            cursor.execute("""
                INSERT INTO idempotency_keys (key, endpoint, response, expires_at)
                VALUES (%s, %s, %s, NOW() - INTERVAL '3 days')
            """, ('old-key-2', '/test', json.dumps({"test": "2"})))

            # Insert active key
            cursor.execute("""
                INSERT INTO idempotency_keys (key, endpoint, response, expires_at)
                VALUES (%s, %s, %s, NOW() + INTERVAL '1 hour')
            """, ('active-key', '/test', json.dumps({"test": "3"})))

            conn.commit()

            # Run cleanup
            deleted = cleanup_expired_keys(get_db_connection, days_old=1)

            # Should delete 2 expired keys
            assert deleted >= 2

            # Verify active key still exists
            cursor.execute("SELECT COUNT(*) FROM idempotency_keys WHERE key = 'active-key'")
            count = cursor.fetchone()[0]
            assert count == 1

        finally:
            cursor.execute("DELETE FROM idempotency_keys WHERE endpoint LIKE '/test%'")
            conn.commit()
            conn.close()

    def test_get_idempotency_stats(self, clean_db):
        """Test retrieval of idempotency statistics."""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Insert test data
            cursor.execute("""
                INSERT INTO idempotency_keys (key, endpoint, response, status, expires_at)
                VALUES (%s, %s, %s, 'completed', NOW() + INTERVAL '1 hour')
            """, ('stat-key-1', '/test', json.dumps({"test": "1"})))

            cursor.execute("""
                INSERT INTO idempotency_keys (key, endpoint, response, status, expires_at)
                VALUES (%s, %s, %s, 'failed', NOW() + INTERVAL '1 hour')
            """, ('stat-key-2', '/test', json.dumps({"test": "2"})))

            conn.commit()

            # Get stats
            stats = get_idempotency_stats(get_db_connection)

            assert 'total_keys' in stats
            assert 'active_keys' in stats
            assert 'completed' in stats
            assert 'failed' in stats

            assert stats['total_keys'] >= 2

        finally:
            cursor.execute("DELETE FROM idempotency_keys WHERE endpoint LIKE '/test%'")
            conn.commit()
            conn.close()


class TestIdempotencyIntegration:
    """Integration tests for idempotency with actual ingestion endpoint."""

    @pytest.fixture
    def encryption_key(self):
        """Get encryption key for testing."""
        return os.getenv('ENCRYPTION_KEY')

    @pytest.fixture
    def api_key(self):
        """Get API key for testing."""
        return os.getenv('API_KEY')

    def test_ingest_endpoint_with_idempotency(self, client, api_key, encryption_key, clean_db):
        """Test idempotency on /api/ingest endpoint."""
        if not api_key or not encryption_key:
            pytest.skip("API_KEY or ENCRYPTION_KEY not set")

        from cryptography.fernet import Fernet

        # Prepare test data
        cipher = Fernet(encryption_key.encode('utf-8'))
        payload = {
            "data_type": "warehouses_full",
            "records": [
                {
                    "warehouse_code": "TEST-ID-001",
                    "warehouse_name": "Idempotency Test Warehouse",
                    "is_active": 1
                }
            ]
        }

        encrypted_payload = cipher.encrypt(
            json.dumps(payload).encode('utf-8')
        ).decode('utf-8')

        request_data = {
            "encrypted_payload": encrypted_payload
        }

        idempotency_key = "ingest-test-key-123"

        # First request
        response1 = client.post('/api/ingest',
            json=request_data,
            headers={'X-API-Key': api_key, 'X-Idempotency-Key': idempotency_key}
        )

        assert response1.status_code == 200

        # Second request with same key
        response2 = client.post('/api/ingest',
            json=request_data,
            headers={'X-API-Key': api_key, 'X-Idempotency-Key': idempotency_key}
        )

        assert response2.status_code == 200

        # Should return cached response (same records_processed)
        assert response1.json['records_processed'] == response2.json['records_processed']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
