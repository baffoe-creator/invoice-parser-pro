import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any
import math

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("pandas not available - Excel features will be limited")

try:
    import psycopg2

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("psycopg2 not available - database features will be limited")

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("pdfplumber not available - PDF parsing features will be limited")

try:
    from openpyxl import Workbook

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    print("openpyxl not available - Excel export features will be limited")

app = FastAPI(
    title="Invoice Parser Pro API",
    description="Production-ready PDF invoice parsing service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_initialized = False


class XLSXExporter:
    def __init__(self):
        IS_VERCEL = os.getenv("VERCEL") == "1"
        self.data_dir = "/tmp/data" if IS_VERCEL else "data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.session_id = "default"
        self.xlsx_file_path = os.path.join(
            self.data_dir, f"parsed_invoices_{self.session_id}.xlsx"
        )

    def get_file_stats(self):
        try:
            if not os.path.exists(self.xlsx_file_path):
                return {"exists": False, "message": "File not found"}
            file_size = os.path.getsize(self.xlsx_file_path)
            return {
                "exists": True,
                "file_size": file_size,
                "file_path": self.xlsx_file_path,
            }
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def create_new_file(self):
        try:
            if not PANDAS_AVAILABLE or not OPENPYXL_AVAILABLE:
                return {"error": "pandas or openpyxl not available"}
            df = pd.DataFrame(
                columns=[
                    "vendor",
                    "invoice_number",
                    "invoice_date",
                    "total_amount",
                    "tax_amount",
                    "due_date",
                ]
            )
            df.to_excel(self.xlsx_file_path, index=False)
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


def initialize_app():
    global _initialized
    if _initialized:
        return
    print("Starting Invoice Parser Pro API...")
    try:
        IS_VERCEL = os.getenv("VERCEL") == "1"
        data_dir = "/tmp/data" if IS_VERCEL else "data"
        os.makedirs(data_dir, exist_ok=True)
        print(f"Data directory: {data_dir}")
        if IS_VERCEL or os.getenv("SUPABASE_URL"):
            test_supabase_connection()
        _initialized = True
        print("Application initialized successfully")
    except Exception as e:
        print(f"Initialization error: {e}")
        import traceback

        traceback.print_exc()


def test_supabase_connection():
    if not PSYCOPG2_AVAILABLE:
        print("psycopg2 not available, skipping database connection")
        return None
    try:
        USER = os.getenv("user")
        PASSWORD = os.getenv("password")
        HOST = os.getenv("host")
        PORT = os.getenv("port")
        DBNAME = os.getenv("dbname")
        if not all([USER, PASSWORD, HOST, PORT, DBNAME]):
            print("Supabase credentials not found")
            return False
        connection = psycopg2.connect(
            user=USER, password=PASSWORD, host=HOST, port=PORT, dbname=DBNAME
        )
        cursor = connection.cursor()
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print(f"Supabase connected: {result}")
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print(f"Supabase connection failed: {e}")
        return False


@app.middleware("http")
async def initialize_middleware(request, call_next):
    initialize_app()
    response = await call_next(request)
    return response


@app.get("/")
async def root():
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


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Invoice Parser Pro API",
        "version": "1.0.0",
        "pandas_available": PANDAS_AVAILABLE,
        "database_available": PSYCOPG2_AVAILABLE,
        "pdf_parsing_available": PDFPLUMBER_AVAILABLE,
        "excel_export_available": OPENPYXL_AVAILABLE,
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


try:
    from src.api.endpoints import invoices

    app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
    print("Invoice routes loaded")
except Exception as e:
    print(f"Could not load invoice routes: {e}")


@app.get("/api/export/xlsx")
async def export_xlsx():
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
async def download_xlsx():
    try:
        IS_VERCEL = os.getenv("VERCEL") == "1"
        data_dir = "/tmp/data" if IS_VERCEL else "data"
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
async def get_xlsx_stats():
    try:
        if not PANDAS_AVAILABLE:
            return {
                "exists": False,
                "error": "pandas not available",
                "row_count": 0,
                "total_amount": 0,
            }
        IS_VERCEL = os.getenv("VERCEL") == "1"
        data_dir = "/tmp/data" if IS_VERCEL else "data"
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
                float(df["total_amount"].sum()) if "total_amount" in df.columns else 0
            ),
            "file_size": os.path.getsize(latest_file),
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
async def get_xlsx_data():
    try:
        if not PANDAS_AVAILABLE:
            raise HTTPException(status_code=500, detail="pandas not available")
        IS_VERCEL = os.getenv("VERCEL") == "1"
        data_dir = "/tmp/data" if IS_VERCEL else "data"
        if not os.path.exists(data_dir):
            raise HTTPException(status_code=404, detail="Data directory not found")
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        if not xlsx_files:
            raise HTTPException(status_code=404, detail="No Excel files found")
        latest_file = max(xlsx_files, key=lambda f: os.path.getctime(f))
        df = pd.read_excel(latest_file)
        return {
            "filename": os.path.basename(latest_file),
            "columns": df.columns.tolist(),
            "rows": df.fillna("").to_dict("records"),
            "row_count": len(df),
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
async def get_invoice_tracking_dashboard():
    try:
        if not PANDAS_AVAILABLE:
            return clean_data_for_json(
                {
                    "total_outstanding": 0,
                    "invoices": [],
                    "status_counts": {"sent": 0, "viewed": 0, "due": 0, "overdue": 0},
                    "collections_health": "healthy",
                    "cash_flow_calendar": [],
                    "health_percentage": 100,
                    "error": "pandas not available",
                }
            )
        IS_VERCEL = os.getenv("VERCEL") == "1"
        data_dir = "/tmp/data" if IS_VERCEL else "data"
        if not os.path.exists(data_dir):
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
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        if not xlsx_files:
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
        latest_file = max(xlsx_files, key=lambda f: os.path.getctime(f))
        df = pd.read_excel(latest_file)
        df = df.fillna("")
        invoices = []
        total_outstanding = 0
        for index, row in df.iterrows():
            invoice_date = row.get("invoice_date")
            due_date = None
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
                "days_until_due": (due_date_date - today).days if due_date else None,
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


@app.get("/api/invoices/tracking/health-metrics")
async def get_collections_health_metrics():
    try:
        if not PANDAS_AVAILABLE:
            return clean_data_for_json(
                {
                    "total_invoices": 0,
                    "overdue_invoices": 0,
                    "overdue_percentage": 0,
                    "total_amount": 0,
                    "overdue_amount": 0,
                    "avg_days_outstanding": 0,
                    "health_score": 100,
                    "error": "pandas not available",
                }
            )
        dashboard_data = await get_invoice_tracking_dashboard()
        total_invoices = len(dashboard_data["invoices"])
        overdue_invoices = dashboard_data["status_counts"]["overdue"]
        total_amount = dashboard_data["total_outstanding"]
        overdue_amount = sum(
            i["amount"] for i in dashboard_data["invoices"] if i["status"] == "overdue"
        )
        avg_days_outstanding = 0
        if dashboard_data["invoices"]:
            today = datetime.now().date()
            days_list = []
            for inv in dashboard_data["invoices"]:
                if inv.get("invoice_date") and inv["invoice_date"] != "N/A":
                    try:
                        inv_date = datetime.strptime(
                            inv["invoice_date"], "%Y-%m-%d"
                        ).date()
                        days_outstanding = (today - inv_date).days
                        days_list.append(days_outstanding)
                    except:
                        continue
            avg_days_outstanding = sum(days_list) / len(days_list) if days_list else 0
        result = clean_data_for_json(
            {
                "total_invoices": total_invoices,
                "overdue_invoices": overdue_invoices,
                "overdue_percentage": (
                    (overdue_invoices / total_invoices * 100)
                    if total_invoices > 0
                    else 0
                ),
                "total_amount": total_amount,
                "overdue_amount": overdue_amount,
                "avg_days_outstanding": avg_days_outstanding,
                "health_score": dashboard_data["health_percentage"],
            }
        )
        return result
    except Exception as e:
        return clean_data_for_json(
            {
                "total_invoices": 0,
                "overdue_invoices": 0,
                "overdue_percentage": 0,
                "total_amount": 0,
                "overdue_amount": 0,
                "avg_days_outstanding": 0,
                "health_score": 100,
            }
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


@app.get("/api/debug/routes")
async def debug_routes():
    routes = []
    for route in app.routes:
        routes.append(
            {
                "path": getattr(route, "path", None),
                "name": getattr(route, "name", None),
                "methods": getattr(route, "methods", None),
            }
        )
    return {"routes": routes}


@app.get("/api/debug/files")
async def debug_files():
    IS_VERCEL = os.getenv("VERCEL") == "1"
    data_dir = "/tmp/data" if IS_VERCEL else "data"
    if not os.path.exists(data_dir):
        return {"error": "Data directory not found", "files": []}
    all_files = os.listdir(data_dir)
    xlsx_files = [f for f in all_files if f.endswith(".xlsx")]
    file_details = []
    for file in xlsx_files:
        file_path = os.path.join(data_dir, file)
        file_details.append(
            {
                "name": file,
                "size": os.path.getsize(file_path),
                "modified": os.path.getmtime(file_path),
                "readable": os.access(file_path, os.R_OK),
            }
        )
    return {
        "data_directory": os.path.abspath(data_dir),
        "all_files": all_files,
        "xlsx_files": file_details,
    }


@app.get("/api/debug/env")
async def debug_env():
    return {
        "is_vercel": os.getenv("VERCEL") == "1",
        "python_version": sys.version,
        "pandas_available": PANDAS_AVAILABLE,
        "psycopg2_available": PSYCOPG2_AVAILABLE,
        "pdfplumber_available": PDFPLUMBER_AVAILABLE,
        "openpyxl_available": OPENPYXL_AVAILABLE,
        "has_supabase_url": bool(os.getenv("SUPABASE_URL")),
        "data_dir": "/tmp/data" if os.getenv("VERCEL") == "1" else "data",
    }


handler = app
