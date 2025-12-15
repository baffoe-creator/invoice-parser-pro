from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime

class ParsedField(BaseModel):
    value: Optional[Any] = None
    confidence: float = 0.0  # 0.0 - 1.0
    source: Optional[str] = None  # e.g., "ocr", "regex", "manual"

class InvoiceParsed(BaseModel):
    vendor: Optional[ParsedField] = None
    invoice_number: Optional[ParsedField] = None
    invoice_date: Optional[ParsedField] = None
    due_date: Optional[ParsedField] = None
    subtotal: Optional[ParsedField] = None
    tax_amount: Optional[ParsedField] = None
    discount_amount: Optional[ParsedField] = None
    shipping_amount: Optional[ParsedField] = None
    total_amount: Optional[ParsedField] = None
    currency: Optional[ParsedField] = None
    line_items: Optional[List[Dict[str, Any]]] = None

    overall_confidence: float = 0.0
    parsed_timestamp: datetime = datetime.utcnow()
    file_name: Optional[str] = None