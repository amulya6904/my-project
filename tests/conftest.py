"""Pytest configuration and fixtures for bank statement processor tests."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import io
import pytest

from src.parsers.base_parser import Transaction, TransactionType


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_transactions() -> List[Transaction]:
    """Create sample transaction data for testing."""
    return [
        Transaction(
            date=datetime(2025, 7, 1),
            description="UPI/123456789/merchant@paytm/Online Purchase",
            reference="UPI123456",
            debit=100.50,
            credit=None,
            balance=2400.00,
            transaction_type=TransactionType.UPI,
            counterparty="merchant@paytm",
            bank_name="Union Bank of India",
            account_number="****1234"
        ),
        Transaction(
            date=datetime(2025, 7, 2),
            description="SALARY CREDIT BY EMP123",
            reference="SAL202507",
            debit=None,
            credit=50000.00,
            balance=52400.00,
            transaction_type=TransactionType.DEPOSIT,
            counterparty="EMP123",
            bank_name="Union Bank of India",
            account_number="****1234"
        ),
        Transaction(
            date=datetime(2025, 7, 3),
            description="ATM CASH WITHDRAWAL",
            reference="ATM789123",
            debit=500.00,
            credit=None,
            balance=51900.00,
            transaction_type=TransactionType.ATM,
            counterparty=None,
            bank_name="Union Bank of India",
            account_number="****1234"
        )
    ]


@pytest.fixture
def union_bank_sample_data() -> Dict[str, Any]:
    """Sample data that would be extracted from Union Bank PDF."""
    return {
        'bank_indicators': [
            'Union Bank of India',
            'UBI',
            'Account Statement'
        ],
        'account_info': {
            'account_number': '12345678901234',
            'account_holder': 'JOHN DOE',
            'branch': 'MAIN BRANCH'
        },
        'raw_transactions': [
            ['01/07/2025', 'UPI/123456789/merchant@paytm', '100.50', '', '2400.00'],
            ['02/07/2025', 'SALARY CREDIT BY EMP123', '', '50000.00', '52400.00'],
            ['03/07/2025', 'ATM CASH WITHDRAWAL', '500.00', '', '51900.00']
        ]
    }


@pytest.fixture
def sbi_sample_data() -> Dict[str, Any]:
    """Sample data that would be extracted from SBI PDF."""
    return {
        'bank_indicators': [
            'State Bank of India',
            'SBI',
            'Statement of Account'
        ],
        'account_info': {
            'account_number': '98765432109876',
            'account_holder': 'JANE SMITH',
            'branch': 'CENTRAL BRANCH'
        },
        'raw_transactions': [
            ['01-Jul-25', 'UPI-MERCHANT PAYMENT', '75.25', '', '1924.75'],
            ['02-Jul-25', 'INTEREST CREDIT', '', '25.50', '1950.25'],
            ['03-Jul-25', 'NEFT TRANSFER', '1000.00', '', '950.25']
        ]
    }


@pytest.fixture
def mock_pdf_content_union():
    """Mock PDF content for Union Bank statement."""
    return """
    Union Bank of India
    Account Statement
    
    Account No: ****1234
    Name: JOHN DOE
    Branch: Main Branch
    
    Date        Particulars                         Debit    Credit   Balance
    01/07/2025  UPI/123456789/merchant@paytm       100.50            2400.00
    02/07/2025  SALARY CREDIT BY EMP123                     50000.00 52400.00
    03/07/2025  ATM CASH WITHDRAWAL                500.00            51900.00
    """


@pytest.fixture
def mock_pdf_content_sbi():
    """Mock PDF content for SBI statement."""
    return """
    State Bank of India
    Statement of Account
    
    A/c No: ****9876
    Name: JANE SMITH
    Branch: Central Branch
    
    Date       Particulars              Debit     Credit    Balance
    01-Jul-25  UPI-MERCHANT PAYMENT    75.25               1924.75
    02-Jul-25  INTEREST CREDIT                   25.50     1950.25
    03-Jul-25  NEFT TRANSFER          1000.00             950.25
    """


@pytest.fixture
def mock_pdf_content_unsupported():
    """Mock PDF content for unsupported bank."""
    return """
    Unsupported Bank Ltd
    Account Statement
    
    Account: 123456
    Name: TEST USER
    
    This is not a supported bank format.
    """


@pytest.fixture
def create_mock_pdf(temp_dir):
    """Factory fixture to create mock PDF files with specific content."""
    def _create_pdf(filename: str, content: str, password: bool = False) -> Path:
        """Create a mock PDF file for testing.
        
        Args:
            filename: Name of the PDF file
            content: Text content to include in the mock PDF
            password: Whether the PDF should be password protected
            
        Returns:
            Path to the created mock PDF file
        """
        pdf_path = temp_dir / filename
        
        # Create a simple text file acting as a mock PDF
        with open(pdf_path, 'w', encoding='utf-8') as f:
            if password:
                f.write("ENCRYPTED_PDF_MARKER\n")
            f.write(content)
        
        return pdf_path
    
    return _create_pdf


@pytest.fixture
def sample_csv_data() -> str:
    """Sample CSV data for testing exports."""
    return """Date,Description,Reference,Debit,Credit,Balance,Type,Counterparty,Bank
2025-07-01,UPI/123456789/merchant@paytm,UPI123456,100.50,,2400.00,UPI,merchant@paytm,Union Bank of India
2025-07-02,SALARY CREDIT BY EMP123,SAL202507,,50000.00,52400.00,DEPOSIT,EMP123,Union Bank of India
2025-07-03,ATM CASH WITHDRAWAL,ATM789123,500.00,,51900.00,ATM,,Union Bank of India"""


@pytest.fixture
def mock_parser_factory(monkeypatch):
    """Mock the ParserFactory for testing without actual PDF processing."""
    from src.parsers.parser_factory import ParserFactory
    
    original_analyze = ParserFactory._analyze_pdf_content
    original_create = ParserFactory.create_parser
    
    def mock_analyze(pdf_path: str, password=None):
        # Return mock analysis based on filename
        filename = Path(pdf_path).name.lower()
        
        if 'union' in filename:
            return "Union Bank sample content", {
                'page_count': 2,
                'bank_confidence': {'Union Bank of India': 30, 'State Bank of India': 0},
                'has_tables': True,
                'content_sample': "Union Bank of India Account Statement"
            }
        elif 'sbi' in filename:
            return "SBI sample content", {
                'page_count': 3,
                'bank_confidence': {'Union Bank of India': 0, 'State Bank of India': 25},
                'has_tables': True,
                'content_sample': "State Bank of India Statement"
            }
        else:
            return "Unknown content", {
                'page_count': 1,
                'bank_confidence': {'Union Bank of India': 0, 'State Bank of India': 0},
                'has_tables': False,
                'content_sample': "Unknown bank content"
            }
    
    monkeypatch.setattr(ParserFactory, '_analyze_pdf_content', mock_analyze)
    return ParserFactory


@pytest.fixture
def mock_click_context():
    """Create a mock Click context for CLI testing."""
    import click
    
    ctx = click.Context(click.Command('test'))
    ctx.ensure_object(dict)
    ctx.obj['debug'] = False
    return ctx


@pytest.fixture
def validation_test_data():
    """Test data for validation scenarios."""
    return {
        'valid_transaction': {
            'date': '2025-07-01',
            'description': 'Test transaction',
            'debit': 100.0,
            'credit': None,
            'balance': 900.0,
            'reference': 'TEST123'
        },
        'invalid_transactions': [
            {
                'name': 'missing_date',
                'data': {'description': 'Test', 'balance': 100.0},
                'expected_errors': ['missing date']
            },
            {
                'name': 'missing_description',
                'data': {'date': '2025-07-01', 'balance': 100.0},
                'expected_errors': ['missing description']
            },
            {
                'name': 'missing_balance',
                'data': {'date': '2025-07-01', 'description': 'Test'},
                'expected_errors': ['missing balance']
            },
            {
                'name': 'no_amount',
                'data': {
                    'date': '2025-07-01',
                    'description': 'Test',
                    'balance': 100.0,
                    'debit': None,
                    'credit': None
                },
                'expected_errors': ['missing both debit and credit']
            }
        ]
    }


@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing."""
    return {
        'pdf_not_found': {
            'path': '/nonexistent/file.pdf',
            'error_type': 'PDFProcessingError',
            'message_contains': ['not found', 'nonexistent']
        },
        'invalid_file_type': {
            'path': 'document.txt',
            'error_type': 'PDFReadError',
            'message_contains': ['not a PDF']
        },
        'unsupported_bank': {
            'content': 'Unknown Bank Statement',
            'error_type': 'UnsupportedBankError',
            'message_contains': ['Cannot identify bank']
        },
        'password_protected': {
            'needs_password': True,
            'error_type': 'PasswordProtectedPDFError',
            'message_contains': ['password-protected']
        }
    }


@pytest.fixture
def batch_processing_scenario(temp_dir, create_mock_pdf, mock_pdf_content_union, mock_pdf_content_sbi):
    """Create a batch processing test scenario with multiple PDFs."""
    
    # Create test PDFs
    pdf_files = []
    
    # Valid Union Bank PDF
    union_pdf = create_mock_pdf('union_statement.pdf', mock_pdf_content_union)
    pdf_files.append(union_pdf)
    
    # Valid SBI PDF
    sbi_pdf = create_mock_pdf('sbi_statement.pdf', mock_pdf_content_sbi)
    pdf_files.append(sbi_pdf)
    
    # Password protected PDF
    protected_pdf = create_mock_pdf('protected_statement.pdf', mock_pdf_content_union, password=True)
    pdf_files.append(protected_pdf)
    
    # Invalid PDF (wrong extension)
    invalid_file = temp_dir / 'not_a_pdf.txt'
    invalid_file.write_text('This is not a PDF')
    
    # Create output directory
    output_dir = temp_dir / 'output'
    output_dir.mkdir()
    
    return {
        'input_dir': temp_dir,
        'output_dir': output_dir,
        'pdf_files': pdf_files,
        'expected_success_count': 2,  # Union and SBI
        'expected_failure_count': 1   # Password protected
    }


# Test configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", 
        "unit: marks tests as unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (may use files/network)"
    )
    config.addinivalue_line(
        "markers",
        "cli: marks tests as CLI interface tests"
    )


# Custom assertion helpers
def assert_transaction_equals(actual: Transaction, expected: Dict[str, Any]):
    """Helper to assert transaction fields match expected values."""
    if 'date' in expected:
        expected_date = expected['date']
        if isinstance(expected_date, str):
            expected_date = datetime.strptime(expected_date, '%Y-%m-%d')
        assert actual.date == expected_date
    
    for field in ['description', 'reference', 'debit', 'credit', 'balance', 'counterparty', 'bank_name']:
        if field in expected:
            assert getattr(actual, field) == expected[field]
    
    if 'transaction_type' in expected:
        expected_type = expected['transaction_type']
        if isinstance(expected_type, str):
            expected_type = TransactionType(expected_type)
        assert actual.transaction_type == expected_type


def assert_error_contains(error: Exception, expected_messages: List[str]):
    """Helper to assert error message contains expected text."""
    error_str = str(error).lower()
    for message in expected_messages:
        assert message.lower() in error_str, f"Expected '{message}' in error message: {error_str}"