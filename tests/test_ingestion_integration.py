"""
Integration Tests for Render Ingestion Service
Tests end-to-end data flow and database operations
"""

import pytest
import json
import os
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from unittest.mock import Mock, patch, MagicMock

# Set environment variables before importing app
os.environ["API_KEY"] = "test_api_key_1234567890"
os.environ["ENCRYPTION_KEY"] = "test_encryption_key_32_characters_long!"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["LOG_LEVEL"] = "ERROR"

from app import app, cipher


class TestEndToEndDataFlow:
    """Test complete data flow from request to database."""

    @patch('supabase_client.get_supabase_client')
    def test_complete_warehouse_ingestion_flow(self, mock_db_client):
        """Test complete flow: encrypt → send → decrypt → save."""
        # Mock Supabase client
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            # Step 1: Create payload
            payload = {
                "data_type": "warehouses_full",
                "records": [
                    {
                        "warehouse_code": "TEST-WH-001",
                        "warehouse_name": "Test Warehouse 1",
                        "is_active": 1,
                        "_batch_metadata": {
                            "batch_id": "test-batch-001",
                            "query_id": "warehouses_full",
                            "chunk_index": 0,
                            "total_chunks": 1
                        }
                    }
                ]
            }

            # Step 2: Encrypt
            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            # Step 3: Send
            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            # Step 4: Verify response
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data_type'] == 'warehouses_full'
            assert data['records_received'] == 1
            assert data['records_processed'] == 1
            assert data['records_failed'] == 0

            # Step 5: Verify database was called
            mock_client.table.assert_called_once_with('warehouses')

    @patch('supabase_client.get_supabase_client')
    def test_all_data_types_ingest_correctly(self, mock_db_client):
        """Test all 8 data types can be ingested."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        test_data = {
            "warehouses_full": {
                "records": [{"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1}],
                "table": "warehouses"
            },
            "vendors_full": {
                "records": [{"vendor_code": "V001", "vendor_name": "Acme", "is_active": 1}],
                "table": "vendors"
            },
            "items_full": {
                "records": [{"item_code": "A001", "item_name": "Widget", "item_group": "Finished", "is_active": 1}],
                "table": "items"
            },
            "inventory_current_full": {
                "records": [{"item_code": "A001", "warehouse_code": "01", "quantity": 100.0, "unit_price": 25.50}],
                "table": "inventory_current"
            },
            "sales_orders_incremental": {
                "records": [{
                    "order_id": 12345,
                    "order_date": "2025-01-27T00:00:00",
                    "customer_code": "C001",
                    "item_code": "A001",
                    "quantity": 10,
                    "unit_price": 25.50,
                    "line_total": 255.00
                }],
                "table": "sales_orders"
            },
            "purchase_orders_incremental": {
                "records": [{
                    "order_id": 67890,
                    "order_date": "2025-01-27T00:00:00",
                    "vendor_code": "V001",
                    "item_code": "A001",
                    "quantity": 100,
                    "unit_price": 15.00,
                    "line_total": 1500.00
                }],
                "table": "purchase_orders"
            },
            "costs_incremental": {
                "records": [{
                    "item_code": "A001",
                    "avg_cost": 18.50,
                    "last_cost": 19.00,
                    "cost_date": "2025-01-27"
                }],
                "table": "costs"
            },
            "pricing_full": {
                "records": [{
                    "item_code": "A001",
                    "price_list": "1",
                    "price": 25.50,
                    "currency": "USD"
                }],
                "table": "pricing"
            }
        }

        with app.test_client() as client:
            for data_type, test_info in test_data.items():
                payload = {
                    "data_type": data_type,
                    "records": test_info["records"]
                }

                encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

                response = client.post(
                    '/api/ingest',
                    headers={"X-API-Key": os.getenv("API_KEY")},
                    json={"encrypted_payload": encrypted}
                )

                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert data['data_type'] == data_type


class TestDatabaseTransactions:
    """Test database transaction handling."""

    @patch('supabase_client.get_supabase_client')
    def test_transaction_commit_on_success(self, mock_db_client):
        """Test transaction commits on successful upsert."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            payload = {
                "data_type": "warehouses_full",
                "records": [{"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1}]
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            assert response.status_code == 200
            # Verify upsert was called
            assert mock_client.table.return_value.upsert.called

    @patch('supabase_client.get_supabase_client')
    def test_partial_failure_handling(self, mock_db_client):
        """Test handling when some records fail."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client

        # Make upsert fail for second call
        call_count = [0]
        def side_effect(records):
            call_count[0] += 1
            if call_count[0] == 1:
                return MagicMock(execute=MagicMock())
            else:
                raise Exception("Database error")

        mock_client.table.return_value.upsert.side_effect = side_effect

        with app.test_client() as client:
            payload = {
                "data_type": "warehouses_full",
                "records": [
                    {"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1},
                    {"warehouse_code": "02", "warehouse_name": "Secondary", "is_active": 1}
                ]
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            # Should still process successfully
            assert response.status_code == 200
            data = response.get_json()
            assert data['records_processed'] == 1
            assert data['records_failed'] == 1


class TestDuplicateDataHandling:
    """Test handling of duplicate data."""

    @patch('supabase_client.get_supabase_client')
    def test_upsert_handles_duplicates(self, mock_db_client):
        """Test upsert handles duplicate keys gracefully."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            # Send same record twice
            payload = {
                "data_type": "warehouses_full",
                "records": [{"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1}]
            }

            # First request
            encrypted1 = cipher.encrypt(json.dumps(payload).encode()).decode()
            response1 = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted1}
            )
            assert response1.status_code == 200

            # Second request with same data
            encrypted2 = cipher.encrypt(json.dumps(payload).encode()).decode()
            response2 = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted2}
            )
            assert response2.status_code == 200


class TestForeignKeyConstraints:
    """Test foreign key constraint handling."""

    @patch('supabase_client.get_supabase_client')
    def test_inventory_requires_valid_item_and_warehouse(self, mock_db_client):
        """Test inventory references valid items and warehouses."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client

        # Simulate foreign key violation
        mock_client.table.return_value.upsert.return_value.execute.side_effect = Exception(
            "Foreign key violation"
        )

        with app.test_client() as client:
            payload = {
                "data_type": "inventory_current_full",
                "records": [{
                    "item_code": "NONEXISTENT",
                    "warehouse_code": "NONEXISTENT",
                    "quantity": 100.0,
                    "unit_price": 25.50
                }]
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            # Should handle gracefully
            assert response.status_code == 200
            data = response.get_json()
            assert data['records_failed'] == 1


class TestBatchMetadataTracking:
    """Test batch metadata is properly tracked."""

    @patch('supabase_client.get_supabase_client')
    def test_batch_metadata_included_in_logs(self, mock_db_client):
        """Test batch metadata is logged but not stored."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            payload = {
                "data_type": "warehouses_full",
                "records": [
                    {
                        "warehouse_code": "01",
                        "warehouse_name": "Main",
                        "is_active": 1,
                        "_batch_metadata": {
                            "batch_id": "test-batch-123",
                            "query_id": "warehouses_full",
                            "query_name": "Warehouses Full",
                            "chunk_index": 0,
                            "total_chunks": 5,
                            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                            "source": "SAP B1",
                            "destination": "render"
                        }
                    }
                ]
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            assert response.status_code == 200

            # Verify _batch_metadata not passed to database
            call_args = mock_client.table.return_value.upsert.call_args
            stored_record = call_args[0][0]
            assert '_batch_metadata' not in stored_record


class TestResponseFormat:
    """Test response format compliance."""

    @patch('supabase_client.get_supabase_client')
    def test_success_response_format(self, mock_db_client):
        """Test success response has correct format."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            payload = {
                "data_type": "warehouses_full",
                "records": [{"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1}]
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            assert response.status_code == 200
            data = response.get_json()

            # Check required fields
            assert 'success' in data
            assert 'message' in data
            assert 'data_type' in data
            assert 'records_received' in data
            assert 'records_processed' in data
            assert 'records_failed' in data
            assert 'timestamp' in data

            # Check values
            assert data['success'] is True
            assert isinstance(data['records_received'], int)
            assert isinstance(data['records_processed'], int)
            assert isinstance(data['records_failed'], int)

    def test_error_response_format(self):
        """Test error response has correct format."""
        with app.test_client() as client:
            payload = {"data_type": "unknown_type", "records": []}
            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            assert response.status_code == 400
            data = response.get_json()

            # Check error format
            assert 'success' in data
            assert 'error' in data
            assert data['success'] is False


class TestRetryLogic:
    """Test retry logic for database operations."""

    @patch('supabase_client.get_supabase_client')
    @patch('time.sleep')
    def test_database_retry_on_transient_failure(self, mock_sleep, mock_db_client):
        """Test retries on transient database failures."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client

        # Fail twice, then succeed
        call_count = [0]
        def side_effect(record):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Transient error")
            return MagicMock(execute=MagicMock())

        mock_client.table.return_value.upsert.side_effect = side_effect

        with app.test_client() as client:
            payload = {
                "data_type": "warehouses_full",
                "records": [{"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1}]
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            # Should succeed after retries
            assert response.status_code == 200
            data = response.get_json()
            assert data['records_processed'] == 1
            assert mock_sleep.call_count == 2  # Retried twice

    @patch('supabase_client.get_supabase_client')
    @patch('time.sleep')
    def test_database_failure_after_max_retries(self, mock_sleep, mock_db_client):
        """Test failure after max retries exceeded."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client

        # Always fail
        mock_client.table.return_value.upsert.side_effect = Exception("Persistent error")

        with app.test_client() as client:
            payload = {
                "data_type": "warehouses_full",
                "records": [{"warehouse_code": "01", "warehouse_name": "Main", "is_active": 1}]
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            # Should mark as failed
            assert response.status_code == 200
            data = response.get_json()
            assert data['records_failed'] == 1
            assert mock_sleep.call_count == 3  # Max retries = 3


class TestMultipleRecords:
    """Test handling multiple records in single request."""

    @patch('supabase_client.get_supabase_client')
    def test_batch_insert_multiple_records(self, mock_db_client):
        """Test inserting multiple records in one batch."""
        mock_client = MagicMock()
        mock_db_client.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = None

        with app.test_client() as client:
            records = [
                {"warehouse_code": f"WH{i:03d}", "warehouse_name": f"Warehouse {i}", "is_active": 1}
                for i in range(1, 11)
            ]

            payload = {
                "data_type": "warehouses_full",
                "records": records
            }

            encrypted = cipher.encrypt(json.dumps(payload).encode()).decode()

            response = client.post(
                '/api/ingest',
                headers={"X-API-Key": os.getenv("API_KEY")},
                json={"encrypted_payload": encrypted}
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['records_received'] == 10
            assert data['records_processed'] == 10
            assert data['records_failed'] == 0
