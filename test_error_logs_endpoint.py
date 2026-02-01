"""
Test script for the /api/v1/error-logs endpoint

This script tests the error log ingestion endpoint according to the protocol
specified in docs/render/RENDER_ERROR_LOGGING_PROTOCOL.md

Usage:
    python test_error_logs_endpoint.py
"""

import json
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8080")
API_KEY = os.getenv("API_KEY")
FULL_URL = f"{INGESTION_URL}/api/v1/error-logs"

print(f"Testing error log endpoint: {FULL_URL}")
print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: NOT SET")

if not API_KEY:
    print("\n❌ ERROR: API_KEY not set in environment variables")
    exit(1)


def test_1_simple_error_log():
    """Test 1: Send a simple error log"""
    print("\n" + "="*80)
    print("TEST 1: Simple Error Log")
    print("="*80)

    payload = {
        "source": "sap-b1-agent",
        "batch_id": "test-batch-001",
        "chunk_index": 0,
        "total_chunks": 1,
        "error_count": 1,
        "errors": [{
            "error_id": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}-001",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "logger": "test.logger",
            "message": "Test error message",
            "location": {
                "file": "test.py",
                "line": 42,
                "function": "test_function",
                "module": "test"
            },
            "exception": {
                "type": "ValueError",
                "message": "Test exception",
                "traceback": "Traceback...",
                "module": "builtins"
            },
            "context": {
                "test_key": "test_value"
            },
            "hostname": "test-server",
            "process_id": 12345,
            "thread_id": 6789
        }]
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }

    print(f"Sending payload with {len(payload['errors'])} error(s)...")

    try:
        response = requests.post(FULL_URL, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"✅ SUCCESS: {result['processed']} error(s) processed")
                return True
            else:
                print(f"❌ FAILED: {result.get('error')}")
                return False
        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False


def test_2_idempotency():
    """Test 2: Test idempotency (send same error twice)"""
    print("\n" + "="*80)
    print("TEST 2: Idempotency (Duplicate Error Handling)")
    print("="*80)

    error_id = f"test-idempotent-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    payload = {
        "source": "sap-b1-agent",
        "batch_id": "test-batch-idempotent",
        "chunk_index": 0,
        "total_chunks": 1,
        "error_count": 1,
        "errors": [{
            "error_id": error_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "logger": "test.logger",
            "message": "Test idempotency",
            "location": {
                "file": "test.py",
                "line": 1,
                "function": "test",
                "module": "test"
            },
            "exception": None,
            "context": {},
            "hostname": "test-server",
            "process_id": 1234,
            "thread_id": 5678
        }]
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }

    try:
        # First request
        print("Sending first request...")
        response1 = requests.post(FULL_URL, json=payload, headers=headers, timeout=10)
        print(f"First Response: {response1.status_code} - {response1.json()}")

        # Second request (same payload)
        print("\nSending second request (duplicate)...")
        response2 = requests.post(FULL_URL, json=payload, headers=headers, timeout=10)
        print(f"Second Response: {response2.status_code} - {response2.json()}")

        # Verify idempotency
        result1 = response1.json()
        result2 = response2.json()

        if response1.status_code == 200 and response2.status_code == 200:
            if result1.get('processed') == 1 and result2.get('processed') == 0:
                print("✅ SUCCESS: Idempotency working (first inserted, second ignored)")
                return True
            else:
                print(f"❌ FAILED: Expected processed=1 then 0, got {result1.get('processed')} then {result2.get('processed')}")
                return False
        else:
            print(f"❌ FAILED: HTTP {response1.status_code} and {response2.status_code}")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False


def test_3_invalid_api_key():
    """Test 3: Test authentication failure"""
    print("\n" + "="*80)
    print("TEST 3: Invalid API Key")
    print("="*80)

    payload = {
        "source": "sap-b1-agent",
        "batch_id": "test-batch-auth",
        "chunk_index": 0,
        "total_chunks": 1,
        "error_count": 1,
        "errors": []
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": "INVALID_KEY_12345"
    }

    try:
        response = requests.post(FULL_URL, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 401:
            print("✅ SUCCESS: Unauthorized (401) as expected")
            return True
        else:
            print(f"❌ FAILED: Expected 401, got {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False


def test_4_multiple_errors():
    """Test 4: Send multiple errors in one batch"""
    print("\n" + "="*80)
    print("TEST 4: Multiple Errors in Batch")
    print("="*80)

    errors = []
    for i in range(5):
        errors.append({
            "error_id": f"test-multi-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR" if i % 2 == 0 else "CRITICAL",
            "logger": "test.multi",
            "message": f"Test error {i}",
            "location": {
                "file": "test.py",
                "line": i,
                "function": "test_multi",
                "module": "test"
            },
            "exception": None,
            "context": {"index": i},
            "hostname": "test-server",
            "process_id": 1234,
            "thread_id": 5678
        })

    payload = {
        "source": "sap-b1-agent",
        "batch_id": "test-batch-multi",
        "chunk_index": 0,
        "total_chunks": 1,
        "error_count": len(errors),
        "errors": errors
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }

    print(f"Sending batch with {len(errors)} errors...")

    try:
        response = requests.post(FULL_URL, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Processed: {result.get('processed')}, Failed: {result.get('failed')}")

        if response.status_code == 200 and result.get('processed') == len(errors):
            print(f"✅ SUCCESS: All {len(errors)} errors processed")
            return True
        else:
            print(f"❌ FAILED: Expected {len(errors)} processed, got {result.get('processed')}")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False


def test_5_missing_fields():
    """Test 5: Test validation of required fields"""
    print("\n" + "="*80)
    print("TEST 5: Missing Required Fields")
    print("="*80)

    # Missing 'source' field
    payload = {
        "batch_id": "test-batch-missing",
        "chunk_index": 0,
        "total_chunks": 1,
        "error_count": 1,
        "errors": []
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }

    try:
        response = requests.post(FULL_URL, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 400:
            print("✅ SUCCESS: Bad Request (400) as expected")
            return True
        else:
            print(f"❌ FAILED: Expected 400, got {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False


# Run all tests
if __name__ == "__main__":
    print("\n" + "="*80)
    print("ERROR LOG ENDPOINT TEST SUITE")
    print("="*80)

    tests = [
        ("Simple Error Log", test_1_simple_error_log),
        ("Idempotency", test_2_idempotency),
        ("Invalid API Key", test_3_invalid_api_key),
        ("Multiple Errors", test_4_multiple_errors),
        ("Missing Fields", test_5_missing_fields),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        exit(1)
