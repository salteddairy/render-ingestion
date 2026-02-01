"""
Supabase Client Integration
Handles database operations with connection pooling and retry logic
"""

import os
from typing import Dict, List, Any, Optional
from supabase import create_client, Client
from datetime import datetime
import time
import logging
import sys

# Add current directory for imports (works on both local and Render)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)

# Global Supabase client instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or initialize Supabase client singleton.

    Environment Variables:
        SUPABASE_URL: Supabase project URL (required)
        Format: https://your-project.supabase.co

        SUPABASE_SERVICE_ROLE_KEY: Supabase service role JWT key (required)
        Format: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        Obtained from: Supabase Dashboard → Project Settings → API

    Returns:
        Supabase client instance

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set
    """
    global _supabase_client

    if _supabase_client is None:
        # Load Supabase credentials from environment
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        # Validate required environment variables
        if not supabase_url:
            logger.error("SUPABASE_URL environment variable not set")
            raise ValueError("SUPABASE_URL environment variable not set")

        if not supabase_key:
            logger.error("SUPABASE_SERVICE_ROLE_KEY environment variable not set")
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable not set")

        try:
            # Initialize Supabase client with URL and service role key
            _supabase_client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise

    return _supabase_client


def upsert_records(
    table_name: str,
    records: List[Dict[str, Any]],
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Dict[str, int]:
    """
    Upsert records to Supabase table with retry logic and circuit breaker.

    Enhanced with:
    - Exponential backoff with jitter
    - Circuit breaker for cascading failure prevention
    - Comprehensive error handling
    - Detailed logging

    Args:
        table_name: Name of the Supabase table
        records: List of records to upsert
        max_retries: Maximum number of retry attempts (kept for backward compatibility)
        retry_delay: Initial delay between retries in seconds (kept for backward compatibility)

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    from src.retry_utils import retry_with_backoff, RETRY_DATABASE
    from src.circuit_breaker import ingestion_breaker, CircuitBreakerError

    if not records:
        return {'processed': 0, 'failed': 0}

    processed = 0
    failed = 0

    for record in records:
        try:
            @retry_with_backoff(
                exceptions=(Exception,),
                config=RETRY_DATABASE
            )
            @ingestion_breaker.call
            def _upsert_with_retry():
                client = get_supabase_client()
                # Perform upsert
                client.table(table_name).upsert(record).execute()
                return True

            _upsert_with_retry()
            processed += 1
            logger.debug(f"Successfully upserted record to {table_name}")

        except CircuitBreakerError:
            logger.error(f"Circuit breaker is open for ingestion operations")
            failed += 1
            # Break circuit is open, no point continuing
            break

        except Exception as e:
            logger.error(f"Failed to upsert record to {table_name} after all retries: {str(e)}")
            failed += 1

    return {'processed': processed, 'failed': failed}


def upsert_records_batch(
    table_name: str,
    records: List[Dict[str, Any]],
    validator_func: Optional[Any] = None
) -> Dict[str, int]:
    """
    Upsert records to Supabase table with transactional batch semantics.

    This function provides better consistency than upsert_records by:
    1. Pre-validating all records before any processing
    2. Processing all records with error collection
    3. Returning detailed results for manual review

    Args:
        table_name: Name of the Supabase table
        records: List of records to upsert
        validator_func: Optional validation function

    Returns:
        Dictionary with 'processed', 'failed', 'is_partial', 'errors' counts
    """
    if not records:
        return {'processed': 0, 'failed': 0, 'is_partial': False}

    def batch_operation(batch_records: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process a batch of records."""
        from src.retry_utils import retry_with_backoff, RETRY_DATABASE
        from src.circuit_breaker import ingestion_breaker, CircuitBreakerError

        processed = 0
        failed = 0

        for record in batch_records:
            try:
                @retry_with_backoff(
                    exceptions=(Exception,),
                    config=RETRY_DATABASE
                )
                @ingestion_breaker.call
                def _upsert_with_retry():
                    client = get_supabase_client()
                    client.table(table_name).upsert(record).execute()
                    return True

                _upsert_with_retry()
                processed += 1
                logger.debug(f"Successfully upserted record to {table_name}")

            except CircuitBreakerError:
                logger.error(f"Circuit breaker is open for ingestion operations")
                failed += len(batch_records) - processed
                break

            except Exception as e:
                logger.error(f"Failed to upsert record to {table_name} after all retries: {str(e)}")
                failed += 1

        return {'processed': processed, 'failed': failed}

    # Use transaction manager for batch processing
    # Import with full path handling for Render
    import importlib.util
    import sys

    # Get the directory where this file (supabase_client.py) is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct path to transaction_manager.py
    tm_path = os.path.join(current_dir, 'transaction_manager.py')

    # Load the module dynamically
    spec = importlib.util.spec_from_file_location('transaction_manager', tm_path)
    tm_module = importlib.util.module_from_spec(spec)
    sys.modules['transaction_manager'] = tm_module
    spec.loader.exec_module(tm_module)

    TransactionManager = tm_module.TransactionManager

    manager = TransactionManager()
    result = manager.execute_batch(
        records=records,
        operation_func=batch_operation,
        validator_func=validator_func,
        batch_size=50  # Process in batches of 50
    )

    return result.to_dict()


def upsert_warehouses(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert warehouse records to Supabase with transactional batch processing.
    """
    from transaction_manager import validate_warehouse_record

    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'warehouse_code': record.get('warehouse_code'),
                'warehouse_name': record.get('warehouse_name'),
                'region': record.get('region', 'UNKNOWN'),
                'is_active': bool(record.get('is_active', 1)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing warehouse record: {str(e)}")

    return upsert_records_batch('warehouses', clean_records, validate_warehouse_record)


def upsert_vendors(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert vendor records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'vendor_code': record.get('vendor_code'),
                'vendor_name': record.get('vendor_name'),
                'contact_person': record.get('contact_person'),
                'phone': record.get('phone'),
                'email': record.get('email'),
                'is_active': bool(record.get('is_active', 1)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing vendor record: {str(e)}")

    return upsert_records('vendors', clean_records)


def upsert_items(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert item records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'item_code': record.get('item_code'),
                'item_description': record.get('item_description'),
                'item_group': record.get('item_group'),
                'is_active': bool(record.get('is_active', 1)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing item record: {str(e)}")

    return upsert_records('items', clean_records)


def upsert_inventory(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert inventory records to Supabase with transactional batch processing.

    CRITICAL: This table joins items and warehouses, so consistency is vital.
    """
    from transaction_manager import validate_inventory_record

    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'item_code': record.get('item_code'),
                'warehouse_code': record.get('warehouse_code'),
                'on_hand_qty': float(record.get('on_hand_qty', 0)),
                'on_order_qty': float(record.get('on_order_qty', 0)),
                'committed_qty': float(record.get('committed_qty', 0)),
                'available_qty': float(record.get('available_qty', 0)),
                'unit_cost': float(record.get('unit_cost', 0)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing inventory record: {str(e)}")

    return upsert_records_batch('inventory_current', clean_records, validate_inventory_record)


def upsert_sales_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert sales order records to Supabase with transactional batch processing.
    """
    from transaction_manager import validate_sales_order_record

    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'order_id': int(record.get('order_id')),
                'order_date': record.get('order_date'),
                'customer_code': record.get('customer_code'),
                'item_code': record.get('item_code'),
                'warehouse_code': record.get('warehouse_code', ''),
                'quantity': int(record.get('quantity')),
                'unit_price': float(record.get('unit_price', 0)),
                'line_total': float(record.get('line_total', 0)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing sales order record: {str(e)}")

    return upsert_records_batch('sales_orders', clean_records, validate_sales_order_record)


def upsert_purchase_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert purchase order records to Supabase with transactional batch processing.
    """
    from transaction_manager import validate_purchase_order_record

    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'order_id': int(record.get('order_id')),
                'order_date': record.get('order_date'),
                'vendor_code': record.get('vendor_code'),
                'item_code': record.get('item_code'),
                'warehouse_code': record.get('warehouse_code', ''),
                'quantity': int(record.get('quantity')),
                'unit_price': float(record.get('unit_price', 0)),
                'line_total': float(record.get('line_total', 0)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing purchase order record: {str(e)}")

    return upsert_records_batch('purchase_orders', clean_records, validate_purchase_order_record)


def upsert_costs(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert cost records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'item_code': record.get('item_code'),
                'avg_cost': float(record.get('avg_cost', 0)),
                'last_cost': float(record.get('last_cost', 0)),
                'cost_date': record.get('cost_date'),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing cost record: {str(e)}")

    return upsert_records('costs', clean_records)


def upsert_pricing(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert pricing records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'item_code': record.get('item_code'),
                'price_list': record.get('price_list'),
                'price': float(record.get('price', 0)),
                'currency': record.get('currency', 'USD'),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing pricing record: {str(e)}")

    return upsert_records('pricing', clean_records)


def test_connection() -> bool:
    """
    Test Supabase database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = get_supabase_client()
        # Simple query to test connection
        result = client.table('warehouses').select('warehouse_code').limit(1).execute()
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False
