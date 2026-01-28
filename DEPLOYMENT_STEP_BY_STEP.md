# Render Ingestion Service - Step-by-Step Deployment Guide

**Date:** 2026-01-27
**Repository:** https://github.com/salteddairy/render-ingestion
**Service Type:** Flask Web Service (Python 3)
**Objective:** Deploy production-ready ingestion service for SAP B1 data

---

## ✅ COMPLETED STEPS

### 1. GitHub Repository Created
- ✅ Repository URL: https://github.com/salteddairy/render-ingestion
- ✅ All code pushed to master branch
- ✅ Contains all necessary files (app.py, handlers.py, Dockerfile, render.yaml, etc.)

---

## 🔧 MANUAL DEPLOYMENT STEPS

### Step 2: Access Render Dashboard

1. **Go to Render Dashboard:**
   - URL: https://dashboard.render.com
   - Log in with your account

2. **Navigate to New Service:**
   - Click **"New"** button (top right)
   - Select **"Web Service"**

---

### Step 3: Connect GitHub Repository

1. **Connect GitHub:**
   - If prompted, click **"Connect GitHub"**
   - Authorize Render to access your GitHub account
   - Search for repository: `render-ingestion`
   - Owner: `salteddairy`
   - Click **"Connect"**

---

### Step 4: Configure Web Service

**Basic Settings:**
- **Name:** `forecast-ingestion`
- **Region:** Oregon (or closest to your users)
- **Branch:** `master`
- **Root Directory:** `.` (leave empty for root)

**Build & Deploy Settings:**
- **Environment:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:app`

---

### Step 5: Add Environment Variables

**CRITICAL:** These must be added BEFORE clicking "Deploy"

Click **"Advanced"** → **"Add Environment Variable"**

Add these variables:

| Key | Value | Sync | Note |
|-----|-------|------|------|
| `API_KEY` | `BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM` | **No** | Authentication key for SAP Agent |
| `ENCRYPTION_KEY` | `RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA=` | **No** | Fernet encryption key |
| `DATABASE_URL` | `postgresql://postgres:FV3_SafePass2026!Migration@db.jgqegjvrphjsmdojqwyt.supabase.co:6543/postgres` | **No** | Supabase connection string |
| `LOG_LEVEL` | `INFO` | Yes | Logging level |
| `PORT` | `8080` | Yes | Application port |

**IMPORTANT:**
- Set **Sync = No** for sensitive variables (API_KEY, ENCRYPTION_KEY, DATABASE_URL)
- This prevents them from being pulled from git or displayed in logs

---

### Step 6: Deploy Service

1. **Review Configuration:**
   - Double-check all settings
   - Verify environment variables are correct
   - Ensure service name is `forecast-ingestion`

2. **Create Service:**
   - Click **"Create Web Service"** button
   - Render will automatically deploy from GitHub

3. **Monitor Deployment:**
   - Watch the deployment logs in real-time
   - Wait for "Deploy succeeded" message
   - This typically takes 2-3 minutes

---

### Step 7: Note Your Service URL

After successful deployment, Render will provide:
- **Service URL:** `https://forecast-ingestion.onrender.com`
- **Or custom URL:** `https://forecast-ingestion-XXXX.onrender.com`

**Copy this URL** - you'll need it for testing and SAP Agent configuration.

---

## ✅ POST-DEPLOYMENT VERIFICATION

### Step 8: Test Health Check Endpoint

**Using curl:**
```bash
curl https://forecast-ingestion.onrender.com/health
```

**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "forecast-ingestion",
  "timestamp": "2026-01-27T...",
  "version": "1.0.0"
}
```

**If successful:** The service is running and ready to receive data.

---

### Step 9: Test Ingestion Endpoint

Create a test file `test_render_deployment.py`:

```python
import requests
import json
from cryptography.fernet import Fernet

# Configuration
ENDPOINT = "https://forecast-ingestion.onrender.com/api/ingest"
API_KEY = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
ENCRYPTION_KEY = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="

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

# Encrypt payload
cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
encrypted = cipher.encrypt(json.dumps(test_payload).encode('utf-8'))

# Send request
print("Sending test request to Render...")
response = requests.post(
    ENDPOINT,
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={"encrypted_payload": encrypted.decode('utf-8')}
)

print(f"\nStatus Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 200:
    print("\n✅ SUCCESS: Service is working correctly!")
else:
    print(f"\n❌ ERROR: Service returned {response.status_code}")
```

**Run the test:**
```bash
python test_render_deployment.py
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Data ingested successfully",
  "data_type": "warehouses_full",
  "records_received": 1,
  "records_processed": 1,
  "records_failed": 0,
  "timestamp": "2026-01-27T..."
}
```

---

### Step 10: Verify Data in Supabase

**Option 1: Via psql:**
```bash
psql "postgresql://postgres:FV3_SafePass2026!Migration@db.jgqegjvrphjsmdojqwyt.supabase.co:6543/postgres" -c "SELECT * FROM warehouses WHERE warehouse_code = 'DEPLOY01';"
```

**Option 2: Via Supabase Dashboard:**
1. Go to https://app.supabase.com
2. Select your project
3. Go to **Table Editor** → **warehouses**
4. Look for `warehouse_code = 'DEPLOY01'`

**Expected Result:**
- warehouse_code: `DEPLOY01`
- warehouse_name: `Deployment Test Warehouse`
- is_active: `true`

---

### Step 11: Test All 8 Data Types (Optional but Recommended)

Create comprehensive test script `test_all_data_types.py`:

```python
import requests
import json
from cryptography.fernet import Fernet

ENDPOINT = "https://forecast-ingestion.onrender.com/api/ingest"
API_KEY = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
ENCRYPTION_KEY = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="
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

print("Testing all 8 data types...\n")
passed = 0
failed = 0

for test_case in test_cases:
    encrypted = cipher.encrypt(json.dumps(test_case).encode('utf-8'))
    response = requests.post(
        ENDPOINT,
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json={"encrypted_payload": encrypted.decode('utf-8')}
    )

    status = "✅ PASS" if response.status_code == 200 else "❌ FAIL"
    print(f"{status} - {test_case['data_type']}: {response.status_code}")

    if response.status_code == 200:
        passed += 1
    else:
        failed += 1
        print(f"  Error: {response.json()}")

print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print(f"{'='*60}")
```

**Run comprehensive test:**
```bash
python test_all_data_types.py
```

**Expected Result:**
```
Testing all 8 data types...

✅ PASS - warehouses_full: 200
✅ PASS - vendors_full: 200
✅ PASS - items_full: 200
✅ PASS - inventory_current_full: 200
✅ PASS - sales_orders_incremental: 200
✅ PASS - purchase_orders_incremental: 200
✅ PASS - costs_incremental: 200
✅ PASS - pricing_full: 200

============================================================
Results: 8 passed, 0 failed out of 8 tests
============================================================
```

---

## 📊 MONITORING & LOGS

### View Logs in Render Dashboard

1. Go to: https://dashboard.render.com
2. Select service: `forecast-ingestion`
3. Click **"Logs"** tab
4. Filter by:
   - `ERROR` - Critical errors
   - `WARNING` - Warnings
   - `INFO` - Informational messages

### Key Metrics to Monitor

- **Request rate:** Check number of incoming requests
- **Response time:** Should be < 2 seconds
- **Success rate:** Should be > 95%
- **Error rate:** Should be < 5%
- **Database connections:** Monitor Supabase pool

### Set Up Alerts (Recommended)

1. Go to service dashboard → **Events** → **Alerts**
2. Configure alerts for:
   - Service goes down
   - Response time > 5 seconds
   - Error rate > 5%

---

## 🔧 TROUBLESHOOTING

### Issue 1: Deployment Fails

**Symptoms:**
- Build fails during deployment
- Error in build logs

**Solutions:**
1. Check build logs in Render dashboard
2. Verify `requirements.txt` has correct versions
3. Check for syntax errors in Python files
4. Ensure `gunicorn` is in requirements.txt (it is)

**Debug:**
```bash
# Test locally
pip install -r requirements.txt
python app.py
```

---

### Issue 2: Health Check Returns 404 or 500

**Symptoms:**
- `/health` endpoint returns 404 or 500

**Solutions:**
1. Wait 1-2 minutes for service to fully start
2. Check Render logs for startup errors
3. Verify PORT environment variable is set to `8080`
4. Ensure gunicorn workers started successfully

**Debug:**
```bash
# Check logs
curl https://forecast-ingestion.onrender.com/health -v
```

---

### Issue 3: Unauthorized (401)

**Symptoms:**
- Response: `{"success": false, "error": "Unauthorized"}`

**Solutions:**
1. Verify `API_KEY` environment variable is set correctly in Render
2. Check `X-API-Key` header matches exactly: `BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM`
3. Ensure no extra spaces in API key

**Debug:**
```python
import requests
response = requests.post(
    "https://forecast-ingestion.onrender.com/api/ingest",
    headers={"X-API-Key": "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"}
)
print(response.status_code)
```

---

### Issue 4: Decryption Failed

**Symptoms:**
- Response: `{"success": false, "error": "Decryption failed: ..."}`

**Solutions:**
1. Verify `ENCRYPTION_KEY` matches SAP Agent exactly
2. Check for extra spaces or special characters
3. Ensure key is NOT base64 decoded (use as-is)
4. Test encryption/decryption locally

**Debug:**
```python
from cryptography.fernet import Fernet
import json

ENCRYPTION_KEY = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="
cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))

# Test encryption/decryption
test_data = {"test": "data"}
encrypted = cipher.encrypt(json.dumps(test_data).encode('utf-8'))
decrypted = cipher.decrypt(encrypted)
print("Decryption working:", json.loads(decrypted.decode('utf-8')))
```

---

### Issue 5: Database Connection Failed

**Symptoms:**
- Logs show database connection errors
- 500 errors on ingestion endpoint

**Solutions:**
1. Verify `DATABASE_URL` is correct in Render environment
2. Test Supabase connection locally:
   ```bash
   psql "postgresql://postgres:FV3_SafePass2026!Migration@db.jgqegjvrphjsmdojqwyt.supabase.co:6543/postgres" -c "SELECT 1"
   ```
3. Check Supabase dashboard for service status
4. Ensure Supabase allows connections from Render IPs

---

### Issue 6: High Memory Usage

**Symptoms:**
- Service crashes or restarts frequently
- Render shows high memory usage

**Solutions:**
1. Reduce number of gunicorn workers (try 2 instead of 4)
2. Update start command in Render:
   ```
   gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app
   ```
3. Implement batch size limits
4. Consider upgrading Render plan

---

## 📝 NEXT STEPS FOR SAP MIDDLEWARE TEAM

### 1. Update SAP Agent Configuration

**New Endpoint Configuration:**
```python
# SAP Agent configuration
INGESTION_ENDPOINT = "https://forecast-ingestion.onrender.com/api/ingest"
API_KEY = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
ENCRYPTION_KEY = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="
```

**Request Format:**
```python
import requests
from cryptography.fernet import Fernet
import json

cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))

payload = {
    "data_type": "warehouses_full",
    "records": [...]
}

encrypted = cipher.encrypt(json.dumps(payload).encode('utf-8'))

response = requests.post(
    INGESTION_ENDPOINT,
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={"encrypted_payload": encrypted.decode('utf-8')}
)
```

---

### 2. Test Data Samples

**Minimum Test Data:**
- Send 1 record for each of 8 data types
- Verify response is 200 OK
- Check Supabase for data persistence

**Recommended Test Load:**
- 100-1000 records per data type
- Test batch processing
- Monitor response times

---

### 3. Configure Data Schedules

**8 Data Type Schedules:**

| Data Type | Frequency | Schedule (UTC) |
|-----------|-----------|----------------|
| warehouses_full | Daily | 8:00 AM |
| vendors_full | Daily | 8:00 AM |
| items_full | Daily | 8:30 AM |
| inventory_current_full | Every 6 hours | 00:00, 06:00, 12:00, 18:00 |
| sales_orders_incremental | Every 4 hours | 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 |
| purchase_orders_incremental | Every 4.5 hours | 00:30, 04:30, 08:30, 12:30, 16:30, 20:30 |
| costs_incremental | Daily | 9:00 AM |
| pricing_full | Weekly | Sunday 10:00 AM |

---

### 4. Monitoring Instructions

**Key Metrics:**
- Ingestion success rate (should be > 95%)
- Processing time per data type
- Error rate by data type
- Database connection pool status

**Alerting:**
- Set up alerts for failure rates > 5%
- Monitor Render logs for errors
- Check Supabase for data quality

---

## ✅ DEPLOYMENT SUCCESS CHECKLIST

After completing all steps, verify:

- [ ] Service deployed successfully to Render
- [ ] Health check returns 200 OK
- [ ] Ingestion endpoint accepts POST requests
- [ ] Test data appears in Supabase
- [ ] All 8 data types tested successfully
- [ ] Environment variables configured correctly
- [ ] Logs show no errors
- [ ] Response time < 2 seconds
- [ ] SAP Agent can send data successfully
- [ ] Monitoring and alerting configured

---

## 📄 SUPPORT INFORMATION

**Render Dashboard:**
- URL: https://dashboard.render.com
- Service Name: forecast-ingestion
- Service URL: https://forecast-ingestion.onrender.com

**Supabase Dashboard:**
- URL: https://app.supabase.com
- Host: db.jgqegjvrphjsmdojqwyt.supabase.co
- Port: 6543
- Database: postgres

**GitHub Repository:**
- URL: https://github.com/salteddairy/render-ingestion
- Branch: master

**Documentation:**
- README: https://github.com/salteddairy/render-ingestion/blob/master/README.md
- Deployment Guide: https://github.com/salteddairy/render-ingestion/blob/master/RENDER_INGESTION_DEPLOYMENT.md
- Endpoint Spec: D:\code\forecastv3\SAP_AGENT_RENDER_ENDPOINT_SPEC.md

---

**Last Updated:** 2026-01-27
**Status:** Ready for Manual Deployment
**Version:** 1.0.0
