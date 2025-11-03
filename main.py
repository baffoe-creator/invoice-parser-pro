import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from api.endpoints import invoices
from api.dependencies import get_auth_service, get_xlsx_exporter
from infrastructure.repositories.sqlalchemy_repo import SQLAlchemyInvoiceRepository
from xlsx_exporter import XLSXExporter
import pandas as pd
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
import math

app = FastAPI(
    title="Invoice Parser Pro API",
    description="Production-ready PDF invoice parsing service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def serve_frontend():
    return {"message": "Invoice Parser Pro API is running"}


app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Invoice Parser Pro API",
        "version": "1.0.0",
    }


@app.post("/api/auth/demo-login")
async def demo_login(auth_service=Depends(get_auth_service)):
    token = auth_service.create_access_token(
        {"user_id": "demo_user", "username": "demo"}
    )
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/export/xlsx")
async def export_xlsx(xlsx_exporter: XLSXExporter = Depends(get_xlsx_exporter)):
    try:
        if not os.path.exists(xlsx_exporter.xlsx_file_path):
            raise HTTPException(status_code=404, detail="No parsed invoices found")

        stats = xlsx_exporter.get_file_stats()

        return {
            "file_path": xlsx_exporter.xlsx_file_path,
            "filename": f"parsed_invoices_{xlsx_exporter.session_id}.xlsx",
            "message": "XLSX export available",
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/api/export/download-xlsx")
async def download_xlsx():
    try:
        data_dir = "data"
        print(f"🔍 Looking for Excel files in: {os.path.abspath(data_dir)}")

        if not os.path.exists(data_dir):
            print("❌ Data directory not found")
            raise HTTPException(status_code=404, detail="Data directory not found")

        # Find all Excel files with the pattern used by the application
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        xlsx_files = [os.path.basename(f) for f in xlsx_files]

        print(f"📁 Found Excel files: {xlsx_files}")

        if not xlsx_files:
            print("❌ No Excel files found")
            raise HTTPException(status_code=404, detail="No Excel files found")

        # Get the latest file by creation time
        latest_file = max(
            xlsx_files, key=lambda f: os.path.getctime(os.path.join(data_dir, f))
        )

        file_path = os.path.join(data_dir, latest_file)
        print(f"📄 Using latest file: {file_path}")

        # Extract session ID from filename
        if "session_" in latest_file:
            session_id = latest_file.split("session_")[1].replace(".xlsx", "")
        else:
            session_id = "export"

        if not os.access(file_path, os.R_OK):
            print("❌ File is not readable")
            raise HTTPException(status_code=403, detail="XLSX file is not readable")

        file_size = os.path.getsize(file_path)
        print(f"📊 File size: {file_size} bytes")

        if file_size == 0:
            print("❌ File is empty")
            raise HTTPException(status_code=500, detail="XLSX file is empty")

        filename = f"parsed_invoices_{session_id}.xlsx"
        print(f"⬇️ Downloading file: {filename}")

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Download failed: {str(e)}"
        print(f"❌ ERROR in download_xlsx: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/api/invoices/xlsx/stats")
async def get_xlsx_stats():
    try:
        data_dir = "data"
        if not os.path.exists(data_dir):
            return {
                "exists": False,
                "message": "Data directory not found",
                "session_id": None,
                "file_path": None,
                "row_count": 0,
                "total_amount": 0,
                "file_size": 0,
            }

        # Find all Excel files with the pattern used by the application
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        xlsx_files = [os.path.basename(f) for f in xlsx_files]

        if not xlsx_files:
            return {
                "exists": False,
                "message": "No Excel files found",
                "session_id": None,
                "file_path": None,
                "row_count": 0,
                "total_amount": 0,
                "file_size": 0,
            }

        # Get the latest file by creation time
        latest_file = max(
            xlsx_files, key=lambda f: os.path.getctime(os.path.join(data_dir, f))
        )

        file_path = os.path.join(data_dir, latest_file)

        # Extract session ID from filename
        if "session_" in latest_file:
            session_id = latest_file.split("session_")[1].replace(".xlsx", "")
        else:
            session_id = "default"

        # Read the Excel file
        df = pd.read_excel(file_path)

        total_amount = df["total_amount"].sum() if "total_amount" in df.columns else 0
        file_size = os.path.getsize(file_path)

        return {
            "exists": True,
            "session_id": session_id,
            "file_path": file_path,
            "row_count": len(df),
            "total_amount": float(total_amount),
            "file_size": file_size,
            "filename": latest_file,
        }

    except Exception as e:
        print(f"Error in get_xlsx_stats: {str(e)}")
        return {
            "exists": False,
            "error": str(e),
            "session_id": None,
            "file_path": None,
            "row_count": 0,
            "total_amount": 0,
            "file_size": 0,
        }


@app.get("/api/invoices/xlsx/data")
async def get_xlsx_data():
    """
    New endpoint to fetch Excel data for the Excel Viewer tab
    """
    try:
        data_dir = "data"
        print(
            f"🔍 [Excel Data Endpoint] Looking for Excel files in: {os.path.abspath(data_dir)}"
        )

        if not os.path.exists(data_dir):
            print("❌ [Excel Data Endpoint] Data directory not found")
            raise HTTPException(status_code=404, detail="Data directory not found")

        # Find all Excel files with the pattern used by the application
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        xlsx_files = [os.path.basename(f) for f in xlsx_files]

        print(f"📁 [Excel Data Endpoint] Found Excel files: {xlsx_files}")

        if not xlsx_files:
            print("❌ [Excel Data Endpoint] No Excel files found")
            raise HTTPException(status_code=404, detail="No Excel files found")

        # Get the latest file by creation time
        latest_file = max(
            xlsx_files, key=lambda f: os.path.getctime(os.path.join(data_dir, f))
        )

        file_path = os.path.join(data_dir, latest_file)
        print(f"📄 [Excel Data Endpoint] Using latest file: {file_path}")

        # Check if file is readable and not empty
        if not os.access(file_path, os.R_OK):
            print("❌ [Excel Data Endpoint] File is not readable")
            raise HTTPException(status_code=403, detail="XLSX file is not readable")

        file_size = os.path.getsize(file_path)
        print(f"📊 [Excel Data Endpoint] File size: {file_size} bytes")

        if file_size == 0:
            print("❌ [Excel Data Endpoint] File is empty")
            raise HTTPException(status_code=500, detail="XLSX file is empty")

        # Read the Excel file
        print("📖 [Excel Data Endpoint] Reading Excel file...")
        df = pd.read_excel(file_path)
        print(
            f"✅ [Excel Data Endpoint] Successfully read Excel file with {len(df)} rows and {len(df.columns)} columns"
        )
        print(f"📋 [Excel Data Endpoint] Columns: {df.columns.tolist()}")

        # Convert DataFrame to dictionary for JSON response
        data = {
            "filename": latest_file,
            "columns": df.columns.tolist(),
            "rows": df.fillna("").to_dict("records"),
            "row_count": len(df),
            "file_size": file_size,
            "last_modified": os.path.getmtime(file_path),
        }

        print(f"✅ [Excel Data Endpoint] Returning data with {len(data['rows'])} rows")
        return data

    except HTTPException:
        raise
    except pd.errors.EmptyDataError:
        print("❌ [Excel Data Endpoint] Excel file is empty")
        raise HTTPException(status_code=500, detail="Excel file is empty")
    except Exception as e:
        error_msg = f"Failed to read Excel data: {str(e)}"
        print(f"❌ [Excel Data Endpoint] ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


def clean_data_for_json(data):
    """
    Recursively clean data to remove NaN and other non-JSON-serializable values
    """
    if isinstance(data, dict):
        return {k: clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif isinstance(data, float) and (math.isnan(data) or math.isinf(data)):
        return None
    elif pd.isna(data):
        return None
    else:
        return data


@app.get("/api/invoices/tracking/dashboard")
async def get_invoice_tracking_dashboard():
    """
    Get data for the invoice tracking dashboard
    """
    try:
        data_dir = "data"
        print(
            f"🔍 [Invoice Tracking] Looking for Excel files in: {os.path.abspath(data_dir)}"
        )

        if not os.path.exists(data_dir):
            print("❌ [Invoice Tracking] Data directory not found")
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

        # Find the latest Excel file
        xlsx_files = glob.glob(os.path.join(data_dir, "parsed_invoices_*.xlsx"))
        print(f"📁 [Invoice Tracking] Found Excel files: {xlsx_files}")

        if not xlsx_files:
            print("❌ [Invoice Tracking] No Excel files found")
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
        print(f"📄 [Invoice Tracking] Using latest file: {latest_file}")

        # Read the Excel file and handle NaN values
        df = pd.read_excel(latest_file)
        df = df.fillna("")  # Replace NaN with empty strings

        print(f"✅ [Invoice Tracking] Successfully read Excel file with {len(df)} rows")

        # Transform parsed invoices into receivable tracking data
        invoices = []
        total_outstanding = 0

        for index, row in df.iterrows():
            # Calculate due date (30 days from invoice date if available)
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

            # Determine status based on due date and current date
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

            # Simulate some invoices as viewed
            vendor_str = str(row.get("vendor", ""))
            invoice_num_str = str(row.get("invoice_number", ""))
            if hash(vendor_str + invoice_num_str) % 3 == 0:  # Random selection for demo
                status = "viewed"

            # Handle amount - ensure it's a valid float
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

        # Calculate status counts
        status_counts = {
            "sent": len([i for i in invoices if i["status"] == "sent"]),
            "viewed": len([i for i in invoices if i["status"] == "viewed"]),
            "due": len([i for i in invoices if i["status"] == "due"]),
            "overdue": len([i for i in invoices if i["status"] == "overdue"]),
        }

        print(f"📊 [Invoice Tracking] Status counts: {status_counts}")

        # Calculate collections health
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

        print(
            f"🏥 [Invoice Tracking] Collections health: {collections_health} ({health_percentage:.1f}%)"
        )

        # Generate cash flow calendar
        cash_flow_calendar = []
        for i in range(30):  # Next 30 days
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

        print(
            f"📅 [Invoice Tracking] Cash flow calendar entries: {len(cash_flow_calendar)}"
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

        print(
            f"✅ [Invoice Tracking] Returning dashboard data with {len(invoices)} invoices"
        )
        return result

    except Exception as e:
        print(f"❌ [Invoice Tracking] Error in invoice tracking dashboard: {str(e)}")
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
    """
    Update invoice status (for demo purposes - in production, you'd save to database)
    """
    try:
        invoice_id = invoice_data.get("id")
        new_status = invoice_data.get("status")

        print(
            f"🔄 [Invoice Tracking] Updating invoice {invoice_id} to status: {new_status}"
        )

        # In a real application, you'd update this in a database
        # For now, we'll just return success
        return {
            "success": True,
            "message": f"Invoice status updated to {new_status}",
            "invoice_id": invoice_id,
        }
    except Exception as e:
        print(f"❌ [Invoice Tracking] Failed to update invoice status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update invoice status: {str(e)}"
        )


@app.get("/api/invoices/tracking/health-metrics")
async def get_collections_health_metrics():
    """
    Get detailed collections health metrics
    """
    try:
        print("📈 [Invoice Tracking] Getting health metrics")
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

        print(f"✅ [Invoice Tracking] Health metrics calculated: {result}")
        return result

    except Exception as e:
        print(f"❌ [Invoice Tracking] Error getting health metrics: {str(e)}")
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
async def create_new_xlsx(xlsx_exporter: XLSXExporter = Depends(get_xlsx_exporter)):
    try:
        result = xlsx_exporter.create_new_file()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create new XLSX: {str(e)}"
        )


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
    """
    Debug endpoint to check what files exist in the data directory
    """
    data_dir = "data"
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


if __name__ == "__main__":
    import uvicorn

    os.makedirs("data", exist_ok=True)

    database_url = os.getenv("DATABASE_URL", "sqlite:///./invoices.db")
    repo = SQLAlchemyInvoiceRepository(database_url)
    print("✅ Database initialized successfully")
    print("✅ All endpoints registered")

    print("📋 Registered routes:")
    for route in app.routes:
        if hasattr(route, "methods"):
            print(f"  {route.path} - {route.methods}")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
