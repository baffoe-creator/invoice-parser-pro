import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
import datetime
from typing import List, Dict, Any
import logging

from src.infrastructure.repositories.supabase_repository import (
    SupabaseInvoiceRepository,
)
from src.infrastructure.parsers.pdfplumber_parser import PdfPlumberParser
from src.application.services.data_normalizer import InvoiceDataNormalizer

try:
    from src.xlsx_exporter import XLSXExporter

    XLSX_AVAILABLE = True
    print("✅ XLSXExporter imported successfully")
except ImportError as e:
    XLSX_AVAILABLE = False
    print(f"❌ XLSXExporter import failed: {e}")

IMPORTS_AVAILABLE = True
print("✅ Core imports available")

pdfplumber_parser = PdfPlumberParser()
data_normalizer = InvoiceDataNormalizer()


class ParseInvoiceUseCase:
    def __init__(self, parser, repository, file_handler):
        self.parser = parser
        self.repository = repository
        self.file_handler = file_handler

    async def execute(
        self, file_content: bytes, filename: str, user_id: str
    ) -> Dict[str, Any]:
        try:
            print(f"🔍 USE CASE: Starting execution for {filename}")

            await self.file_handler.validate_file(file_content, filename)

            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as tmp_file:
                    tmp_file.write(file_content)
                    temp_path = tmp_file.name

                print("🔍 USE CASE: Calling PdfPlumberParser...")
                invoice_data = self.parser.parse(temp_path)

                print(f"💰 PDFPLUMBER PARSER EXTRACTED:")
                print(f"   vendor: {invoice_data.vendor}")
                print(f"   invoice_number: {invoice_data.invoice_number}")
                print(f"   subtotal: {invoice_data.subtotal}")
                print(f"   shipping_amount: {invoice_data.shipping_amount}")
                print(f"   tax_amount: {invoice_data.tax_amount}")
                print(f"   total_amount: {invoice_data.total_amount}")
                print(f"   discount_amount: {invoice_data.discount_amount}")

                parsed_dict = {
                    "vendor": invoice_data.vendor,
                    "invoice_number": invoice_data.invoice_number,
                    "invoice_date": invoice_data.invoice_date,
                    "subtotal": float(invoice_data.subtotal),
                    "shipping_amount": float(invoice_data.shipping_amount),
                    "tax_amount": float(invoice_data.tax_amount),
                    "total_amount": float(invoice_data.total_amount),
                    "currency": invoice_data.currency,
                    "discount_amount": float(invoice_data.discount_amount),
                    "discount_percentage": float(invoice_data.discount_percentage),
                    "line_items": [
                        {
                            "description": item.description,
                            "quantity": float(item.quantity),
                            "unit_price": float(item.unit_price),
                            "amount": float(item.amount),
                        }
                        for item in invoice_data.line_items
                    ],
                    "raw_text": invoice_data.raw_text,
                }

                parsed_dict = self._clean_parsed_data(parsed_dict)

                print("🔍 USE CASE: Saving to repository...")
                invoice_id = self.repository.save(parsed_dict, user_id, filename)

                return {
                    "success": True,
                    "invoice_id": invoice_id,
                    "parsed_data": parsed_dict,
                    "message": "Invoice parsed successfully",
                }

            except Exception as parse_error:
                print(f"❌ USE CASE: Parser error: {str(parse_error)}")
                import traceback

                print(f"❌ Full traceback:\n{traceback.format_exc()}")
                return {
                    "success": False,
                    "error": f"Parsing failed: {str(parse_error)}",
                    "message": "Failed to parse invoice content",
                }
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            print(f"❌ USE CASE: General error: {str(e)}")
            import traceback

            print(f"❌ Full traceback:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "message": "Failed to process invoice file",
            }

    def _clean_parsed_data(self, parsed_dict: Dict[str, Any]) -> Dict[str, Any]:
        financial_fields = [
            "subtotal",
            "shipping_amount",
            "tax_amount",
            "total_amount",
            "discount_amount",
            "discount_percentage",
        ]
        for field in financial_fields:
            if field not in parsed_dict or parsed_dict[field] is None:
                parsed_dict[field] = 0.0

        if "line_items" not in parsed_dict:
            parsed_dict["line_items"] = []

        return parsed_dict


router = APIRouter()
logger = logging.getLogger(__name__)


class SecureFileHandler:
    async def validate_file(self, file_content, filename):
        if len(file_content) > 10 * 1024 * 1024:
            raise ValueError("File too large. Maximum size is 10MB.")
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")
        if not file_content.startswith(b"%PDF"):
            raise ValueError("Invalid PDF file format.")
        return True


class SQLAlchemyInvoiceRepository:
    def __init__(self, database_url):
        self.database_url = database_url
        self.connected = False
        print(f"📝 Fallback repository initialized")

    def save(self, invoice_data, user_id, filename):
        print(f"📝 Fallback save: {user_id}, {filename}")
        return f"fallback_{user_id}_{hash(filename)}"

    def get_by_user(self, user_id):
        print(f"📝 Fallback get_by_user: {user_id}")
        return []

    def is_connected(self):
        return self.connected


def get_invoice_repository():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("⚠️ Database credentials not complete, using fallback repository")
        return SQLAlchemyInvoiceRepository("fallback")

    try:
        return SupabaseInvoiceRepository(database_url)
    except Exception as e:
        print(f"⚠️ Failed to initialize Supabase repository: {e}")
        return SQLAlchemyInvoiceRepository(database_url)


def get_file_handler():
    return SecureFileHandler()


def get_xlsx_exporter() -> XLSXExporter:
    return XLSXExporter()


def get_invoice_parser():
    return pdfplumber_parser


@router.post("/parse")
async def parse_invoice(
    file: UploadFile = File(...),
    repo: SupabaseInvoiceRepository = Depends(get_invoice_repository),
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

        if not parsed_result["success"]:
            raise HTTPException(
                status_code=500, detail=parsed_result.get("error", "Parsing failed")
            )

        normalized_data = data_normalizer.normalize(
            parsed_result["parsed_data"], filename
        )

        xlsx_exporter = XLSXExporter()
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
    repo: SupabaseInvoiceRepository = Depends(get_invoice_repository),
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
    repo: SupabaseInvoiceRepository = Depends(get_invoice_repository),
):
    try:
        if repo and repo.is_connected():
            invoices = repo.get_by_user("demo_user")
        else:
            invoices = []
        return {"invoices": invoices}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving invoices: {str(e)}"
        )


@router.post("/test")
async def test_parsing(
    file: UploadFile = File(...),
    repo: SupabaseInvoiceRepository = Depends(get_invoice_repository),
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
