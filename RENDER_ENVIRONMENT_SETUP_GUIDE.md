# Render Environment Configuration Guide

**Date:** 2026-02-01
**Purpose:** Configure Supabase environment variables in Render dashboard

---

## 🚨 CRITICAL: Database Inserts Currently Failing

**Root Cause:** Supabase Python client is not initialized with authentication key

**Fix Required:** Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to Render environment

---

## Step-by-Step Configuration

### 1. Access Render Dashboard

Navigate to: https://dashboard.render.com

### 2. Select the Ingestion Service

Find and click on: **forecast-ingestion** (or equivalent service name)

### 3. Open Environment Settings

Click on the **"Environment"** tab in the service dashboard

### 4. Add Required Environment Variables

Add the following two environment variables:

#### Variable 1: SUPABASE_URL

**Key:** `SUPABASE_URL`

**Value:** `https://jgqegjvrphjsmdojqwyt.supabase.co`

**Description:** Supabase project URL (from project settings)

#### Variable 2: SUPABASE_SERVICE_ROLE_KEY

**Key:** `SUPABASE_SERVICE_ROLE_KEY`

**Value:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpncWVnanZycGhqc21kb2pxd3l0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczODA4NTc3MCwiZXhwIjoyMDUzNjYxNzcwfQ.QhMvEqTq1hKNpbyj99dQ3tQVZqwFGZX0Uj_WJMeWIM`

**Description:** Supabase service role JWT key (provides admin database access)

**⚠️ SECURITY WARNING:**
- This key bypasses Row Level Security (RLS)
- Keep it secret and never commit to git
- Rotate quarterly

### 5. Save Changes

Click the **"Save Changes"** button

### 6. Wait for Redeployment

Render will automatically redeploy the service with new environment variables

**Estimated time:** 1-2 minutes

### 7. Verify Deployment

After redeployment completes, verify the service is healthy:

```bash
curl https://forecast-ingestion.onrender.com/health \
  -H "X-API-Key: eaHy0NiejpUdFWljWG66zD4hipUEkRhf5rZrIHiLSm0"
```

Expected response:
```json
{
  "service": "forecast-ingestion",
  "status": "healthy"
}
```

---

## Verification Steps

### 1. Check Render Logs for Successful Initialization

After deployment, check logs for this message:

```
Supabase client initialized successfully
```

**If you see this error instead:**
```
SUPABASE_URL environment variable not set
```
or
```
SUPABASE_SERVICE_ROLE_KEY environment variable not set
```

Then the environment variables were not added correctly - go back to step 4.

### 2. Run End-to-End Test

```bash
python test_self_cleaning_e2e.py
```

Expected output:
```json
{
  "records_received": 1,
  "records_processed": 1,  ← Should be 1, not 0!
  "records_failed": 0       ← Should be 0, not 1!
}
```

### 3. Verify Database Insert

Go to Supabase SQL Editor and run:

```sql
SELECT
    item_code,
    warehouse_code,
    on_hand_qty,
    unit_cost,
    updated_at
FROM inventory_current
WHERE item_code = 'PMC01163-VGH'
  AND warehouse_code = '60'
ORDER BY updated_at DESC
LIMIT 1;
```

You should see the test record with `on_hand_qty = 888.88` (or your test value).

---

## Troubleshooting

### Issue: "SUPABASE_SERVICE_ROLE_KEY not set"

**Solution:**
1. Check the exact key name in Render environment
2. Ensure no typos in the key name
3. Ensure no extra spaces before/after the value
4. Try removing and re-adding the variable

### Issue: "Failed to initialize Supabase client"

**Solution:**
1. Verify SUPABASE_URL format: `https://project-ref.supabase.co`
2. Verify SUPABASE_SERVICE_ROLE_KEY is a valid JWT (starts with `eyJhbGci...`)
3. Check Render logs for detailed error message
4. Ensure key is not expired (JWT tokens have expiration)

### Issue: Still getting records_processed=0

**Possible Causes:**
1. Environment variables not applied - wait for full redeploy
2. Wrong key type (using anon key instead of service_role)
3. Key is for different project (URL mismatch)
4. Database permissions issue

**Solution:**
1. Wait 2-3 minutes for full redeploy to complete
2. Check Supabase dashboard → Project Settings → API to confirm key
3. Verify SUPABASE_URL matches your project
4. Check Render logs for detailed error messages

---

## Environment Variable Reference

| Variable | Required | Format | Example |
|----------|----------|--------|---------|
| `SUPABASE_URL` | ✅ Yes | `https://project-ref.supabase.co` | `https://jgqegjvrphjsmdojqwyt.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ Yes | JWT token (starts with `eyJhbGci...`) | See above |
| `DATABASE_URL` | ❌ No | Postgres connection string (legacy, not used) | - |
| `API_KEY` | ✅ Yes | Random 32-char string | `eaHy0NiejpUdFWljWG66zD4hipUEkRhf5rZrIHiLSm0` |
| `ENCRYPTION_KEY` | ✅ Yes | Fernet key (44 chars base64) | `eRsVKRHqzmVEYTqXPknNgon3rFou1ALfhKicAFBomIc=` |

---

## Security Best Practices

### ✅ DO:
- Store keys in Render environment (not in code)
- Use service_role key for backend services
- Rotate keys quarterly
- Monitor for unauthorized access
- Keep backup of keys in secure location

### ❌ DON'T:
- Never commit keys to git
- Never use anon key for backend operations
- Never share service_role_key publicly
- Never log keys or include in error messages
- Never use production keys in development

---

## What Changed

### Code Changes

**File:** `render-ingestion/supabase_client.py`

**Before (Lines 36-47):**
```python
database_url = os.getenv("DATABASE_URL")

if not database_url:
    logger.error("DATABASE_URL environment variable not set")
    raise ValueError("DATABASE_URL environment variable not set")

try:
    _supabase_client = create_client(database_url)  # ← WRONG!
```

**After (Lines 36-60):**
```python
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url:
    logger.error("SUPABASE_URL environment variable not set")
    raise ValueError("SUPABASE_URL environment variable not set")

if not supabase_key:
    logger.error("SUPABASE_SERVICE_ROLE_KEY environment variable not set")
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable not set")

try:
    _supabase_client = create_client(supabase_url, supabase_key)  # ← CORRECT!
```

### Documentation Updates

**File:** `render-ingestion/.env.example`

Added:
- `SUPABASE_URL` environment variable documentation
- `SUPABASE_SERVICE_ROLE_KEY` environment variable documentation
- Security warnings about service_role_key
- Clear explanation of each variable's purpose

---

## Next Steps After Configuration

1. ✅ **Save environment variables** in Render dashboard
2. ✅ **Wait for redeployment** (1-2 minutes)
3. ✅ **Verify health check** returns 200
4. ✅ **Run E2E test** - should see `records_processed: 1`
5. ✅ **Verify database insert** - check Supabase SQL Editor
6. ✅ **Clean up test data** (if needed)
7. 🚀 **PRODUCTION READY** - Begin SAP integration!

---

## Support

**If you encounter issues:**

1. **Check Render logs:** Dashboard → Service → Logs
2. **Check environment variables:** Dashboard → Service → Environment
3. **Verify Supabase credentials:** Supabase Dashboard → Project Settings → API
4. **Review this guide:** Ensure all steps followed correctly

**Useful Commands:**
```bash
# Test health endpoint
curl https://forecast-ingestion.onrender.com/health \
  -H "X-API-Key: eaHy0NiejpUdFWljWG66zD4hipUEkRhf5rZrIHiLSm0"

# Run E2E validation test
python test_self_cleaning_e2e.py
```

---

**Last Updated:** 2026-02-01
**Component:** Render Ingestion Service
**Status:** Ready for configuration
**Estimated Time:** 2 minutes to complete
