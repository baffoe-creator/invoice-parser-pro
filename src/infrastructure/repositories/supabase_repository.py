import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.infrastructure.models.supabase_models import Invoice, Base
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


class SupabaseInvoiceRepository:
    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")

        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        return self.SessionLocal()

    def save(self, invoice_data: Dict[str, Any], user_id: str, filename: str) -> str:
        invoice_data["pdf_path"] = filename
        invoice_data["user_id"] = user_id
        return self.add_invoice(invoice_data)

    def add_invoice(self, invoice_data: Dict[str, Any]) -> str:
        session = self.get_session()
        try:
            invoice_id = str(uuid.uuid4())

            invoice = Invoice(
                id=invoice_id,
                vendor=invoice_data.get("vendor", ""),
                invoice_number=invoice_data.get("invoice_number", ""),
                invoice_date=invoice_data.get("invoice_date"),
                due_date=invoice_data.get("due_date"),
                total_amount=invoice_data.get("total_amount", 0.0),
                tax_amount=invoice_data.get("tax_amount", 0.0),
                items=invoice_data.get("items", []),
                pdf_path=invoice_data.get("pdf_path", ""),
                parsed_data=invoice_data.get("parsed_data", {}),
                session_id=invoice_data.get("session_id", "default"),
                user_id=invoice_data.get("user_id", "demo_user"),
            )

            session.add(invoice)
            session.commit()
            return invoice_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        try:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            return invoice.to_dict() if invoice else None
        finally:
            session.close()

    def get_all_invoices(
        self, session_id: str = None, user_id: str = "demo_user"
    ) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            query = session.query(Invoice).filter(Invoice.user_id == user_id)

            if session_id:
                query = query.filter(Invoice.session_id == session_id)

            invoices = query.order_by(Invoice.created_at.desc()).all()
            return [invoice.to_dict() for invoice in invoices]
        finally:
            session.close()

    def get_invoices_by_session(
        self, session_id: str, user_id: str = "demo_user"
    ) -> List[Dict[str, Any]]:
        return self.get_all_invoices(session_id=session_id, user_id=user_id)

    def delete_invoice(self, invoice_id: str) -> bool:
        session = self.get_session()
        try:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            if invoice:
                session.delete(invoice)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete_session_invoices(
        self, session_id: str, user_id: str = "demo_user"
    ) -> bool:
        session = self.get_session()
        try:
            session.query(Invoice).filter(
                Invoice.session_id == session_id, Invoice.user_id == user_id
            ).delete()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_session_stats(
        self, session_id: str, user_id: str = "demo_user"
    ) -> Dict[str, Any]:
        session = self.get_session()
        try:
            result = (
                session.query(
                    text("COUNT(*) as count"),
                    text("COALESCE(SUM(total_amount), 0) as total"),
                )
                .filter(Invoice.session_id == session_id, Invoice.user_id == user_id)
                .first()
            )

            return {"count": result[0] or 0, "total_amount": float(result[1] or 0)}
        finally:
            session.close()
