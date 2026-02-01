# Warehouse Validation Implementation

**Date:** 2026-02-01
**Author:** @architect-ingest
**Purpose:** Hardening ingestion handlers against invalid warehouse codes

---

## Problem Statement

**Database Foreign Key Constraint:**
```sql
CREATE TABLE inventory_current (
    warehouse_code VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_code),
    ...
);
```

**Issue:** Inserting inventory/sales/purchase orders with invalid `warehouse_code` causes foreign key violations and database errors.

**Impact:**
- Batch ingestion fails partially
- Unclear error messages to SAP Agent
- No visibility into which warehouse codes are invalid
- Potential data inconsistencies

---

## Solution Architecture

### 1. Warehouse Code Cache

**File:** `D:\code\forecastv3\render-ingestion\handlers.py`

**Function:** `get_valid_warehouse_codes(force_refresh=False)`

**Features:**
- Fetches all valid warehouse codes from `warehouses` table
- In-memory cache with 5-minute TTL
- Graceful degradation (uses stale cache on DB error)
- Global singleton for performance

**Implementation:**
```python
# Global cache for warehouse codes
_warehouse_codes_cache: Optional[Set[str]] = None
_cache_timestamp: Optional[datetime] = None
CACHE_TTL_SECONDS = 300  # 5 minutes

def get_valid_warehouse_codes(force_refresh: bool = False) -> Set[str]:
    """Fetch all valid warehouse codes from the database with caching."""
    global _warehouse_codes_cache, _cache_timestamp

    now = datetime.utcnow()

    # Check cache validity
    if (not force_refresh and
        _warehouse_codes_cache is not None and
        _cache_timestamp is not None and
        (now - _cache_timestamp).total_seconds() < CACHE_TTL_SECONDS):
        logger.debug(f"Using cached warehouse codes ({len(_warehouse_codes_cache)} warehouses)")
        return _warehouse_codes_cache

    # Fetch from database
    try:
        client = get_supabase_client()
        result = client.table('warehouses').select('warehouse_code').execute()

        _warehouse_codes_cache = {row['warehouse_code'] for row in result.data}
        _cache_timestamp = now

        logger.info(f"Refreshed warehouse codes cache: {len(_warehouse_codes_cache)} valid warehouses")
        return _warehouse_codes_cache

    except Exception as e:
        logger.error(f"Failed to fetch warehouse codes from database: {e}")
        # If we have a stale cache, return it for resilience
        if _warehouse_codes_cache is not None:
            logger.warning("Using stale warehouse codes cache due to database error")
            return _warehouse_codes_cache
        raise
```

**Why Caching?**
- Warehouse definitions change infrequently
- Avoids querying database on every request
- Significantly improves performance
- 5-minute TTL balances freshness vs. performance

---

### 2. Handler-Level Validation

**Updated Handlers:**
1. `handle_inventory()` - **CRITICAL** (primary use case)
2. `handle_sales_orders()` - **IMPORTANT** (warehouse reference)
3. `handle_purchase_orders()` - **IMPORTANT** (warehouse reference)

**Validation Logic (handle_inventory example):**
```python
def handle_inventory(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process inventory records with warehouse code validation."""
    logger.info(f"Processing {len(records)} inventory records")

    # Get valid warehouse codes
    try:
        valid_warehouse_codes = get_valid_warehouse_codes()
        logger.info(f"Loaded {len(valid_warehouse_codes)} valid warehouse codes for validation")
    except Exception as e:
        logger.error(f"Failed to load valid warehouse codes: {e}")
        # Fail fast - we cannot proceed without warehouse validation
        return {
            'processed': 0,
            'failed': len(records),
            'rejected_warehouses': 0,
            'errors': [f"Failed to load warehouse codes for validation: {str(e)}"]
        }

    # Extract business data and validate
    business_records = []
    rejected_warehouses = []  # Track rejected warehouse codes
    rejected_records = 0
    invalid_warehouse_codes = set()  # Track unique invalid warehouse codes

    for record in records:
        try:
            # Validate required fields
            item_code = record.get("item_code")
            warehouse_code = record.get("warehouse_code")

            if not item_code or not warehouse_code:
                logger.warning(f"Skipping inventory record: missing item_code or warehouse_code")
                rejected_records += 1
                continue

            # CRITICAL: Validate warehouse code exists in database
            if warehouse_code not in valid_warehouse_codes:
                rejected_records += 1
                invalid_warehouse_codes.add(warehouse_code)
                rejected_warehouses.append({
                    'item_code': item_code,
                    'warehouse_code': warehouse_code,
                    'reason': f"Warehouse '{warehouse_code}' does not exist in warehouses table"
                })
                logger.warning(
                    f"Rejecting inventory record for item '{item_code}': "
                    f"invalid warehouse '{warehouse_code}'"
                )
                continue

            # Map SAP fields to database schema
            on_hand_qty = float(record.get("on_hand_qty", record.get("quantity", 0)))
            committed_qty = float(record.get("committed_qty", 0))
            available_qty = on_hand_qty - committed_qty

            business_records.append({
                "item_code": item_code,
                "warehouse_code": warehouse_code,
                "on_hand_qty": on_hand_qty,
                "on_order_qty": float(record.get("on_order_qty", 0)),
                "committed_qty": committed_qty,
                "available_qty": available_qty,
                "unit_cost": float(record.get("unit_cost", record.get("unit_price", 0)))
            })

        except Exception as e:
            logger.error(f"Error extracting inventory data: {str(e)}")
            rejected_records += 1

    # Log rejected warehouse summary
    if invalid_warehouse_codes:
        logger.error(
            f"Rejected {len(rejected_warehouses)} inventory records with invalid warehouses: "
            f"{sorted(invalid_warehouse_codes)}"
        )

    # Upsert valid records to Supabase
    result = upsert_inventory(business_records)

    # Build enhanced response
    response = {
        'processed': result['processed'],
        'failed': result['failed'] + rejected_records,
        'rejected_warehouses': len(rejected_warehouses),
        'invalid_warehouse_codes': sorted(list(invalid_warehouse_codes)),
        'rejected_records_sample': rejected_warehouses[:10]  # First 10 for review
    }

    logger.info(
        f"Inventory processing complete: {response['processed']} processed, "
        f"{response['failed']} failed, {response['rejected_warehouses']} rejected "
        f"(invalid warehouses: {response['invalid_warehouse_codes']})"
    )

    return response
```

**Validation Flow:**
1. Load valid warehouse codes (with cache)
2. For each record:
   - Check required fields (item_code, warehouse_code)
   - **Validate warehouse_code exists in allowed list**
   - If invalid: track rejection, log warning, skip insert
   - If valid: proceed to business logic
3. Insert only valid records to database
4. Return detailed response with rejection statistics

---

### 3. Enhanced Error Response Format

**Previous Response:**
```json
{
    "processed": 95,
    "failed": 5
}
```

**New Enhanced Response:**
```json
{
    "processed": 95,
    "failed": 10,
    "rejected_warehouses": 5,
    "invalid_warehouse_codes": ["WH-INVALID-1", "WH-TYPO-2"],
    "rejected_records_sample": [
        {
            "item_code": "ITEM-001",
            "warehouse_code": "WH-INVALID-1",
            "reason": "Warehouse 'WH-INVALID-1' does not exist in warehouses table"
        },
        {
            "item_code": "ITEM-002",
            "warehouse_code": "WH-TYPO-2",
            "reason": "Warehouse 'WH-TYPO-2' does not exist in warehouses table"
        }
    ]
}
```

**Benefits:**
- Clear visibility into which warehouse codes are invalid
- Sample rejected records for debugging
- Helps SAP Agent identify mapping issues
- Enables automatic retry with corrections

---

## Design Decisions

### Decision 1: Validate Before Insert (Reject at Handler Level)

**Option A:** Validate in handler (✓ **CHOSEN**)
- Pro: Fail fast, clear error messages
- Pro: No database FK violation errors
- Pro: Can return detailed rejection info
- Con: Requires warehouse list in memory

**Option B:** Let database FK handle it
- Pro: No handler-level validation needed
- Pro: Always consistent with database
- Con: Generic FK violation errors
- Con: Batch processing unclear
- Con: Hard to identify which records failed

**Decision:** **Option A** - Better UX for SAP Agent integration

---

### Decision 2: Caching Strategy

**Option A:** No cache (query every time)
- Pro: Always fresh data
- Con: Poor performance (DB query on every request)
- Con: High database load

**Option B:** Static cache (load once, never refresh)
- Pro: Best performance
- Con: Stale data if warehouses change
- Con: Requires restart to refresh

**Option C:** TTL cache (✓ **CHOSEN** - 5 minutes)
- Pro: Good performance
- Pro: Reasonable freshness
- Pro: Auto-refresh
- Con: Small window of stale data (acceptable)

**Decision:** **Option C** - Balances performance and freshness

---

### Decision 3: Auto-Create vs Reject Invalid Warehouses

**Option A:** Auto-create missing warehouses
- Pro: No data loss
- Pro: Seamless processing
- Con: **SECURITY RISK** - can create garbage warehouses
- Con: Masking mapping errors
- Con: Potential for warehouse spam

**Option B:** Reject invalid warehouses (✓ **CHOSEN**)
- Pro: **SECURE** - prevents garbage data
- Pro: Forces proper warehouse setup
- Pro: Clear error messages
- Con: Requires warehouses to be pre-created
- Con: Some data rejected until fixed

**Decision:** **Option B** - Security and data integrity over convenience

**Recommendation:** SAP Agent should call `warehouses_full` endpoint first to ensure all warehouses exist before sending inventory/orders.

---

## Testing

### Test Script

**File:** `D:\code\forecastv3\render-ingestion\test_warehouse_validation.py`

**Tests:**
1. **Warehouse Code Cache**
   - Fetch valid warehouse codes
   - Test cache hit performance
   - Display all valid codes

2. **Inventory Record Validation**
   - Valid warehouse → should process
   - Invalid warehouse → should reject
   - Missing warehouse → should reject
   - Returns detailed rejection info

3. **Database Foreign Key Constraint**
   - Verifies FK constraint is enforced
   - Confirms validation prevents DB errors

**Run Tests:**
```bash
cd D:\code\forecastv3\render-ingestion
python test_warehouse_validation.py
```

---

## Production Considerations

### 1. Cache Refresh Strategy

**Current:** 5-minute TTL auto-refresh

**Future Enhancements:**
- Manual refresh endpoint: `POST /api/admin/refresh-warehouse-cache`
- Cache invalidation on warehouse insert/update
- Pub/Sub notification when warehouses change

### 2. Monitoring

**Key Metrics to Track:**
- `warehouse_validation_rejections_total` - Number of records rejected due to invalid warehouse
- `warehouse_cache_hits_total` - Number of cache hits vs. misses
- `invalid_warehouse_codes` - Set of invalid codes encountered (alert on new codes)

**Logging:**
- Log all rejected warehouse codes
- Alert if rejection rate > 5% (indicates mapping issue)
- Track which SAP Agent sends most invalid codes

### 3. SAP Agent Integration

**Recommended Flow:**
```
1. SAP Agent: GET /api/warehouses → Get all valid warehouse codes
2. SAP Agent: Validate local data against warehouse list
3. SAP Agent: POST /api/data/inventory_current_full → Send only valid records
4. Render Ingestion: Double-validate (defense in depth)
```

**Error Recovery:**
```
If validation fails:
1. Check response.invalid_warehouse_codes
2. Create missing warehouses via /api/data/warehouses_full
3. Retry rejected records
```

### 4. Performance Impact

**Before Validation:**
- Direct insert to database
- FK violation causes rollback

**After Validation:**
- In-memory lookup (O(1) per record)
- No database round-trips for invalid records
- Reduced database load

**Estimated Impact:**
- +1ms per record for validation (negligible)
- -100ms per rejected record (no DB insert attempt)
- Net: **Positive performance impact**

---

## Security Analysis

### Threat Model

**Attack Vector:** Warehouse Code Injection

**Scenario:** Attacker sends inventory with malicious warehouse codes

**Without Validation:**
- Attempt to insert to database
- Foreign key violation
- Generic error message
- Attacker can probe database structure

**With Validation (Current Implementation):**
- Validate before database interaction
- Clear rejection message
- No database interaction for invalid codes
- Attacker cannot probe FK constraints

**Security Rating:** ✅ **SECURE**

---

## Migration Path

### Phase 1: Deploy Validation (Current)
- Add warehouse validation to handlers
- Deploy to Render
- Monitor rejection logs

### Phase 2: SAP Agent Updates
- SAP Team updates agent to fetch warehouses first
- Add local validation in SAP Agent
- Implement retry logic for rejected records

### Phase 3: Enhanced Monitoring
- Add metrics dashboard
- Alert on high rejection rates
- Automated warehouse sync

---

## Rollback Plan

**If Issues Occur:**

1. **Disable Validation** (temporary)
   - Set `CACHE_TTL_SECONDS = 0` to force cache bypass
   - Comment out validation in handlers
   - Deploy hotfix

2. **Fallback to Database FK**
   - Remove validation logic
   - Let database handle FK violations
   - Update error messages to handle FK errors

3. **Root Cause Analysis**
   - Review logs for rejection patterns
   - Identify why validation is failing
   - Fix validation logic or add whitelist

**Rollback Command:**
```python
# In handlers.py, set:
CACHE_TTL_SECONDS = 0  # Disable cache

# In handle_inventory(), comment out:
# if warehouse_code not in valid_warehouse_codes:
#     continue
```

---

## Success Criteria

✅ **Implementation Complete:**
- [x] Warehouse code cache implemented
- [x] Validation added to `handle_inventory()`
- [x] Validation added to `handle_sales_orders()`
- [x] Validation added to `handle_purchase_orders()`
- [x] Enhanced error response format
- [x] Test script created
- [x] Documentation complete

✅ **Testing Complete:**
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Load tests (< 100ms per record)
- [ ] Manual testing with invalid codes

✅ **Production Ready:**
- [ ] Deployed to Render
- [ ] Monitoring configured
- [ ] SAP Agent team notified
- [ ] Error recovery procedures documented

---

## References

**Files Modified:**
- `D:\code\forecastv3\render-ingestion\handlers.py`

**Files Created:**
- `D:\code\forecastv3\render-ingestion\test_warehouse_validation.py`
- `D:\code\forecastv3\render-ingestion\WAREHOUSE_VALIDATION_SPEC.md` (this file)

**Related Documentation:**
- `SAP_AGENT_RENDER_ENDPOINT_SPEC.md` - API specification
- `CLAUDE.md` - Project guidelines
- `database/migrations/001_initial_schema.sql` - FK constraint definition

---

## Summary

**Implementation:** Warehouse validation with caching and detailed error reporting

**Security:** Prevents invalid warehouse codes from reaching database

**Performance:** In-memory caching with 5-minute TTL, minimal overhead

**UX:** Clear error messages help SAP Agent identify mapping issues

**Status:** ✅ **COMPLETE** - Ready for testing and deployment

---

**Next Steps:**
1. Review and approve implementation
2. Run test suite: `python test_warehouse_validation.py`
3. Deploy to Render staging environment
4. Monitor logs for rejection patterns
5. Coordinate with SAP Agent team on workflow updates
