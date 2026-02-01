"""
Test Transaction Wrapping for Multi-Table Operations
Tests that batch operations have proper consistency guarantees

Created: 2026-01-31
Author: Distributed Systems Reliability Engineer
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transaction_manager import (
    TransactionManager,
    TransactionBatchResult,
    validate_warehouse_record,
    validate_inventory_record,
    validate_sales_order_record
)


class TestTransactionManager:
    """Test suite for transaction manager."""

    def test_batch_with_all_valid_records(self):
        """Test batch processing with all valid records."""
        manager = TransactionManager()

        records = [
            {'warehouse_code': f'TEST-{i}', 'warehouse_name': f'Warehouse {i}'}
            for i in range(10)
        ]

        def mock_operation(batch):
            return {'processed': len(batch), 'failed': 0}

        result = manager.execute_batch(
            records=records,
            operation_func=mock_operation,
            validator_func=validate_warehouse_record
        )

        assert result.processed == 10
        assert result.failed == 0
        assert result.is_partial is False
        assert len(result.errors) == 0

    def test_batch_with_validation_failures(self):
        """Test batch processing with validation failures."""
        manager = TransactionManager()

        records = [
            {'warehouse_code': 'TEST-001', 'warehouse_name': 'Valid 1'},
            {'warehouse_name': 'Invalid - no code'},  # Missing warehouse_code
            {'warehouse_code': 'TEST-002', 'warehouse_name': 'Valid 2'},
            {},  # Empty record
        ]

        def mock_operation(batch):
            return {'processed': len(batch), 'failed': 0}

        result = manager.execute_batch(
            records=records,
            operation_func=mock_operation,
            validator_func=validate_warehouse_record
        )

        # Only 2 valid records should be processed
        assert result.processed == 2
        assert result.failed == 2
        assert result.is_partial is True
        assert len(result.errors) == 2

    def test_batch_with_processing_failures(self):
        """Test batch processing with some records failing during processing."""
        manager = TransactionManager()

        records = [
            {'item_code': f'ITEM-{i}', 'warehouse_code': 'WH-001', 'on_hand_qty': 100}
            for i in range(10)
        ]

        def failing_operation(batch):
            # Fail the last record in batch
            processed = len(batch) - 1
            return {'processed': processed, 'failed': 1}

        result = manager.execute_batch(
            records=records,
            operation_func=failing_operation,
            validator_func=validate_inventory_record
        )

        assert result.processed > 0
        assert result.failed > 0
        assert result.is_partial is True

    def test_transactional_batch_all_or_nothing(self):
        """Test transactional batch fails completely if any record fails."""
        manager = TransactionManager()

        records = [
            {'warehouse_code': f'TEST-{i}', 'warehouse_name': f'Warehouse {i}'}
            for i in range(5)
        ]

        call_count = [0]

        def mock_operation(record):
            call_count[0] += 1
            # Fail on 3rd record
            if call_count[0] == 3:
                return {'processed': 0, 'failed': 1}
            return {'processed': 1, 'failed': 0}

        result = manager.execute_transactional_batch(
            records=records,
            operation_func=mock_operation,
            validator_func=validate_warehouse_record
        )

        # All should fail due to one failure
        assert result.failed == 5
        assert result.processed == 0
        assert result.is_partial is False

    def test_transactional_batch_all_succeed(self):
        """Test transactional batch succeeds when all records are valid."""
        manager = TransactionManager()

        records = [
            {'warehouse_code': f'TEST-{i}', 'warehouse_name': f'Warehouse {i}'}
            for i in range(5)
        ]

        def mock_operation(record):
            return {'processed': 1, 'failed': 0}

        result = manager.execute_transactional_batch(
            records=records,
            operation_func=mock_operation,
            validator_func=validate_warehouse_record
        )

        assert result.processed == 5
        assert result.failed == 0
        assert result.is_partial is False

    def test_inventory_validation_with_invalid_quantity(self):
        """Test inventory record validation rejects invalid quantities."""
        # Invalid quantity (non-numeric)
        is_valid, error = validate_inventory_record({
            'item_code': 'ITEM-001',
            'warehouse_code': 'WH-001',
            'on_hand_qty': 'not_a_number'
        })

        assert is_valid is False
        assert 'must be numeric' in error

    def test_sales_order_validation_with_invalid_order_id(self):
        """Test sales order validation rejects non-integer order IDs."""
        is_valid, error = validate_sales_order_record({
            'order_id': 'not_an_integer'
        })

        assert is_valid is False
        assert 'must be integer' in error

    def test_empty_batch(self):
        """Test that empty batch returns zero results."""
        manager = TransactionManager()

        def mock_operation(batch):
            return {'processed': len(batch), 'failed': 0}

        result = manager.execute_batch(
            records=[],
            operation_func=mock_operation
        )

        assert result.processed == 0
        assert result.failed == 0


class TestTransactionBatchResult:
    """Test suite for TransactionBatchResult."""

    def test_to_dict_conversion(self):
        """Test converting result to dictionary."""
        result = TransactionBatchResult(
            processed=100,
            failed=5,
            errors=[{'error': 'test error'}],
            is_partial=True
        )

        result_dict = result.to_dict()

        assert result_dict['processed'] == 100
        assert result_dict['failed'] == 5
        assert result_dict['is_partial'] is True
        assert len(result_dict['errors']) == 1

    def test_to_dict_limits_errors(self):
        """Test that to_dict limits errors to first 10."""
        result = TransactionBatchResult(
            processed=0,
            failed=20,
            errors=[{'error': f'error {i}'} for i in range(20)]
        )

        result_dict = result.to_dict()

        assert len(result_dict['errors']) == 10


class TestValidationFunctions:
    """Test suite for validation functions."""

    def test_validate_warehouse_record_valid(self):
        """Test valid warehouse record passes validation."""
        is_valid, error = validate_warehouse_record({
            'warehouse_code': 'WH-001',
            'warehouse_name': 'Test Warehouse'
        })

        assert is_valid is True
        assert error is None

    def test_validate_warehouse_record_missing_code(self):
        """Test warehouse record without code fails validation."""
        is_valid, error = validate_warehouse_record({
            'warehouse_name': 'Test Warehouse'
        })

        assert is_valid is False
        assert 'warehouse_code' in error

    def test_validate_inventory_record_valid(self):
        """Test valid inventory record passes validation."""
        is_valid, error = validate_inventory_record({
            'item_code': 'ITEM-001',
            'warehouse_code': 'WH-001',
            'on_hand_qty': 100
        })

        assert is_valid is True
        assert error is None

    def test_validate_inventory_record_missing_item_code(self):
        """Test inventory record without item_code fails validation."""
        is_valid, error = validate_inventory_record({
            'warehouse_code': 'WH-001',
            'on_hand_qty': 100
        })

        assert is_valid is False
        assert 'item_code' in error

    def test_validate_inventory_record_missing_warehouse_code(self):
        """Test inventory record without warehouse_code fails validation."""
        is_valid, error = validate_inventory_record({
            'item_code': 'ITEM-001',
            'on_hand_qty': 100
        })

        assert is_valid is False
        assert 'warehouse_code' in error

    def test_validate_sales_order_record_valid(self):
        """Test valid sales order record passes validation."""
        is_valid, error = validate_sales_order_record({
            'order_id': 12345,
            'item_code': 'ITEM-001'
        })

        assert is_valid is True
        assert error is None

    def test_validate_sales_order_record_missing_order_id(self):
        """Test sales order without order_id fails validation."""
        is_valid, error = validate_sales_order_record({
            'item_code': 'ITEM-001'
        })

        assert is_valid is False
        assert 'order_id' in error


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
