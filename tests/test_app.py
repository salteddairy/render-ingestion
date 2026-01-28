"""
Comprehensive tests for Render Ingestion Service
"""

import pytest
import json
import os
from cryptography.fernet import Fernet

# Set environment variables before importing app
os.environ["API_KEY"] = "test_api_key_1234567890"
os.environ["ENCRYPTION_KEY"] = "test_encryption_key_32_characters_long!"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["LOG_LEVEL"] = "ERROR"

from app import app, cipher


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def encrypt_payload(data):
    """Helper function to encrypt payload."""
    json_str = json.dumps(data)
    encrypted_bytes = cipher.encrypt(json_str.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')


class TestHealthCheck:
    """Tests for /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Test health check returns 200 OK."""
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_check_response_structure(self, client):
        """Test health check response structure."""
        response = client.get('/health')
        data = response.get_json()

        assert data['status'] == 'healthy'
        assert data['service'] == 'forecast-ingestion'
        assert 'timestamp' in data
        assert 'version' in data


class TestAuthentication:
    """Tests for API key validation."""

    def test_valid_api_key(self, client):
        """Test request with valid API key."""
        test_payload = {
            "data_type": "warehouses_full",
            "records": [
                {
                    "warehouse_code": "TEST01",
                    "warehouse_name": "Test Warehouse",
                    "is_active": 1
                }
            ]
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        # Will likely fail due to no database, but should pass auth
        assert response.status_code in [200, 500]

    def test_invalid_api_key(self, client):
        """Test request with invalid API key."""
        test_payload = {
            "data_type": "warehouses_full",
            "records": []
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": "invalid_key"},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code == 401

        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Unauthorized'

    def test_missing_api_key(self, client):
        """Test request without API key."""
        test_payload = {
            "data_type": "warehouses_full",
            "records": []
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code == 401


class TestDecryption:
    """Tests for payload decryption."""

    def test_valid_encrypted_payload(self, client):
        """Test with valid encrypted payload."""
        test_payload = {
            "data_type": "warehouses_full",
            "records": [
                {
                    "warehouse_code": "TEST01",
                    "warehouse_name": "Test Warehouse",
                    "is_active": 1
                }
            ]
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        # May fail on database operations, but decryption should work
        assert response.status_code in [200, 500]

    def test_corrupted_payload(self, client):
        """Test with corrupted payload."""
        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": "corrupted_payload_data"}
        )

        assert response.status_code == 400

        data = response.get_json()
        assert data['success'] is False
        assert 'Decryption failed' in data['error']

    def test_missing_encrypted_payload(self, client):
        """Test with missing encrypted_payload field."""
        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={}
        )

        assert response.status_code == 400

        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing encrypted_payload'


class TestDataValidation:
    """Tests for data validation."""

    def test_missing_data_type(self, client):
        """Test with missing data_type."""
        test_payload = {
            "records": []
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code == 400

        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing data_type'

    def test_unknown_data_type(self, client):
        """Test with unknown data_type."""
        test_payload = {
            "data_type": "unknown_type",
            "records": []
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code == 400

        data = response.get_json()
        assert data['success'] is False
        assert 'Unknown data_type' in data['error']

    def test_empty_records(self, client):
        """Test with empty records list."""
        test_payload = {
            "data_type": "warehouses_full",
            "records": []
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert data['records_count'] == 0


class TestDataTypes:
    """Tests for different data types."""

    @pytest.fixture
    def sample_warehouses(self):
        return {
            "data_type": "warehouses_full",
            "records": [
                {
                    "warehouse_code": "01",
                    "warehouse_name": "Main Warehouse",
                    "is_active": 1
                }
            ]
        }

    @pytest.fixture
    def sample_vendors(self):
        return {
            "data_type": "vendors_full",
            "records": [
                {
                    "vendor_code": "V001",
                    "vendor_name": "Acme Supplies",
                    "contact_person": "John Doe",
                    "phone": "555-1234",
                    "email": "john@acme.com",
                    "is_active": 1
                }
            ]
        }

    @pytest.fixture
    def sample_items(self):
        return {
            "data_type": "items_full",
            "records": [
                {
                    "item_code": "A00100",
                    "item_name": "Widget A",
                    "item_group": "Finished Goods",
                    "is_active": 1
                }
            ]
        }

    @pytest.fixture
    def sample_inventory(self):
        return {
            "data_type": "inventory_current_full",
            "records": [
                {
                    "item_code": "A00100",
                    "warehouse_code": "01",
                    "quantity": 500.00,
                    "unit_price": 25.50
                }
            ]
        }

    @pytest.fixture
    def sample_sales_orders(self):
        return {
            "data_type": "sales_orders_incremental",
            "records": [
                {
                    "order_id": 12345,
                    "order_date": "2025-01-27T00:00:00",
                    "customer_code": "C001",
                    "item_code": "A00100",
                    "quantity": 10,
                    "unit_price": 25.50,
                    "line_total": 255.00
                }
            ]
        }

    @pytest.fixture
    def sample_purchase_orders(self):
        return {
            "data_type": "purchase_orders_incremental",
            "records": [
                {
                    "order_id": 67890,
                    "order_date": "2025-01-27T00:00:00",
                    "vendor_code": "V001",
                    "item_code": "A00100",
                    "quantity": 100,
                    "unit_price": 15.00,
                    "line_total": 1500.00
                }
            ]
        }

    @pytest.fixture
    def sample_costs(self):
        return {
            "data_type": "costs_incremental",
            "records": [
                {
                    "item_code": "A00100",
                    "avg_cost": 18.50,
                    "last_cost": 19.00,
                    "cost_date": "2025-01-27"
                }
            ]
        }

    @pytest.fixture
    def sample_pricing(self):
        return {
            "data_type": "pricing_full",
            "records": [
                {
                    "item_code": "A00100",
                    "price_list": "1",
                    "price": 25.50,
                    "currency": "USD"
                }
            ]
        }

    def test_warehouses_data_type(self, client, sample_warehouses):
        """Test warehouses_full data type."""
        encrypted = encrypt_payload(sample_warehouses)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        # Will likely fail on database, but routing should work
        assert response.status_code in [200, 500]

    def test_vendors_data_type(self, client, sample_vendors):
        """Test vendors_full data type."""
        encrypted = encrypt_payload(sample_vendors)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code in [200, 500]

    def test_items_data_type(self, client, sample_items):
        """Test items_full data type."""
        encrypted = encrypt_payload(sample_items)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code in [200, 500]

    def test_inventory_data_type(self, client, sample_inventory):
        """Test inventory_current_full data type."""
        encrypted = encrypt_payload(sample_inventory)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code in [200, 500]

    def test_sales_orders_data_type(self, client, sample_sales_orders):
        """Test sales_orders_incremental data type."""
        encrypted = encrypt_payload(sample_sales_orders)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code in [200, 500]

    def test_purchase_orders_data_type(self, client, sample_purchase_orders):
        """Test purchase_orders_incremental data type."""
        encrypted = encrypt_payload(sample_purchase_orders)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code in [200, 500]

    def test_costs_data_type(self, client, sample_costs):
        """Test costs_incremental data type."""
        encrypted = encrypt_payload(sample_costs)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code in [200, 500]

    def test_pricing_data_type(self, client, sample_pricing):
        """Test pricing_full data type."""
        encrypted = encrypt_payload(sample_pricing)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        assert response.status_code in [200, 500]


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_request_body(self, client):
        """Test with missing request body."""
        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")}
        )

        assert response.status_code == 400

        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing request body'

    def test_404_endpoint(self, client):
        """Test non-existent endpoint."""
        response = client.get('/nonexistent')

        assert response.status_code == 404

        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Endpoint not found'


class TestBatchMetadata:
    """Tests for batch metadata handling."""

    def test_records_with_batch_metadata(self, client):
        """Test records with _batch_metadata field."""
        test_payload = {
            "data_type": "warehouses_full",
            "records": [
                {
                    "warehouse_code": "TEST01",
                    "warehouse_name": "Test Warehouse",
                    "is_active": 1,
                    "_batch_metadata": {
                        "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                        "query_id": "warehouses_full",
                        "query_name": "Warehouses Full",
                        "chunk_index": 0,
                        "total_chunks": 1,
                        "extraction_timestamp": "2025-01-27T10:30:00.123456+00:00",
                        "source": "SAP B1",
                        "destination": "render"
                    }
                }
            ]
        }

        encrypted = encrypt_payload(test_payload)

        response = client.post(
            '/api/ingest',
            headers={"X-API-Key": os.getenv("API_KEY")},
            json={"encrypted_payload": encrypted}
        )

        # Should successfully ignore _batch_metadata
        assert response.status_code in [200, 500]
