# Render Ingestion Service

Production-ready Flask service for receiving encrypted SAP B1 data from the SAP Agent middleware and storing it in Supabase.

## Architecture

```
SAP Business One → SAP Agent → Render Ingestion → Supabase → Forecasting Jobs
```

## Features

- ✅ Fernet encryption for secure data transfer
- ✅ API key authentication
- ✅ Support for 8 SAP data types
- ✅ Batch processing with metadata tracking
- ✅ Retry logic for transient failures
- ✅ Structured JSON logging
- ✅ Health check endpoint
- ✅ Comprehensive test suite
- ✅ Docker containerization
- ✅ Render deployment ready

## Supported Data Types

| Data Type | Description | Frequency |
|-----------|-------------|-----------|
| `warehouses_full` | Complete warehouse list | Daily (8:00 AM UTC) |
| `vendors_full` | Complete vendor list | Daily (8:00 AM UTC) |
| `items_full` | Complete item catalog | Daily (8:30 AM UTC) |
| `inventory_current_full` | Current inventory levels | Every 6 hours |
| `sales_orders_incremental` | Sales orders (last 24h) | Every 4 hours |
| `purchase_orders_incremental` | Purchase orders (last 48h) | Every 4.5 hours |
| `costs_incremental` | Item costs (last 7 days) | Daily (9:00 AM UTC) |
| `pricing_full` | Complete pricing data | Weekly (Sunday 10:00 AM UTC) |

## Prerequisites

- Python 3.11+
- Supabase account and database
- Render account (for deployment)
- Git

## Local Development

### 1. Clone and Setup

```bash
# Clone repository
git clone <your-repo-url>
cd render-ingestion

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your values
# Required variables:
# - API_KEY: BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM
# - ENCRYPTION_KEY: RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA=
# - DATABASE_URL: Your Supabase PostgreSQL connection string
```

### 3. Run Locally

```bash
# Start Flask development server
python app.py
```

The service will be available at `http://localhost:8080`

### 4. Test Health Check

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

## Testing

### Run All Tests

```bash
# Run pytest
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Manual Test Script

```python
import requests
import json
from cryptography.fernet import Fernet

# Configuration
ENDPOINT = "http://localhost:8080/api/ingest"
API_KEY = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
ENCRYPTION_KEY = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="

# Create test data
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

# Encrypt payload
cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
encrypted = cipher.encrypt(json.dumps(test_payload).encode('utf-8'))

# Send request
response = requests.post(
    ENDPOINT,
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={"encrypted_payload": encrypted.decode('utf-8')}
)

# Display results
print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
```

## Deployment to Render

### 1. Prepare GitHub Repository

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Render ingestion service"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/your-username/your-repo.git

# Push to GitHub
git push -u origin master
```

### 2. Deploy via Render Dashboard

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure deployment:
   - **Name**: forecast-ingestion
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:app`
5. Add environment variables (see section below)
6. Click **Deploy Web Service**

### 3. Set Environment Variables in Render

Go to your service dashboard → **Environment** tab and add:

```
API_KEY=BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM
ENCRYPTION_KEY=RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA=
DATABASE_URL=postgresql://postgres:[password]@[host]:5432/postgres
LOG_LEVEL=INFO
```

**Important**: Select **"Sync" = false** for sensitive variables to prevent them from being pulled from git.

### 4. Verify Deployment

```bash
# Test health check
curl https://forecast-ingestion.onrender.com/health

# Should return 200 OK with health status
```

## API Documentation

### POST /api/ingest

Main endpoint for receiving SAP Agent data.

**Headers:**
```
X-API-Key: BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM
Content-Type: application/json
```

**Request Body:**
```json
{
  "encrypted_payload": "gAAAAABl...base64_fernet_token..."
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Data ingested successfully",
  "data_type": "warehouses_full",
  "records_received": 1000,
  "records_processed": 1000,
  "records_failed": 0,
  "timestamp": "2025-01-27T10:30:15.123456+00:00"
}
```

**Error Response (401):**
```json
{
  "success": false,
  "error": "Unauthorized"
}
```

### GET /health

Health check endpoint for monitoring.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "forecast-ingestion",
  "timestamp": "2025-01-27T10:30:00.123456+00:00",
  "version": "1.0.0"
}
```

## Troubleshooting

### Common Issues

**1. Decryption Failed**
- Cause: Incorrect encryption key
- Solution: Verify ENCRYPTION_KEY matches SAP Agent exactly

**2. Unauthorized (401)**
- Cause: Missing or incorrect API key
- Solution: Verify X-API-Key header matches expected value

**3. Database Connection Failed**
- Cause: Supabase connection issue
- Solution: Verify DATABASE_URL, check Supabase status

**4. Service Not Responding**
- Cause: Service crashed or not started
- Solution: Check Render logs, verify PORT variable

### Logs

View logs in Render dashboard:
- Your service → **Logs** tab
- Filter by: `ERROR`, `WARNING`, `INFO`

### Monitoring

Key metrics to track:
- Request rate (requests per minute)
- Processing time per data type
- Success rate (success / total requests)
- Error rate by data type

## Security Best Practices

✅ Always use HTTPS in production
✅ Rotate API keys periodically (monthly recommended)
✅ Implement rate limiting to prevent abuse
✅ Log all access with IP addresses and timestamps
✅ Validate all input data before database insertion
✅ Use parameterized queries to prevent SQL injection
✅ Monitor for anomalies (unusual traffic, error spikes)

## Project Structure

```
render-ingestion/
├── app.py                      # Main Flask application
├── handlers.py                 # Data processing handlers
├── supabase_client.py          # Supabase integration
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container configuration
├── render.yaml                 # Render deployment config
├── .env.example                # Environment variables template
├── README.md                   # This file
└── tests/
    ├── __init__.py
    └── test_app.py             # Comprehensive test suite
```

## Support

For technical issues or questions:
- Render Documentation: https://render.com/docs
- Supabase Documentation: https://supabase.com/docs
- Fernet Encryption: https://cryptography.io/en/latest/fernet/

## License

Proprietary - Internal use only

---

**Version**: 1.0.0
**Last Updated**: 2026-01-27
**Status**: Production Ready
