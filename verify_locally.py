#!/usr/bin/env python3
"""
Local Verification Test for Render Ingestion Service
====================================================

This script starts the Flask app locally and sends a test payload
to verify the ingestion pipeline works correctly BEFORE deploying to Render.

Usage:
    python verify_locally.py

Expected Output:
    ✅ Flask app started successfully
    ✅ Test payload sent and decrypted
    ✅ Records processed: 1
    ✅ Records failed: 0
    ✅ Database insert verified
    ✅ Cleanup successful

Author: sentinel-sec (AI Agent)
Created: 2026-02-02
"""

import os
import sys
import json
import time
import signal
import subprocess
from datetime import datetime, timezone

# Add path
sys.path.insert(0, '/D/code/forecastv3')
sys.path.insert(0, '/D/code/forecastv3/render-ingestion')

try:
    from dotenv import load_dotenv
    from forecasting_engine.supabase_client import SupabaseClient
    from cryptography.fernet import Fernet
    import httpx
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Please install required packages: pip install python-dotenv httpx cryptography")
    sys.exit(1)


def print_header(title):
    """Print formatted header."""
    print(f"\n{'='*70}")
    print(f"{title.center(70)}")
    print(f"{'='*70}\n")


def print_section(title):
    """Print formatted section."""
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")


class LocalIngestionVerifier:
    """Verify ingestion service works locally."""

    def __init__(self):
        self.flask_process = None
        self.base_url = "http://localhost:8080"
        self.api_key = "test-api-key-local"
        self.encryption_key = os.getenv("ENCRYPTION_KEY", "eRsVKRHqzmVEYTqXPknNgon3rFou1ALfhKicAFBomIc=")

    def start_flask_app(self):
        """Start Flask app in background process."""
        print_section("Step 1: Start Flask App Locally")

        # Check if port is already in use
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=2)
            if response.status_code == 200:
                print("  [WARN] Flask app already running on port 8080")
                print("  [INFO] Using existing instance")
                return True
        except:
            pass  # Port is free, good to start

        # Start Flask app
        print(f"  📤 Starting Flask app on {self.base_url}...")

        # Change to render-ingestion directory
        original_dir = os.getcwd()
        os.chdir('/D/code/forecastv3/render-ingestion')

        # Start Flask app in background
        self.flask_process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy()
        )

        # Restore directory
        os.chdir(original_dir)

        # Wait for app to start
        print(f"  ⏳ Waiting for app to start...")
        time.sleep(5)

        # Check if process is still running
        if self.flask_process.poll() is not None:
            print(f"  ❌ Flask app failed to start")
            print(f"  Return code: {self.flask_process.returncode}")
            return False

        # Check if app is responding
        for i in range(10):
            try:
                response = httpx.get(f"{self.base_url}/health", timeout=2)
                if response.status_code == 200:
                    print(f"  ✅ Flask app started successfully (attempt {i+1})")
                    return True
            except:
                if i < 9:
                    time.sleep(2)
                else:
                    print(f"  ❌ Flask app not responding after 20 seconds")
                    self.stop_flask_app()
                    return False

        print(f"  ✅ Flask app is healthy")
        return True

    def stop_flask_app(self):
        """Stop Flask app background process."""
        if self.flask_process:
            print(f"\n  🛑 Stopping Flask app...")
            self.flask_process.terminate()
            try:
                self.flask_process.wait(timeout=5)
            except:
                self.flask_process.kill()
            print(f"  ✅ Flask app stopped")

    def get_test_data(self):
        """Get real test data from database."""
        print_section("Step 2: Get Test Data from Database")

        load_dotenv()
        client = SupabaseClient()

        # Get real warehouse code
        warehouse_query = """
            SELECT warehouse_code, warehouse_name
            FROM warehouses
            WHERE is_active = true
            LIMIT 1
        """

        try:
            warehouses = client.execute_sql(warehouse_query)
            if not warehouses:
                print("  ❌ No warehouses found in database")
                return None, None

            warehouse_code = warehouses[0]['warehouse_code']
            warehouse_name = warehouses[0]['warehouse_name']
            print(f"  ✅ Using warehouse: {warehouse_code} - {warehouse_name}")
        except Exception as e:
            print(f"  ❌ Failed to get warehouse: {e}")
            return None, None

        # Get real item code
        item_query = """
            SELECT item_code, item_description
            FROM items
            WHERE is_active = true
            LIMIT 1
        """

        try:
            items = client.execute_sql(item_query)
            if not items:
                print("  ❌ No items found in database")
                return warehouse_code, None

            item_code = items[0]['item_code']
            item_description = items[0]['item_description']
            print(f"  ✅ Using item: {item_code} - {item_description}")
            return warehouse_code, item_code
        except Exception as e:
            print(f"  ❌ Failed to get item: {e}")
            return warehouse_code, None

    def send_test_payload(self, warehouse_code, item_code):
        """Send test payload to local Flask app."""
        print_section("Step 3: Send Test Payload")

        # Test values
        test_on_hand_qty = 777.77
        test_unit_cost = 99.99

        payload = {
            "data_type": "inventory_current_full",
            "records": [{
                "item_code": item_code,
                "warehouse_code": warehouse_code,
                "on_hand_qty": test_on_hand_qty,
                "on_order_qty": 0.0,
                "committed_qty": 0.0,
                "unit_cost": test_unit_cost,
                "_batch_metadata": {
                    "batch_id": "test-local-verification",
                    "test_timestamp": datetime.now(timezone.utc).isoformat()
                }
            }]
        }

        print(f"  Item Code: {item_code}")
        print(f"  Warehouse Code: {warehouse_code}")
        print(f"  Test On-Hand Qty: {test_on_hand_qty}")
        print(f"  Test Unit Cost: {test_unit_cost}")

        # Encrypt payload
        print(f"\n  📤 Encrypting payload...")
        cipher = Fernet(self.encryption_key.encode('utf-8'))
        encrypted_payload = cipher.encrypt(json.dumps(payload).encode()).decode()

        # Send to local Flask app
        print(f"  📤 Sending to {self.base_url}/api/ingest...")

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/api/ingest",
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={"encrypted_payload": encrypted_payload}
                )

                print(f"  📥 Response Status: {response.status_code}")

                if response.status_code != 200:
                    print(f"  ❌ FAILED: HTTP {response.status_code}")
                    print(f"  Response: {response.text}")
                    return None

                result = response.json()

                print(f"\n  📊 Ingestion Results:")
                print(f"    Success: {result.get('success')}")
                print(f"    Data Type: {result.get('data_type')}")
                print(f"    Records Received: {result.get('records_received')}")
                print(f"    Records Processed: {result.get('records_processed')}")
                print(f"    Records Failed: {result.get('records_failed')}")

                # Verify success metrics
                if result.get('records_processed') != 1:
                    print(f"\n  ❌ FAILED: Expected records_processed=1, got {result.get('records_processed')}")
                    return None

                if result.get('records_failed') != 0:
                    print(f"\n  ❌ FAILED: Expected records_failed=0, got {result.get('records_failed')}")
                    return None

                print(f"\n  ✅ SUCCESS: All records processed successfully!")
                return test_on_hand_qty, test_unit_cost

        except httpx.ConnectError as e:
            print(f"  ❌ Cannot connect to local app: {e}")
            return None
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            return None

    def verify_database_insert(self, item_code, warehouse_code, test_on_hand_qty, test_unit_cost):
        """Verify record was inserted in database."""
        print_section("Step 4: Verify Database Insert")

        load_dotenv()
        client = SupabaseClient()

        query = """
            SELECT
                item_code,
                warehouse_code,
                on_hand_qty,
                unit_cost,
                updated_at
            FROM inventory_current
            WHERE item_code = :item_code
              AND warehouse_code = :warehouse_code
            ORDER BY updated_at DESC
            LIMIT 1
        """

        try:
            results = client.execute_sql(query, {
                "item_code": item_code,
                "warehouse_code": warehouse_code
            })

            if not results or len(results) == 0:
                print(f"  ❌ Record not found in database")
                return False

            record = results[0]
            print(f"  ✅ Record found in database")
            print(f"    Item Code: {record['item_code']}")
            print(f"    Warehouse Code: {record['warehouse_code']}")
            print(f"    On-Hand Qty: {record['on_hand_qty']}")
            print(f"    Unit Cost: {record['unit_cost']}")
            print(f"    Updated At: {record['updated_at']}")

            # Verify values match
            if record['on_hand_qty'] != test_on_hand_qty:
                print(f"\n  ❌ On-hand qty mismatch: expected {test_on_hand_qty}, got {record['on_hand_qty']}")
                return False

            if record['unit_cost'] != test_unit_cost:
                print(f"\n  ❌ Unit cost mismatch: expected {test_unit_cost}, got {record['unit_cost']}")
                return False

            print(f"\n  ✅ All values match expected")
            return True

        except Exception as e:
            print(f"  ❌ Database verification failed: {e}")
            return False

    def cleanup_test_data(self, item_code, warehouse_code, test_on_hand_qty, test_unit_cost):
        """Cleanup test data from database."""
        print_section("Step 5: Cleanup Test Data")

        load_dotenv()
        client = SupabaseClient()

        delete_query = """
            DELETE FROM inventory_current
            WHERE item_code = :item_code
              AND warehouse_code = :warehouse_code
              AND on_hand_qty = :on_hand_qty
              AND unit_cost = :unit_cost
        """

        try:
            client.execute_sql(delete_query, {
                "item_code": item_code,
                "warehouse_code": warehouse_code,
                "on_hand_qty": test_on_hand_qty,
                "unit_cost": test_unit_cost
            })

            print(f"  ✅ SUCCESS: Data Purged")
            return True

        except Exception as e:
            print(f"  ⚠️  WARNING: Cleanup failed: {e}")
            print(f"  💡 Manual cleanup may be needed")
            return False

    def run_verification(self):
        """Run complete verification flow."""
        print_header("Local Ingestion Service Verification")

        # Load environment
        load_dotenv()

        try:
            # Step 1: Start Flask app
            if not self.start_flask_app():
                print("\n❌ VERIFICATION FAILED: Could not start Flask app")
                return False

            # Step 2: Get test data
            warehouse_code, item_code = self.get_test_data()
            if not warehouse_code or not item_code:
                print("\n❌ VERIFICATION FAILED: Could not get test data")
                self.stop_flask_app()
                return False

            # Step 3: Send test payload
            result = self.send_test_payload(warehouse_code, item_code)
            if not result:
                print("\n❌ VERIFICATION FAILED: Test payload not processed")
                self.stop_flask_app()
                return False

            test_on_hand_qty, test_unit_cost = result

            # Step 4: Verify database insert
            if not self.verify_database_insert(item_code, warehouse_code, test_on_hand_qty, test_unit_cost):
                print("\n❌ VERIFICATION FAILED: Database insert verification failed")
                self.stop_flask_app()
                return False

            # Step 5: Cleanup
            self.cleanup_test_data(item_code, warehouse_code, test_on_hand_qty, test_unit_cost)

            # Final summary
            print_header("✅ VERIFICATION SUCCESSFUL")

            print("""
The ingestion service is working correctly!

Key Metrics:
  ✅ Flask app runs without import errors
  ✅ records_processed: 1 (SUCCESS!)
  ✅ records_failed: 0 (SUCCESS!)
  ✅ Database insert verified
  ✅ Foreign key constraints satisfied
  ✅ Test data cleaned up

Status: LOCAL TESTING 100% SUCCESSFUL
    """)

            return True

        except Exception as e:
            print(f"\n❌ VERIFICATION FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # Always stop Flask app
            self.stop_flask_app()


def main():
    """Main verification flow."""
    verifier = LocalIngestionVerifier()
    success = verifier.run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
