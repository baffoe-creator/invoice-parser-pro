from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json
from typing import Dict, Any

Base = declarative_base()


class InvoiceORM(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    filename = Column(String)
    vendor_name = Column(String)
    invoice_number = Column(String)
    invoice_date = Column(String)
    total_amount = Column(Float)
    currency = Column(String)
    parsed_data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SQLAlchemyInvoiceRepository:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        Base.metadata.create_all(bind=self.engine)

    def save(self, invoice_data: Dict[str, Any], user_id: str, filename: str) -> str:
        db = self.SessionLocal()
        try:
            invoice_orm = InvoiceORM(
                user_id=user_id,
                filename=filename,
                vendor_name=invoice_data.get("vendor_name", "Unknown Vendor"),
                invoice_number=invoice_data.get("invoice_number", "Unknown"),
                invoice_date=invoice_data.get("date", "Unknown Date"),
                total_amount=float(invoice_data.get("total_amount", 0.0)),
                currency=invoice_data.get("currency", "USD"),
                parsed_data=json.dumps(invoice_data),
            )
            db.add(invoice_orm)
            db.commit()
            db.refresh(invoice_orm)
            return str(invoice_orm.id)
        except Exception as e:
            db.rollback()
            return f"fallback_invoice_{user_id}_{filename}"
        finally:
            db.close()

    def get_by_user(self, user_id: str) -> list:
        db = self.SessionLocal()
        try:
            invoices = db.query(InvoiceORM).filter(InvoiceORM.user_id == user_id).all()
            return [
                {
                    "id": invoice.id,
                    "filename": invoice.filename,
                    "vendor": invoice.vendor_name,
                    "invoice_number": invoice.invoice_number,
                    "total_amount": invoice.total_amount,
                    "created_at": invoice.created_at.isoformat(),
                }
                for invoice in invoices
            ]
        except Exception:
            return []
        finally:
            db.close()
