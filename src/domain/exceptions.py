class InvoiceParsingError(Exception):
    """Base exception for invoice parsing errors"""
    pass

class ParsingFailedError(InvoiceParsingError):
    """Raised when parsing fails"""
    pass

class InvalidFileTypeError(InvoiceParsingError):
    """Raised when file type is not supported"""
    pass

class FileTooLargeError(InvoiceParsingError):
    """Raised when file exceeds size limit"""
    pass

class VendorNotSupportedError(InvoiceParsingError):
    """Raised when vendor format is not supported"""
    pass
