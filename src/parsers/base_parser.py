"""Abstract base class for bank statement parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path


class TransactionType(Enum):
    """Enumeration of transaction types."""
    UPI = "UPI"
    ATM = "ATM"
    TRANSFER = "TRANSFER"
    CHARGE = "CHARGE"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    OTHER = "OTHER"


@dataclass
class Transaction:
    """Data model for a bank transaction."""
    date: datetime
    description: str
    reference: Optional[str]
    debit: Optional[float]
    credit: Optional[float]
    balance: float
    transaction_type: TransactionType
    counterparty: Optional[str]
    bank_name: str
    account_number: str


class ParserError(Exception):
    """Base exception for parser errors."""
    pass


class PDFReadError(ParserError):
    """Raised when PDF cannot be read."""
    pass


class BankDetectionError(ParserError):
    """Raised when bank cannot be detected from PDF."""
    pass


class TransactionExtractionError(ParserError):
    """Raised when transactions cannot be extracted."""
    pass


class BaseParser(ABC):
    """Abstract base class for bank statement parsers."""
    
    def __init__(self, pdf_path: str, password: Optional[str] = None):
        """Initialize parser with PDF path and optional password.
        
        Args:
            pdf_path: Path to the PDF file
            password: Optional password for encrypted PDFs
            
        Raises:
            PDFReadError: If PDF file cannot be accessed
        """
        self.pdf_path = Path(pdf_path)
        self.password = password
        self._validate_pdf_path()
        
    def _validate_pdf_path(self) -> None:
        """Validate that PDF path exists and is readable.
        
        Raises:
            PDFReadError: If PDF file doesn't exist or isn't readable
        """
        if not self.pdf_path.exists():
            raise PDFReadError(f"PDF file not found: {self.pdf_path}")
        
        if not self.pdf_path.is_file():
            raise PDFReadError(f"Path is not a file: {self.pdf_path}")
            
        if self.pdf_path.suffix.lower() != '.pdf':
            raise PDFReadError(f"File is not a PDF: {self.pdf_path}")
    
    @abstractmethod
    def detect_bank(self) -> bool:
        """Check if this parser can handle the PDF.
        
        Returns:
            True if this parser can handle the PDF, False otherwise
            
        Raises:
            PDFReadError: If PDF cannot be read
        """
        pass
    
    @abstractmethod
    def extract_transactions(self) -> List[Transaction]:
        """Extract transaction data from PDF.
        
        Returns:
            List of Transaction objects
            
        Raises:
            TransactionExtractionError: If transactions cannot be extracted
            PDFReadError: If PDF cannot be read
        """
        pass
    
    @abstractmethod
    def get_account_number(self) -> Optional[str]:
        """Extract account number from PDF.

        Returns:
            Masked account number or None if not found
        """
        pass
    
    @property
    @abstractmethod
    def bank_name(self) -> str:
        """Get the name of the bank this parser handles.
        
        Returns:
            Bank name as string
        """
        pass
    
    def parse(self) -> Dict[str, Any]:
        """Parse the PDF and return structured data.
        
        Returns:
            Dictionary containing transactions and metadata
            
        Raises:
            BankDetectionError: If this parser cannot handle the PDF
            TransactionExtractionError: If transactions cannot be extracted
        """
        if not self.detect_bank():
            raise BankDetectionError(f"{self.bank_name} parser cannot handle this PDF")
        
        transactions = self.extract_transactions()
        account_number = self.get_account_number() or "Unknown"

        return {
            'bank_name': self.bank_name,
            'account_number': account_number,
            'transactions': transactions,
            'total_transactions': len(transactions),
            'parsed_at': datetime.now()
        }