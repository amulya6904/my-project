"""State Bank of India statement parser implementation."""

import re
from datetime import datetime
from typing import List, Optional, Dict, Any
import pdfplumber
from pathlib import Path

from .base_parser import BaseParser, Transaction, TransactionType, PDFReadError, TransactionExtractionError, ParserError


class SBIParser(BaseParser):
    """Parser for State Bank of India PDF statements.
    
    Expected format:
    Date | Details | Ref No./Cheque No | Debit | Credit | Balance
    Date Format: DD MMM YYYY HH:MM AM/PM
    Amount Format: XXXX.XX (no comma for thousands under 10000)
    Balance Format: XXXX.XX (absolute value)
    """
    
    # Regular expressions for SBI patterns
    SBI_HEADER_PATTERN = r'(?i)state\s+bank\s+of\s+india|sbi'
    DATE_PATTERN = r'\b\d{2}\s+[A-Z]{3}\s+\d{4}(?:\s+\d{2}:\d{2}\s+[AP]M)?\b'
    AMOUNT_PATTERN = r'\d+\.?\d{0,2}'
    UPI_PATTERN = r'UPI[A-Z]{2}/(\d+)/([A-Z]{2})/([\w\s]+)/([\w]+)/'
    ACCOUNT_PATTERN = r'(?i)account\s+no[.:]?\s*(\d{10,})'
    
    # Month abbreviations mapping
    MONTH_MAP = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    
    @property
    def bank_name(self) -> str:
        """Get the bank name."""
        return "State Bank of India"
    
    def detect_bank(self) -> bool:
        """Detect if PDF is from State Bank of India.
        
        Returns:
            True if PDF is from SBI, False otherwise
            
        Raises:
            PDFReadError: If PDF cannot be read
        """
        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                # Check first few pages for bank identifier
                for page_num in range(min(3, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if text and re.search(self.SBI_HEADER_PATTERN, text):
                        return True
                        
                return False
                
        except Exception as e:
            raise PDFReadError(f"Cannot read PDF {self.pdf_path}: {str(e)}") from e
    
    def get_account_number(self) -> Optional[str]:
        """Extract and mask account number from PDF.

        Returns:
            Masked account number (e.g., XXXX1234) or None if not found
        """
        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                for page in pdf.pages[:3]:  # Check first 3 pages
                    text = page.extract_text()
                    if text:
                        match = re.search(self.ACCOUNT_PATTERN, text)
                        if match:
                            account_num = match.group(1)
                            # Mask account number (show last 4 digits)
                            if len(account_num) > 4:
                                return 'X' * (len(account_num) - 4) + account_num[-4:]
                            return account_num

                return None  # Return None instead of raising error

        except Exception as e:
            return None  # Return None on any error instead of raising
    
    def extract_transactions(self) -> List[Transaction]:
        """Extract transactions from SBI PDF.

        Returns:
            List of Transaction objects

        Raises:
            TransactionExtractionError: If transactions cannot be extracted
        """
        transactions = []
        account_number = self.get_account_number() or "Unknown"  # Use "Unknown" if None

        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                for page in pdf.pages:
                    page_transactions = self._extract_page_transactions(page, account_number)
                    transactions.extend(page_transactions)

            if not transactions:
                raise TransactionExtractionError("No transactions found in PDF")

            return sorted(transactions, key=lambda x: x.date)

        except TransactionExtractionError:
            raise
        except Exception as e:
            raise TransactionExtractionError(f"Cannot extract transactions: {str(e)}") from e
    
    def _extract_page_transactions(self, page, account_number: str) -> List[Transaction]:
        """Extract transactions from a single page.
        
        Args:
            page: pdfplumber page object
            account_number: Masked account number
            
        Returns:
            List of transactions from this page
        """
        transactions = []
        
        try:
            # Extract tables from page
            tables = page.extract_tables()
            
            for table in tables:
                if not table or len(table) < 2:  # Need header + at least one row
                    continue
                    
                # Check if this looks like a transaction table
                header = table[0] if table[0] else []
                if not self._is_transaction_table(header):
                    continue
                
                # Process each transaction row
                for row in table[1:]:
                    if not row or len(row) < 5:  # Need at least 5 columns
                        continue
                        
                    transaction = self._parse_transaction_row(row, account_number)
                    if transaction:
                        transactions.append(transaction)
                        
        except Exception as e:
            # Log error but continue processing other pages
            pass
            
        return transactions
    
    def _is_transaction_table(self, header: List[str]) -> bool:
        """Check if table header indicates transaction data.
        
        Args:
            header: First row of table
            
        Returns:
            True if this appears to be a transaction table
        """
        if not header:
            return False
            
        header_text = ' '.join(str(cell) for cell in header if cell).lower()
        
        # Look for key column headers
        required_patterns = ['date', 'details', 'debit', 'credit', 'balance']
        found_patterns = sum(1 for pattern in required_patterns if pattern in header_text)
        
        return found_patterns >= 3  # At least 3 key columns present
    
    def _parse_transaction_row(self, row: List[str], account_number: str) -> Optional[Transaction]:
        """Parse a single transaction row.
        
        Args:
            row: Table row data
            account_number: Masked account number
            
        Returns:
            Transaction object or None if row cannot be parsed
        """
        try:
            # Expected columns: Date | Details | Ref No./Cheque No | Debit | Credit | Balance
            if len(row) < 5:
                return None
            
            # Extract and validate date
            date_str = str(row[0]).strip() if row[0] else ""
            if not re.match(self.DATE_PATTERN, date_str, re.IGNORECASE):
                return None
                
            transaction_date = self._parse_sbi_date(date_str)
            if not transaction_date:
                return None
            
            # Extract description
            description = str(row[1]).strip() if row[1] else ""
            if not description or description.lower() in ['none', 'null', '']:
                return None
            
            # Extract reference number
            reference = str(row[2]).strip() if row[2] and str(row[2]).strip() != "" else None
            
            # Extract amounts
            debit_str = str(row[3]).strip() if row[3] else ""
            credit_str = str(row[4]).strip() if row[4] else ""
            balance_str = str(row[5]).strip() if len(row) > 5 and row[5] else ""
            
            debit_amount = self._parse_amount(debit_str) if debit_str else None
            credit_amount = self._parse_amount(credit_str) if credit_str else None
            balance = self._parse_amount(balance_str) if balance_str else None
            
            if balance is None:
                return None
            
            # Determine transaction type and counterparty
            transaction_type, counterparty = self._classify_transaction(description)
            
            return Transaction(
                date=transaction_date,
                description=description,
                reference=reference,
                debit=debit_amount,
                credit=credit_amount,
                balance=balance,
                transaction_type=transaction_type,
                counterparty=counterparty,
                bank_name=self.bank_name,
                account_number=account_number
            )
            
        except Exception as e:
            # Skip invalid rows
            return None
    
    def _parse_sbi_date(self, date_str: str) -> Optional[datetime]:
        """Parse SBI date format (DD MMM YYYY HH:MM AM/PM).
        
        Args:
            date_str: Date string in SBI format
            
        Returns:
            datetime object or None if cannot be parsed
        """
        try:
            # Remove extra whitespace and normalize
            date_str = re.sub(r'\s+', ' ', date_str.strip())
            
            # Try with time first: "01 JAN 2024 10:30 AM"
            match = re.match(r'(\d{2})\s+([A-Z]{3})\s+(\d{4})(?:\s+\d{2}:\d{2}\s+[AP]M)?', 
                           date_str, re.IGNORECASE)
            
            if match:
                day = int(match.group(1))
                month_str = match.group(2).upper()
                year = int(match.group(3))
                
                if month_str in self.MONTH_MAP:
                    month = self.MONTH_MAP[month_str]
                    return datetime(year, month, day)
            
            return None
            
        except (ValueError, AttributeError):
            return None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float.
        
        Args:
            amount_str: Amount string (SBI format without commas for small amounts)
            
        Returns:
            Float amount or None if cannot be parsed
        """
        if not amount_str or amount_str.lower() in ['', 'none', 'null']:
            return None
            
        try:
            # Remove currency symbols and extra spaces
            clean_amount = re.sub(r'[₹\s]', '', amount_str)
            # SBI may still use commas for larger amounts
            clean_amount = clean_amount.replace(',', '')
            return float(clean_amount)
        except (ValueError, AttributeError):
            return None
    
    def _classify_transaction(self, description: str) -> tuple[TransactionType, Optional[str]]:
        """Classify transaction type and extract counterparty.
        
        Args:
            description: Transaction description
            
        Returns:
            Tuple of (TransactionType, counterparty)
        """
        desc_lower = description.lower()
        counterparty = None
        
        # UPI transactions
        upi_match = re.search(self.UPI_PATTERN, description, re.IGNORECASE)
        if upi_match or 'upi' in desc_lower:
            counterparty = self._extract_upi_counterparty(description)
            return TransactionType.UPI, counterparty
        
        # ATM transactions
        if 'atm' in desc_lower or 'cash withdrawal' in desc_lower:
            return TransactionType.ATM, None
        
        # Bank charges
        if any(word in desc_lower for word in ['charge', 'fee', 'commission', 'penalty', 'sms']):
            return TransactionType.CHARGE, None
        
        # Transfers
        if any(word in desc_lower for word in ['transfer', 'neft', 'rtgs', 'imps']):
            return TransactionType.TRANSFER, self._extract_transfer_counterparty(description)
        
        # Deposits
        if any(word in desc_lower for word in ['deposit', 'credit', 'salary', 'interest']):
            return TransactionType.DEPOSIT, None
        
        return TransactionType.OTHER, None
    
    def _extract_upi_counterparty(self, description: str) -> Optional[str]:
        """Extract counterparty from UPI transaction description.
        
        Args:
            description: UPI transaction description
            
        Returns:
            Counterparty name or None
        """
        # Try to match UPI pattern and extract merchant/user info
        upi_match = re.search(self.UPI_PATTERN, description, re.IGNORECASE)
        if upi_match:
            return upi_match.group(3)  # Third group should be merchant/user name
        
        # Fallback: look for common UPI patterns
        patterns = [
            r'(?i)to\s+([^/\s]+)',
            r'(?i)from\s+([^/\s]+)',
            r'(?i)upi.*?([A-Za-z]+@[A-Za-z]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_transfer_counterparty(self, description: str) -> Optional[str]:
        """Extract counterparty from transfer transaction description.
        
        Args:
            description: Transfer transaction description
            
        Returns:
            Counterparty name or None
        """
        # Look for common transfer patterns
        patterns = [
            r'(?i)to\s+([A-Za-z\s]+?)(?:\s|$)',
            r'(?i)from\s+([A-Za-z\s]+?)(?:\s|$)',
            r'(?i)transfer.*?to\s+([A-Za-z\s]+?)(?:\s|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                counterparty = match.group(1).strip()
                # Filter out common non-name words
                if counterparty.lower() not in ['account', 'bank', 'self']:
                    return counterparty
        
        return None