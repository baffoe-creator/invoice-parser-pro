import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Dict, Any
import logging
import tempfile

from src.application.use_cases.parse_invoice import ParseInvoiceUseCase
from src.infrastructure.repositories.sqlalchemy_repo import SQLAlchemyInvoiceRepository
from src.infrastructure.file_handlers.secure_file_handler import SecureFileHandler
from src.xlsx_exporter import XLSXExporter
from src.application.services.data_normalizer import InvoiceDataNormalizer
from src.infrastructure.parsers.pdfplumber_parser import PdfPlumberParser

router = APIRouter()
logger = logging.getLogger(__name__)

data_normalizer = InvoiceDataNormalizer()


def get_invoice_repository():
    database_url = os.getenv("DATABASE_URL", "sqlite:///./invoices.db")
    return SQLAlchemyInvoiceRepository(database_url)


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
