"""Enhanced exception classes for bank statement processing."""

from typing import Optional, List, Dict, Any


class BankStatementProcessorError(Exception):
    """Base exception for all bank statement processor errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize base exception.
        
        Args:
            message: Human-readable error message
            details: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """Return formatted error message."""
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


class UnsupportedBankError(BankStatementProcessorError):
    """Raised when factory cannot identify the bank from PDF content."""
    
    def __init__(self, pdf_path: str, detected_content: Optional[str] = None, 
                 supported_banks: Optional[List[str]] = None):
        """Initialize UnsupportedBankError.
        
        Args:
            pdf_path: Path to the PDF file
            detected_content: Sample content found in PDF
            supported_banks: List of currently supported banks
        """
        self.pdf_path = pdf_path
        self.detected_content = detected_content
        self.supported_banks = supported_banks or []
        
        message = f"Cannot identify bank type from PDF: {pdf_path}"
        
        details = {
            "pdf_path": pdf_path,
            "supported_banks": ", ".join(self.supported_banks) if self.supported_banks else "None"
        }
        
        if detected_content:
            details["detected_content"] = detected_content[:100] + "..." if len(detected_content) > 100 else detected_content
        
        super().__init__(message, details)
    
    @property
    def help_message(self) -> str:
        """Provide helpful guidance for resolving this error."""
        if self.supported_banks:
            banks_list = "\n  - ".join(self.supported_banks)
            return (f"Currently supported banks:\n  - {banks_list}\n\n"
                   f"If your bank should be supported, please check:\n"
                   f"1. PDF is a valid bank statement (not corrupted)\n"
                   f"2. PDF contains the bank name/logo in the header\n"
                   f"3. Statement format matches expected layout")
        return "No banks are currently supported. Please check the parser configuration."


class PasswordProtectedPDFError(BankStatementProcessorError):
    """Raised when PDF is encrypted and requires a password."""
    
    def __init__(self, pdf_path: str, attempted_password: bool = False):
        """Initialize PasswordProtectedPDFError.
        
        Args:
            pdf_path: Path to the encrypted PDF file
            attempted_password: Whether a password was already attempted
        """
        self.pdf_path = pdf_path
        self.attempted_password = attempted_password
        
        if attempted_password:
            message = f"PDF is password-protected and provided password is incorrect: {pdf_path}"
        else:
            message = f"PDF is password-protected and requires a password: {pdf_path}"
        
        details = {
            "pdf_path": pdf_path,
            "attempted_password": attempted_password
        }
        
        super().__init__(message, details)
    
    @property
    def help_message(self) -> str:
        """Provide helpful guidance for resolving this error."""
        if self.attempted_password:
            return ("The provided password is incorrect. Please:\n"
                   "1. Verify the password is correct\n"
                   "2. Check if the PDF uses a different protection method\n"
                   "3. Try downloading a new copy of the statement")
        return ("This PDF is password-protected. Please:\n"
               "1. Provide the password when calling the parser\n"
               "2. Check your bank's documentation for default passwords\n"
               "3. Contact your bank if you don't know the password")


class StatementLayoutError(BankStatementProcessorError):
    """Raised when extractor fails to find expected data in the statement."""
    
    def __init__(self, pdf_path: str, missing_elements: List[str], 
                 bank_name: Optional[str] = None, page_count: Optional[int] = None):
        """Initialize StatementLayoutError.
        
        Args:
            pdf_path: Path to the PDF file
            missing_elements: List of expected elements that were not found
            bank_name: Detected bank name if available
            page_count: Number of pages in the PDF
        """
        self.pdf_path = pdf_path
        self.missing_elements = missing_elements
        self.bank_name = bank_name
        self.page_count = page_count
        
        elements_str = ", ".join(missing_elements)
        message = f"Statement layout does not match expected format: missing {elements_str}"
        
        details = {
            "pdf_path": pdf_path,
            "missing_elements": missing_elements,
            "element_count": len(missing_elements)
        }
        
        if bank_name:
            details["detected_bank"] = bank_name
        if page_count:
            details["page_count"] = page_count
        
        super().__init__(message, details)
    
    @property
    def help_message(self) -> str:
        """Provide helpful guidance for resolving this error."""
        bank_info = f" for {self.bank_name}" if self.bank_name else ""
        return (f"The statement layout{bank_info} is not recognized. This could mean:\n"
               f"1. The PDF is not a bank statement\n"
               f"2. The bank has changed their statement format\n"
               f"3. The PDF is corrupted or partially loaded\n"
               f"4. This is a different type of document\n\n"
               f"Missing elements: {', '.join(self.missing_elements)}")


class InvalidTransactionError(BankStatementProcessorError):
    """Raised when transaction data fails validation."""
    
    def __init__(self, transaction_data: Dict[str, Any], validation_errors: List[str], 
                 transaction_index: Optional[int] = None):
        """Initialize InvalidTransactionError.
        
        Args:
            transaction_data: The invalid transaction data
            validation_errors: List of validation error messages
            transaction_index: Index of transaction in the statement (if applicable)
        """
        self.transaction_data = transaction_data
        self.validation_errors = validation_errors
        self.transaction_index = transaction_index
        
        index_info = f" at index {transaction_index}" if transaction_index is not None else ""
        error_count = len(validation_errors)
        message = f"Transaction{index_info} failed validation with {error_count} error(s)"
        
        details = {
            "validation_errors": validation_errors,
            "error_count": error_count
        }
        
        if transaction_index is not None:
            details["transaction_index"] = transaction_index
        
        # Include safe transaction data (exclude sensitive info)
        safe_data = {}
        for key, value in transaction_data.items():
            if key not in ['account_number', 'reference'] and value is not None:
                if isinstance(value, str) and len(str(value)) > 50:
                    safe_data[key] = str(value)[:47] + "..."
                else:
                    safe_data[key] = value
        details["transaction_summary"] = safe_data
        
        super().__init__(message, details)
    
    @property
    def help_message(self) -> str:
        """Provide helpful guidance for resolving this error."""
        errors_list = "\n  - ".join(self.validation_errors)
        return (f"Transaction validation failed with these issues:\n  - {errors_list}\n\n"
               f"To resolve:\n"
               f"1. Check if the source data is correct\n"
               f"2. Verify date and amount formats\n"
               f"3. Ensure required fields are present\n"
               f"4. Consider using lenient validation mode for minor issues")


class PDFProcessingError(BankStatementProcessorError):
    """Raised when PDF cannot be processed due to technical issues."""
    
    def __init__(self, pdf_path: str, operation: str, original_error: Optional[Exception] = None):
        """Initialize PDFProcessingError.
        
        Args:
            pdf_path: Path to the PDF file
            operation: The operation that failed (e.g., 'reading', 'extracting tables')
            original_error: The underlying exception that caused this error
        """
        self.pdf_path = pdf_path
        self.operation = operation
        self.original_error = original_error
        
        message = f"Failed to process PDF during {operation}: {pdf_path}"
        if original_error:
            message += f" ({type(original_error).__name__}: {str(original_error)})"
        
        details = {
            "pdf_path": pdf_path,
            "operation": operation,
            "original_error_type": type(original_error).__name__ if original_error else None,
            "original_error_message": str(original_error) if original_error else None
        }
        
        super().__init__(message, details)
    
    @property
    def help_message(self) -> str:
        """Provide helpful guidance for resolving this error."""
        return (f"PDF processing failed during {self.operation}. This could indicate:\n"
               f"1. The PDF file is corrupted or invalid\n"
               f"2. The PDF uses an unsupported format or encryption\n"
               f"3. Insufficient system resources (memory, disk space)\n"
               f"4. File permissions issues\n\n"
               f"Try:\n"
               f"1. Re-downloading the PDF from your bank\n"
               f"2. Checking file permissions\n"
               f"3. Ensuring the PDF opens correctly in a PDF viewer")


class ExportError(BankStatementProcessorError):
    """Raised when data export fails."""
    
    def __init__(self, export_path: str, export_format: str, 
                 transaction_count: int, original_error: Optional[Exception] = None):
        """Initialize ExportError.
        
        Args:
            export_path: Path where export was attempted
            export_format: Format being exported to (e.g., 'CSV', 'JSON')
            transaction_count: Number of transactions being exported
            original_error: The underlying exception that caused this error
        """
        self.export_path = export_path
        self.export_format = export_format
        self.transaction_count = transaction_count
        self.original_error = original_error
        
        message = f"Failed to export {transaction_count} transactions to {export_format}: {export_path}"
        if original_error:
            message += f" ({type(original_error).__name__}: {str(original_error)})"
        
        details = {
            "export_path": export_path,
            "export_format": export_format,
            "transaction_count": transaction_count,
            "original_error_type": type(original_error).__name__ if original_error else None
        }
        
        super().__init__(message, details)
    
    @property
    def help_message(self) -> str:
        """Provide helpful guidance for resolving this error."""
        return (f"Export to {self.export_format} failed. Common causes:\n"
               f"1. Insufficient disk space\n"
               f"2. File permissions issues\n"
               f"3. Invalid characters in transaction data\n"
               f"4. Output directory doesn't exist\n\n"
               f"Try:\n"
               f"1. Checking available disk space\n"
               f"2. Ensuring output directory exists and is writable\n"
               f"3. Using a different output path")


def format_error_for_user(error: BankStatementProcessorError) -> str:
    """Format error message for user-friendly display.
    
    Args:
        error: The exception to format
        
    Returns:
        Formatted error message with help text
    """
    formatted = f"❌ {error.__class__.__name__}: {error.message}\n"
    
    if hasattr(error, 'help_message'):
        formatted += f"\n💡 {error.help_message}\n"
    
    return formatted