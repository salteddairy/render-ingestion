# Render Ingestion Service - Deployment Guide

Complete step-by-step guide for deploying the Render Ingestion Service to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Local Testing](#local-testing)
4. [GitHub Repository Setup](#github-repository-setup)
5. [Render Deployment](#render-deployment)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Integration Testing](#integration-testing)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts

- [ ] Render account (free tier available)
- [ ] GitHub account
- [ ] Supabase account with database

### Required Information

- [ ] Supabase DATABASE_URL
- [ ] API Key: `YOUR_API_KEY_HERE`
- [ ] Encryption Key: `YOUR_ENCRYPTION_KEY_HERE`

### Local Tools

- [ ] Python 3.11+
- [ ] Git
- [ ] Text editor or IDE
- [ ] curl (for testing)

---

## Pre-Deployment Checklist

### 1. Code Review

Verify all files are present:
```bash
cd render-ingestion
ls -la
```

Expected files:
- ✅ app.py
- ✅ handlers.py
- ✅ supabase_client.py
- ✅ requirements.txt
- ✅ Dockerfile
- ✅ render.yaml
- ✅ .env.example
- ✅ README.md

### 2. Environment Variables

Create a local .env file:
```bash
cp .env.example .env
```

Edit .env with your values:
```env
API_KEY=YOUR_API_KEY_HERE
ENCRYPTION_KEY=YOUR_ENCRYPTION_KEY_HERE
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres
LOG_LEVEL=INFO
PORT=8080
```

**IMPORTANT**: Never commit .env to git!

### 3. Supabase Database Setup

Verify your Supabase tables exist:
```sql
-- Check if tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
    'warehouses',
    'vendors',
    'items',
    'inventory_current',
    'sales_orders',
    'purchase_orders',
    'costs',
    'pricing'
);
```

If tables don't exist, create them using the schema from your project documentation.

---

## Local Testing

### Step 1: Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Run Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Expected output: All tests passing
# (Some tests may show 500 status due to no database connection)
```

### Step 3: Start Local Server

```bash
python app.py
```

Expected output:
```
{"timestamp":"2025-01-27T10:30:00.123456","level":"INFO","message":"Encryption cipher initialized successfully","module":"app","function":"<module>"}
 * Running on http://0.0.0.0:8080
```

### Step 4: Test Health Endpoint

Open new terminal:
```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "forecast-ingestion",
  "timestamp": "2025-01-27T10:30:00.123456",
  "version": "1.0.0"
}
```

### Step 5: Test Ingestion Endpoint

Create test script `test_ingestion.py`:
```python
import requests
import json
from cryptography.fernet import Fernet

ENDPOINT = "http://localhost:8080/api/ingest"
API_KEY = "YOUR_API_KEY_HERE"
ENCRYPTION_KEY = "YOUR_ENCRYPTION_KEY_HERE"

test_payload = {
    "data_type": "warehouses_full",
    "records": [
        {
            "warehouse_code": "TEST01",
            "warehouse_name": "Test Warehouse",
            "is_active": 1
        }
    ]
}

cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
encrypted = cipher.encrypt(json.dumps(test_payload).encode('utf-8'))

response = requests.post(
    ENDPOINT,
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={"encrypted_payload": encrypted.decode('utf-8')}
)

print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
```

Run the test:
```bash
python test_ingestion.py
```

Expected output:
```json
{
  "success": true,
  "message": "Data ingested successfully",
  "data_type": "warehouses_full",
  "records_received": 1,
  "records_processed": 1,
  "records_failed": 0,
  "timestamp": "2025-01-27T10:30:15.123456"
}
```

---

## GitHub Repository Setup

### Step 1: Initialize Git

```bash
cd render-ingestion
git init
```

### Step 2: Create .gitignore

Create `.gitignore` file:
```gitignore
# Environment variables
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/

# Logs
*.log
```

### Step 3: Add Files to Git

```bash
git add .
git status
```

Verify `.env` is NOT in the list!

### Step 4: Commit

```bash
git commit -m "Initial commit: Render ingestion service

- Flask app with /api/ingest and /health endpoints
- 8 data type handlers for SAP B1 data
- Supabase integration with retry logic
- Fernet encryption/decryption
- Comprehensive test suite
- Docker and Render deployment configs"
```

### Step 5: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `render-ingestion` (or your preferred name)
3. Description: "Render Ingestion Service for SAP B1 Data"
4. Visibility: Private (recommended)
5. DO NOT initialize with README (we have one)
6. Click **Create repository**

### Step 6: Push to GitHub

```bash
# Add remote (replace with your username)
git remote add origin https://github.com/YOUR-USERNAME/render-ingestion.git

# Push to GitHub
git push -u origin master
```

Verify at: `https://github.com/YOUR-USERNAME/render-ingestion`

---

## Render Deployment

### Option A: Deploy via Render Dashboard (Recommended)

#### Step 1: Create Render Account

1. Go to https://dashboard.render.com
2. Sign up or log in
3. Verify email address

#### Step 2: Create New Web Service

1. Click **New** → **Web Service**
2. Click **Connect GitHub**
3. Authorize Render to access your GitHub account
4. Select the `render-ingestion` repository
5. Click **Connect**

#### Step 3: Configure Service

**Basic Settings:**
- **Name**: `forecast-ingestion`
- **Region**: Oregon (or closest to your users)
- **Branch**: `master`

**Build & Deploy:**
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:app`

#### Step 4: Add Environment Variables

Click **Advanced** → **Add Environment Variable**:

| Key | Value | Sync |
|-----|-------|------|
| `API_KEY` | `YOUR_API_KEY_HERE` | **No** |
| `ENCRYPTION_KEY` | `YOUR_ENCRYPTION_KEY_HERE` | **No** |
| `DATABASE_URL` | Your Supabase connection string | **No** |
| `LOG_LEVEL` | `INFO` | Yes |
| `PORT` | `8080` | Yes |

**IMPORTANT**: Set **Sync = No** for sensitive variables!

#### Step 5: Deploy

1. Review all settings
2. Click **Create Web Service**
3. Wait for deployment (2-3 minutes)
4. Monitor build logs

### Option B: Deploy via render.yaml

1. Ensure `render.yaml` is in your repository root
2. Go to Render Dashboard → **New** → **Blueprint**
3. Connect your GitHub repository
4. Render will automatically read `render.yaml`
5. Review and click **Apply**

---

## Post-Deployment Verification

### Step 1: Check Deployment Status

1. Go to Render Dashboard → Your service
2. Verify status is **"Live"** (green indicator)
3. Note your service URL:
   - Format: `https://forecast-ingestion.onrender.com`
   - Or custom: `https://YOUR-SERVICE-NAME.onrender.com`

### Step 2: Test Health Endpoint

```bash
curl https://YOUR-SERVICE.onrender.com/health
```

Expected response (200 OK):
```json
{
  "status": "healthy",
  "service": "forecast-ingestion",
  "timestamp": "2025-01-27T10:30:00.123456",
  "version": "1.0.0"
}
```

### Step 3: Test Ingestion Endpoint

Update your test script:
```python
ENDPOINT = "https://YOUR-SERVICE.onrender.com/api/ingest"
```

Run the test:
```bash
python test_ingestion.py
```

Expected response:
```json
{
  "success": true,
  "message": "Data ingested successfully",
  "data_type": "warehouses_full",
  "records_received": 1,
  "records_processed": 1,
  "records_failed": 0,
  "timestamp": "2025-01-27T10:30:15.123456"
}
```

### Step 4: Verify Data in Supabase

Go to Supabase Dashboard → Table Editor → `warehouses` table.

Verify test data exists:
- warehouse_code: `TEST01`
- warehouse_name: `Test Warehouse`
- is_active: `true`

---

## Integration Testing

### Test All 8 Data Types

Create comprehensive test script `test_all_types.py`:
```python
import requests
import json
from cryptography.fernet import Fernet

ENDPOINT = "https://YOUR-SERVICE.onrender.com/api/ingest"
API_KEY = "YOUR_API_KEY_HERE"
ENCRYPTION_KEY = "YOUR_ENCRYPTION_KEY_HERE"

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
            "order_id": 12345,
            "order_date": "2025-01-27T00:00:00",
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
            "order_id": 67890,
            "order_date": "2025-01-27T00:00:00",
            "vendor_code": "V001",
            "item_code": "I001",
            "quantity": 100,
            "unit_price": 15.00,
            "line_total": 1500.00
        }]
    },
    {
        "data_type": "costs_incremental",
        "records": [{"item_code": "I001", "avg_cost": 18.50, "last_cost": 19.00, "cost_date": "2025-01-27"}]
    },
    {
        "data_type": "pricing_full",
        "records": [{"item_code": "I001", "price_list": "1", "price": 25.50, "currency": "USD"}]
    }
]

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

    print(f"\nTesting: {test_case['data_type']}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
```

Run the comprehensive test:
```bash
python test_all_types.py
```

All 8 data types should return 200 OK.

---

## Monitoring & Maintenance

### View Logs

1. Go to Render Dashboard → Your service
2. Click **Logs** tab
3. Filter by level: `ERROR`, `WARNING`, `INFO`
4. Search logs: use search box for specific terms

### Set Up Alerts

1. Go to Render Dashboard → Your service
2. Click **Events** → **Alerts**
3. Configure:
   - Service goes down
   - Response time > 5 seconds
   - Error rate > 5%

### Health Monitoring

Create a monitoring script `monitor_service.py`:
```python
import requests
import time
from datetime import datetime

ENDPOINT = "https://YOUR-SERVICE.onrender.com/health"

def check_health():
    try:
        response = requests.get(ENDPOINT, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"[{datetime.now()}] Status: {data['status']}")
            return True
        else:
            print(f"[{datetime.now()}] ERROR: Status code {response.status_code}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] ERROR: {str(e)}")
        return False

# Check every 5 minutes
while True:
    check_health()
    time.sleep(300)
```

### Database Monitoring

Monitor Supabase:
1. Go to Supabase Dashboard → Database
2. Check **Database size**
3. Monitor **Query performance**
4. Review **Recent queries**

---

## Troubleshooting

### Issue 1: Service Won't Start

**Symptoms:**
- Deployment fails
- Service status: "Deploy failed"

**Solutions:**
1. Check build logs in Render Dashboard
2. Verify all dependencies in `requirements.txt`
3. Check for syntax errors in Python files
4. Ensure `gunicorn` is in requirements.txt

### Issue 2: Health Check Returns 404

**Symptoms:**
- `/health` endpoint returns 404

**Solutions:**
1. Verify service is fully deployed (check logs)
2. Wait 1-2 minutes for service to start
3. Check PORT environment variable is set to 8080
4. Review Render logs for startup errors

### Issue 3: Decryption Failed

**Symptoms:**
- Response: `{"success": false, "error": "Decryption failed: ..."}`

**Solutions:**
1. Verify ENCRYPTION_KEY matches SAP Agent exactly
2. Check for extra spaces or special characters in key
3. Ensure key is not base64 decoded (use as-is)
4. Test encryption/decryption locally

### Issue 4: Unauthorized (401)

**Symptoms:**
- Response: `{"success": false, "error": "Unauthorized"}`

**Solutions:**
1. Verify X-API-Key header is being sent
2. Check API_KEY environment variable in Render
3. Ensure key matches exactly: `YOUR_API_KEY_HERE`

### Issue 5: Database Connection Failed

**Symptoms:**
- Logs show database connection errors
- 500 errors on ingestion

**Solutions:**
1. Verify DATABASE_URL is correct
2. Check Supabase database status
3. Ensure Supabase allows connections from Render IPs
4. Test connection string locally:
```bash
psql $DATABASE_URL -c "SELECT 1"
```

### Issue 6: High Memory Usage

**Symptoms:**
- Service crashes or restarts frequently
- Render shows high memory usage

**Solutions:**
1. Reduce number of gunicorn workers (try 2 instead of 4)
2. Implement batch size limits
3. Add memory monitoring
4. Upgrade Render plan if needed

---

## Security Checklist

### Pre-Production
- [ ] Change API_KEY from default (if desired)
- [ ] Rotate ENCRYPTION_KEY (if desired)
- [ ] Enable HTTPS (automatic on Render)
- [ ] Set up rate limiting
- [ ] Configure firewall rules in Supabase

### Post-Deployment
- [ ] Monitor logs for unauthorized access
- [ ] Set up alerting for suspicious activity
- [ ] Review access logs regularly
- [ ] Test backup/restore procedures

---

## Next Steps

After successful deployment:

1. **Update SAP Agent Configuration**
   - Set ingestion endpoint to Render URL
   - Verify encryption key matches
   - Test agent connection

2. **Schedule Data Ingestion**
   - Configure SAP Agent schedules (see spec)
   - Verify data is flowing
   - Monitor first few runs

3. **Set Up Monitoring**
   - Configure Render alerts
   - Set up external monitoring (e.g., Pingdom)
   - Create alert dashboards

4. **Document for Team**
   - Share service URL and API key
   - Document troubleshooting procedures
   - Create runbook for common issues

---

## Success Criteria

✅ Service deployed and accessible via HTTPS
✅ Health check returns 200 OK
✅ All 8 data types tested successfully
✅ Data appears in Supabase database
✅ Logs show no errors
✅ SAP Agent can send data successfully

---

**Last Updated**: 2026-01-27
**Version**: 1.0.0
**Status**: Production Ready
