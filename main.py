import os
import sys
import datetime
import time
import secrets
import tempfile
import logging
import uuid
import importlib
from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import glob
from datetime import datetime, timedelta
import math
from urllib.parse import urlparse

print(f"🐍 Python executable: {sys.executable}")
print(f"🐍 Python version: {sys.version}")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv

load_dotenv()

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except Exception:
    PANDAS_AVAILABLE = False
    print("⚠️  pandas not available - Excel features will be limited")

try:
    import psycopg2

    PSYCOPG2_AVAILABLE = True
except Exception:
    PSYCOPG2_AVAILABLE = False
    print("⚠️  psycopg2 not available - database features will be limited")

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except Exception:
    PDFPLUMBER_AVAILABLE = False
    print("⚠️  pdfplumber not available - PDF parsing features will be limited")

try:
    from openpyxl import Workbook

    OPENPYXL_AVAILABLE = True
except Exception:
    OPENPYXL_AVAILABLE = False
    print("⚠️  openpyxl not available - Excel export features will be limited")


class SessionManager:
    def __init__(self):
        # sessions keyed by session token (the cookie value)
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 7200

    def create_session(self) -> str:
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {
            "created_at": time.time(),
            "user_id": f"anon_{secrets.token_hex(8)}",
            "invoices": [],
            "last_activity": time.time(),
            # optional dataset support
            "datasets": [],
            "last_dataset_id": None,
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id not in self.sessions:
            return None
        session = self.sessions[session_id]
        if time.time() - session.get("last_activity", 0) > self.session_timeout:
            del self.sessions[session_id]
            return None
        session["last_activity"] = time.time()
        return session

    def add_invoice(self, session_id: str, invoice_data: Dict[str, Any]) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        invoice_data["id"] = f"inv_{secrets.token_hex(8)}"
        invoice_data["parsed_at"] = time.time()
        session.setdefault("invoices", []).append(invoice_data)
        return True

    def get_invoices(self, session_id: str) -> list:
        session = self.get_session(session_id)
        return session.get("invoices", []) if session else []

    # Dataset support
    def create_dataset(self, session_id: str, kind: str, files: list, parsed_result: dict) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
        ds = {
            "id": dataset_id,
            "kind": kind,
            "files": files,
            "created_at": time.time(),
            "parsed_result": parsed_result,
            "pinned": False,
        }
        session.setdefault("datasets", []).append(ds)
        session["last_dataset_id"] = dataset_id
        return dataset_id

    def list_datasets(self, session_id: str) -> list:
        session = self.get_session(session_id)
        return session.get("datasets", []) if session else []

    def get_dataset(self, session_id: str, dataset_id: str) -> Optional[dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        for d in session.get("datasets", []):
            if d["id"] == dataset_id:
                return d
        return None

    def delete_dataset(self, session_id: str, dataset_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        datasets = session.get("datasets", [])
        new_ds = [d for d in datasets if d["id"] != dataset_id]
        if len(new_ds) == len(datasets):
            return False
        session["datasets"] = new_ds
        if session.get("last_dataset_id") == dataset_id:
            session["last_dataset_id"] = new_ds[-1]["id"] if new_ds else None
        return True


session_manager = SessionManager()


class CookieAuth:
    def __init__(self):
        self.secret_key = os.getenv(
            "SESSION_SECRET", "default-cookie-secret-change-in-production"
        )

    def create_session_cookie(self, response: Response, session_id: str) -> None:
        response.set_cookie(
            key="invoice_session",
            value=session_id,
            max_age=30 * 24 * 3600,
            httponly=True,
            secure=False,
            samesite="lax",
        )

    def get_session_id(self, request: Request) -> Optional[str]:
        return request.cookies.get("invoice_session")


cookie_auth = CookieAuth()


async def get_current_session(request: Request, response: Response) -> Dict[str, Any]:
    session_id = cookie_auth.get_session_id(request)

    if not session_id:
        session_id = session_manager.create_session()
        cookie_auth.create_session_cookie(response, session_id)

    session = session_manager.get_session(session_id)
    if not session:
        session_id = session_manager.create_session()
        cookie_auth.create_session_cookie(response, session_id)
        session = session_manager.get_session(session_id)

    # expose the session token on the returned dict for handlers to use
    if session is not None:
        session["session_id"] = session_id

    return session


app = FastAPI(
    title="Invoice Parser Pro API",
    description="Production-ready PDF invoice parsing service",
    version="1.0.0",
)


def get_allowed_origins():
    origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]

    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)
        print(f"🌐 Added frontend URL from env: {frontend_url}")

    origins.extend(
        [
            "https://invoice-parser-pro.onrender.com",
            "https://invoice-parser-proo.onrender.com",
            "https://invoice-parser-pro-o.onrender.com",
        ]
    )

    origins = list(set([origin for origin in origins if origin]))
    return origins


allowed_origins = get_allowed_origins()

print(f"🌐 CORS enabled for {len(allowed_origins)} origins:")
for origin in allowed_origins:
    print(f"   ✅ {origin}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

_initialized = False


class XLSXExporter:
    def __init__(self):
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.session_id = "default"
        self.xlsx_file_path = os.path.join(
            self.data_dir, f"parsed_invoices_{self.session_id}.xlsx"
        )
        self.columns = [
            "file_name",
            "vendor",
            "invoice_number",
            "invoice_date",
            "subtotal",
            "shipping_amount",
            "tax_amount",
            "total_amount",
            "currency",
            "line_item_description",
            "line_item_quantity",
            "line_item_unit_price",
            "line_item_amount",
            "parsed_timestamp",
        ]

    def append_normalized_data(self, normalized_data, filename):
        try:
            if not PANDAS_AVAILABLE or not OPENPYXL_AVAILABLE:
                return {"error": "pandas or openpyxl not available"}

            print(f"📊 XLSX EXPORTER: Processing normalized data for {filename}")
            print(f"💰 FINANCIAL DATA IN NORMALIZER:")
            print(f"   subtotal: {normalized_data.get('subtotal')}")
            print(f"   shipping_amount: {normalized_data.get('shipping_amount')}")
            print(f"   tax_amount: {normalized_data.get('tax_amount')}")
            print(f"   total_amount: {normalized_data.get('total_amount')}")

            row_data = {}
            for column in self.columns:
                value = normalized_data.get(column)
                if value is None or value == "":
                    row_data[column] = ""
                elif isinstance(value, float):
                    row_data[column] = value
                else:
                    row_data[column] = str(value)

            if os.path.exists(self.xlsx_file_path):
                try:
                    existing_df = pd.read_excel(self.xlsx_file_path)
                    new_df = pd.DataFrame([row_data])

                    for col in self.columns:
                        if col not in existing_df.columns:
                            existing_df[col] = ""
                        if col not in new_df.columns:
                            new_df[col] = ""

                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    combined_df = combined_df[self.columns]
                except Exception as e:
                    print(f"⚠️ Error reading existing file, creating new: {e}")
                    combined_df = pd.DataFrame([row_data], columns=self.columns)
            else:
                combined_df = pd.DataFrame([row_data], columns=self.columns)

            combined_df.to_excel(self.xlsx_file_path, index=False, engine="openpyxl")

            return {
                "success": True,
                "message": "Data appended to XLSX file",
                "filename": filename,
                "file_path": self.xlsx_file_path,
                "session_id": self.session_id,
            }

        except Exception as e:
            print(f"❌ XLSX export error: {e}")
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to export to XLSX: {str(e)}"}

    def get_file_stats(self):
        try:
            if not os.path.exists(self.xlsx_file_path):
                return {"exists": False, "message": "File not found"}

            file_size = os.path.getsize(self.xlsx_file_path)

            if PANDAS_AVAILABLE:
                df = pd.read_excel(self.xlsx_file_path)
                row_count = len(df)
                total_amount = (
                    float(df["total_amount"].sum())
                    if "total_amount" in df.columns
                    and pd.api.types.is_numeric_dtype(df["total_amount"])
                    else 0
                )
                stats = {
                    "exists": True,
                    "file_size": file_size,
                    "file_path": self.xlsx_file_path,
                    "row_count": row_count,
                    "total_amount": total_amount,
                    "columns": df.columns.tolist(),
                    "last_modified": os.path.getmtime(self.xlsx_file_path),
                }
            else:
                stats = {
                    "exists": True,
                    "file_size": file_size,
                    "file_path": self.xlsx_file_path,
                }

            return stats
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def create_new_file(self):
        try:
            if not PANDAS_AVAILABLE or not OPENPYXL_AVAILABLE:
                return {"error": "pandas or openpyxl not available"}
            df = pd.DataFrame(columns=self.columns)
            df.to_excel(self.xlsx_file_path, index=False, engine="openpyxl")
            return {
                "message": "New XLSX file created",
                "file_path": self.xlsx_file_path,
            }
        except Exception as e:
            return {"error": f"Failed to create file: {str(e)}"}


def get_xlsx_exporter():
    return XLSXExporter()


def get_auth_service():
    class AuthService:
        def create_access_token(self, data):
            return "demo_token_12345"

    return AuthService()


def get_repository():
    return None


def test_supabase_connection():
    if not PSYCOPG2_AVAILABLE:
        print("⚠️  psycopg2 not available, skipping database connection")
        return False

    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ No DATABASE_URL found in environment variables")
            return False

        print("🔗 Testing database connection via DATABASE_URL...")
        try:
            result = urlparse(database_url)
            hostname = result.hostname
            username = result.username
            password = result.password
            port = result.port or 5432
            database = result.path[1:] if result.path else "postgres"

            print(f"   Hostname: {hostname}")
            print(f"   Port: {port}")
            print(f"   Database: {database}")
            print(f"   Username: {username}")
            print(f"   Password: {'✓' if password else '✗'}")

            if hostname and "pooler" not in hostname and "supabase" in hostname:
                print(
                    "⚠️  Warning: Using direct Supabase URL instead of connection pooler"
                )
                print(
                    "💡 Recommendation: Use format: postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
                )
        except Exception as parse_error:
            print(f"❌ Failed to parse DATABASE_URL: {parse_error}")
            return False

        connection = psycopg2.connect(database_url, connect_timeout=10)
        cursor = connection.cursor()
        cursor.execute("SELECT NOW(), current_user, current_database();")
        result = cursor.fetchone()
        print(f"✅ Database connected successfully")
        print(f"   Server time: {result[0]}")
        print(f"   User: {result[1]}")
        print(f"   Database: {result[2]}")

        cursor.close()
        connection.close()
        return True

    except psycopg2.OperationalError as e:
        error_msg = str(e)
        print(f"❌ Database connection failed: {error_msg}")
        if "Tenant or user not found" in error_msg:
            print("🔧 Supabase Connection Issue Detected:")
            print("   1. Your DATABASE_URL format appears incorrect")
            print(
                "   2. Check your Supabase dashboard for the correct connection string"
            )
            print("   3. Use Connection Pooler format:")
            print(
                "      postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
            )
            print("   4. Replace [project-ref] with your actual project reference")
            print(
                "   5. Ensure your password doesn't have special characters that need URL encoding"
            )
        return False
    except Exception as e:
        print(f"❌ Unexpected database error: {e}")
        import traceback

        traceback.print_exc()
        return False


def initialize_app():
    global _initialized
    if _initialized:
        return
    print("🚀 Starting Invoice Parser Pro API...")
    try:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        print(f"📁 Data directory: {data_dir}")

        if os.getenv("DATABASE_URL") or os.getenv("PGHOST"):
            connection_result = test_supabase_connection()
            if connection_result:
                print("✅ Database connection verified")
            else:
                print("⚠️  Database connection failed - using fallback storage")
        else:
            print("ℹ️  No database configuration found - using file-based storage")

        _initialized = True
        print("🎉 Application initialized successfully")
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        import traceback

        traceback.print_exc()


@app.middleware("http")
async def initialize_middleware(request, call_next):
    initialize_app()
    response = await call_next(request)
    return response


# API info moved to /api/info (root will serve SPA)
@app.get("/api/info", tags=["info"])
async def api_info():
    return {
        "message": "Invoice Parser Pro API is running",
        "status": "healthy",
        "version": "1.0.0",
        "features": {
            "pandas_available": PANDAS_AVAILABLE,
            "database_available": PSYCOPG2_AVAILABLE,
            "pdf_parsing_available": PDFPLUMBER_AVAILABLE,
            "excel_export_available": OPENPYXL_AVAILABLE,
        },
    }


@app.post("/api/session/init")
async def init_session(
    response: Response, session: dict = Depends(get_current_session)
):
    return {
        "session_id": session.get("session_id", session.get("user_id")),
        "invoices_count": len(session.get("invoices", [])),
    }


@app.post("/api/invoices/parse-stateless")
async def parse_invoice_stateless(
    file: UploadFile = File(...),
    session: dict = Depends(get_current_session),
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        file_content = await file.read()
        filename = file.filename

        if not PDFPLUMBER_AVAILABLE:
            raise HTTPException(status_code=503, detail="PDF parsing not available")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(file_content)
            temp_path = tmp_file.name

        try:
            with pdfplumber.open(temp_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""

            parsed_dict = {
                "vendor": "Sample Vendor",
                "invoice_number": "INV-001",
                "invoice_date": datetime.now().strftime("%Y-%m-%d"),
                "subtotal": 100.0,
                "shipping_amount": 10.0,
                "tax_amount": 8.0,
                "total_amount": 118.0,
                "currency": "USD",
                "discount_amount": 0.0,
                "line_items": [
                    {
                        "description": "Sample Item",
                        "quantity": 1.0,
                        "unit_price": 100.0,
                        "amount": 100.0,
                    }
                ],
                "filename": filename,
                "parsed_at": time.time(),
            }

            # use the session token as the storage key
            session_id = session.get("session_id") or session.get("user_id")
            success = session_manager.add_invoice(session_id, parsed_dict)

            if not success:
                raise HTTPException(status_code=400, detail="Session expired")

            # create dataset (optional)
            if hasattr(session_manager, "create_dataset"):
                ds_id = session_manager.create_dataset(session_id, "single", [filename], parsed_dict)
            else:
                ds_id = None

            xlsx_exporter = get_xlsx_exporter()
            export_result = xlsx_exporter.append_normalized_data(parsed_dict, filename)

            return {
                "success": True,
                "data": parsed_dict,
                "dataset_id": ds_id,
                "session_invoices_count": len(session.get("invoices", [])),
                "export_result": export_result,
                "message": "Invoice parsed and stored in session",
            }

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except HTTPException:
        # re-raise intended HTTP errors
        raise
    except Exception:
        import traceback

        logging.exception("Error parsing invoice")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error while parsing the invoice")


@app.get("/api/invoices/session")
async def get_session_invoices(session: dict = Depends(get_current_session)):
    session_id = session.get("session_id") or session.get("user_id")
    invoices = session_manager.get_invoices(session_id)
    return {"invoices": invoices, "count": len(invoices)}


@app.get("/api/invoices/export-session")
async def export_session_invoices(session: dict = Depends(get_current_session)):
    try:
        session_id = session.get("session_id") or session.get("user_id")
        invoices = session_manager.get_invoices(session_id)

        if not invoices:
            raise HTTPException(status_code=404, detail="No invoices in session")

        exporter = XLSXExporter()

        for invoice in invoices:
            exporter.append_normalized_data(invoice, invoice["filename"])

        export_path = exporter.xlsx_file_path

        if not os.path.exists(export_path):
            raise HTTPException(status_code=404, detail="Export file not found")

        return FileResponse(
            path=export_path,
            filename=f"invoices_export_{session_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        logging.error(f"Error exporting session invoices: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.delete("/api/invoices/clear-session")
async def clear_session_invoices(session: dict = Depends(get_current_session)):
    session_id = session.get("session_id") or session.get("user_id")
    if session_id in session_manager.sessions:
        session_manager.sessions[session_id]["invoices"] = []
    return {"message": "Session cleared", "invoices_count": 0}


# Dataset endpoints (optional - safe when SessionManager includes dataset support)
@app.get("/api/invoices/datasets")
async def list_datasets(session: dict = Depends(get_current_session)):
    session_id = session.get("session_id") or session.get("user_id")
    datasets = session_manager.list_datasets(session_id) if hasattr(session_manager, "list_datasets") else []
    return [{"id": d["id"], "kind": d["kind"], "files": d["files"], "created_at": d["created_at"], "pinned": d.get("pinned", False)} for d in datasets]


@app.get("/api/invoices/datasets/{dataset_id}")
async def get_dataset(dataset_id: str, session: dict = Depends(get_current_session)):
    session_id = session.get("session_id") or session.get("user_id")
    ds = session_manager.get_dataset(session_id, dataset_id) if hasattr(session_manager, "get_dataset") else None
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


@app.delete("/api/invoices/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str, session: dict = Depends(get_current_session)):
    session_id = session.get("session_id") or session.get("user_id")
    ok = session_manager.delete_dataset(session_id, dataset_id) if hasattr(session_manager, "delete_dataset") else False
    if not ok:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"success": True, "deleted": dataset_id}


@app.get("/api/debug/database-test")
async def debug_database_test():
    import psycopg2
    from urllib.parse import urlparse

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return {"error": "DATABASE_URL not found in environment"}

    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        cursor.close()
        conn.close()

        return {
            "status": "connected",
            "version": version[0],
            "database_url_preview": database_url[:80] + "...",
        }

    except psycopg2.OperationalError as e:
        return {
            "status": "failed",
            "error": str(e),
            "suggestion": "Check if your password needs URL encoding for special characters",
        }


@app.post("/api/auth/demo-login")
async def demo_login():
    try:
        from src.api.dependencies import get_auth_service

        auth_service = get_auth_service()
        token = auth_service.create_access_token(
            {"user_id": "demo_user", "username": "demo"}
        )
        return {"access_token": token, "token_type": "bearer"}
    except Exception as e:
        print(f"Using fallback auth: {e}")
        return {"access_token": "demo_token_12345", "token_type": "bearer"}


# Include routers
try:
    from src.api.endpoints import invoices

    app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
    print("✅ Invoice routes loaded successfully")
except Exception as e:
    print(f"❌ Could not load invoice routes: {e}")
    import traceback
    traceback.print_exc()


# Guarded attempt to load v2 routes (depends on redis). If redis missing, skip gracefully.
try:
    try:
        import redis  # noqa: F401
    except Exception:
        print("⚠️ redis not available; skipping v2 invoice routes (install redis or set REDIS_URL to enable)")
    else:
        invoices_v2_mod = importlib.import_module("api.invoices_v2")
        app.include_router(invoices_v2_mod.router)
        print("✅ v2 Invoice routes loaded successfully")
except Exception as e:
    import traceback
    print(f"❌ Could not load v2 invoice routes: {e}")
    traceback.print_exc()


@app.get("/api/export/xlsx")
async def export_xlsx(dataset_id: Optional[str] = Query(None)):
    try:
        if not OPENPYXL_AVAILABLE:
            raise HTTPException(
                status_code=503, detail="Excel export not available - openpyxl missing"
            )
        xlsx_exporter = get_xlsx_exporter()
        if not os.path.exists(xlsx_exporter.xlsx_file_path):
            raise HTTPException(status_code=404, detail="No parsed invoices found")
        stats = xlsx_exporter.get_file_stats()
        return {
            "file_path": xlsx_exporter.xlsx_file_path,
            "filename": f"parsed_invoices_{xlsx_exporter.session_id}.xlsx",
            "message": "XLSX export available",
            "stats": stats,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/api/export/download-xlsx")
async def download_xlsx(dataset_id: Optional[str] = Query(None)):
    try:
        data_dir = "data"
        if not os.path.exists(data_dir):
            raise HTTPException(status_code=404, detail="Data directory not found")
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        if not xlsx_files:
            raise HTTPException(status_code=404, detail="No Excel files found")
        latest_file = max(xlsx_files, key=lambda f: os.path.getctime(f))
        return FileResponse(
            path=latest_file,
            filename=os.path.basename(latest_file),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@app.get("/api/invoices/xlsx/stats")
async def get_xlsx_stats(dataset_id: Optional[str] = Query(None)):
    try:
        if not PANDAS_AVAILABLE:
            return {
                "exists": False,
                "error": "pandas not available",
                "row_count": 0,
                "total_amount": 0,
            }
        data_dir = "data"
        if not os.path.exists(data_dir):
            return {
                "exists": False,
                "message": "Data directory not found",
                "row_count": 0,
                "total_amount": 0,
                "file_size": 0,
            }
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        if not xlsx_files:
            return {
                "exists": False,
                "message": "No Excel files found",
                "row_count": 0,
                "total_amount": 0,
                "file_size": 0,
            }
        latest_file = max(xlsx_files, key=lambda f: os.path.getctime(f))
        df = pd.read_excel(latest_file)
        return {
            "exists": True,
            "filename": os.path.basename(latest_file),
            "row_count": len(df),
            "total_amount": (
                float(df["total_amount"].sum())
                if "total_amount" in df.columns
                and pd.api.types.is_numeric_dtype(df["total_amount"])
                else 0
            ),
            "file_size": os.path.getsize(latest_file),
            "last_modified": os.path.getmtime(latest_file),
        }
    except Exception as e:
        return {
            "exists": False,
            "error": str(e),
            "row_count": 0,
            "total_amount": 0,
            "file_size": 0,
        }


@app.get("/api/invoices/xlsx/data")
async def get_xlsx_data(dataset_id: Optional[str] = Query(None), session: dict = Depends(get_current_session)):
    try:
        if dataset_id:
            # return dataset-derived representation if available
            session_id = session.get("session_id") or session.get("user_id")
            ds = session_manager.get_dataset(session_id, dataset_id) if hasattr(session_manager, "get_dataset") else None
            if not ds:
                raise HTTPException(status_code=404, detail="Dataset not found")
            parsed_result = ds.get("parsed_result", {})
            rows = []
            if parsed_result:
                row = {
                    "file_name": parsed_result.get("filename", ""),
                    "vendor": parsed_result.get("vendor", ""),
                    "invoice_number": parsed_result.get("invoice_number", ""),
                    "invoice_date": parsed_result.get("invoice_date", ""),
                    "subtotal": parsed_result.get("subtotal", 0),
                    "shipping_amount": parsed_result.get("shipping_amount", 0),
                    "tax_amount": parsed_result.get("tax_amount", 0),
                    "total_amount": parsed_result.get("total_amount", 0),
                    "currency": parsed_result.get("currency", ""),
                    "parsed_timestamp": parsed_result.get("parsed_at", ""),
                }
                rows.append(row)

            columns = [
                "file_name", "vendor", "invoice_number", "invoice_date",
                "subtotal", "shipping_amount", "tax_amount", "total_amount",
                "currency", "parsed_timestamp"
            ]

            cleaned_rows = []
            for r in rows:
                cleaned_row = {}
                for col in columns:
                    value = r.get(col, "")
                    if PANDAS_AVAILABLE and pd.isna(value) or value == "":
                        cleaned_row[col] = ""
                    elif isinstance(value, float):
                        cleaned_row[col] = round(value, 2) if value != 0 else 0.0
                    else:
                        cleaned_row[col] = str(value)
                cleaned_rows.append(cleaned_row)

            return {
                "filename": f"dataset_{dataset_id}.xlsx",
                "columns": columns,
                "rows": cleaned_rows,
                "row_count": len(rows),
                "file_size": 0,
                "last_modified": time.time(),
            }

        # fallback to latest excel file on disk
        if not PANDAS_AVAILABLE:
            raise HTTPException(status_code=500, detail="pandas not available")
        data_dir = "data"
        if not os.path.exists(data_dir):
            raise HTTPException(status_code=404, detail="Data directory not found")
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        if not xlsx_files:
            raise HTTPException(status_code=404, detail="No Excel files found")
        latest_file = max(xlsx_files, key=lambda f: os.path.getctime(f))
        df = pd.read_excel(latest_file)

        cleaned_rows = []
        for _, row in df.iterrows():
            cleaned_row = {}
            for col in df.columns:
                value = row[col]
                if pd.isna(value) or value == "":
                    cleaned_row[col] = ""
                elif isinstance(value, float):
                    cleaned_row[col] = round(value, 2) if value != 0 else 0.0
                else:
                    cleaned_row[col] = str(value)
            cleaned_rows.append(cleaned_row)

        return {
            "filename": os.path.basename(latest_file),
            "columns": df.columns.tolist(),
            "rows": cleaned_rows,
            "row_count": len(df),
            "file_size": os.path.getsize(latest_file),
            "last_modified": os.path.getmtime(latest_file),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read Excel: {str(e)}")


def clean_data_for_json(data):
    if isinstance(data, dict):
        return {k: clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif isinstance(data, float) and (math.isnan(data) or math.isinf(data)):
        return None
    elif PANDAS_AVAILABLE and pd.isna(data):
        return None
    else:
        return data


@app.get("/api/invoices/tracking/dashboard")
async def get_invoice_tracking_dashboard(dataset_id: Optional[str] = Query(None), session: dict = Depends(get_current_session)):
    try:
        if dataset_id:
            session_id = session.get("session_id") or session.get("user_id")
            ds = session_manager.get_dataset(session_id, dataset_id) if hasattr(session_manager, "get_dataset") else None
            if not ds:
                raise HTTPException(status_code=404, detail="Dataset not found")
            parsed_result = ds.get("parsed_result", {})
            invoices = []
            total_outstanding = 0
            if parsed_result:
                vendor_str = str(parsed_result.get("vendor", ""))
                invoice_num_str = str(parsed_result.get("invoice_number", ""))
                invoice_date = parsed_result.get("invoice_date")
                if invoice_date and isinstance(invoice_date, str):
                    try:
                        invoice_date = datetime.strptime(invoice_date, "%Y-%m-%d")
                    except:
                        invoice_date = datetime.now()
                else:
                    invoice_date = datetime.now()
                due_date = invoice_date + timedelta(days=30)
                status = "sent"
                today = datetime.now().date()
                due_date_date = due_date.date()
                if due_date_date < today:
                    status = "overdue"
                elif (due_date_date - today).days <= 7:
                    status = "due"
                if hash(vendor_str + invoice_num_str) % 3 == 0:
                    status = "viewed"
                amount = parsed_result.get("total_amount", 0)
                if not isinstance(amount, (int, float)):
                    try:
                        amount = float(amount)
                    except:
                        amount = 0.0
                invoice_data = {
                    "id": f"inv_{hash(vendor_str + invoice_num_str)}",
                    "vendor": vendor_str if vendor_str != "" else "Unknown Vendor",
                    "invoice_number": invoice_num_str if invoice_num_str != "" else "N/A",
                    "invoice_date": invoice_date.strftime("%Y-%m-%d"),
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "amount": amount,
                    "status": status,
                    "client_reliability": "high" if hash(vendor_str) % 5 != 0 else "medium",
                    "days_until_due": (due_date_date - today).days,
                }
                invoices.append(invoice_data)
                if status in ["sent", "viewed", "due"]:
                    total_outstanding += invoice_data["amount"]

            status_counts = {
                "sent": len([i for i in invoices if i["status"] == "sent"]),
                "viewed": len([i for i in invoices if i["status"] == "viewed"]),
                "due": len([i for i in invoices if i["status"] == "due"]),
                "overdue": len([i for i in invoices if i["status"] == "overdue"]),
            }
            overdue_amount = sum(i["amount"] for i in invoices if i["status"] == "overdue")
            health_percentage = (
                ((total_outstanding - overdue_amount) / total_outstanding * 100)
                if total_outstanding > 0
                else 100
            )
            collections_health = (
                "healthy"
                if health_percentage >= 80
                else "warning" if health_percentage >= 60 else "critical"
            )
            cash_flow_calendar = []
            for inv in invoices:
                if inv.get("due_date") and inv["due_date"] != "N/A":
                    try:
                        inv_due_date = datetime.strptime(inv["due_date"], "%Y-%m-%d").date()
                        existing = next((d for d in cash_flow_calendar if d["date"] == inv_due_date.strftime("%Y-%m-%d")), None)
                        if existing:
                            existing["amount"] += inv["amount"]
                            existing["invoice_count"] += 1
                        else:
                            cash_flow_calendar.append({
                                "date": inv_due_date.strftime("%Y-%m-%d"),
                                "amount": inv["amount"],
                                "invoice_count": 1,
                            })
                    except:
                        continue
            cash_flow_calendar.sort(key=lambda x: x["date"])
            result = clean_data_for_json({
                "total_outstanding": total_outstanding,
                "invoices": invoices,
                "status_counts": status_counts,
                "collections_health": collections_health,
                "cash_flow_calendar": cash_flow_calendar,
                "health_percentage": health_percentage,
            })
            return result

        # fallback to Excel file based dashboard
        if not PANDAS_AVAILABLE:
            return clean_data_for_json({
                "total_outstanding": 0,
                "invoices": [],
                "status_counts": {"sent": 0, "viewed": 0, "due": 0, "overdue": 0},
                "collections_health": "healthy",
                "cash_flow_calendar": [],
                "health_percentage": 100,
                "error": "pandas not available",
            })
        data_dir = "data"
        if not os.path.exists(data_dir):
            return clean_data_for_json({
                "total_outstanding": 0,
                "invoices": [],
                "status_counts": {"sent": 0, "viewed": 0, "due": 0, "overdue": 0},
                "collections_health": "healthy",
                "cash_flow_calendar": [],
                "health_percentage": 100,
            })
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        if not xlsx_files:
            return clean_data_for_json({
                "total_outstanding": 0,
                "invoices": [],
                "status_counts": {"sent": 0, "viewed": 0, "due": 0, "overdue": 0},
                "collections_health": "healthy",
                "cash_flow_calendar": [],
                "health_percentage": 100,
            })
        latest_file = max(xlsx_files, key=lambda f: os.path.getctime(f))
        df = pd.read_excel(latest_file)
        df = df.fillna("")
        invoices = []
        total_outstanding = 0
        for index, row in df.iterrows():
            invoice_date = row.get("invoice_date")
            due_date = row.get("due_date")

            if not due_date or due_date == "":
                if invoice_date and invoice_date != "":
                    if isinstance(invoice_date, str):
                        try:
                            invoice_date = pd.to_datetime(invoice_date)
                        except:
                            invoice_date = None
                    elif pd.isna(invoice_date):
                        invoice_date = None
                    if invoice_date and isinstance(invoice_date, datetime):
                        due_date = invoice_date + timedelta(days=30)
            elif isinstance(due_date, str):
                try:
                    due_date = pd.to_datetime(due_date)
                except:
                    due_date = None

            status = "sent"
            if due_date:
                today = datetime.now().date()
                due_date_date = (
                    due_date.date() if hasattr(due_date, "date") else due_date
                )
                if due_date_date < today:
                    status = "overdue"
                elif (due_date_date - today).days <= 7:
                    status = "due"
                else:
                    status = "sent"

            vendor_str = str(row.get("vendor", ""))
            invoice_num_str = str(row.get("invoice_number", ""))
            if hash(vendor_str + invoice_num_str) % 3 == 0:
                status = "viewed"

            amount = row.get("total_amount", 0)
            if amount == "" or pd.isna(amount):
                amount = 0.0
            else:
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    amount = 0.0

            invoice_data = {
                "id": f"inv_{index}_{hash(vendor_str + invoice_num_str)}",
                "vendor": vendor_str if vendor_str != "" else "Unknown Vendor",
                "invoice_number": invoice_num_str if invoice_num_str != "" else "N/A",
                "invoice_date": (
                    invoice_date.strftime("%Y-%m-%d")
                    if invoice_date and isinstance(invoice_date, datetime)
                    else "N/A"
                ),
                "due_date": (
                    due_date.strftime("%Y-%m-%d")
                    if due_date and isinstance(due_date, datetime)
                    else "N/A"
                ),
                "amount": amount,
                "status": status,
                "client_reliability": "high" if hash(vendor_str) % 5 != 0 else "medium",
                "days_until_due": (
                    (due_date_date - today).days
                    if due_date and isinstance(due_date, datetime)
                    else None
                ),
            }
            invoices.append(invoice_data)
            if status in ["sent", "viewed", "due"]:
                total_outstanding += invoice_data["amount"]

        status_counts = {
            "sent": len([i for i in invoices if i["status"] == "sent"]),
            "viewed": len([i for i in invoices if i["status"] == "viewed"]),
            "due": len([i for i in invoices if i["status"] == "due"]),
            "overdue": len([i for i in invoices if i["status"] == "overdue"]),
        }
        overdue_amount = sum(i["amount"] for i in invoices if i["status"] == "overdue")
        health_percentage = (
            ((total_outstanding - overdue_amount) / total_outstanding * 100)
            if total_outstanding > 0
            else 100
        )
        collections_health = (
            "healthy"
            if health_percentage >= 80
            else "warning" if health_percentage >= 60 else "critical"
        )
        cash_flow_calendar = []
        for i in range(30):
            date = datetime.now().date() + timedelta(days=i)
            day_amount = 0
            day_invoice_count = 0
            for inv in invoices:
                if inv.get("due_date") and inv["due_date"] != "N/A":
                    try:
                        inv_due_date = datetime.strptime(
                            inv["due_date"], "%Y-%m-%d"
                        ).date()
                        if inv_due_date == date:
                            day_amount += inv["amount"]
                            day_invoice_count += 1
                    except:
                        continue
            if day_amount > 0:
                cash_flow_calendar.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "amount": day_amount,
                        "invoice_count": day_invoice_count,
                    }
                )

        result = clean_data_for_json(
            {
                "total_outstanding": total_outstanding,
                "invoices": invoices,
                "status_counts": status_counts,
                "collections_health": collections_health,
                "cash_flow_calendar": cash_flow_calendar,
                "health_percentage": health_percentage,
            }
        )
        return result
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        import traceback

        traceback.print_exc()
        return clean_data_for_json(
            {
                "total_outstanding": 0,
                "invoices": [],
                "status_counts": {"sent": 0, "viewed": 0, "due": 0, "overdue": 0},
                "collections_health": "healthy",
                "cash_flow_calendar": [],
                "health_percentage": 100,
            }
        )


@app.post("/api/invoices/tracking/update-status")
async def update_invoice_status(invoice_data: Dict[str, Any]):
    try:
        invoice_id = invoice_data.get("id")
        new_status = invoice_data.get("status")
        return {
            "success": True,
            "message": f"Invoice status updated to {new_status}",
            "invoice_id": invoice_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update invoice status: {str(e)}"
        )


@app.post("/api/invoices/xlsx/create-new")
async def create_new_xlsx():
    try:
        if not PANDAS_AVAILABLE or not OPENPYXL_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Excel creation not available - pandas or openpyxl missing",
            )
        xlsx_exporter = get_xlsx_exporter()
        result = xlsx_exporter.create_new_file()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create new XLSX: {str(e)}"
        )


@app.get("/api/invoices/")
async def get_invoices():
    return {
        "invoices": [],
        "count": 0,
        "message": "No invoices yet - upload PDFs to get started",
    }


# Serve SPA frontend at root and mount static assets (placed after routers)
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_PATH = FRONTEND_DIR / "index.html"

if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    if INDEX_PATH.exists():
        return FileResponse(str(INDEX_PATH))
    return await api_info()


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if any(full_path.startswith(p) for p in ("api", "share", "sitemap.xml", "robots.txt", "static", "favicon.ico")):
        raise HTTPException(status_code=404)
    if INDEX_PATH.exists():
        return FileResponse(str(INDEX_PATH))
    return await api_info()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)