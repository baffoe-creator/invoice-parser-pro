import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Dict, Any
import logging
import tempfile

# Graceful import for XLSXExporter with fallback
try:
    from src.xlsx_exporter import XLSXExporter

    XLSX_AVAILABLE = True
    print("✅ XLSXExporter imported successfully")
except ImportError as e:
    XLSX_AVAILABLE = False
    print(f"❌ XLSXExporter import failed: {e}")

    class XLSXExporter:
        def __init__(self, session_id: str = None):
            self.session_id = session_id or "default"
            print("⚠️ Using fallback XLSXExporter - Excel features disabled")

        def append_normalized_data(self, data, filename):
            return {
                "success": False,
                "error": "XLSX export not available - openpyxl missing",
                "filename": filename,
            }

        def get_file_stats(self):
            return {
                "exists": False,
                "error": "XLSX export not available - openpyxl missing",
                "session_id": self.session_id,
            }


try:
    from src.application.use_cases.parse_invoice import ParseInvoiceUseCase
    from src.infrastructure.repositories.sqlalchemy_repo import (
        SQLAlchemyInvoiceRepository,
    )
    from src.infrastructure.file_handlers.secure_file_handler import SecureFileHandler
    from src.application.services.data_normalizer import InvoiceDataNormalizer
    from src.infrastructure.parsers.pdfplumber_parser import PdfPlumberParser

    IMPORTS_AVAILABLE = True
    print("✅ All core imports successful")
except ImportError as e:
    IMPORTS_AVAILABLE = False
    print(f"❌ Some core imports failed: {e}")

    # Create minimal fallback classes
    class ParseInvoiceUseCase:
        def __init__(self, parser, repo, file_handler):
            self.parser = parser
            self.repo = repo
            self.file_handler = file_handler

        async def execute(self, file_content, filename, user_id):
            return {
                "success": False,
                "error": "ParseInvoiceUseCase not available",
                "parsed_data": {},
            }

    class SQLAlchemyInvoiceRepository:
        def __init__(self, database_url):
            self.database_url = database_url

        def get_by_user(self, user_id):
            return []

    class SecureFileHandler:
        async def validate_file(self, file_content, filename):
            return True

    class InvoiceDataNormalizer:
        def normalize(self, data, filename):
            return {"error": "Data normalizer not available"}

    class PdfPlumberParser:
        def parse_invoice(self, file_content, filename):
            return {"error": "PDF parser not available"}


router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize data_normalizer only if imports were successful
if IMPORTS_AVAILABLE:
    data_normalizer = InvoiceDataNormalizer()
else:
    data_normalizer = None


def get_invoice_repository():
    if not IMPORTS_AVAILABLE:
        return SQLAlchemyInvoiceRepository("sqlite:///./invoices.db")

    database_url = os.getenv("DATABASE_URL", "sqlite:///./invoices.db")
    return SQLAlchemyInvoiceRepository(database_url)


def get_file_handler():
    return SecureFileHandler()


def get_xlsx_exporter() -> XLSXExporter:
    return XLSXExporter()


def get_invoice_parser():
    if not IMPORTS_AVAILABLE:
        return PdfPlumberParser()
    return PdfPlumberParser()


@router.post("/parse")
async def parse_invoice(
    file: UploadFile = File(...),
    repo: SQLAlchemyInvoiceRepository = Depends(get_invoice_repository),
    file_handler: SecureFileHandler = Depends(get_file_handler),
    xlsx_exporter: XLSXExporter = Depends(get_xlsx_exporter),
    parser: PdfPlumberParser = Depends(get_invoice_parser),
):
    try:
        if not IMPORTS_AVAILABLE:
            raise HTTPException(
                status_code=503, detail="Core services not available - check imports"
            )

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        file_content = await file.read()
        filename = file.filename

        await file_handler.validate_file(file_content, filename)

        use_case = ParseInvoiceUseCase(parser, repo, file_handler)
        parsed_result = await use_case.execute(file_content, filename, "demo_user")

        normalized_data = data_normalizer.normalize(
            parsed_result["parsed_data"], filename
        )

        export_result = xlsx_exporter.append_normalized_data(normalized_data, filename)

        return {
            "filename": filename,
            "parsed_data": normalized_data,
            "normalized_data": normalized_data,
            "export_result": export_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing invoice: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error parsing invoice: {str(e)}")


@router.post("/bulk")
async def parse_bulk_invoices(
    files: List[UploadFile] = File(...),
    repo: SQLAlchemyInvoiceRepository = Depends(get_invoice_repository),
    file_handler: SecureFileHandler = Depends(get_file_handler),
    xlsx_exporter: XLSXExporter = Depends(get_xlsx_exporter),
    parser: PdfPlumberParser = Depends(get_invoice_parser),
):
    try:
        if not IMPORTS_AVAILABLE:
            return {
                "files_processed": len(files),
                "files_successful": 0,
                "detailed_results": [
                    {
                        "filename": f.filename,
                        "success": False,
                        "error": "Core services not available",
                    }
                    for f in files
                ],
                "message": "Service temporarily unavailable",
            }

        results = []
        successful_parses = 0

        for file in files:
            try:
                if not file.filename.lower().endswith(".pdf"):
                    results.append(
                        {
                            "filename": file.filename,
                            "success": False,
                            "error": "Only PDF files are supported",
                        }
                    )
                    continue

                file_content = await file.read()
                filename = file.filename

                await file_handler.validate_file(file_content, filename)

                use_case = ParseInvoiceUseCase(parser, repo, file_handler)
                parsed_result = await use_case.execute(
                    file_content, filename, "demo_user"
                )

                if parsed_result["success"]:
                    normalized_data = data_normalizer.normalize(
                        parsed_result["parsed_data"], filename
                    )
                    export_result = xlsx_exporter.append_normalized_data(
                        normalized_data, filename
                    )

                    results.append(
                        {
                            "filename": filename,
                            "success": True,
                            "parsed_data": normalized_data,
                            "normalized_data": normalized_data,
                            "export_result": export_result,
                        }
                    )
                    successful_parses += 1
                else:
                    results.append(
                        {
                            "filename": filename,
                            "success": False,
                            "error": parsed_result.get(
                                "error", "Unknown parsing error"
                            ),
                        }
                    )

            except Exception as e:
                logger.error(f"Error parsing {file.filename}: {str(e)}")
                results.append(
                    {"filename": file.filename, "success": False, "error": str(e)}
                )

        return {
            "files_processed": len(files),
            "files_successful": successful_parses,
            "detailed_results": results,
        }

    except Exception as e:
        logger.error(f"Error in bulk parsing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in bulk parsing: {str(e)}")


@router.get("/")
async def get_all_invoices(
    repo: SQLAlchemyInvoiceRepository = Depends(get_invoice_repository),
):
    try:
        invoices = repo.get_by_user("demo_user")
        return {"invoices": invoices}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving invoices: {str(e)}"
        )


@router.post("/test")
async def test_parsing(
    file: UploadFile = File(...),
    repo: SQLAlchemyInvoiceRepository = Depends(get_invoice_repository),
    file_handler: SecureFileHandler = Depends(get_file_handler),
    parser: PdfPlumberParser = Depends(get_invoice_parser),
):
    try:
        if not IMPORTS_AVAILABLE:
            raise HTTPException(
                status_code=503, detail="Core services not available - check imports"
            )

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        file_content = await file.read()
        filename = file.filename

        await file_handler.validate_file(file_content, filename)

        use_case = ParseInvoiceUseCase(parser, repo, file_handler)
        parsed_result = await use_case.execute(file_content, filename, "demo_user")

        if parsed_result["success"]:
            normalized_data = data_normalizer.normalize(
                parsed_result["parsed_data"], filename
            )
            return {
                "filename": filename,
                "raw_parsed_data": parsed_result["parsed_data"],
                "normalized_data": normalized_data,
                "message": "Test parsing completed successfully",
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=parsed_result.get("error", "Test parsing failed"),
            )

    except Exception as e:
        logger.error(f"Error in test parsing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in test parsing: {str(e)}")


@router.get("/xlsx/stats")
async def get_xlsx_stats(
    xlsx_exporter: XLSXExporter = Depends(get_xlsx_exporter),
):
    try:
        stats = xlsx_exporter.get_file_stats()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting XLSX stats: {str(e)}"
        )


# Add a simple health check for this router
@router.get("/health")
async def invoices_health():
    return {
        "status": "available" if IMPORTS_AVAILABLE else "degraded",
        "xlsx_available": XLSX_AVAILABLE,
        "core_imports_available": IMPORTS_AVAILABLE,
        "message": "Invoice parsing service"
        + (
            " (some features disabled)"
            if not IMPORTS_AVAILABLE or not XLSX_AVAILABLE
            else ""
        ),
    }
