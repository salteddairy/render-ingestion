#!/usr/bin/env python3
"""
Test Warehouse Validation
Tests the warehouse code validation functionality

This script demonstrates:
1. Fetching valid warehouse codes
2. Validating inventory records before insert
3. Proper error reporting for invalid warehouses
"""

import sys
import os
from datetime import datetime

# Add paths
sys.path.insert(0, 'D:/code/forecastv3/render-ingestion')
sys.path.insert(0, 'D:/code/forecastv3')

from handlers import get_valid_warehouse_codes, handle_inventory
from supabase_client import get_supabase_client


def test_warehouse_cache():
    """Test warehouse code caching."""
    print("\n" + "="*80)
    print("TEST 1: Warehouse Code Cache")
    print("="*80)

    try:
        # Fetch warehouse codes
        warehouse_codes = get_valid_warehouse_codes(force_refresh=True)

        print(f"\n✓ Successfully loaded {len(warehouse_codes)} valid warehouse codes")
        print(f"\nValid warehouse codes:")
        for wh in sorted(warehouse_codes):
            print(f"  - {wh}")

        # Test cache hit (should be instant)
        start = datetime.utcnow()
        warehouse_codes_cached = get_valid_warehouse_codes(force_refresh=False)
        elapsed = (datetime.utcnow() - start).total_seconds()

        print(f"\n✓ Cache test: Retrieved {len(warehouse_codes_cached)} codes in {elapsed:.3f}s")

        return warehouse_codes

    except Exception as e:
        print(f"\n✗ Failed to load warehouse codes: {e}")
        return None


def test_inventory_validation():
    """Test inventory record validation."""
    print("\n" + "="*80)
    print("TEST 2: Inventory Record Validation")
    print("="*80)

    # Get valid warehouse codes first
    try:
        valid_codes = get_valid_warehouse_codes()
        print(f"\nLoaded {len(valid_codes)} valid warehouse codes for testing")
    except Exception as e:
        print(f"\n✗ Cannot proceed without valid warehouse codes: {e}")
        return

    # Create test records with mixed valid/invalid warehouses
    first_valid = sorted(valid_codes)[0] if valid_codes else "UNKNOWN"

    test_records = [
        # Valid record
        {
            "item_code": "TEST-ITEM-001",
            "warehouse_code": first_valid,
            "on_hand_qty": 100.0,
            "committed_qty": 10.0,
            "on_order_qty": 50.0,
            "unit_cost": 25.50
        },
        # Invalid warehouse
        {
            "item_code": "TEST-ITEM-002",
            "warehouse_code": "INVALID-WH",
            "on_hand_qty": 200.0,
            "committed_qty": 20.0,
            "on_order_qty": 0.0,
            "unit_cost": 50.00
        },
        # Missing warehouse
        {
            "item_code": "TEST-ITEM-003",
            # warehouse_code missing
            "on_hand_qty": 150.0
        },
        # Another valid record
        {
            "item_code": "TEST-ITEM-004",
            "warehouse_code": first_valid,
            "on_hand_qty": 75.0,
            "committed_qty": 5.0,
            "on_order_qty": 25.0,
            "unit_cost": 15.75
        }
    ]

    print(f"\nTest records created:")
    for i, rec in enumerate(test_records, 1):
        wh = rec.get('warehouse_code', 'MISSING')
        print(f"  {i}. Item: {rec['item_code']:20s} | Warehouse: {wh}")

    # Process records
    print("\nProcessing records...")
    result = handle_inventory(test_records)

    # Display results
    print("\n" + "-"*80)
    print("RESULTS:")
    print("-"*80)
    print(f"  Processed:       {result['processed']}")
    print(f"  Failed:          {result['failed']}")
    print(f"  Rejected (WH):   {result['rejected_warehouses']}")
    print(f"  Invalid WHs:     {result.get('invalid_warehouse_codes', [])}")

    if result.get('rejected_records_sample'):
        print(f"\n  Sample rejected records:")
        for i, rec in enumerate(result['rejected_records_sample'], 1):
            print(f"    {i}. {rec}")

    print("\n" + "="*80)
    if result['processed'] == 2 and result['rejected_warehouses'] == 2:
        print("✓ TEST PASSED: Correctly validated warehouse codes")
    else:
        print("✗ TEST FAILED: Unexpected validation results")
    print("="*80)


def test_database_foreign_key():
    """Test that database foreign key constraint is enforced."""
    print("\n" + "="*80)
    print("TEST 3: Database Foreign Key Constraint")
    print("="*80)

    try:
        client = get_supabase_client()

        # Try to insert inventory with invalid warehouse (should fail)
        print("\nAttempting to insert inventory with invalid warehouse code...")

        try:
            result = client.table('inventory_current').insert({
                "item_code": "FOREIGN-KEY-TEST",
                "warehouse_code": "NONEXISTENT-WH",
                "on_hand_qty": 100,
                "on_order_qty": 0,
                "committed_qty": 0,
                "uom": "EA"
            }).execute()

            print("✗ UNEXPECTED: Insert succeeded (FK constraint not enforced?)")

        except Exception as e:
            error_str = str(e).lower()
            if 'foreign key' in error_str or 'violates' in error_str or 'warehouse' in error_str:
                print("✓ EXPECTED: Foreign key constraint enforced")
                print(f"  Error: {str(e)[:100]}...")
            else:
                print(f"? UNCERTAIN: Got error but unclear if FK-related: {e}")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("WAREHOUSE VALIDATION TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.utcnow().isoformat()}")

    # Test 1: Warehouse cache
    codes = test_warehouse_cache()

    # Test 2: Inventory validation (only if warehouse codes loaded)
    if codes:
        test_inventory_validation()

    # Test 3: Database FK constraint
    test_database_foreign_key()

    print("\n" + "="*80)
    print("TEST SUITE COMPLETED")
    print("="*80)
    print(f"Finished at: {datetime.utcnow().isoformat()}")
    print()


if __name__ == "__main__":
    main()
