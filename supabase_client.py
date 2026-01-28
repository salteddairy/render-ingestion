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

logger = logging.getLogger(__name__)

# Global Supabase client instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or initialize Supabase client singleton.

    Returns:
        Supabase client instance

    Raises:
        ValueError: If DATABASE_URL is not set
    """
    global _supabase_client

    if _supabase_client is None:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            raise ValueError("DATABASE_URL environment variable not set")

        try:
            _supabase_client = create_client(database_url)
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
    Upsert records to Supabase table with retry logic.

    Args:
        table_name: Name of the Supabase table
        records: List of records to upsert
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    if not records:
        return {'processed': 0, 'failed': 0}

    processed = 0
    failed = 0

    for record in records:
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            try:
                client = get_supabase_client()

                # Perform upsert
                client.table(table_name).upsert(record).execute()

                processed += 1
                success = True

                logger.debug(f"Successfully upserted record to {table_name}")

            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"Upsert failed for {table_name} (attempt {retry_count}/{max_retries}): {str(e)}"
                )

                if retry_count < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to upsert record to {table_name} after {max_retries} attempts: {str(e)}")
                    failed += 1

    return {'processed': processed, 'failed': failed}


def upsert_warehouses(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert warehouse records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'warehouse_code': record.get('warehouse_code'),
                'warehouse_name': record.get('warehouse_name'),
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
                'item_name': record.get('item_name'),
                'item_group': record.get('item_group'),
                'is_active': bool(record.get('is_active', 1)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing item record: {str(e)}")

    return upsert_records('items', clean_records)


def upsert_inventory(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert inventory records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'item_code': record.get('item_code'),
                'warehouse_code': record.get('warehouse_code'),
                'quantity': float(record.get('quantity', 0)),
                'unit_price': float(record.get('unit_price', 0)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing inventory record: {str(e)}")

    return upsert_records('inventory_current', clean_records)


def upsert_sales_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert sales order records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'order_id': int(record.get('order_id')),
                'order_date': record.get('order_date'),
                'customer_code': record.get('customer_code'),
                'item_code': record.get('item_code'),
                'quantity': int(record.get('quantity')),
                'unit_price': float(record.get('unit_price', 0)),
                'line_total': float(record.get('line_total', 0)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing sales order record: {str(e)}")

    return upsert_records('sales_orders', clean_records)


def upsert_purchase_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Upsert purchase order records to Supabase."""
    clean_records = []

    for record in records:
        try:
            clean_records.append({
                'order_id': int(record.get('order_id')),
                'order_date': record.get('order_date'),
                'vendor_code': record.get('vendor_code'),
                'item_code': record.get('item_code'),
                'quantity': int(record.get('quantity')),
                'unit_price': float(record.get('unit_price', 0)),
                'line_total': float(record.get('line_total', 0)),
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error preparing purchase order record: {str(e)}")

    return upsert_records('purchase_orders', clean_records)


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
