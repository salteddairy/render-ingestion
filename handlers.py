"""
Data Handlers for SAP Agent Data Types
Processes and validates records before storing in Supabase
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from supabase_client import (
    get_supabase_client,
    upsert_warehouses,
    upsert_vendors,
    upsert_items,
    upsert_inventory,
    upsert_sales_orders,
    upsert_purchase_orders,
    upsert_costs,
    upsert_pricing
)

logger = logging.getLogger(__name__)

# Global cache for warehouse codes
_warehouse_codes_cache: Optional[Set[str]] = None
_cache_timestamp: Optional[datetime] = None
CACHE_TTL_SECONDS = 300  # 5 minutes


def get_valid_warehouse_codes(force_refresh: bool = False) -> Set[str]:
    """
    Fetch all valid warehouse codes from the database with caching.

    Args:
        force_refresh: Force cache refresh even if not expired

    Returns:
        Set of valid warehouse codes

    Raises:
        Exception: If database query fails
    """
    global _warehouse_codes_cache, _cache_timestamp

    now = datetime.utcnow()

    # Check cache validity
    if (not force_refresh and
        _warehouse_codes_cache is not None and
        _cache_timestamp is not None and
        (now - _cache_timestamp).total_seconds() < CACHE_TTL_SECONDS):
        logger.debug(f"Using cached warehouse codes ({len(_warehouse_codes_cache)} warehouses)")
        return _warehouse_codes_cache

    # Fetch from database
    try:
        client = get_supabase_client()
        result = client.table('warehouses').select('warehouse_code').execute()

        _warehouse_codes_cache = {row['warehouse_code'] for row in result.data}
        _cache_timestamp = now

        logger.info(f"Refreshed warehouse codes cache: {len(_warehouse_codes_cache)} valid warehouses")
        return _warehouse_codes_cache

    except Exception as e:
        logger.error(f"Failed to fetch warehouse codes from database: {e}")
        # If we have a stale cache, return it for resilience
        if _warehouse_codes_cache is not None:
            logger.warning("Using stale warehouse codes cache due to database error")
            return _warehouse_codes_cache
        raise


def handle_warehouses(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process warehouse records.

    Args:
        records: List of warehouse records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} warehouse records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            warehouse_code = record.get("warehouse_code")
            if not warehouse_code:
                logger.warning("Skipping warehouse record: missing warehouse_code")
                continue

            business_records.append({
                "warehouse_code": warehouse_code,
                "warehouse_name": record.get("warehouse_name", ""),
                "region": record.get("region", "UNKNOWN"),
                "is_active": record.get("is_active", 1)
            })

        except Exception as e:
            logger.error(f"Error extracting warehouse data: {str(e)}")

    # Upsert to Supabase
    result = upsert_warehouses(business_records)
    logger.info(f"Warehouses processed: {result['processed']}, failed: {result['failed']}")

    return result


def handle_vendors(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process vendor records.

    Args:
        records: List of vendor records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} vendor records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            vendor_code = record.get("vendor_code")
            if not vendor_code:
                logger.warning("Skipping vendor record: missing vendor_code")
                continue

            business_records.append({
                "vendor_code": vendor_code,
                "vendor_name": record.get("vendor_name", ""),
                "contact_person": record.get("contact_person"),
                "phone": record.get("phone"),
                "email": record.get("email"),
                "is_active": record.get("is_active", 1)
            })

        except Exception as e:
            logger.error(f"Error extracting vendor data: {str(e)}")

    # Upsert to Supabase
    result = upsert_vendors(business_records)
    logger.info(f"Vendors processed: {result['processed']}, failed: {result['failed']}")

    return result


def handle_items(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process item records.

    Args:
        records: List of item records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} item records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            item_code = record.get("item_code")
            if not item_code:
                logger.warning("Skipping item record: missing item_code")
                continue

            business_records.append({
                "item_code": item_code,
                "item_description": record.get("item_description", ""),
                "item_group": record.get("item_group", ""),
                "is_active": record.get("is_active", 1)
            })

        except Exception as e:
            logger.error(f"Error extracting item data: {str(e)}")

    # Upsert to Supabase
    result = upsert_items(business_records)
    logger.info(f"Items processed: {result['processed']}, failed: {result['failed']}")

    return result


def handle_inventory(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process inventory records with warehouse code validation.

    Args:
        records: List of inventory records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed', 'failed', 'rejected_warehouses', and 'errors' counts
    """
    logger.info(f"Processing {len(records)} inventory records")

    # Get valid warehouse codes
    try:
        valid_warehouse_codes = get_valid_warehouse_codes()
        logger.info(f"Loaded {len(valid_warehouse_codes)} valid warehouse codes for validation")
    except Exception as e:
        logger.error(f"Failed to load valid warehouse codes: {e}")
        # Fail fast - we cannot proceed without warehouse validation
        return {
            'processed': 0,
            'failed': len(records),
            'rejected_warehouses': 0,
            'errors': [f"Failed to load warehouse codes for validation: {str(e)}"]
        }

    # Extract business data and validate
    business_records = []
    rejected_warehouses = []  # Track rejected warehouse codes
    rejected_records = 0
    invalid_warehouse_codes = set()  # Track unique invalid warehouse codes

    for record in records:
        try:
            # Validate required fields
            item_code = record.get("item_code")
            warehouse_code = record.get("warehouse_code")

            if not item_code or not warehouse_code:
                logger.warning(f"Skipping inventory record: missing item_code or warehouse_code")
                rejected_records += 1
                continue

            # CRITICAL: Validate warehouse code exists in database
            if warehouse_code not in valid_warehouse_codes:
                rejected_records += 1
                invalid_warehouse_codes.add(warehouse_code)
                rejected_warehouses.append({
                    'item_code': item_code,
                    'warehouse_code': warehouse_code,
                    'reason': f"Warehouse '{warehouse_code}' does not exist in warehouses table"
                })
                logger.warning(
                    f"Rejecting inventory record for item '{item_code}': "
                    f"invalid warehouse '{warehouse_code}'"
                )
                continue

            # Map SAP fields to database schema
            on_hand_qty = float(record.get("on_hand_qty", record.get("quantity", 0)))
            committed_qty = float(record.get("committed_qty", 0))
            available_qty = on_hand_qty - committed_qty

            business_records.append({
                "item_code": item_code,
                "warehouse_code": warehouse_code,
                "on_hand_qty": on_hand_qty,
                "on_order_qty": float(record.get("on_order_qty", 0)),
                "committed_qty": committed_qty,
                "available_qty": available_qty,
                "unit_cost": float(record.get("unit_cost", record.get("unit_price", 0)))
            })

        except Exception as e:
            logger.error(f"Error extracting inventory data: {str(e)}")
            rejected_records += 1

    # Log rejected warehouse summary
    if invalid_warehouse_codes:
        logger.error(
            f"Rejected {len(rejected_warehouses)} inventory records with invalid warehouses: "
            f"{sorted(invalid_warehouse_codes)}"
        )

    # Upsert valid records to Supabase
    result = upsert_inventory(business_records)

    # Build enhanced response
    response = {
        'processed': result['processed'],
        'failed': result['failed'] + rejected_records,
        'rejected_warehouses': len(rejected_warehouses),
        'invalid_warehouse_codes': sorted(list(invalid_warehouse_codes)),
        'rejected_records_sample': rejected_warehouses[:10]  # First 10 for review
    }

    logger.info(
        f"Inventory processing complete: {response['processed']} processed, "
        f"{response['failed']} failed, {response['rejected_warehouses']} rejected "
        f"(invalid warehouses: {response['invalid_warehouse_codes']})"
    )

    return response


def handle_sales_orders(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process sales order records with warehouse code validation.

    Args:
        records: List of sales order records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed', 'failed', 'rejected_warehouses', and 'errors' counts
    """
    logger.info(f"Processing {len(records)} sales order records")

    # Get valid warehouse codes
    try:
        valid_warehouse_codes = get_valid_warehouse_codes()
    except Exception as e:
        logger.error(f"Failed to load valid warehouse codes: {e}")
        return {
            'processed': 0,
            'failed': len(records),
            'rejected_warehouses': 0,
            'errors': [f"Failed to load warehouse codes for validation: {str(e)}"]
        }

    # Extract business data and validate
    business_records = []
    rejected_warehouses = []
    rejected_records = 0
    invalid_warehouse_codes = set()

    for record in records:
        try:
            # Validate required fields
            order_id = record.get("order_id")
            if not order_id:
                logger.warning("Skipping sales order record: missing order_id")
                rejected_records += 1
                continue

            warehouse_code = record.get("warehouse_code", "")

            # Only validate if warehouse_code is present
            if warehouse_code and warehouse_code not in valid_warehouse_codes:
                rejected_records += 1
                invalid_warehouse_codes.add(warehouse_code)
                rejected_warehouses.append({
                    'order_id': order_id,
                    'warehouse_code': warehouse_code,
                    'reason': f"Warehouse '{warehouse_code}' does not exist in warehouses table"
                })
                logger.warning(
                    f"Rejecting sales order '{order_id}': invalid warehouse '{warehouse_code}'"
                )
                continue

            business_records.append({
                "order_id": int(order_id),
                "order_date": record.get("order_date"),
                "customer_code": record.get("customer_code", ""),
                "item_code": record.get("item_code", ""),
                "warehouse_code": warehouse_code,
                "quantity": int(record.get("quantity", 0)),
                "unit_price": float(record.get("unit_price", 0)),
                "line_total": float(record.get("line_total", 0))
            })

        except Exception as e:
            logger.error(f"Error extracting sales order data: {str(e)}")
            rejected_records += 1

    # Log rejected warehouse summary
    if invalid_warehouse_codes:
        logger.error(
            f"Rejected {len(rejected_warehouses)} sales orders with invalid warehouses: "
            f"{sorted(invalid_warehouse_codes)}"
        )

    # Upsert to Supabase
    result = upsert_sales_orders(business_records)

    # Build enhanced response
    response = {
        'processed': result['processed'],
        'failed': result['failed'] + rejected_records,
        'rejected_warehouses': len(rejected_warehouses),
        'invalid_warehouse_codes': sorted(list(invalid_warehouse_codes)),
        'rejected_records_sample': rejected_warehouses[:10]
    }

    logger.info(
        f"Sales orders processing complete: {response['processed']} processed, "
        f"{response['failed']} failed, {response['rejected_warehouses']} rejected"
    )

    return response


def handle_purchase_orders(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process purchase order records with warehouse code validation.

    Args:
        records: List of purchase order records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed', 'failed', 'rejected_warehouses', and 'errors' counts
    """
    logger.info(f"Processing {len(records)} purchase order records")

    # Get valid warehouse codes
    try:
        valid_warehouse_codes = get_valid_warehouse_codes()
    except Exception as e:
        logger.error(f"Failed to load valid warehouse codes: {e}")
        return {
            'processed': 0,
            'failed': len(records),
            'rejected_warehouses': 0,
            'errors': [f"Failed to load warehouse codes for validation: {str(e)}"]
        }

    # Extract business data and validate
    business_records = []
    rejected_warehouses = []
    rejected_records = 0
    invalid_warehouse_codes = set()

    for record in records:
        try:
            # Validate required fields
            order_id = record.get("order_id")
            if not order_id:
                logger.warning("Skipping purchase order record: missing order_id")
                rejected_records += 1
                continue

            warehouse_code = record.get("warehouse_code", "")

            # Only validate if warehouse_code is present
            if warehouse_code and warehouse_code not in valid_warehouse_codes:
                rejected_records += 1
                invalid_warehouse_codes.add(warehouse_code)
                rejected_warehouses.append({
                    'order_id': order_id,
                    'warehouse_code': warehouse_code,
                    'reason': f"Warehouse '{warehouse_code}' does not exist in warehouses table"
                })
                logger.warning(
                    f"Rejecting purchase order '{order_id}': invalid warehouse '{warehouse_code}'"
                )
                continue

            business_records.append({
                "order_id": int(order_id),
                "order_date": record.get("order_date"),
                "vendor_code": record.get("vendor_code", ""),
                "item_code": record.get("item_code", ""),
                "warehouse_code": warehouse_code,
                "quantity": int(record.get("quantity", 0)),
                "unit_price": float(record.get("unit_price", 0)),
                "line_total": float(record.get("line_total", 0))
            })

        except Exception as e:
            logger.error(f"Error extracting purchase order data: {str(e)}")
            rejected_records += 1

    # Log rejected warehouse summary
    if invalid_warehouse_codes:
        logger.error(
            f"Rejected {len(rejected_warehouses)} purchase orders with invalid warehouses: "
            f"{sorted(invalid_warehouse_codes)}"
        )

    # Upsert to Supabase
    result = upsert_purchase_orders(business_records)

    # Build enhanced response
    response = {
        'processed': result['processed'],
        'failed': result['failed'] + rejected_records,
        'rejected_warehouses': len(rejected_warehouses),
        'invalid_warehouse_codes': sorted(list(invalid_warehouse_codes)),
        'rejected_records_sample': rejected_warehouses[:10]
    }

    logger.info(
        f"Purchase orders processing complete: {response['processed']} processed, "
        f"{response['failed']} failed, {response['rejected_warehouses']} rejected"
    )

    return response


def handle_costs(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process cost records.

    Args:
        records: List of cost records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} cost records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            item_code = record.get("item_code")
            cost_date = record.get("cost_date")

            if not item_code or not cost_date:
                logger.warning("Skipping cost record: missing item_code or cost_date")
                continue

            business_records.append({
                "item_code": item_code,
                "avg_cost": float(record.get("avg_cost", 0)),
                "last_cost": float(record.get("last_cost", 0)),
                "cost_date": cost_date
            })

        except Exception as e:
            logger.error(f"Error extracting cost data: {str(e)}")

    # Upsert to Supabase
    result = upsert_costs(business_records)
    logger.info(f"Costs processed: {result['processed']}, failed: {result['failed']}")

    return result


def handle_pricing(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process pricing records.

    Args:
        records: List of pricing records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} pricing records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            item_code = record.get("item_code")
            price_list = record.get("price_list")

            if not item_code or not price_list:
                logger.warning("Skipping pricing record: missing item_code or price_list")
                continue

            business_records.append({
                "item_code": item_code,
                "price_list": price_list,
                "price": float(record.get("price", 0)),
                "currency": record.get("currency", "USD")
            })

        except Exception as e:
            logger.error(f"Error extracting pricing data: {str(e)}")

    # Upsert to Supabase
    result = upsert_pricing(business_records)
    logger.info(f"Pricing processed: {result['processed']}, failed: {result['failed']}")

    return result


# Mapping of data types to handler functions
DATA_HANDLERS = {
    "warehouses_full": handle_warehouses,
    "vendors_full": handle_vendors,
    "items_full": handle_items,
    "inventory_current_full": handle_inventory,
    "sales_orders_incremental": handle_sales_orders,
    "purchase_orders_incremental": handle_purchase_orders,
    "costs_incremental": handle_costs,
    "pricing_full": handle_pricing
}
