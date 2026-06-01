# PDF Report Generation Fix Plan

## Problem Analysis

**Current Situation:**
- ✅ Android app connects successfully to server
- ✅ Profile fetching works correctly
- ❌ PDF report generation returns **403 Forbidden** error

**Root Cause:**
1. Android app calls: `POST /api/service/report/generate` on port 8000
2. Desktop server (Previlium) **does not have this endpoint**
3. Server returns 403 (or 404) because endpoint doesn't exist
4. Desktop app has PDF generation capability but it's not exposed via this API

**Android App Expects:**
- Endpoint: `POST /api/service/report/generate`
- Headers: `X-API-Key: <api_key>`
- Body: `GeneratePDFReportRequest` with:
  - `profile_id`, `profile_name`, `report_type`
  - Options: `include_diagnostics`, `include_fuel_data`, etc.
- Response: `GeneratePDFReportResponse` with:
  - `success: Boolean`
  - `report_url: String` (download URL)
  - `message: String`

**Desktop Server Has:**
- `GET /report?device_id=...` on port 8001 (DirectReportServer)
- PDF generation in `main_pyside.py` via `PDFExporter`
- But no `POST /api/service/report/generate` endpoint

---

## Solution Strategy

### Option A: Add Missing Endpoint to Previlium Server (RECOMMENDED)
**Pros:**
- Matches Android app's expectations
- Clean RESTful API
- Can handle report type and options
- Returns proper JSON response

**Implementation:**
1. Add `POST /api/service/report/generate` endpoint to `C:\OBDserver\Previlium_OBD_Server\main.py`
2. Endpoint validates API key and extracts profile_id
3. Triggers PDF generation in desktop app (via shared mechanism)
4. Returns download URL pointing to port 8001

### Option B: Modify Android App to Use Existing Endpoint
**Pros:**
- No server changes needed
**Cons:**
- Requires Android app rebuild
- Less flexible (can't specify report type/options)
- Different API pattern

---

## Implementation Plan (Option A)

### Step 1: Add PDF Report Endpoint to Previlium Server
**File:** `C:\OBDserver\Previlium_OBD_Server\main.py`

**Add:**
- Pydantic model for `GeneratePDFReportRequest`
- Pydantic model for `GeneratePDFReportResponse`
- `POST /api/service/report/generate` endpoint
- Logic to:
  1. Validate API key
  2. Get profile_id from API key
  3. Trigger PDF generation (via file-based queue or HTTP call to desktop)
  4. Return download URL

### Step 2: Bridge Previlium Server ↔ Desktop App
**Options:**
- **A:** Use shared file/database to queue PDF requests
- **B:** Previlium makes HTTP call to desktop app's internal API
- **C:** Desktop app polls Previlium for pending requests

**Recommended:** Option A (shared file queue)
- Simple and reliable
- No network dependencies
- Works even if desktop app is busy

### Step 3: Desktop App Processes PDF Queue
**File:** `main_pyside.py`

**Add:**
- Timer/thread that checks for pending PDF requests
- When found, generates PDF using existing `PDFExporter`
- Saves PDF to accessible location
- Updates queue with completion status and file path

### Step 4: Return Download URL
- Previlium endpoint returns: `http://<desktop_ip>:8001/reports/<filename>`
- Or uses existing DirectReportServer endpoint

---

## Detailed Implementation Steps

### Step 1.1: Add Request/Response Models
```python
class GeneratePDFReportRequest(BaseModel):
    profile_id: int
    profile_name: str
    report_type: str  # "comprehensive", "diagnostics", "service", "fuel_trips"
    include_diagnostics: Optional[bool] = None
    include_fuel_data: Optional[bool] = None
    include_trip_data: Optional[bool] = None
    include_maintenance_history: Optional[bool] = None
    include_service_records: Optional[bool] = None

class GeneratePDFReportResponse(BaseModel):
    success: bool
    report_url: Optional[str] = None
    message: Optional[str] = None
```

### Step 1.2: Add Endpoint
```python
@app.post("/api/service/report/generate")
async def generate_pdf_report(
    request: GeneratePDFReportRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> GeneratePDFReportResponse:
    # 1. Validate API key
    # 2. Verify profile_id matches API key
    # 3. Queue PDF generation request
    # 4. Return response with download URL
```

### Step 1.3: PDF Queue System
**Shared file:** `C:\OBDserver\Previlium_OBD_Server\data\pdf_queue.json`
```json
{
  "pending": [
    {
      "request_id": "pdf_20251218_123456",
      "profile_id": 16,
      "profile_name": "Omar",
      "report_type": "comprehensive",
      "status": "pending",
      "created_at": "2025-12-18T12:34:56Z"
    }
  ],
  "completed": []
}
```

### Step 2: Desktop App Integration
**File:** `main_pyside.py`

**Add PDF Queue Processor:**
- Timer checks `pdf_queue.json` every 5 seconds
- When pending request found:
  1. Generate PDF using `PDFExporter`
  2. Save to `data/reports/` directory
  3. Update queue: mark as completed, add file path
  4. Previlium can then return download URL

---

## Testing Checklist

- [ ] Endpoint accepts POST request with valid API key
- [ ] Endpoint rejects request with invalid API key (401)
- [ ] Endpoint validates profile_id matches API key
- [ ] PDF generation request is queued correctly
- [ ] Desktop app processes queue and generates PDF
- [ ] Download URL is returned correctly
- [ ] Android app can download PDF from returned URL
- [ ] Error handling works (missing profile, generation failure, etc.)

---

## Alternative Quick Fix (Temporary)

If you need a working solution immediately:

1. **Modify Android app** to use existing endpoint:
   - Change from `POST /api/service/report/generate`
   - To: `GET http://<desktop_ip>:8001/report?device_id=<device_id>`
   - This uses the existing DirectReportServer

2. **Limitations:**
   - Can't specify report type/options
   - Always generates comprehensive report
   - Requires device_id parameter

---

## Files to Modify

1. **`C:\OBDserver\Previlium_OBD_Server\main.py`**
   - Add request/response models
   - Add `/api/service/report/generate` endpoint
   - Add PDF queue management

2. **`main_pyside.py`** (Desktop app)
   - Add PDF queue processor
   - Integrate with existing PDF generation

3. **Optional:** `mobile_server_wrapper.py`
   - Enhance DirectReportServer if needed

---

## Next Steps

1. Implement Step 1 (Add endpoint to Previlium server)
2. Implement Step 2 (PDF queue system)
3. Implement Step 3 (Desktop app queue processor)
4. Test end-to-end
5. Update Android app if needed (should work as-is)



