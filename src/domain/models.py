from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


@dataclass
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass
class InvoiceData:
    vendor: str
    invoice_number: str
    invoice_date: str
    total_amount: Decimal
    currency: str
    line_items: List[LineItem]
    raw_text: Optional[str] = None
    subtotal: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    shipping_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vendor": self.vendor,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "total_amount": float(self.total_amount),
            "currency": self.currency,
            "line_items": [
                {
                    "description": item.description,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                    "amount": float(item.amount),
                }
                for item in self.line_items
            ],
            "raw_text": self.raw_text,
            "subtotal": float(self.subtotal) if self.subtotal else None,
            "discount_amount": (
                float(self.discount_amount) if self.discount_amount else None
            ),
            "discount_percentage": (
                float(self.discount_percentage) if self.discount_percentage else None
            ),
            "shipping_amount": (
                float(self.shipping_amount) if self.shipping_amount else None
            ),
            "tax_amount": float(self.tax_amount) if self.tax_amount else None,
        }
