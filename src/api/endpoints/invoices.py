import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Dict, Any
import logging
import tempfile
from src.infrastructure.repositories.supabase_repository import (
    SupabaseInvoiceRepository,
)

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


IMPORTS_AVAILABLE = True
print("✅ Core imports available")


class ParseInvoiceUseCase:
    def __init__(self, parser, repo, file_handler):
        self.parser = parser
        self.repo = repo
        self.file_handler = file_handler

    async def execute(self, file_content, filename, user_id):
        try:
            parsed_data = self.parser.parse_invoice(file_content, filename)
            saved_id = self.repo.save(parsed_data, user_id, filename)
            return {
                "success": True,
                "parsed_data": parsed_data,
                "saved_id": saved_id,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "parsed_data": {},
            }


class SQLAlchemyInvoiceRepository:
    def __init__(self, database_url):
        self.database_url = database_url
        print(f"📝 Fallback repository for: {database_url}")

    def save(self, invoice_data, user_id, filename):
        print(f"📝 Fallback save: {user_id}, {filename}")
        return f"fallback_{user_id}_{hash(filename)}"

    def get_by_user(self, user_id):
        print(f"📝 Fallback get_by_user: {user_id}")
        return []


class SecureFileHandler:
    async def validate_file(self, file_content, filename):
        if len(file_content) > 10 * 1024 * 1024:
            raise ValueError("File too large. Maximum size is 10MB.")
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")
        if not file_content.startswith(b"%PDF"):
            raise ValueError("Invalid PDF file format.")
        return True


class InvoiceDataNormalizer:
    def normalize(self, data, filename):
        normalized = {
            "vendor": data.get("vendor", "Unknown Vendor"),
            "invoice_number": data.get("invoice_number", "Unknown"),
            "invoice_date": data.get("invoice_date", "Unknown Date"),
            "total_amount": float(data.get("total_amount", 0)),
            "tax_amount": float(data.get("tax_amount", 0)),
            "due_date": data.get("due_date", ""),
            "currency": data.get("currency", "USD"),
            "filename": filename,
        }
        return normalized


class PdfPlumberParser:
    def parse_invoice(self, file_content, filename):
        try:
            import pdfplumber
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name

            extracted_data = {}

            try:
                with pdfplumber.open(tmp_file_path) as pdf:
                    full_text = ""
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            full_text += text + "\n"

                    extracted_data = {
                        "vendor": self._extract_vendor(full_text),
                        "invoice_number": self._extract_invoice_number(full_text),
                        "invoice_date": self._extract_date(full_text),
                        "total_amount": self._extract_total(full_text),
                        "currency": "USD",
                        "raw_text": full_text[:500],
                        "filename": filename,
                    }

            finally:
                os.unlink(tmp_file_path)

            return extracted_data

        except Exception as e:
            print(f"PDF parsing error: {e}")
            return {
                "vendor": "Unknown Vendor",
                "invoice_number": "Unknown",
                "invoice_date": "Unknown",
                "total_amount": 0.0,
                "currency": "USD",
                "error": str(e),
                "filename": filename,
            }

    def _extract_vendor(self, text):
        lines = text.split("\n")
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 2 and len(line) < 100:
                return line
        return "Unknown Vendor"

    def _extract_invoice_number(self, text):
        import re

        patterns = [
            r"Invoice\s*#?\s*:?\s*([A-Z0-9-]+)",
            r"Invoice\s*Number\s*:?\s*([A-Z0-9-]+)",
            r"INV-?(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return "Unknown"

    def _extract_date(self, text):
        import re

        patterns = [
            r"Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Invoice\s*Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return "Unknown Date"

    def _extract_total(self, text):
        import re

        patterns = [
            r"Total\s*:?\s*\$?(\d+[.,]\d+)",
            r"Amount\s*Due\s*:?\s*\$?(\d+[.,]\d+)",
            r"Balance\s*Due\s*:?\s*\$?(\d+[.,]\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except:
                    continue
        return 0.0


data_normalizer = InvoiceDataNormalizer()

router = APIRouter()
logger = logging.getLogger(__name__)


def get_invoice_repository():
    """Get the Supabase invoice repository"""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        # Fallback: construct from individual parts
        user = os.getenv("user")
        password = os.getenv("password")
        host = os.getenv("host")
        port = os.getenv("port", "5432")
        dbname = os.getenv("database", "postgres")

        if all([user, password, host]):
            database_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        else:
            raise HTTPException(
                status_code=503, detail="Database configuration not available"
            )

    return SupabaseInvoiceRepository(database_url)


def get_file_handler():
    return SecureFileHandler()


def get_xlsx_exporter() -> XLSXExporter:
    return XLSXExporter()


def get_invoice_parser():
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
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        file_content = await file.read()
        filename = file.filename
        await file_handler.validate_file(file_content, filename)
        use_case = ParseInvoiceUseCase(parser, repo, file_handler)
        parsed_result = await use_case.execute(file_content, filename, "demo_user")
        if not parsed_result["success"]:
            raise HTTPException(
                status_code=500, detail=parsed_result.get("error", "Parsing failed")
            )
        normalized_data = data_normalizer.normalize(
            parsed_result["parsed_data"], filename
        )
        export_result = xlsx_exporter.append_normalized_data(normalized_data, filename)
        return {
            "filename": filename,
            "parsed_data": parsed_result["parsed_data"],
            "normalized_data": normalized_data,
            "export_result": export_result,
            "saved_id": parsed_result.get("saved_id"),
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
                            "parsed_data": parsed_result["parsed_data"],
                            "normalized_data": normalized_data,
                            "export_result": export_result,
                            "saved_id": parsed_result.get("saved_id"),
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


@router.get("/health")
async def invoices_health():
    return {
        "status": "available",
        "xlsx_available": XLSX_AVAILABLE,
        "core_imports_available": True,
        "message": "Invoice parsing service ready",
    }
