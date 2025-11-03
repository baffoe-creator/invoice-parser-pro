import os
import tempfile
import secrets
from typing import Optional
import magic
from ...domain.exceptions import InvalidFileTypeError, FileTooLargeError

class SecureFileHandler:
    """Secure file upload and validation handler"""
    
    def __init__(self, max_file_size: int = 5_000_000, allowed_types: list = None):
        self.max_file_size = max_file_size
        self.allowed_types = allowed_types or ["application/pdf"]
    
    async def validate_file(self, file_content: bytes, filename: str) -> None:
        """Validate file type and size"""
        # Check file size
        if len(file_content) > self.max_file_size:
            raise FileTooLargeError(
                f"File size {len(file_content)} exceeds maximum {self.max_file_size}"
            )
        
        # Check MIME type using python-magic
        file_type = magic.from_buffer(file_content, mime=True)
        if file_type not in self.allowed_types:
            raise InvalidFileTypeError(
                f"File type {file_type} not allowed. Allowed: {self.allowed_types}"
            )
    
    def create_secure_temp_file(self, file_content: bytes) -> str:
        """Create secure temporary file with random name"""
        safe_name = f"invoice_{secrets.token_urlsafe(16)}.pdf"
        temp_path = os.path.join(tempfile.gettempdir(), safe_name)
        
        with open(temp_path, "wb") as f:
            f.write(file_content)
        
        return temp_path
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """Clean up temporary file"""
        if os.path.exists(file_path):
            os.remove(file_path)