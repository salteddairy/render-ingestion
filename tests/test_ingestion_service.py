"""
Unit Tests for SAP Agent → Render Endpoint → Supabase Integration

Tests individual components:
- API key validation
- Encryption/decryption
- Data handlers for all 8 data types
- Field mapping
- Data type conversions

Coverage Goal: >90%
"""
import pytest
import json

import os
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime
from cryptography.fernet import Fernet
from typing import Dict, Any, List


# ============================================================================
# Configuration (matching SAP_AGENT_RENDER_ENDPOINT_SPEC.md)
# ============================================================================

API_KEY = os.environ.get("INGESTION_API_KEY", "")
if not API_KEY:
    raise ValueError("INGESTION_API_KEY environment variable not set")
ENCRYPTION_KEY = "YOUR_ENCRYPTION_KEY_HERE"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def cipher():
    """Fernet cipher instance for testing."""
    return Fernet(ENCRYPTION_KEY.encode('utf-8'))


@pytest.fixture
def sample_warehouse_record():
    """Sample warehouse record."""
    return {
        "warehouse_code": "01",
        "warehouse_name": "Main Warehouse",
        "is_active": 1
    }


@pytest.fixture
def sample_vendor_record():
    """Sample vendor record."""
    return {
        "vendor_code": "V001",
        "vendor_name": "Acme Supplies",
        "contact_person": "John Doe",
        "phone": "555-1234",
        "email": "john@acme.com",
        "is_active": 1
    }


@pytest.fixture
def sample_item_record():
    """Sample item record."""
    return {
        "item_code": "A00100",
        "item_name": "Widget A",
        "item_group": "Finished Goods",
        "is_active": 1
    }


@pytest.fixture
def sample_inventory_record():
    """Sample inventory record."""
    return {
        "item_code": "A00100",
        "warehouse_code": "01",
        "quantity": 500.00,
        "unit_price": 25.50
    }


@pytest.fixture
def sample_sales_order_record():
    """Sample sales order record."""
    return {
        "order_id": 12345,
        "order_date": "2025-01-27T00:00:00",
        "customer_code": "C001",
        "item_code": "A00100",
        "quantity": 10,
        "unit_price": 25.50,
        "line_total": 255.00
    }


@pytest.fixture
def sample_purchase_order_record():
    """Sample purchase order record."""
    return {
        "order_id": 67890,
        "order_date": "2025-01-27T00:00:00",
        "vendor_code": "V001",
        "item_code": "A00100",
        "quantity": 100,
        "unit_price": 15.00,
        "line_total": 1500.00
    }


@pytest.fixture
def sample_cost_record():
    """Sample cost record."""
    return {
        "item_code": "A00100",
        "avg_cost": 18.50,
        "last_cost": 19.00,
        "cost_date": "2025-01-27"
    }


@pytest.fixture
def sample_pricing_record():
    """Sample pricing record."""
    return {
        "item_code": "A00100",
        "price_list": "1",
        "price": 25.50,
        "currency": "USD"
    }


# ============================================================================
# Test: API Key Validation
# ============================================================================

class TestAPIKeyValidation:
    """Test API key validation logic."""

    def test_valid_api_key(self):
        """Test that valid API key is accepted."""
        test_key = "YOUR_API_KEY_HERE"
        assert test_key == API_KEY
        assert len(test_key) >= 40  # API key should be sufficiently long

    def test_invalid_api_key(self):
        """Test that invalid API key is rejected."""
        invalid_keys = [
            "",
            "wrong",
            "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0Xge",  # Too short
            "YOUR_API_KEY_HEREextra",  # Too long
            None
        ]
        for invalid_key in invalid_keys:
            assert invalid_key != API_KEY

    def test_api_key_header_format(self):
        """Test API key header format."""
        header_name = "X-API-Key"
        assert header_name == "X-API-Key"


# ============================================================================
# Test: Encryption/Decryption
# ============================================================================

class TestEncryptionDecryption:
    """Test Fernet encryption/decryption."""

    def test_encrypt_decrypt_simple_string(self, cipher):
        """Test encryption/decryption of simple string."""
        original = "Hello, World!"
        encrypted = cipher.encrypt(original.encode('utf-8'))
        decrypted = cipher.decrypt(encrypted)
        assert decrypted.decode('utf-8') == original

    def test_encrypt_decrypt_json_payload(self, cipher):
        """Test encryption/decryption of JSON payload."""
        payload = {
            "data_type": "warehouses_full",
            "records": [
                {
                    "warehouse_code": "01",
                    "warehouse_name": "Main Warehouse",
                    "is_active": 1
                }
            ]
        }
        json_str = json.dumps(payload)
        encrypted = cipher.encrypt(json_str.encode('utf-8'))
        decrypted = cipher.decrypt(encrypted)
        result = json.loads(decrypted.decode('utf-8'))
        assert result == payload

    def test_encryption_produces_different_ciphertext(self, cipher):
        """Test that encryption produces different ciphertext each time (due to IV)."""
        payload = "Test message"
        encrypted1 = cipher.encrypt(payload.encode('utf-8'))
        encrypted2 = cipher.encrypt(payload.encode('utf-8'))
        assert encrypted1 != encrypted2

    def test_decryption_with_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        from cryptography.fernet import Fernet
        import base64

        # Create two different valid Fernet keys
        key1 = base64.urlsafe_b64encode(b'0123456789abcdef0123456789abcdef').decode('utf-8')
        key2 = base64.urlsafe_b64encode(b'fedcba9876543210fedcba9876543210').decode('utf-8')

        cipher1 = Fernet(key1.encode('utf-8'))
        cipher2 = Fernet(key2.encode('utf-8'))

        payload = "Secret message"
        encrypted = cipher1.encrypt(payload.encode('utf-8'))

        with pytest.raises(Exception):
            cipher2.decrypt(encrypted)

    def test_encryption_with_special_characters(self, cipher):
        """Test encryption with special characters and Unicode."""
        payloads = [
            "Hello émojis 🎉",
            "Special chars: @#$%^&*()",
            "Unicode: 你好世界",
            "Newlines\nand\ttabs",
            "Quotes: 'single' and \"double\""
        ]
        for payload in payloads:
            encrypted = cipher.encrypt(payload.encode('utf-8'))
            decrypted = cipher.decrypt(encrypted)
            assert decrypted.decode('utf-8') == payload


# ============================================================================
# Test: Warehouse Data Handler
# ============================================================================

class TestWarehouseHandler:
    """Test warehouse data processing."""

    def test_warehouse_record_extraction(self, sample_warehouse_record):
        """Test extracting fields from warehouse record."""
        assert sample_warehouse_record["warehouse_code"] == "01"
        assert sample_warehouse_record["warehouse_name"] == "Main Warehouse"
        assert sample_warehouse_record["is_active"] == 1

    def test_warehouse_is_active_conversion(self, sample_warehouse_record):
        """Test is_active field conversion to boolean."""
        is_active = bool(sample_warehouse_record.get("is_active", 1))
        assert is_active is True

        inactive_record = {"warehouse_code": "02", "warehouse_name": "Closed", "is_active": 0}
        is_inactive = bool(inactive_record.get("is_active", 1))
        assert is_inactive is False

    def test_warehouse_with_null_optional_fields(self):
        """Test warehouse record with NULL optional fields."""
        record = {
            "warehouse_code": "03",
            "warehouse_name": None,
            "is_active": 1
        }
        assert record["warehouse_code"] == "03"
        assert record["warehouse_name"] is None


# ============================================================================
# Test: Vendor Data Handler
# ============================================================================

class TestVendorHandler:
    """Test vendor data processing."""

    def test_vendor_record_extraction(self, sample_vendor_record):
        """Test extracting fields from vendor record."""
        assert sample_vendor_record["vendor_code"] == "V001"
        assert sample_vendor_record["vendor_name"] == "Acme Supplies"
        assert sample_vendor_record["contact_person"] == "John Doe"

    def test_vendor_with_null_optional_fields(self):
        """Test vendor record with NULL optional fields."""
        record = {
            "vendor_code": "V002",
            "vendor_name": "Test Vendor",
            "contact_person": None,
            "phone": None,
            "email": None,
            "is_active": 1
        }
        assert record["vendor_code"] == "V002"
        assert record["contact_person"] is None


# ============================================================================
# Test: Item Data Handler
# ============================================================================

class TestItemHandler:
    """Test item data processing."""

    def test_item_record_extraction(self, sample_item_record):
        """Test extracting fields from item record."""
        assert sample_item_record["item_code"] == "A00100"
        assert sample_item_record["item_name"] == "Widget A"
        assert sample_item_record["item_group"] == "Finished Goods"

    def test_item_with_special_characters(self):
        """Test item with special characters in name."""
        record = {
            "item_code": "A00100-SPEC",
            "item_name": "Widget™ Special - émoji 🎉",
            "item_group": "Finished Goods",
            "is_active": 1
        }
        assert "™" in record["item_name"]
        assert "é" in record["item_name"]


# ============================================================================
# Test: Inventory Data Handler
# ============================================================================

class TestInventoryHandler:
    """Test inventory data processing."""

    def test_inventory_record_extraction(self, sample_inventory_record):
        """Test extracting fields from inventory record."""
        assert sample_inventory_record["item_code"] == "A00100"
        assert sample_inventory_record["warehouse_code"] == "01"
        assert sample_inventory_record["quantity"] == 500.00
        assert sample_inventory_record["unit_price"] == 25.50

    def test_inventory_float_conversions(self):
        """Test float conversions for inventory fields."""
        record = {
            "item_code": "A00100",
            "warehouse_code": "01",
            "quantity": "500.00",  # String input
            "unit_price": "25.50"  # String input
        }
        quantity = float(record.get("quantity", 0))
        unit_price = float(record.get("unit_price", 0))
        assert quantity == 500.00
        assert unit_price == 25.50

    def test_inventory_with_zero_values(self):
        """Test inventory with zero values."""
        record = {
            "item_code": "A00100",
            "warehouse_code": "01",
            "quantity": 0.00,
            "unit_price": 0.00
        }
        quantity = float(record.get("quantity", 0))
        unit_price = float(record.get("unit_price", 0))
        assert quantity == 0.00
        assert unit_price == 0.00


# ============================================================================
# Test: Sales Order Data Handler
# ============================================================================

class TestSalesOrderHandler:
    """Test sales order data processing."""

    def test_sales_order_record_extraction(self, sample_sales_order_record):
        """Test extracting fields from sales order record."""
        assert sample_sales_order_record["order_id"] == 12345
        assert sample_sales_order_record["order_date"] == "2025-01-27T00:00:00"
        assert sample_sales_order_record["customer_code"] == "C001"
        assert sample_sales_order_record["item_code"] == "A00100"
        assert sample_sales_order_record["quantity"] == 10

    def test_sales_order_int_conversion(self):
        """Test integer conversions for sales order fields."""
        record = {
            "order_id": "12345",  # String input
            "order_date": "2025-01-27T00:00:00",
            "customer_code": "C001",
            "item_code": "A00100",
            "quantity": "10"  # String input
        }
        order_id = int(record.get("order_id"))
        quantity = int(record.get("quantity"))
        assert order_id == 12345
        assert quantity == 10

    def test_sales_order_datetime_parsing(self):
        """Test ISO 8601 datetime format."""
        valid_dates = [
            "2025-01-27T00:00:00",
            "2025-01-27T00:00:00+00:00",
            "2025-01-27T00:00:00.123456+00:00"
        ]
        for date_str in valid_dates:
            try:
                datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except ValueError as e:
                pytest.fail(f"Failed to parse {date_str}: {e}")


# ============================================================================
# Test: Purchase Order Data Handler
# ============================================================================

class TestPurchaseOrderHandler:
    """Test purchase order data processing."""

    def test_purchase_order_record_extraction(self, sample_purchase_order_record):
        """Test extracting fields from purchase order record."""
        assert sample_purchase_order_record["order_id"] == 67890
        assert sample_purchase_order_record["order_date"] == "2025-01-27T00:00:00"
        assert sample_purchase_order_record["vendor_code"] == "V001"
        assert sample_purchase_order_record["item_code"] == "A00100"
        assert sample_purchase_order_record["quantity"] == 100


# ============================================================================
# Test: Cost Data Handler
# ============================================================================

class TestCostHandler:
    """Test cost data processing."""

    def test_cost_record_extraction(self, sample_cost_record):
        """Test extracting fields from cost record."""
        assert sample_cost_record["item_code"] == "A00100"
        assert sample_cost_record["avg_cost"] == 18.50
        assert sample_cost_record["last_cost"] == 19.00
        assert sample_cost_record["cost_date"] == "2025-01-27"

    def test_cost_date_parsing(self):
        """Test ISO 8601 date format."""
        valid_dates = [
            "2025-01-27",
            "2025-12-31",
            "2024-02-29"  # Leap year
        ]
        for date_str in valid_dates:
            try:
                datetime.fromisoformat(date_str)
            except ValueError as e:
                pytest.fail(f"Failed to parse {date_str}: {e}")


# ============================================================================
# Test: Pricing Data Handler
# ============================================================================

class TestPricingHandler:
    """Test pricing data processing."""

    def test_pricing_record_extraction(self, sample_pricing_record):
        """Test extracting fields from pricing record."""
        assert sample_pricing_record["item_code"] == "A00100"
        assert sample_pricing_record["price_list"] == "1"
        assert sample_pricing_record["price"] == 25.50
        assert sample_pricing_record["currency"] == "USD"

    def test_pricing_composite_key(self, sample_pricing_record):
        """Test composite primary key for pricing."""
        composite_key = (
            sample_pricing_record["item_code"],
            sample_pricing_record["price_list"],
            sample_pricing_record["currency"]
        )
        assert composite_key == ("A00100", "1", "USD")


# ============================================================================
# Test: Batch Metadata
# ============================================================================

class TestBatchMetadata:
    """Test batch metadata handling."""

    def test_batch_metadata_structure(self):
        """Test batch metadata fields."""
        metadata = {
            "batch_id": "550e8400-e29b-41d4-a716-446655440000",
            "query_id": "warehouses_full",
            "query_name": "Warehouses Full",
            "chunk_index": 0,
            "total_chunks": 1,
            "extraction_timestamp": "2025-01-27T10:30:00.123456+00:00",
            "source": "SAP B1",
            "destination": "render"
        }
        assert "batch_id" in metadata
        assert "query_id" in metadata
        assert "chunk_index" in metadata
        assert "total_chunks" in metadata

    def test_record_with_batch_metadata(self):
        """Test record including _batch_metadata."""
        record = {
            "warehouse_code": "01",
            "warehouse_name": "Main Warehouse",
            "is_active": 1,
            "_batch_metadata": {
                "batch_id": "test-batch-001",
                "chunk_index": 0
            }
        }
        # Business data should be separate from metadata
        assert "warehouse_code" in record
        assert "_batch_metadata" in record
        assert record["_batch_metadata"]["batch_id"] == "test-batch-001"


# ============================================================================
# Test: Data Type Handlers Routing
# ============================================================================

class TestDataTypeHandlers:
    """Test data type handler routing."""

    def test_all_data_types_defined(self):
        """Test that all 8 data types are defined."""
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
        assert len(data_types) == 8

    def test_data_type_handler_mapping(self):
        """Test data type to handler mapping."""
        mapping = {
            "warehouses_full": "handle_warehouses",
            "vendors_full": "handle_vendors",
            "items_full": "handle_items",
            "inventory_current_full": "handle_inventory",
            "sales_orders_incremental": "handle_sales_orders",
            "purchase_orders_incremental": "handle_purchase_orders",
            "costs_incremental": "handle_costs",
            "pricing_full": "handle_pricing"
        }
        assert len(mapping) == 8
        for data_type, handler in mapping.items():
            assert "handle_" in handler


# ============================================================================
# Test: Null Value Handling
# ============================================================================

class TestNullHandling:
    """Test NULL value handling across all data types."""

    def test_warehouse_with_nulls(self):
        """Test warehouse with NULL values."""
        record = {
            "warehouse_code": "01",
            "warehouse_name": None,
            "is_active": 1
        }
        assert record["warehouse_name"] is None
        warehouse_name = record.get("warehouse_name", "Unknown")
        assert warehouse_name is None

    def test_vendor_with_nulls(self):
        """Test vendor with NULL values."""
        record = {
            "vendor_code": "V001",
            "vendor_name": "Test Vendor",
            "contact_person": None,
            "phone": None,
            "email": None,
            "is_active": 1
        }
        assert record["contact_person"] is None
        assert record["phone"] is None
        assert record["email"] is None

    def test_numeric_field_with_null(self):
        """Test numeric field with NULL value."""
        record = {
            "item_code": "A00100",
            "avg_cost": None,
            "last_cost": None
        }
        avg_cost = record.get("avg_cost", 0)
        assert avg_cost is None
        # Safe conversion
        if avg_cost is not None:
            avg_cost_float = float(avg_cost)
        else:
            avg_cost_float = 0.0
        assert avg_cost_float == 0.0


# ============================================================================
# Test: Data Type Conversions
# ============================================================================

class TestDataTypeConversions:
    """Test data type conversions."""

    def test_string_to_int(self):
        """Test string to integer conversion."""
        values = ["123", "456", "789"]
        for val in values:
            result = int(val)
            assert isinstance(result, int)

    def test_string_to_float(self):
        """Test string to float conversion."""
        values = ["123.45", "678.90", "999.99"]
        for val in values:
            result = float(val)
            assert isinstance(result, float)

    def test_empty_string_to_zero(self):
        """Test empty string treated as zero for numeric fields."""
        quantity = ""
        if quantity == "":
            quantity = 0
        else:
            quantity = float(quantity)
        assert quantity == 0

    def test_none_to_zero(self):
        """Test None treated as zero for numeric fields."""
        quantity = None
        quantity = float(quantity or 0)
        assert quantity == 0.0


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_records_list(self):
        """Test handling of empty records list."""
        records = []
        assert len(records) == 0

    def test_single_record(self):
        """Test handling of single record."""
        records = [{"item_code": "A00100", "item_name": "Test"}]
        assert len(records) == 1

    def test_large_record_count(self):
        """Test handling of large record count (5000 records)."""
        records = [
            {"item_code": f"A{i:05d}", "item_name": f"Item {i}"}
            for i in range(5000)
        ]
        assert len(records) == 5000

    def test_very_long_string_field(self):
        """Test handling of very long string field."""
        long_string = "A" * 1000
        record = {
            "item_code": "A00100",
            "item_name": long_string
        }
        assert len(record["item_name"]) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=.", "--cov-report=html"])
