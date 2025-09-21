# Design Patterns Documentation

This document explains the key design patterns used in the Bank Statement Processor and provides guidance for extending the system.

## Architecture Overview

The Bank Statement Processor uses several design patterns to ensure maintainability, extensibility, and separation of concerns:

- **Factory Pattern**: For creating appropriate parsers
- **Strategy Pattern**: For bank-specific parsing logic
- **Template Method**: For standardized processing workflows
- **Command Pattern**: For CLI operations
- **Builder Pattern**: For constructing transaction objects

## 1. Factory Pattern Implementation

### Purpose
The Factory pattern centralizes parser creation logic and automatically selects the appropriate parser based on PDF content analysis.

### Location
- `src/parsers/parser_factory.py`

### Key Components

```python
class ParserFactory:
    """Factory for creating bank statement parsers."""
    
    # Registry of available parsers
    _parsers: List[Type[BaseParser]] = [
        UnionBankParser,
        SBIParser,
    ]
    
    @classmethod
    def create_parser(cls, pdf_path: str, password: Optional[str] = None) -> BaseParser:
        """Create appropriate parser based on PDF content analysis."""
```

### How It Works

1. **Content Analysis**: Factory analyzes PDF content using pattern matching
2. **Parser Ranking**: Parsers are ranked by confidence scores
3. **Sequential Testing**: Each parser's `detect_bank()` method is tested
4. **Error Handling**: Comprehensive error reporting with helpful messages

### Benefits

- **Automatic Detection**: No manual bank selection required
- **Extensible**: Easy to add new parsers
- **Robust Error Handling**: Clear error messages for unsupported banks
- **Performance**: Smart ranking reduces unnecessary parser attempts

## 2. Strategy Pattern for Parsers

### Purpose
Each bank has unique statement formats requiring different parsing strategies while maintaining a consistent interface.

### Location
- `src/parsers/base_parser.py` (Interface)
- `src/parsers/union_bank_parser.py` (Concrete Strategy)
- `src/parsers/sbi_parser.py` (Concrete Strategy)

### Key Components

```python
class BaseParser(ABC):
    """Abstract base class defining the parser interface."""
    
    @abstractmethod
    def detect_bank(self) -> bool:
        """Strategy for bank detection."""
        
    @abstractmethod
    def extract_transactions(self) -> List[Dict[str, Any]]:
        """Strategy for transaction extraction."""
```

### Implementation Pattern

Each concrete parser implements:

1. **Bank Detection**: Unique patterns for identifying the bank
2. **Data Extraction**: Bank-specific logic for finding transaction data
3. **Data Normalization**: Converting to standardized format

### Benefits

- **Separation of Concerns**: Each parser handles one bank
- **Maintainability**: Changes to one bank don't affect others
- **Testability**: Each strategy can be tested independently

## 3. Template Method Pattern

### Purpose
Standardizes the processing workflow while allowing customization at specific steps.

### Location
- `src/parsers/base_parser.py`

### Implementation

```python
def process_statement(self) -> List[Transaction]:
    """Template method defining the processing workflow."""
    # 1. Validate PDF
    self._validate_pdf()
    
    # 2. Extract raw data (customizable)
    raw_data = self.extract_transactions()
    
    # 3. Normalize data (customizable)
    normalized_data = self._normalize_transactions(raw_data)
    
    # 4. Validate transactions
    validated_data = self._validate_transactions(normalized_data)
    
    return validated_data
```

### Benefits

- **Consistent Workflow**: Same processing steps for all banks
- **Flexibility**: Subclasses can override specific steps
- **Code Reuse**: Common functionality is shared

## 4. Command Pattern for CLI

### Purpose
Encapsulates CLI operations as objects, enabling features like undo, logging, and batch processing.

### Location
- `src/main.py`

### Implementation

```python
@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.pass_context
def cli(ctx, debug):
    """Bank Statement Processor CLI."""
    
@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', required=True, type=click.Path())
def process(pdf_path, output):
    """Process a single PDF statement."""
```

### Benefits

- **Modularity**: Each command is self-contained
- **Extensibility**: Easy to add new commands
- **Consistency**: Uniform interface for all operations

## 5. Builder Pattern for Transactions

### Purpose
Constructs complex transaction objects step-by-step with validation at each stage.

### Location
- `src/models/transaction.py`

### Implementation

```python
class TransactionBuilder:
    """Builder for constructing validated transaction objects."""
    
    def set_date(self, date_str: str) -> 'TransactionBuilder':
        """Set and validate transaction date."""
        
    def set_amount(self, amount: float, transaction_type: str) -> 'TransactionBuilder':
        """Set and validate transaction amount."""
        
    def build(self) -> Transaction:
        """Build final transaction object with validation."""
```

## Adding a New Bank: Step-by-Step Guide

### Step 1: Create Parser Class

```python
# src/parsers/new_bank_parser.py
from .base_parser import BaseParser

class NewBankParser(BaseParser):
    """Parser for New Bank statements."""
    
    bank_name = "New Bank"
    
    def detect_bank(self) -> bool:
        # Implement bank detection logic
        pass
        
    def extract_transactions(self) -> List[Dict[str, Any]]:
        # Implement transaction extraction
        pass
```

### Step 2: Add Detection Patterns

```python
# In src/parsers/parser_factory.py
_bank_patterns = {
    # ... existing patterns ...
    'New Bank': [
        r'(?i)new\s+bank',
        r'(?i)newbank',
        r'(?i)NB\s+statement'
    ]
}
```

### Step 3: Register Parser

```python
# In src/parsers/parser_factory.py
_parsers: List[Type[BaseParser]] = [
    UnionBankParser,
    SBIParser,
    NewBankParser,  # Add new parser
]
```

### Step 4: Implement Detection Logic

```python
def detect_bank(self) -> bool:
    """Detect if this PDF is from New Bank."""
    try:
        with pdfplumber.open(self.pdf_path) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            
            # Look for specific indicators
            indicators = [
                'NEW BANK' in first_page_text.upper(),
                'ACCOUNT STATEMENT' in first_page_text.upper(),
                # Add more specific checks
            ]
            
            return any(indicators)
            
    except Exception as e:
        logger.debug(f"Detection failed: {e}")
        return False
```

### Step 5: Implement Transaction Extraction

```python
def extract_transactions(self) -> List[Dict[str, Any]]:
    """Extract transactions from New Bank PDF."""
    transactions = []
    
    try:
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                # Extract tables or text patterns
                tables = page.extract_tables()
                
                for table in tables:
                    for row in table[1:]:  # Skip header
                        if self._is_transaction_row(row):
                            transaction = self._parse_transaction_row(row)
                            transactions.append(transaction)
                            
        return transactions
        
    except Exception as e:
        raise StatementLayoutError(
            pdf_path=self.pdf_path,
            missing_elements=['transaction_table'],
            bank_name=self.bank_name
        ) from e
```

### Step 6: Add Tests

```python
# tests/test_new_bank_parser.py
import pytest
from src.parsers.new_bank_parser import NewBankParser

class TestNewBankParser:
    def test_bank_detection(self, new_bank_sample_pdf):
        parser = NewBankParser(new_bank_sample_pdf)
        assert parser.detect_bank() == True
        
    def test_transaction_extraction(self, new_bank_sample_pdf):
        parser = NewBankParser(new_bank_sample_pdf)
        transactions = parser.extract_transactions()
        assert len(transactions) > 0
```

### Step 7: Update Documentation

Update this file and any relevant README sections to document the new bank support.

## Error Handling Patterns

### Hierarchical Exception Structure

```
BankStatementProcessorError (Base)
├── UnsupportedBankError
├── PasswordProtectedPDFError
├── StatementLayoutError
├── InvalidTransactionError
├── PDFProcessingError
└── ExportError
```

### Error Context Pattern

Each exception includes:
- **Descriptive Message**: Clear explanation of what went wrong
- **Context Details**: Relevant information for debugging
- **Help Message**: User-friendly guidance for resolution

### Example Usage

```python
try:
    parser = ParserFactory.create_parser(pdf_path)
    transactions = parser.extract_transactions()
except UnsupportedBankError as e:
    print(e.help_message)
    # Show supported banks and suggestions
except PasswordProtectedPDFError as e:
    password = input("Enter PDF password: ")
    # Retry with password
```

## Testing Patterns

### Fixture-Based Testing

```python
@pytest.fixture
def sample_pdf():
    return Path("tests/fixtures/union_bank_sample.pdf")

@pytest.fixture
def expected_transactions():
    return [
        {
            'date': '2025-07-01',
            'description': 'UPI Transfer',
            'amount': 100.0,
            # ... more fields
        }
    ]
```

### Parametrized Testing

```python
@pytest.mark.parametrize("bank_name,parser_class", [
    ("Union Bank of India", UnionBankParser),
    ("State Bank of India", SBIParser),
])
def test_parser_creation(bank_name, parser_class):
    # Test parser creation for different banks
```

## Performance Patterns

### Lazy Loading

Parsers are created only when needed, and PDF content is cached during analysis.

### Content Analysis Optimization

```python
# Analyze only first few pages for bank detection
pages_to_check = min(3, len(pdf.pages))

# Cache analysis results
analysis_results = {
    'page_count': len(pdf.pages),
    'bank_confidence': {},
    'content_sample': sample_text[:500]  # Limited sample
}
```

### Memory Management

```python
# Use context managers for PDF files
with pdfplumber.open(pdf_path) as pdf:
    # Process content
    pass
# PDF automatically closed, memory freed
```

## Security Patterns

### Sensitive Data Handling

```python
# Mask account numbers in logs
safe_data = {}
for key, value in transaction_data.items():
    if key not in ['account_number', 'reference']:
        safe_data[key] = value
```

### Password Security

```python
# Don't log passwords
logger.debug(f"Opening PDF with {'password' if password else 'no password'}")
```

## Extension Points

### Custom Extractors

```python
class CustomUPIExtractor(UPIExtractor):
    """Custom UPI reference extractor for specific bank formats."""
    
    def extract_upi_reference(self, description: str) -> Optional[str]:
        # Custom extraction logic
        pass
```

### Custom Validators

```python
class CustomTransactionValidator(TransactionValidator):
    """Custom validation rules for specific requirements."""
    
    def validate_amount_range(self, amount: float) -> bool:
        # Custom validation logic
        pass
```

This architecture ensures the system remains maintainable, testable, and extensible as new banks and features are added.