"""
Load Tests for Render Ingestion Service
Tests performance under high load and stress conditions
"""

import pytest
import json
import os
import time
import threading
import statistics
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from unittest.mock import patch, MagicMock

# Set environment variables before importing app
os.environ["API_KEY"] = "test_api_key_1234567890"
os.environ["ENCRYPTION_KEY"] = "test_encryption_key_32_characters_long!"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["LOG_LEVEL"] = "ERROR"

from app import app, cipher


class TestConcurrentRequests:
    """Test concurrent request handling."""

    @patch('supabase_client.get_supabase_client')
    def test_100_concurrent_requests(self, mock_db_client):
        """Test service can handle 100 concurrent requests."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        results = []
        errors = []

        def make_request(request_id):
            try:
                with app.test_client() as client:
                    payload = {
                        "data_type": "warehouses_full",
                        "records": [
                            {
                                "warehouse_code": f"WH{request_id:04d}",
                                "warehouse_name": f"Warehouse {request_id}",
                                "is_active": 1
                            }
                        ]
                    }

                    start = time.time()
                    encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

                    response = client.post(
                        '/api/ingest',
                        headers={"X-API-Key": os.getenv("API_KEY")},
                        json={"encrypted_payload": encrypted}
                    )

                    elapsed = time.time() - start
                    results.append({
                        'request_id': request_id,
                        'status': response.status_code,
                        'time': elapsed
                    })
            except Exception as e:
                errors.append(str(e))

        # Create 100 threads
        threads = []
        for i in range(100):
            t = threading.Thread(target=make_request, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Verify results
        assert len(results) == 100, f"Expected 100 results, got {len(results)}"
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Check status codes
        success_count = sum(1 for r in results if r['status'] == 200)
        assert success_count == 100, f"Expected 100 successful requests, got {success_count}"

        # Check response times
        response_times = [r['time'] for r in results]
        avg_time = statistics.mean(response_times)
        max_time = max(response_times)

        print(f"\n--- Concurrent Requests Performance ---")
        print(f"Total requests: {len(results)}")
        print(f"Average response time: {avg_time:.3f}s")
        print(f"Max response time: {max_time:.3f}s")
        print(f"Min response time: {min(response_times):.3f}s")

        # Performance assertions
        assert avg_time < 2.0, f"Average response time too high: {avg_time:.3f}s"

    @patch('supabase_client.get_supabase_client')
    def test_concurrent_different_data_types(self, mock_db_client):
        """Test concurrent requests with different data types."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        data_types = [
            "warehouses_full",
            "vendors_full",
            "items_full",
            "inventory_current_full",
            "sales_orders_incremental",
            "purchase_orders_incremental",
            "costs_incremental",
            "pricing_full"
        ]

        results = []

        def make_request(data_type):
            with app.test_client() as client:
                if data_type == "warehouses_full":
                    record = {"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1}
                elif data_type == "vendors_full":
                    record = {"vendor_code": "V001", "vendor_name": "Acme", "is_active": 1}
                elif data_type == "items_full":
                    record = {"item_code": "A001", "item_name": "Widget", "item_group": "Finished", "is_active": 1}
                elif data_type == "inventory_current_full":
                    record = {"item_code": "A001", "warehouse_code": "01", "quantity": 100.0, "unit_price": 25.50}
                elif data_type == "sales_orders_incremental":
                    record = {"order_id": 12345, "order_date": "2025-01-27T00:00:00", "customer_code": "C001", "item_code": "A001", "quantity": 10, "unit_price": 25.50, "line_total": 255.00}
                elif data_type == "purchase_orders_incremental":
                    record = {"order_id": 67890, "order_date": "2025-01-27T00:00:00", "vendor_code": "V001", "item_code": "A001", "quantity": 100, "unit_price": 15.00, "line_total": 1500.00}
                elif data_type == "costs_incremental":
                    record = {"item_code": "A001", "avg_cost": 18.50, "last_cost": 19.00, "cost_date": "2025-01-27"}
                else:  # pricing_full
                    record = {"item_code": "A001", "price_list": "1", "price": 25.50, "currency": "USD"}

                payload = {"data_type": data_type, "records": [record]}
                encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

                start = time.time()
                response = client.post(
                    '/api/ingest',
                    headers={"X-API-Key": os.getenv("API_KEY")},
                    json={"encrypted_payload": encrypted}
                )
                elapsed = time.time() - start

                results.append({
                    'data_type': data_type,
                    'status': response.status_code,
                    'time': elapsed
                })

        # Send concurrent requests
        threads = []
        for data_type in data_types:
            t = threading.Thread(target=make_request, args=(data_type,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify all succeeded
        assert len(results) == 8
        success_count = sum(1 for r in results if r['status'] == 200)
        assert success_count == 8


class TestLargePayloads:
    """Test handling of large payloads."""

    @patch('supabase_client.get_supabase_client')
    def test_10000_records(self, mock_db_client):
        """Test ingesting 10,000 records in single request."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            # Create 10,000 records
            records = [
                {
                    "warehouse_code": f"WH{i:06d}",
                    "warehouse_name": f"Warehouse {i}",
                    "is_active": 1
                }
                for i in range(10000)
            ]

            payload = {
                "data_type": "warehouses_full",
                "records": records
            }

            start = time.time()
            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            elapsed = time.time() - start

            print(f"\n--- Large Payload Performance ---")
            print(f"Records: 10,000")
            print(f"Total time: {elapsed:.3f}s")
            print(f"Time per record: {(elapsed / 10000) * 1000:.3f}ms")

            assert response.status_code == 200
            data = response.get_json()
            assert data['records_processed'] == 10000

            # Should complete in reasonable time
            assert elapsed < 30.0, f"Processing 10k records took too long: {elapsed:.3f}s"

    @patch('supabase_client.get_supabase_client')
    def test_large_field_values(self, mock_db_client):
        """Test records with very large field values."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            # Create record with 100KB text field
            large_text = "A" * 100000

            payload = {
                "data_type": "warehouses_full",
                "records": [
                    {
                        "warehouse_code": "TEST",
                        "warehouse_name": large_text,
                        "is_active": 1
                    }
                ]
            }

            start = time.time()
            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            elapsed = time.time() - start

            print(f"\n--- Large Field Performance ---")
            print(f"Field size: 100KB")
            print(f"Total time: {elapsed:.3f}s")

            assert response.status_code == 200
            assert elapsed < 5.0, f"Large field processing took too long: {elapsed:.3f}s"


class TestSustainedLoad:
    """Test sustained load over time."""

    @patch('supabase_client.get_supabase_client')
    def test_sustained_load_5_minutes(self, mock_db_client):
        """Test sustained load: 100 requests/minute for 5 minutes."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        # Run for shorter time in tests (30 seconds instead of 5 minutes)
        duration = 30  # seconds
        requests_per_minute = 100
        interval = 60 / requests_per_minute

        results = []
        start_time = time.time()

        while time.time() - start_time < duration:
            with app.test_client() as client:
                payload = {
                    "data_type": "warehouses_full",
                    "records": [{
                        "warehouse_code": f"WH{int(time.time() * 1000)}",
                        "warehouse_name": "Test",
                        "is_active": 1
                    }]
                }

                request_start = time.time()
                encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

                response = client.post(
                    '/api/ingest',
                    headers={"X-API-Key": os.getenv("API_KEY")},
                    json={"encrypted_payload": encrypted}
                )

                request_time = time.time() - request_start

                results.append({
                    'timestamp': time.time(),
                    'status': response.status_code,
                    'time': request_time
                })

            time.sleep(max(0, interval - request_time))

        # Analyze results
        total_requests = len(results)
        success_count = sum(1 for r in results if r['status'] == 200)
        response_times = [r['time'] for r in results if r['status'] == 200]

        print(f"\n--- Sustained Load Performance ---")
        print(f"Duration: {duration}s")
        print(f"Total requests: {total_requests}")
        print(f"Successful requests: {success_count}")
        print(f"Success rate: {(success_count / total_requests) * 100:.1f}%")
        print(f"Average response time: {statistics.mean(response_times):.3f}s")
        print(f"Max response time: {max(response_times):.3f}s")
        print(f"Min response time: {min(response_times):.3f}s")

        # Assertions
        assert success_count == total_requests, "Some requests failed"
        assert statistics.mean(response_times) < 1.0, "Average response time too high"


class TestMemoryLeaks:
    """Test for memory leaks during sustained operation."""

    @patch('supabase_client.get_supabase_client')
    def test_no_memory_leak_on_repeated_requests(self, mock_db_client):
        """Test memory doesn't grow unbounded with repeated requests."""
        import gc
        import sys

        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        # Force garbage collection before test
        gc.collect()

        # Measure initial memory
        initial_objects = len(gc.get_objects())

        # Make 1000 requests
        with app.test_client() as client:
            for i in range(1000):
                payload = {
                    "data_type": "warehouses_full",
                    "records": [{
                        "warehouse_code": f"WH{i:04d}",
                        "warehouse_name": f"Warehouse {i}",
                        "is_active": 1
                    }]
                }

                encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

                response = client.post(
                    '/api/ingest',
                    headers={"X-API-Key": os.getenv("API_KEY")},
                    json={"encrypted_payload": encrypted}
                )

                assert response.status_code == 200

                # Force GC every 100 requests
                if i % 100 == 0:
                    gc.collect()

        # Force garbage collection
        gc.collect()

        # Measure final memory
        final_objects = len(gc.get_objects())

        # Object count should not have grown significantly
        # Allow 50% growth as buffer (Python creates objects internally)
        growth = final_objects - initial_objects
        growth_percentage = (growth / initial_objects) * 100

        print(f"\n--- Memory Leak Test ---")
        print(f"Initial objects: {initial_objects}")
        print(f"Final objects: {final_objects}")
        print(f"Growth: {growth} objects ({growth_percentage:.1f}%)")

        # This is a soft assertion - memory management varies
        # Significant growth (> 100%) might indicate issues
        assert growth_percentage < 100, f"Potential memory leak: {growth_percentage:.1f}% growth"


class TestConnectionPoolExhaustion:
    """Test database connection pool handling."""

    @patch('supabase_client.get_supabase_client')
    def test_connection_pool_exhaustion(self, mock_db_client):
        """Test service handles connection pool exhaustion gracefully."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client

        # Simulate connection pool exhaustion
        call_count = [0]
        def side_effect(record):
            call_count[0] += 1
            if call_count[0] > 50:
                # Simulate pool exhaustion after 50 calls
                raise Exception("Connection pool exhausted")
            return MagicMock(execute=MagicMock())

        mock_client.table.return_value.upsert.side_effect = side_effect

        results = []

        def make_request(request_id):
            with app.test_client() as client:
                payload = {
                    "data_type": "warehouses_full",
                    "records": [{
                        "warehouse_code": f"WH{request_id:04d}",
                        "warehouse_name": "Test",
                        "is_active": 1
                    }]
                }

                encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

                response = client.post(
                    '/api/ingest',
                    headers={"X-API-Key": os.getenv("API_KEY")},
                    json={"encrypted_payload": encrypted}
                )

                results.append({
                    'request_id': request_id,
                    'status': response.status_code
                })

        # Send 100 requests concurrently
        threads = []
        for i in range(100):
            t = threading.Thread(target=make_request, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Some should succeed, some should fail gracefully
        success_count = sum(1 for r in results if r['status'] == 200)
        fail_count = sum(1 for r in results if r['status'] == 500)

        print(f"\n--- Connection Pool Test ---")
        print(f"Successful requests: {success_count}")
        print(f"Failed requests: {fail_count}")

        # All requests should complete (no crashes)
        assert len(results) == 100


class TestPerformanceBenchmarks:
    """Benchmark performance metrics."""

    @patch('supabase_client.get_supabase_client')
    def test_single_request_performance(self, mock_db_client):
        """Benchmark single request performance."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            payload = {
                "data_type": "warehouses_full",
                "records": [{
                    "warehouse_code": "01",
                    "warehouse_name": "Main Warehouse",
                    "is_active": 1
                }]
            }

            # Warm up
            for _ in range(10):
                encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()
                client.post(
                    '/api/ingest',
                    headers={"X-API-Key": os.getenv("API_KEY")},
                    json={"encrypted_payload": encrypted}
                )

            # Benchmark
            times = []
            for _ in range(100):
                start = time.time()
                encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

                response = client.post(
                    '/api/ingest',
                    headers={"X-API-Key": os.getenv("API_KEY")},
                    json={"encrypted_payload": encrypted}
                )

                elapsed = time.time() - start
                times.append(elapsed)

                assert response.status_code == 200

            avg_time = statistics.mean(times)
            p50 = statistics.median(times)
            p95 = statistics.quantiles(times, n=20)[18]  # 95th percentile
            p99 = statistics.quantiles(times, n=100)[98]  # 99th percentile

            print(f"\n--- Performance Benchmarks ---")
            print(f"Average: {avg_time*1000:.2f}ms")
            print(f"P50 (median): {p50*1000:.2f}ms")
            print(f"P95: {p95*1000:.2f}ms")
            print(f"P99: {p99*1000:.2f}ms")
            print(f"Min: {min(times)*1000:.2f}ms")
            print(f"Max: {max(times)*1000:.2f}ms")

            # Performance targets
            assert avg_time < 0.5, f"Average request time too high: {avg_time*1000:.2f}ms"
            assert p95 < 1.0, f"P95 latency too high: {p95*1000:.2f}ms"
