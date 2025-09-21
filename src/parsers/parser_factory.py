"""Factory for creating bank statement parsers."""

import logging
from typing import Optional, List, Type, Dict, Any
from pathlib import Path
import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError

from .base_parser import BaseParser
from .union_bank_parser import UnionBankParser
from .sbi_parser import SBIParser
from ..core.exceptions import (
    UnsupportedBankError, 
    PasswordProtectedPDFError, 
    PDFProcessingError
)

# Configure logger
logger = logging.getLogger(__name__)


class ParserFactory:
    """Factory class for creating appropriate bank statement parsers."""
    
    # Registry of available parsers
    _parsers: List[Type[BaseParser]] = [
        UnionBankParser,
        SBIParser,
    ]
    
    # Bank detection patterns for content analysis
    _bank_patterns = {
        'Union Bank of India': [
            r'(?i)union\s+bank\s+of\s+india',
            r'(?i)UBI',
            r'(?i)union\s+bank'
        ],
        'State Bank of India': [
            r'(?i)state\s+bank\s+of\s+india',
            r'(?i)SBI',
            r'(?i)state\s+bank'
        ]
    }
    
    @classmethod
    def create_parser(cls, pdf_path: str, password: Optional[str] = None) -> BaseParser:
        """Create appropriate parser for the given PDF.
        
        Args:
            pdf_path: Path to the PDF file
            password: Optional password for encrypted PDFs
            
        Returns:
            Appropriate parser instance
            
        Raises:
            UnsupportedBankError: If no suitable parser is found
            PasswordProtectedPDFError: If PDF is encrypted
            PDFProcessingError: If PDF cannot be processed
        """
        pdf_path_obj = Path(pdf_path)
        logger.info(f"Attempting to create parser for: {pdf_path_obj.name}")
        
        # Analyze PDF content for bank detection
        detected_content, analysis_results = cls._analyze_pdf_content(pdf_path, password)
        
        # Try each parser in order based on analysis
        parser_candidates = cls._rank_parsers(analysis_results)
        
        for parser_class in parser_candidates:
            try:
                logger.debug(f"Testing parser: {parser_class.__name__}")
                parser = parser_class(pdf_path, password)
                
                if parser.detect_bank():
                    logger.info(f"Successfully created parser: {parser_class.__name__}")
                    return parser
                else:
                    logger.debug(f"Parser {parser_class.__name__} rejected PDF")
                    
            except PasswordProtectedPDFError:
                raise  # Re-raise password errors immediately
            except Exception as e:
                logger.debug(f"Parser {parser_class.__name__} failed: {str(e)}")
                continue
        
        # No parser could handle this PDF
        supported_banks = cls.get_supported_banks()
        logger.warning(f"No parser found for PDF: {pdf_path_obj.name}")
        
        raise UnsupportedBankError(
            pdf_path=pdf_path,
            detected_content=detected_content,
            supported_banks=supported_banks
        )
    
    @classmethod
    def _analyze_pdf_content(cls, pdf_path: str, password: Optional[str] = None) -> tuple[Optional[str], Dict[str, Any]]:
        """Analyze PDF content to assist with bank detection.
        
        Args:
            pdf_path: Path to PDF file
            password: Optional password for encrypted PDFs
            
        Returns:
            Tuple of (sample_content, analysis_results)
            
        Raises:
            PasswordProtectedPDFError: If PDF is encrypted
            PDFProcessingError: If PDF cannot be processed
        """
        try:
            with pdfplumber.open(pdf_path, password=password) as pdf:
                analysis_results = {
                    'page_count': len(pdf.pages),
                    'bank_confidence': {},
                    'has_tables': False,
                    'content_sample': None
                }
                
                # Extract text from first few pages
                sample_text = ""
                pages_to_check = min(3, len(pdf.pages))
                
                for page_num in range(pages_to_check):
                    try:
                        page = pdf.pages[page_num]
                        page_text = page.extract_text()
                        
                        if page_text:
                            sample_text += page_text + "\n"
                            
                        # Check for tables
                        if not analysis_results['has_tables']:
                            tables = page.extract_tables()
                            if tables:
                                analysis_results['has_tables'] = True
                                
                    except Exception as e:
                        logger.debug(f"Error extracting from page {page_num}: {str(e)}")
                        continue
                
                # Store content sample
                analysis_results['content_sample'] = sample_text[:500]
                
                # Analyze bank confidence scores
                cls._calculate_bank_confidence(sample_text, analysis_results)
                
                logger.debug(f"PDF analysis complete: {analysis_results['page_count']} pages, "
                           f"tables: {analysis_results['has_tables']}")
                
                return sample_text[:200], analysis_results
                
        except PDFSyntaxError as e:
            raise PDFProcessingError(pdf_path, "reading", e) from e
        except Exception as e:
            error_msg = str(e).lower()
            if 'password' in error_msg or 'encrypted' in error_msg:
                attempted = password is not None
                raise PasswordProtectedPDFError(pdf_path, attempted) from e
            else:
                raise PDFProcessingError(pdf_path, "content analysis", e) from e
    
    @classmethod
    def _calculate_bank_confidence(cls, content: str, analysis_results: Dict[str, Any]) -> None:
        """Calculate confidence scores for each bank based on content.
        
        Args:
            content: Extracted PDF text content
            analysis_results: Dictionary to store confidence scores
        """
        import re
        
        content_lower = content.lower()
        
        for bank_name, patterns in cls._bank_patterns.items():
            confidence = 0
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                confidence += len(matches) * 10  # 10 points per match
            
            # Additional heuristics
            if bank_name == 'Union Bank of India':
                if 'account statement' in content_lower:
                    confidence += 5
                if 'transaction' in content_lower:
                    confidence += 3
                    
            elif bank_name == 'State Bank of India':
                if 'statement of account' in content_lower:
                    confidence += 5
                if 'particulars' in content_lower:
                    confidence += 3
            
            analysis_results['bank_confidence'][bank_name] = confidence
            
        logger.debug(f"Bank confidence scores: {analysis_results['bank_confidence']}")
    
    @classmethod
    def _rank_parsers(cls, analysis_results: Dict[str, Any]) -> List[Type[BaseParser]]:
        """Rank parsers based on analysis results.
        
        Args:
            analysis_results: Results from PDF content analysis
            
        Returns:
            List of parser classes ranked by likelihood
        """
        confidence_scores = analysis_results.get('bank_confidence', {})
        
        # Create parser ranking based on confidence
        parser_scores = []
        
        for parser_class in cls._parsers:
            bank_name = parser_class.__new__(parser_class).bank_name
            confidence = confidence_scores.get(bank_name, 0)
            parser_scores.append((confidence, parser_class))
        
        # Sort by confidence (highest first)
        parser_scores.sort(key=lambda x: x[0], reverse=True)
        
        ranked_parsers = [parser_class for _, parser_class in parser_scores]
        
        logger.debug(f"Parser ranking: {[p.__name__ for p in ranked_parsers]}")
        
        return ranked_parsers
    
    @classmethod
    def get_supported_banks(cls) -> List[str]:
        """Get list of supported bank names.
        
        Returns:
            List of supported bank names
        """
        banks = []
        for parser_class in cls._parsers:
            try:
                # Create a dummy instance to get bank name
                # Using a dummy path that won't be validated
                dummy_parser = parser_class.__new__(parser_class)
                banks.append(dummy_parser.bank_name)
            except Exception:
                # Skip if we can't get the bank name
                continue
        
        return banks
    
    @classmethod
    def register_parser(cls, parser_class: Type[BaseParser]) -> None:
        """Register a new parser class.
        
        Args:
            parser_class: Parser class to register
            
        Raises:
            ValueError: If parser_class is not a BaseParser subclass
        """
        if not issubclass(parser_class, BaseParser):
            raise ValueError("Parser class must inherit from BaseParser")
        
        if parser_class not in cls._parsers:
            cls._parsers.append(parser_class)
    
    @classmethod
    def unregister_parser(cls, parser_class: Type[BaseParser]) -> bool:
        """Unregister a parser class.
        
        Args:
            parser_class: Parser class to unregister
            
        Returns:
            True if parser was unregistered, False if not found
        """
        try:
            cls._parsers.remove(parser_class)
            return True
        except ValueError:
            return False
    
    @classmethod
    def detect_bank_type(cls, pdf_path: str, password: Optional[str] = None) -> Optional[str]:
        """Detect bank type without creating a full parser.
        
        Args:
            pdf_path: Path to the PDF file
            password: Optional password for encrypted PDFs
            
        Returns:
            Bank name if detected, None otherwise
        """
        try:
            parser = cls.create_parser(pdf_path, password)
            return parser.bank_name
        except UnsupportedBankError:
            return None