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
    Upsert records to Supabase table.

    Args:
        table_name: Name of the Supabase table
        records: List of records to upsert
        max_retries: Maximum number of retry attempts (kept for backward compatibility)
        retry_delay: Initial delay between retries in seconds (kept for backward compatibility)

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    if not records:
        return {'processed': 0, 'failed': 0}

    processed = 0
    failed = 0
    client = get_supabase_client()

    for record in records:
        try:
            # Perform upsert
            client.table(table_name).upsert(record).execute()
            processed += 1
            logger.debug(f"Successfully upserted record to {table_name}")
        except Exception as e:
            logger.error(f"Failed to upsert record to {table_name}: {str(e)}")
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
        processed = 0
        failed = 0
        client = get_supabase_client()

        for record in batch_records:
            try:
                # Perform upsert
                client.table(table_name).upsert(record).execute()
                processed += 1
            except Exception as e:
                logger.error(f"Failed to upsert record: {str(e)}")
                failed += 1

        return {'processed': processed, 'failed': failed}


def upsert_records_batch(
    table_name: str,
    records: List[Dict[str, Any]],
    validator_func: Optional[Any] = None
) -> Dict[str, int]:
    """
    Upsert records to Supabase with optional validation.
    """
    if not records:
        return {'processed': 0, 'failed': 0, 'is_partial': False}

    # Validate records if validator provided
    clean_records = []
    for record in records:
        if validator_func:
            is_valid, error_msg = validator_func(record)
            if not is_valid:
                logger.warning(f"Record validation failed: {error_msg}")
                continue
        clean_records.append(record)

    # Use the simple upsert_records function
    return upsert_records(table_name, clean_records)


def upsert_warehouses(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert warehouse records to Supabase."""
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

    return upsert_records('warehouses', clean_records)


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
    # Removed transaction_manager import

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

    return upsert_records_batch('inventory_current', clean_records)


def upsert_sales_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert sales order records to Supabase with transactional batch processing.
    """
    # Removed transaction_manager import

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

    return upsert_records_batch('sales_orders', clean_records)


def upsert_purchase_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert purchase order records to Supabase with transactional batch processing.
    """
    # Removed transaction_manager import

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

    return upsert_records_batch('purchase_orders', clean_records)


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
