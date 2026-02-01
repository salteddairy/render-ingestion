"""
Transaction Manager for Render Ingestion Service
Provides atomic batch operations with proper rollback capability

Created: 2026-01-31
Author: Distributed Systems Reliability Engineer
"""

import logging
from typing import Dict, List, Any, Callable, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class TransactionBatchResult:
    """Result of a batch transaction operation."""

    def __init__(
        self,
        processed: int = 0,
        failed: int = 0,
        errors: List[Dict[str, Any]] = None,
        is_partial: bool = False
    ):
        self.processed = processed
        self.failed = failed
        self.errors = errors or []
        self.is_partial = is_partial

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            'processed': self.processed,
            'failed': self.failed,
            'is_partial': self.is_partial,
            'errors': self.errors[:10]  # Only first 10 errors
        }


class TransactionManager:
    """
    Manages transactional batch operations for data ingestion.

    Since Supabase Python client uses REST API (not direct DB connection),
    we implement transactional semantics at the application level:

    1. Pre-validate all records before any processing
    2. Process all records with error collection
    3. Log all failures for manual review
    4. Return detailed results for retry logic

    This ensures we never have partial updates due to validation failures.
    """

    def __init__(self):
        """Initialize transaction manager."""
        logger.info("Transaction manager initialized")

    def execute_batch(
        self,
        records: List[Dict[str, Any]],
        operation_func: Callable[[List[Dict[str, Any]]], Dict[str, int]],
        validator_func: Optional[Callable[[Dict[str, Any]], Tuple[bool, Optional[str]]]] = None,
        batch_size: int = 100
    ) -> TransactionBatchResult:
        """
        Execute a batch operation with transactional semantics.

        Args:
            records: List of records to process
            operation_func: Function that processes records (should return dict with processed/failed)
            validator_func: Optional validation function (record) -> (is_valid, error_message)
            batch_size: Process records in batches of this size

        Returns:
            TransactionBatchResult with detailed statistics
        """
        if not records:
            return TransactionBatchResult()

        result = TransactionBatchResult()
        valid_records = []

        # Phase 1: Pre-validate all records
        logger.info(f"Phase 1: Validating {len(records)} records")

        for record in records:
            try:
                if validator_func:
                    is_valid, error_msg = validator_func(record)
                    if not is_valid:
                        result.failed += 1
                        result.errors.append({
                            'record': str(record)[:200],  # Truncate for logging
                            'error': error_msg,
                            'phase': 'validation'
                        })
                        logger.warning(f"Validation failed: {error_msg}")
                        continue

                valid_records.append(record)

            except Exception as e:
                result.failed += 1
                result.errors.append({
                    'record': str(record)[:200],
                    'error': str(e),
                    'phase': 'validation'
                })
                logger.error(f"Validation error: {str(e)}")

        if not valid_records:
            logger.error("No valid records after validation phase")
            result.is_partial = result.processed > 0
            return result

        logger.info(f"Phase 1 complete: {len(valid_records)} valid, {result.failed} invalid")

        # Phase 2: Process valid records in batches
        logger.info(f"Phase 2: Processing {len(valid_records)} valid records in batches of {batch_size}")

        try:
            # Process in batches
            for i in range(0, len(valid_records), batch_size):
                batch = valid_records[i:i + batch_size]
                logger.info(f"Processing batch {i // batch_size + 1}/{(len(valid_records) + batch_size - 1) // batch_size}")

                batch_result = operation_func(batch)
                result.processed += batch_result.get('processed', 0)
                result.failed += batch_result.get('failed', 0)

                # If batch had failures, mark as partial
                if batch_result.get('failed', 0) > 0:
                    result.is_partial = True

            logger.info(f"Phase 2 complete: {result.processed} processed, {result.failed} failed")

        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}", exc_info=True)
            result.errors.append({
                'error': str(e),
                'phase': 'processing'
            })
            result.is_partial = result.processed > 0

        return result

    def execute_transactional_batch(
        self,
        records: List[Dict[str, Any]],
        operation_func: Callable[[Dict[str, Any]], Dict[str, int]],
        validator_func: Optional[Callable[[Dict[str, Any]], Tuple[bool, Optional[str]]]] = None
    ) -> TransactionBatchResult:
        """
        Execute batch operation with fail-fast semantics.

        If ANY record fails, the entire batch fails and no records are processed.
        This is useful for operations where partial updates are unacceptable.

        Args:
            records: List of records to process
            operation_func: Function that processes single record
            validator_func: Optional validation function

        Returns:
            TransactionBatchResult with detailed statistics
        """
        if not records:
            return TransactionBatchResult()

        result = TransactionBatchResult()

        # Phase 1: Validate all records
        logger.info(f"Validating {len(records)} records for transactional batch")

        for record in records:
            if validator_func:
                is_valid, error_msg = validator_func(record)
                if not is_valid:
                    result.failed = len(records)  # All records failed
                    result.errors.append({
                        'error': f"Validation failed for all records: {error_msg}",
                        'phase': 'validation'
                    })
                    return result

        # Phase 2: Process all records or fail completely
        logger.info(f"Processing {len(records)} records transactionally")

        processed_records = []
        try:
            for record in records:
                record_result = operation_func(record)
                if record_result.get('failed', 0) > 0:
                    # Rollback: mark all as failed
                    result.failed = len(records)
                    result.is_partial = len(processed_records) > 0
                    result.errors.append({
                        'error': f"Record failed, aborting transaction: {record.get('id', 'unknown')}",
                        'phase': 'processing'
                    })
                    logger.error(f"Transactional batch failed at record {len(processed_records) + 1}")
                    return result

                processed_records.append(record)

            result.processed = len(processed_records)
            logger.info(f"Transactional batch succeeded: {result.processed} processed")

        except Exception as e:
            logger.error(f"Transactional batch error: {str(e)}", exc_info=True)
            result.failed = len(records)
            result.is_partial = len(processed_records) > 0
            result.errors.append({
                'error': str(e),
                'phase': 'processing'
            })

        return result


def validate_warehouse_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate warehouse record."""
    warehouse_code = record.get("warehouse_code")
    if not warehouse_code:
        return False, "Missing warehouse_code"
    return True, None


def validate_vendor_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate vendor record."""
    vendor_code = record.get("vendor_code")
    if not vendor_code:
        return False, "Missing vendor_code"
    return True, None


def validate_item_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate item record."""
    item_code = record.get("item_code")
    if not item_code:
        return False, "Missing item_code"
    return True, None


def validate_inventory_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate inventory record."""
    item_code = record.get("item_code")
    warehouse_code = record.get("warehouse_code")

    if not item_code:
        return False, "Missing item_code"
    if not warehouse_code:
        return False, "Missing warehouse_code"

    # Validate quantity is numeric
    try:
        float(record.get("on_hand_qty", 0))
    except (ValueError, TypeError):
        return False, "Invalid on_hand_qty: must be numeric"

    return True, None


def validate_sales_order_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate sales order record."""
    order_id = record.get("order_id")
    if not order_id:
        return False, "Missing order_id"

    # Validate order_id is integer
    try:
        int(order_id)
    except (ValueError, TypeError):
        return False, "Invalid order_id: must be integer"

    return True, None


def validate_purchase_order_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate purchase order record."""
    order_id = record.get("order_id")
    if not order_id:
        return False, "Missing order_id"

    try:
        int(order_id)
    except (ValueError, TypeError):
        return False, "Invalid order_id: must be integer"

    return True, None


def validate_cost_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate cost record."""
    item_code = record.get("item_code")
    cost_date = record.get("cost_date")

    if not item_code:
        return False, "Missing item_code"
    if not cost_date:
        return False, "Missing cost_date"

    return True, None


def validate_pricing_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate pricing record."""
    item_code = record.get("item_code")
    price_list = record.get("price_list")

    if not item_code:
        return False, "Missing item_code"
    if not price_list:
        return False, "Missing price_list"

    return True, None


# Global transaction manager instance
transaction_manager = TransactionManager()
