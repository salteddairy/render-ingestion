#!/usr/bin/env python3
"""
Render Deployment Test Script

This script tests the Render ingestion service after deployment.
Run this after completing deployment to verify everything works.

Usage:
    python test_render_deployment.py

Expected: All tests pass with 200 OK responses
"""

import os
import requests
import json
import sys
from cryptography.fernet import Fernet
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration - UPDATE THIS WITH YOUR RENDER URL
RENDER_URL = os.environ.get("RENDER_URL", "https://forecast-ingestion.onrender.com")
API_KEY = os.environ.get("INGESTION_API_KEY", "")
if not API_KEY:
    raise ValueError("INGESTION_API_KEY environment variable not set")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA=")

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_info(text):
    print(f"{YELLOW}ℹ {text}{RESET}")

def test_health_check():
    """Test 1: Health check endpoint"""
    print_header("TEST 1: Health Check Endpoint")

    endpoint = f"{RENDER_URL}/health"
    print_info(f"Testing: {endpoint}")

    try:
        response = requests.get(endpoint, timeout=10)

        if response.status_code == 200:
            data = response.json()
            print_success(f"Health check passed!")
            print(f"  Status: {data.get('status')}")
            print(f"  Service: {data.get('service')}")
            print(f"  Version: {data.get('version')}")
            print(f"  Timestamp: {data.get('timestamp')}")
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"Health check failed with exception: {str(e)}")
        return False

def test_ingestion_endpoint():
    """Test 2: Ingestion endpoint with test data"""
    print_header("TEST 2: Ingestion Endpoint")

    endpoint = f"{RENDER_URL}/api/ingest"
    print_info(f"Testing: {endpoint}")

    # Create test data
    test_payload = {
        "data_type": "warehouses_full",
        "records": [
            {
                "warehouse_code": "DEPLOY01",
                "warehouse_name": "Deployment Test Warehouse",
                "is_active": 1
            }
        ]
    }

    try:
        # Encrypt payload
        cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
        encrypted = cipher.encrypt(json.dumps(test_payload).encode('utf-8'))

        # Send request
        print_info("Sending encrypted test payload...")
        response = requests.post(
            endpoint,
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json={"encrypted_payload": encrypted.decode('utf-8')},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"Ingestion successful!")
            print(f"  Data Type: {data.get('data_type')}")
            print(f"  Records Received: {data.get('records_received')}")
            print(f"  Records Processed: {data.get('records_processed')}")
            print(f"  Records Failed: {data.get('records_failed')}")
            print(f"  Timestamp: {data.get('timestamp')}")
            return True
        else:
            print_error(f"Ingestion failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"Ingestion failed with exception: {str(e)}")
        return False

def test_all_data_types():
    """Test 3: All 8 data types"""
    print_header("TEST 3: All 8 Data Types")

    endpoint = f"{RENDER_URL}/api/ingest"
    cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))

    test_cases = [
        {
            "data_type": "warehouses_full",
            "records": [{"warehouse_code": "W01", "warehouse_name": "Warehouse 1", "is_active": 1}]
        },
        {
            "data_type": "vendors_full",
            "records": [{"vendor_code": "V001", "vendor_name": "Vendor 1", "is_active": 1}]
        },
        {
            "data_type": "items_full",
            "records": [{"item_code": "I001", "item_name": "Item 1", "item_group": "Group A", "is_active": 1}]
        },
        {
            "data_type": "inventory_current_full",
            "records": [{"item_code": "I001", "warehouse_code": "W01", "quantity": 100.0, "unit_price": 25.50}]
        },
        {
            "data_type": "sales_orders_incremental",
            "records": [{
                "order_id": 99999,
                "order_date": "2026-01-27T00:00:00",
                "customer_code": "C001",
                "item_code": "I001",
                "quantity": 10,
                "unit_price": 25.50,
                "line_total": 255.00
            }]
        },
        {
            "data_type": "purchase_orders_incremental",
            "records": [{
                "order_id": 99999,
                "order_date": "2026-01-27T00:00:00",
                "vendor_code": "V001",
                "item_code": "I001",
                "quantity": 100,
                "unit_price": 15.00,
                "line_total": 1500.00
            }]
        },
        {
            "data_type": "costs_incremental",
            "records": [{"item_code": "I001", "avg_cost": 18.50, "last_cost": 19.00, "cost_date": "2026-01-27"}]
        },
        {
            "data_type": "pricing_full",
            "records": [{"item_code": "I001", "price_list": "1", "price": 25.50, "currency": "USD"}]
        }
    ]

    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        try:
            encrypted = cipher.encrypt(json.dumps(test_case).encode('utf-8'))
            response = requests.post(
                endpoint,
                headers={
                    "X-API-Key": API_KEY,
                    "Content-Type": "application/json"
                },
                json={"encrypted_payload": encrypted.decode('utf-8')},
                timeout=30
            )

            if response.status_code == 200:
                print_success(f"Test {i}/8: {test_case['data_type']}")
                passed += 1
            else:
                print_error(f"Test {i}/8: {test_case['data_type']} (Status: {response.status_code})")
                failed += 1

        except Exception as e:
            print_error(f"Test {i}/8: {test_case['data_type']} (Error: {str(e)})")
            failed += 1

    print(f"\n{GREEN if failed == 0 else RED}Results: {passed} passed, {failed} failed out of {len(test_cases)} tests{RESET}")
    return failed == 0

def test_unauthorized_access():
    """Test 4: Unauthorized access (should fail with 401)"""
    print_header("TEST 4: Unauthorized Access (Negative Test)")

    endpoint = f"{RENDER_URL}/api/ingest"
    print_info(f"Testing: {endpoint}")
    print_info("Sending request with INVALID API key...")

    test_payload = {
        "data_type": "warehouses_full",
        "records": [{"warehouse_code": "TEST", "warehouse_name": "Test", "is_active": 1}]
    }

    try:
        cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
        encrypted = cipher.encrypt(json.dumps(test_payload).encode('utf-8'))

        # Send with INVALID API key
        response = requests.post(
            endpoint,
            headers={
                "X-API-Key": "INVALID_KEY_12345",
                "Content-Type": "application/json"
            },
            json={"encrypted_payload": encrypted.decode('utf-8')},
            timeout=10
        )

        if response.status_code == 401:
            print_success("Unauthorized access correctly rejected!")
            return True
        else:
            print_error(f"Security issue: Invalid key was not rejected (Status: {response.status_code})")
            return False

    except Exception as e:
        print_error(f"Test failed with exception: {str(e)}")
        return False

def main():
    """Run all tests"""
    print_header(f"Render Deployment Verification")
    print(f"Service URL: {RENDER_URL}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"Testing Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run all tests
    results = []

    results.append(("Health Check", test_health_check()))
    results.append(("Ingestion Endpoint", test_ingestion_endpoint()))
    results.append(("All 8 Data Types", test_all_data_types()))
    results.append(("Unauthorized Access", test_unauthorized_access()))

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{status} - {test_name}")

    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}")

    if passed == total:
        print(f"\n{GREEN}{'='*70}{RESET}")
        print(f"{GREEN}ALL TESTS PASSED - Deployment is successful!{RESET}")
        print(f"{GREEN}{'='*70}{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{'='*70}{RESET}")
        print(f"{RED}SOME TESTS FAILED - Please check the errors above{RESET}")
        print(f"{RED}{'='*70}{RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
