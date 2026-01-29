"""
Render Ingestion Service for SAP Agent Data
Receives encrypted SAP B1 data and stores it in Supabase

Updated: 2026-01-28 - Added rate limiting
"""

from flask import Flask, request, jsonify
from cryptography.fernet import Fernet
import json
import os
from datetime import datetime
import logging
from dotenv import load_dotenv

# Import rate limiting
from middleware.rate_limiter import rate_limit

# Load environment variables
load_dotenv()

# Configure structured logging (JSON format)
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

# Set up logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level))

# Console handler with JSON formatter
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Initialize Flask app
app = Flask(__name__)

# Configuration from environment variables
API_KEY = os.getenv("API_KEY")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not API_KEY:
    logger.error("API_KEY environment variable not set")
    raise ValueError("API_KEY environment variable not set")

if not ENCRYPTION_KEY:
    logger.error("ENCRYPTION_KEY environment variable not set")
    raise ValueError("ENCRYPTION_KEY environment variable not set")

# Initialize cipher
try:
    cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
    logger.info("Encryption cipher initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize cipher: {str(e)}")
    raise

# Data type handlers mapping
DATA_TYPE_HANDLERS = {
    "warehouses_full": "handle_warehouses",
    "vendors_full": "handle_vendors",
    "items_full": "handle_items",
    "inventory_current_full": "handle_inventory",
    "sales_orders_incremental": "handle_sales_orders",
    "purchase_orders_incremental": "handle_purchase_orders",
    "costs_incremental": "handle_costs",
    "pricing_full": "handle_pricing"
}


@app.route('/health', methods=['GET'])
@rate_limit(limit_name='health')  # 1000 requests per minute
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "forecast-ingestion",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }), 200


@app.route('/api/ingest', methods=['POST'])
@rate_limit(limit=1000, period=3600)  # 1000 requests per hour by IP
def ingest_data():
    """
    Main ingestion endpoint for SAP Agent data.

    Flow:
    1. Validate API key
    2. Decrypt payload
    3. Extract data_type and records
    4. Route to appropriate handler
    5. Return success response
    """

    # Step 1: Validate API key
    api_key = request.headers.get("X-API-Key")
    if api_key != API_KEY:
        logger.warning(f"Unauthorized access attempt from {request.remote_addr}")
        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 401

    # Step 2: Get and validate request body
    request_data = request.get_json()
    if not request_data:
        logger.error("Missing request body")
        return jsonify({
            "success": False,
            "error": "Missing request body"
        }), 400

    encrypted_payload = request_data.get("encrypted_payload")
    if not encrypted_payload:
        logger.error("Missing encrypted_payload field")
        return jsonify({
            "success": False,
            "error": "Missing encrypted_payload"
        }), 400

    # Step 3: Decrypt payload
    try:
        logger.info("Decrypting payload...")
        decrypted_bytes = cipher.decrypt(encrypted_payload.encode('utf-8'))
        data = json.loads(decrypted_bytes.decode('utf-8'))
        logger.info("Payload decrypted successfully")
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Decryption failed: {str(e)}"
        }), 400

    # Step 4: Extract and validate data
    data_type = data.get("data_type")
    records = data.get("records", [])

    if not data_type:
        logger.error("Missing data_type in payload")
        return jsonify({
            "success": False,
            "error": "Missing data_type"
        }), 400

    if not records:
        logger.warning(f"No records in payload for data_type={data_type}")
        return jsonify({
            "success": True,
            "message": "No records to process",
            "data_type": data_type,
            "records_count": 0
        }), 200

    # Step 5: Validate data_type
    if data_type not in DATA_TYPE_HANDLERS:
        logger.error(f"Unknown data_type: {data_type}")
        return jsonify({
            "success": False,
            "error": f"Unknown data_type: {data_type}"
        }), 400

    # Step 6: Process records
    try:
        logger.info(f"Processing {len(records)} records for data_type={data_type}")

        # Import handlers dynamically to avoid circular imports
        from handlers import DATA_HANDLERS

        handler = DATA_HANDLERS.get(data_type)
        if not handler:
            logger.error(f"No handler found for data_type: {data_type}")
            return jsonify({
                "success": False,
                "error": f"No handler found for data_type: {data_type}"
            }), 500

        result = handler(records)

        logger.info(f"Successfully processed {result['processed']} records")

        return jsonify({
            "success": True,
            "message": "Data ingested successfully",
            "data_type": data_type,
            "records_received": len(records),
            "records_processed": result['processed'],
            "records_failed": result.get('failed', 0),
            "timestamp": datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Processing failed: {str(e)}"
        }), 500


# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
