"""PDF table extraction utilities."""

import re
from typing import List, Dict, Any, Optional, Tuple
import pdfplumber
from pathlib import Path

from ..parsers.base_parser import PDFReadError


class TableExtractionError(Exception):
    """Raised when table extraction fails."""
    pass


class TableExtractor:
    """Utility class for extracting tables from PDF files."""
    
    def __init__(self, pdf_path: str, password: Optional[str] = None):
        """Initialize table extractor.
        
        Args:
            pdf_path: Path to the PDF file
            password: Optional password for encrypted PDFs
            
        Raises:
            PDFReadError: If PDF cannot be accessed
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
    
    def extract_all_tables(self) -> List[List[List[str]]]:
        """Extract all tables from all pages.
        
        Returns:
            List of tables, where each table is a list of rows,
            and each row is a list of cell values
            
        Raises:
            TableExtractionError: If tables cannot be extracted
        """
        all_tables = []
        
        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        tables = page.extract_tables()
                        if tables:
                            # Add page information to each table
                            for table in tables:
                                if table and len(table) > 1:  # Must have header + data
                                    clean_table = self._clean_table(table)
                                    if clean_table:
                                        all_tables.append(clean_table)
                    except Exception as e:
                        # Log warning but continue with other pages
                        continue
                        
            return all_tables
            
        except Exception as e:
            raise TableExtractionError(f"Cannot extract tables from PDF: {str(e)}") from e
    
    def extract_tables_from_page(self, page_num: int) -> List[List[List[str]]]:
        """Extract tables from a specific page.
        
        Args:
            page_num: Page number (0-based)
            
        Returns:
            List of tables from the specified page
            
        Raises:
            TableExtractionError: If tables cannot be extracted
        """
        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                if page_num >= len(pdf.pages):
                    raise TableExtractionError(f"Page {page_num} does not exist")
                
                page = pdf.pages[page_num]
                tables = page.extract_tables()
                
                clean_tables = []
                if tables:
                    for table in tables:
                        if table and len(table) > 1:
                            clean_table = self._clean_table(table)
                            if clean_table:
                                clean_tables.append(clean_table)
                
                return clean_tables
                
        except TableExtractionError:
            raise
        except Exception as e:
            raise TableExtractionError(f"Cannot extract tables from page {page_num}: {str(e)}") from e
    
    def find_transaction_tables(self, transaction_keywords: List[str]) -> List[Dict[str, Any]]:
        """Find tables that contain transaction data.
        
        Args:
            transaction_keywords: Keywords to identify transaction tables
            
        Returns:
            List of dictionaries containing table data and metadata
            
        Raises:
            TableExtractionError: If table search fails
        """
        transaction_tables = []
        
        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        tables = page.extract_tables()
                        if not tables:
                            continue
                        
                        for table_num, table in enumerate(tables):
                            if not table or len(table) < 2:
                                continue
                            
                            # Check if table contains transaction keywords
                            if self._contains_transaction_keywords(table, transaction_keywords):
                                clean_table = self._clean_table(table)
                                if clean_table:
                                    transaction_tables.append({
                                        'page_num': page_num,
                                        'table_num': table_num,
                                        'table_data': clean_table,
                                        'row_count': len(clean_table),
                                        'col_count': len(clean_table[0]) if clean_table else 0
                                    })
                    except Exception as e:
                        continue
                        
            return transaction_tables
            
        except Exception as e:
            raise TableExtractionError(f"Cannot find transaction tables: {str(e)}") from e
    
    def _clean_table(self, table: List[List[str]]) -> Optional[List[List[str]]]:
        """Clean and normalize table data.
        
        Args:
            table: Raw table data from pdfplumber
            
        Returns:
            Cleaned table data or None if table is invalid
        """
        if not table:
            return None
        
        cleaned_table = []
        
        for row in table:
            if not row:
                continue
            
            # Clean each cell
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_cell = ""
                else:
                    # Convert to string and clean whitespace
                    cleaned_cell = str(cell).strip()
                    # Remove multiple whitespace
                    cleaned_cell = re.sub(r'\s+', ' ', cleaned_cell)
                
                cleaned_row.append(cleaned_cell)
            
            # Only add rows that have some content
            if any(cell.strip() for cell in cleaned_row):
                cleaned_table.append(cleaned_row)
        
        return cleaned_table if cleaned_table else None
    
    def _contains_transaction_keywords(self, table: List[List[str]], keywords: List[str]) -> bool:
        """Check if table contains transaction-related keywords.
        
        Args:
            table: Table data to check
            keywords: Keywords to search for
            
        Returns:
            True if table contains transaction keywords
        """
        if not table or not keywords:
            return False
        
        # Check header row and first few data rows
        rows_to_check = table[:min(3, len(table))]
        
        # Combine all text from these rows
        combined_text = ' '.join(
            ' '.join(str(cell) for cell in row if cell) 
            for row in rows_to_check
        ).lower()
        
        # Count how many keywords are found
        keyword_count = sum(1 for keyword in keywords if keyword.lower() in combined_text)
        
        # Return True if at least 2 keywords are found
        return keyword_count >= 2
    
    def extract_table_with_settings(self, 
                                  page_num: int,
                                  table_settings: Optional[Dict[str, Any]] = None) -> List[List[List[str]]]:
        """Extract tables with custom pdfplumber settings.
        
        Args:
            page_num: Page number to extract from
            table_settings: Custom settings for table extraction
            
        Returns:
            List of extracted tables
            
        Raises:
            TableExtractionError: If extraction fails
        """
        default_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "edge_min_length": 3,
            "min_words_vertical": 3,
            "min_words_horizontal": 1,
            "intersection_tolerance": 3,
            "text_tolerance": 3
        }
        
        if table_settings:
            default_settings.update(table_settings)
        
        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                if page_num >= len(pdf.pages):
                    raise TableExtractionError(f"Page {page_num} does not exist")
                
                page = pdf.pages[page_num]
                tables = page.extract_tables(table_settings=default_settings)
                
                clean_tables = []
                if tables:
                    for table in tables:
                        if table and len(table) > 1:
                            clean_table = self._clean_table(table)
                            if clean_table:
                                clean_tables.append(clean_table)
                
                return clean_tables
                
        except TableExtractionError:
            raise
        except Exception as e:
            raise TableExtractionError(f"Cannot extract tables with custom settings: {str(e)}") from e
    
    def get_page_count(self) -> int:
        """Get the number of pages in the PDF.
        
        Returns:
            Number of pages
            
        Raises:
            PDFReadError: If PDF cannot be read
        """
        try:
            with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
                return len(pdf.pages)
        except Exception as e:
            raise PDFReadError(f"Cannot read PDF page count: {str(e)}") from e