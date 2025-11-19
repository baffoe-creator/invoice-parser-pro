import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from src.infrastructure.models.supabase_models import Invoice, Base
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import time


class SupabaseInvoiceRepository:
    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")

        self.engine = None
        self.SessionLocal = None
        self.connected = False

        if not database_url:
            print("⚠️  No DATABASE_URL provided, running in offline mode")
            return

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                print(f"🔄 Database connection attempt {attempt + 1}/{max_retries}...")

                self.engine = create_engine(
                    database_url,
                    pool_pre_ping=True,
                    pool_recycle=300,
                    connect_args={
                        "connect_timeout": 10,
                        "application_name": "invoice-parser-pro",
                    },
                )

                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

                self.SessionLocal = sessionmaker(
                    autocommit=False, autoflush=False, bind=self.engine
                )

                Base.metadata.create_all(bind=self.engine)

                self.connected = True
                print("✅ Database connected successfully")
                break

            except OperationalError as e:
                error_msg = str(e)
                print(f"❌ Connection attempt {attempt + 1} failed: {error_msg}")

                if attempt < max_retries - 1:
                    print(f"⏳ Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("⚠️  All connection attempts failed, running in offline mode")
                    print("📝 Data will be stored locally only")
                    self.engine = None
                    self.SessionLocal = None

            except Exception as e:
                print(f"❌ Unexpected error during initialization: {e}")
                import traceback

                traceback.print_exc()
                break

    def is_connected(self):
        return self.connected

    def get_session(self):
        if not self.connected or self.SessionLocal is None:
            return None
        return self.SessionLocal()

    def save(self, invoice_data: Dict[str, Any], user_id: str, filename: str) -> str:
        if not self.connected:
            print(f"⚠️  Database not connected, cannot save: {filename}")
            return f"offline_{hash(filename)}"

        invoice_data["pdf_path"] = filename
        invoice_data["user_id"] = user_id
        return self.add_invoice(invoice_data)

    def add_invoice(self, invoice_data: Dict[str, Any]) -> str:
        session = self.get_session()
        if session is None:
            print("⚠️  No database session available")
            return f"offline_{hash(str(invoice_data))}"

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
            print(f"✅ Invoice saved to database: {invoice_id}")
            return invoice_id
        except Exception as e:
            session.rollback()
            print(f"❌ Error saving invoice: {e}")
            raise e
        finally:
            session.close()

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session()
        if session is None:
            return None

        try:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            return invoice.to_dict() if invoice else None
        finally:
            session.close()

    def get_all_invoices(
        self, session_id: str = None, user_id: str = "demo_user"
    ) -> List[Dict[str, Any]]:
        session = self.get_session()
        if session is None:
            return []

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

    def get_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        return self.get_all_invoices(user_id=user_id)

    def delete_invoice(self, invoice_id: str) -> bool:
        session = self.get_session()
        if session is None:
            return False

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
        if session is None:
            return False

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
        if session is None:
            return {"count": 0, "total_amount": 0.0}

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
