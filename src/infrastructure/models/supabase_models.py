from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=generate_uuid)
    vendor = Column(String, nullable=False)
    invoice_number = Column(String, nullable=False)
    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime)
    total_amount = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    items = Column(JSON)
    pdf_path = Column(String)
    parsed_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_id = Column(String, nullable=False)
    user_id = Column(String, default="demo_user")

    def to_dict(self):
        return {
            "id": self.id,
            "vendor": self.vendor,
            "invoice_number": self.invoice_number,
            "invoice_date": (
                self.invoice_date.isoformat() if self.invoice_date else None
            ),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "total_amount": self.total_amount,
            "tax_amount": self.tax_amount,
            "items": self.items or [],
            "pdf_path": self.pdf_path,
            "parsed_data": self.parsed_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }
