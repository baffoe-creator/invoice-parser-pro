from fastapi import APIRouter, UploadFile, File, HTTPException
from src.models_parsed import InvoiceParsed, ParsedField
from src.parser_confidence import compute_field_confidences, overall_confidence
from src.redis_client import setex_json, get_json, set_json
from src.webhook import send_webhook
import uuid
import io
import pandas as pd
import os
import json
import tempfile

router = APIRouter()

PARSED_TTL = int(os.getenv("PARSED_TTL_SECONDS", str(60 * 60 * 2)))  # 2 hours
EDIT_TTL = int(os.getenv("EDIT_TTL_SECONDS", str(60 * 60 * 2)))  # 2 hours
EXPORT_STREAM_THRESHOLD = int(os.getenv("EXPORT_STREAM_THRESHOLD_BYTES", str(1_000_000)))  # 1MB
ENABLE_S3 = os.getenv("ENABLE_S3", "false").lower() in ("1", "true", "yes")

# Import your actual parser
try:
    from src.infrastructure.parsers.pdfplumber_parser import PdfPlumberParser
    PARSER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Could not import PdfPlumberParser: {e}")
    PARSER_AVAILABLE = False

def parse_invoice_bytes(raw_bytes: bytes) -> dict:
    """
    Use your actual PdfPlumberParser to parse invoice bytes.
    """
    if not PARSER_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF parser not available")
    
    try:
        # Save bytes to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(raw_bytes)
            temp_path = tmp_file.name
        
        try:
            # Use your actual parser
            parser = PdfPlumberParser()
            invoice_data = parser.parse(temp_path)
            
            # Convert InvoiceData object to dict format expected by v2 API
            parsed_dict = {
                "vendor": invoice_data.vendor or "Unknown",
                "invoice_number": invoice_data.invoice_number or "N/A",
                "invoice_date": invoice_data.invoice_date or "",
                "due_date": "",  # Your parser might not extract this yet
                "subtotal": str(invoice_data.subtotal) if invoice_data.subtotal else "0",
                "tax_amount": str(invoice_data.tax_amount) if invoice_data.tax_amount else "0",
                "discount_amount": str(invoice_data.discount_amount) if invoice_data.discount_amount else "0",
                "shipping_amount": str(invoice_data.shipping_amount) if invoice_data.shipping_amount else "0",
                "total_amount": str(invoice_data.total_amount) if invoice_data.total_amount else "0",
                "currency": invoice_data.currency or "USD",
                "line_items": [
                    {
                        "description": item.description,
                        "quantity": str(item.quantity),
                        "unit_price": str(item.unit_price),
                        "amount": str(item.amount)
                    }
                    for item in (invoice_data.line_items or [])
                ]
            }
            
            return parsed_dict
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        print(f"❌ Parser error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse invoice: {str(e)}")

@router.post("/api/v2/invoices/parse")
async def parse_invoice_endpoint(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    raw = await file.read()
    parsed = parse_invoice_bytes(raw)
    conf_map = compute_field_confidences(parsed)
    overall = overall_confidence(conf_map)

    # Build InvoiceParsed with per-field ParsedField structures
    parsed_fields = {}
    for k, v in parsed.items():
        if k == "line_items":
            parsed_fields[k] = v
            continue
        parsed_fields[k] = {
            "value": v,
            "confidence": conf_map.get(k, 0.0),
            "source": "ocr"
        }

    invoice_id = str(uuid.uuid4())
    store = {
        "id": invoice_id,
        "parsed": parsed_fields,
        "overall_confidence": overall,
        "file_name": file.filename,
        "raw_parsed": parsed  # Keep original parsed data for reference
    }
    # store parsed payload in Redis (short TTL)
    setex_json(f"invoice:{invoice_id}:parsed", store, PARSED_TTL)

    return {
        "invoice_id": invoice_id, 
        "parsed": store,
        "confidence_scores": conf_map,
        "overall_confidence": overall
    }

@router.get("/api/v2/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    """Retrieve a parsed invoice by ID"""
    parsed = get_json(f"invoice:{invoice_id}:parsed")
    if not parsed:
        raise HTTPException(status_code=404, detail="Invoice session not found or expired")
    return parsed

@router.patch("/api/v2/invoices/{invoice_id}/fields/{field_name}")
async def update_invoice_field(invoice_id: str, field_name: str, payload: dict):
    """
    payload: { "value": "...", "source": "manual" }
    Stores manual override in Redis with TTL.
    """
    parsed = get_json(f"invoice:{invoice_id}:parsed")
    if not parsed:
        raise HTTPException(status_code=404, detail="Invoice session not found or expired")
    
    # Write edit as part of the parsed payload in Redis (merge)
    parsed_fields = parsed.get("parsed", {})
    parsed_fields[field_name] = {
        "value": payload.get("value"),
        "confidence": 1.0,
        "source": payload.get("source", "manual")
    }
    parsed["parsed"] = parsed_fields
    
    # Recalculate overall confidence
    conf_scores = []
    for k, v in parsed_fields.items():
        if k != "line_items" and isinstance(v, dict):
            conf_scores.append(v.get("confidence", 0.0))
    
    if conf_scores:
        parsed["overall_confidence"] = sum(conf_scores) / len(conf_scores)
    
    setex_json(f"invoice:{invoice_id}:parsed", parsed, EDIT_TTL)
    return {
        "ok": True, 
        "invoice_id": invoice_id, 
        "field": field_name, 
        "value": payload.get("value"),
        "new_confidence": parsed["overall_confidence"]
    }

@router.post("/api/v2/invoices/{invoice_id}/webhook")
async def create_webhook_delivery(invoice_id: str, payload: dict):
    """
    payload: { "webhook_url": "...", "secret": "optional-secret" }
    For now, send synchronously. We'll add RQ later.
    """
    parsed = get_json(f"invoice:{invoice_id}:parsed")
    if not parsed:
        raise HTTPException(status_code=404, detail="Invoice session not found or expired")
    
    webhook_url = payload.get("webhook_url")
    secret = payload.get("secret") or os.getenv("SECRET_KEY", "secret")
    
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url is required")
    
    # For now, send synchronously (we'll add RQ queue later)
    result = send_webhook(parsed, webhook_url, secret)
    
    return {
        "sent": result.get("ok", False),
        "status_code": result.get("status_code"),
        "error": result.get("error")
    }

@router.post("/api/v2/invoices/{invoice_id}/approve")
async def approve_invoice(invoice_id: str):
    """
    Finalize invoice, build XLSX export.
    """
    parsed = get_json(f"invoice:{invoice_id}:parsed")
    if not parsed:
        raise HTTPException(status_code=404, detail="Invoice session not found or expired")

    # Flatten parsed fields to row(s)
    flat = {}
    parsed_fields = parsed.get("parsed", {})
    
    for k, v in parsed_fields.items():
        if k == "line_items":
            flat[k] = json.dumps(v)
            continue
        flat[k] = v.get("value") if isinstance(v, dict) else v
    
    # Add metadata
    flat["invoice_id"] = invoice_id
    flat["file_name"] = parsed.get("file_name")
    flat["overall_confidence"] = parsed.get("overall_confidence")
    flat["exported_at"] = pd.Timestamp.now().isoformat()

    df = pd.json_normalize([flat])
    output = io.BytesIO()
    
    # Handle line items if available
    if "line_items" in flat and flat["line_items"]:
        try:
            line_items = json.loads(flat["line_items"])
            if line_items:
                line_items_df = pd.DataFrame(line_items)
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Invoice Summary', index=False)
                    line_items_df.to_excel(writer, sheet_name='Line Items', index=False)
                output.seek(0)
        except Exception as e:
            print(f"⚠️  Error creating multi-sheet Excel: {e}")
            df.to_excel(output, index=False)
    else:
        df.to_excel(output, index=False)
    
    bytes_out = output.getvalue()
    
    # Return as downloadable file
    from fastapi.responses import Response
    headers = {
        "Content-Disposition": f'attachment; filename="invoice_{invoice_id}.xlsx"',
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
    
    return Response(content=bytes_out, headers=headers)

@router.delete("/api/v2/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str):
    """Delete invoice session"""
    from src.redis_client import delete_key
    delete_key(f"invoice:{invoice_id}:parsed")
    return {"ok": True, "message": "Invoice session deleted"}