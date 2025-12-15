import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.infrastructure.parsers.pdfplumber_parser import PdfPlumberParser
from src.infrastructure.repositories.supabase_repository import (
    SupabaseInvoiceRepository,
)
from src.infrastructure.repositories.sqlalchemy_repo import SQLAlchemyInvoiceRepository
from src.infrastructure.file_handlers.secure_file_handler import SecureFileHandler
from src.application.use_cases.parse_invoice import ParseInvoiceUseCase
from src.application.services.auth_service import AuthService
from src.xlsx_exporter import XLSXExporter

security = HTTPBearer()


def get_repository():
    if os.getenv("VERCEL") or os.getenv("SUPABASE_URL"):
        database_url = os.getenv("DATABASE_URL")
        return SupabaseInvoiceRepository(database_url)
    else:
        database_url = os.getenv("LOCAL_DATABASE_URL", "sqlite:///./invoices.db")
        return SQLAlchemyInvoiceRepository(database_url)


def get_parser():
    return PdfPlumberParser()


def get_file_handler():
    max_file_size = int(os.getenv("MAX_FILE_SIZE", "5000000"))
    return SecureFileHandler(max_file_size=max_file_size)


def get_xlsx_exporter():
    return XLSXExporter()


def get_use_case(
    parser: PdfPlumberParser = Depends(get_parser),
    repo=Depends(get_repository),
    file_handler: SecureFileHandler = Depends(get_file_handler),
):
    return ParseInvoiceUseCase(parser, repo, file_handler)


def get_auth_service():
    secret_key = os.getenv("JWT_SECRET")
    if not secret_key or secret_key == "your-super-secret-key-change-in-production":
        raise Exception(
            "JWT_SECRET not set in environment variables. "
            "Generate one using: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    return AuthService(secret_key=secret_key)


def authenticate_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
):
    payload = auth_service.verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
