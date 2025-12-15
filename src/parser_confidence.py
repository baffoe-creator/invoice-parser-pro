"""Lightweight heuristics to produce per-field confidence."""
import re
from difflib import SequenceMatcher
from decimal import Decimal
from typing import Dict, Any

def numeric_confidence(value: str) -> float:
    if value is None:
        return 0.0
    try:
        Decimal(str(value))
        return 0.95
    except Exception:
        return 0.0

def date_confidence(value: str) -> float:
    if not value:
        return 0.0
    if re.match(r'\d{4}-\d{2}-\d{2}', str(value)):
        return 0.95
    if re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', str(value)):
        return 0.85
    return 0.4

def string_similarity_confidence(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return float(SequenceMatcher(None, a.lower(), b.lower()).ratio())

def compute_field_confidences(parsed: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, float]:
    conf = {}
    for f in ('subtotal', 'tax_amount', 'discount_amount', 'shipping_amount', 'total_amount'):
        conf[f] = numeric_confidence(parsed.get(f))
    for f in ('invoice_date', 'due_date'):
        conf[f] = date_confidence(parsed.get(f))
    vendor = parsed.get('vendor')
    conf['vendor'] = string_similarity_confidence(vendor or "", context.get('vendor') if context else vendor or "")
    inv = parsed.get('invoice_number')
    conf['invoice_number'] = 0.9 if inv and len(str(inv)) >= 3 else (0.5 if inv else 0.0)
    conf['currency'] = 0.95 if parsed.get('currency') else 0.0
    items = parsed.get('line_items') or []
    conf['line_items'] = min(1.0, 0.9 if len(items) > 0 else 0.0)
    return conf

def overall_confidence(conf_map: Dict[str, float]) -> float:
    if not conf_map:
        return 0.0
    return float(sum(conf_map.values()) / len(conf_map))