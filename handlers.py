"""
Data Handlers for SAP Agent Data Types
Processes and validates records before storing in Supabase
"""

import logging
from typing import Dict, List, Any
from supabase_client import (
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
                "item_name": record.get("item_name", ""),
                "item_group": record.get("item_group", ""),
                "is_active": record.get("is_active", 1)
            })

        except Exception as e:
            logger.error(f"Error extracting item data: {str(e)}")

    # Upsert to Supabase
    result = upsert_items(business_records)
    logger.info(f"Items processed: {result['processed']}, failed: {result['failed']}")

    return result


def handle_inventory(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process inventory records.

    Args:
        records: List of inventory records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} inventory records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            item_code = record.get("item_code")
            warehouse_code = record.get("warehouse_code")

            if not item_code or not warehouse_code:
                logger.warning(f"Skipping inventory record: missing item_code or warehouse_code")
                continue

            business_records.append({
                "item_code": item_code,
                "warehouse_code": warehouse_code,
                "quantity": float(record.get("quantity", 0)),
                "unit_price": float(record.get("unit_price", 0))
            })

        except Exception as e:
            logger.error(f"Error extracting inventory data: {str(e)}")

    # Upsert to Supabase
    result = upsert_inventory(business_records)
    logger.info(f"Inventory processed: {result['processed']}, failed: {result['failed']}")

    return result


def handle_sales_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process sales order records.

    Args:
        records: List of sales order records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} sales order records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            order_id = record.get("order_id")
            if not order_id:
                logger.warning("Skipping sales order record: missing order_id")
                continue

            business_records.append({
                "order_id": int(order_id),
                "order_date": record.get("order_date"),
                "customer_code": record.get("customer_code", ""),
                "item_code": record.get("item_code", ""),
                "quantity": int(record.get("quantity", 0)),
                "unit_price": float(record.get("unit_price", 0)),
                "line_total": float(record.get("line_total", 0))
            })

        except Exception as e:
            logger.error(f"Error extracting sales order data: {str(e)}")

    # Upsert to Supabase
    result = upsert_sales_orders(business_records)
    logger.info(f"Sales orders processed: {result['processed']}, failed: {result['failed']}")

    return result


def handle_purchase_orders(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Process purchase order records.

    Args:
        records: List of purchase order records with business data + _batch_metadata

    Returns:
        Dictionary with 'processed' and 'failed' counts
    """
    logger.info(f"Processing {len(records)} purchase order records")

    # Extract business data (skip _batch_metadata)
    business_records = []
    for record in records:
        try:
            # Validate required fields
            order_id = record.get("order_id")
            if not order_id:
                logger.warning("Skipping purchase order record: missing order_id")
                continue

            business_records.append({
                "order_id": int(order_id),
                "order_date": record.get("order_date"),
                "vendor_code": record.get("vendor_code", ""),
                "item_code": record.get("item_code", ""),
                "quantity": int(record.get("quantity", 0)),
                "unit_price": float(record.get("unit_price", 0)),
                "line_total": float(record.get("line_total", 0))
            })

        except Exception as e:
            logger.error(f"Error extracting purchase order data: {str(e)}")

    # Upsert to Supabase
    result = upsert_purchase_orders(business_records)
    logger.info(f"Purchase orders processed: {result['processed']}, failed: {result['failed']}")

    return result


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
