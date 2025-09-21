# Contributing to Bank Statement Processor

Thank you for your interest in contributing to the Bank Statement Processor! This document provides comprehensive guidelines for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Code Style and Standards](#code-style-and-standards)
- [Adding New Bank Parsers](#adding-new-bank-parsers)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Documentation](#documentation)

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Virtual environment tool (venv, conda, or virtualenv)
- Basic understanding of PDF processing concepts

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/bank-statement-processor.git
   cd bank-statement-processor
   ```

## Development Environment Setup

### 1. Create Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Using conda
conda create -n bank-processor python=3.9
conda activate bank-processor
```

### 2. Install Dependencies

```bash
# Install package in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

### 3. Install Pre-commit Hooks

```bash
pre-commit install
```

### 4. Verify Setup

```bash
# Run tests
pytest

# Check code style
flake8 bank_statement_processor/

# Run type checking
mypy bank_statement_processor/
```

### Development Dependencies

The `requirements-dev.txt` includes:

- **Testing**: pytest, pytest-cov, pytest-mock
- **Code Quality**: flake8, black, isort, mypy
- **Pre-commit**: pre-commit hooks for automated checks
- **Documentation**: sphinx (if needed)

## Code Style and Standards

### Python Code Style

We follow PEP 8 with these specific guidelines:

#### Line Length
- Maximum 100 characters per line
- Use implicit line continuation for long expressions
- Break long function calls across multiple lines

```python
# Good
result = some_very_long_function_name(
    parameter_one="value_one",
    parameter_two="value_two",
    parameter_three="value_three"
)

# Bad - line too long
result = some_very_long_function_name(parameter_one="value_one", parameter_two="value_two", parameter_three="value_three")
```

#### Imports
- Use absolute imports
- Group imports: standard library, third-party, local
- Sort imports alphabetically within groups

```python
# Standard library
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Third-party
import pandas as pd
import pdfplumber

# Local
from bank_statement_processor.exceptions import ParserError
from bank_statement_processor.models.transaction import Transaction
```

#### Type Hints
- Add type hints to all function signatures
- Use `Optional[Type]` for optional parameters
- Use `List[Type]` instead of `list[Type]` for Python 3.9 compatibility

```python
from typing import List, Optional, Dict, Any

def parse_amount(amount_str: Optional[str]) -> Optional[float]:
    """Parse amount string to float value."""
    if amount_str is None:
        return None
    # Implementation here

def extract_transactions(self) -> List[Dict[str, Any]]:
    """Extract transactions from PDF."""
    # Implementation here
```

#### Docstrings
Use Google-style docstrings:

```python
def safe_parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string using multiple format attempts.
    
    Args:
        date_str: Date string in various possible formats.
        
    Returns:
        Parsed datetime object or None if parsing fails.
        
    Raises:
        ParserError: If date string is completely invalid.
        
    Examples:
        >>> safe_parse_date("15/07/2023")
        datetime.datetime(2023, 7, 15, 0, 0)
        >>> safe_parse_date("invalid")
        None
    """
    # Implementation here
```

### Error Handling

#### Exception Hierarchy
```python
class ParserError(Exception):
    """Base exception for all parser errors."""
    pass

class PDFReadError(ParserError):
    """Raised when PDF cannot be read or parsed."""
    pass

class ValidationError(ParserError):
    """Raised when transaction data validation fails."""
    pass
```

#### Error Handling Pattern
```python
def parse_transaction_row(self, row: List[str]) -> Optional[Transaction]:
    """Parse a single transaction row."""
    try:
        # Main parsing logic
        date = self._parse_date(row[0])
        amount = self._parse_amount(row[3])
        return Transaction(date=date, amount=amount, ...)
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse row {row}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing row {row}: {e}")
        raise ParserError(f"Failed to parse transaction row") from e
```

### Naming Conventions

- **Classes**: PascalCase (`UnionBankParser`)
- **Functions/Methods**: snake_case (`extract_transactions`)
- **Variables**: snake_case (`transaction_data`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_DATE_FORMAT`)
- **Private methods**: Leading underscore (`_parse_amount`)

## Adding New Bank Parsers

### Step 1: Analyze Bank Statement Format

Before coding, analyze the bank's PDF format:

1. **Download sample statements** (anonymize sensitive data)
2. **Identify unique identifiers** for bank detection
3. **Map table structures** and transaction patterns
4. **Note date/amount formats** used by the bank
5. **Identify transaction type patterns**

### Step 2: Create Parser Class

Create a new file in `bank_statement_processor/parsers/`:

```python
# bank_statement_processor/parsers/new_bank.py

from typing import List, Dict, Any, Optional
from datetime import datetime
import re

from .base import BaseParser
from ..models.transaction import Transaction, TransactionType
from ..exceptions import ParserError, PDFReadError


class NewBankParser(BaseParser):
    """Parser for New Bank PDF statements."""
    
    # Bank identification patterns
    BANK_IDENTIFIERS = [
        "NEW BANK LIMITED",
        "NEW BANK ACCOUNT STATEMENT",
        "www.newbank.com"
    ]
    
    # Date format patterns specific to this bank
    DATE_FORMATS = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %b %Y"
    ]
    
    def detect_bank(self) -> bool:
        """Check if this parser can handle the PDF.
        
        Returns:
            True if PDF appears to be from New Bank.
        """
        try:
            text_content = self._extract_full_text()
            return any(
                identifier in text_content.upper()
                for identifier in self.BANK_IDENTIFIERS
            )
        except Exception as e:
            logger.warning(f"Error detecting bank: {e}")
            return False
    
    def extract_transactions(self) -> List[Dict[str, Any]]:
        """Extract transaction data from New Bank PDF.
        
        Returns:
            List of transaction dictionaries.
            
        Raises:
            PDFReadError: If PDF cannot be processed.
            ParserError: If transaction parsing fails.
        """
        transactions = []
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    logger.info(f"Processing page {page_num}/{len(pdf.pages)}")
                    
                    # Extract tables from current page
                    tables = page.extract_tables()
                    
                    for table in tables:
                        if self._is_transaction_table(table):
                            page_transactions = self._parse_transaction_table(table)
                            transactions.extend(page_transactions)
                            
        except Exception as e:
            raise PDFReadError(f"Failed to read PDF: {str(e)}") from e
        
        logger.info(f"Extracted {len(transactions)} transactions")
        return transactions
    
    def _is_transaction_table(self, table: List[List[str]]) -> bool:
        """Check if table contains transaction data."""
        if not table or len(table) < 2:
            return False
            
        # Check for expected headers
        header_row = [cell.upper() if cell else '' for cell in table[0]]
        required_headers = ['DATE', 'DESCRIPTION', 'AMOUNT', 'BALANCE']
        
        return all(
            any(header in cell for cell in header_row)
            for header in required_headers
        )
    
    def _parse_transaction_table(self, table: List[List[str]]) -> List[Dict[str, Any]]:
        """Parse individual transaction table."""
        transactions = []
        header_row = table[0]
        
        # Map column indices
        col_mapping = self._map_columns(header_row)
        
        for row in table[1:]:
            if self._is_valid_transaction_row(row):
                transaction = self._parse_transaction_row(row, col_mapping)
                if transaction:
                    transactions.append(transaction)
        
        return transactions
    
    def _map_columns(self, header_row: List[str]) -> Dict[str, int]:
        """Map column names to indices."""
        mapping = {}
        
        for i, header in enumerate(header_row):
            if not header:
                continue
                
            header_upper = header.upper()
            if 'DATE' in header_upper:
                mapping['date'] = i
            elif 'DESCRIPTION' in header_upper or 'PARTICULARS' in header_upper:
                mapping['description'] = i
            elif 'REFERENCE' in header_upper or 'REF' in header_upper:
                mapping['reference'] = i
            elif 'DEBIT' in header_upper or 'WITHDRAWAL' in header_upper:
                mapping['debit'] = i
            elif 'CREDIT' in header_upper or 'DEPOSIT' in header_upper:
                mapping['credit'] = i
            elif 'BALANCE' in header_upper:
                mapping['balance'] = i
        
        return mapping
    
    def _parse_transaction_row(self, row: List[str], col_mapping: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Parse individual transaction row."""
        try:
            # Extract basic fields
            date_str = row[col_mapping.get('date', 0)] or ''
            description = row[col_mapping.get('description', 1)] or ''
            
            # Parse date
            transaction_date = self._parse_date(date_str)
            if not transaction_date:
                return None
            
            # Parse amounts
            debit_str = row[col_mapping.get('debit', 2)] if 'debit' in col_mapping else ''
            credit_str = row[col_mapping.get('credit', 3)] if 'credit' in col_mapping else ''
            balance_str = row[col_mapping.get('balance', -1)] or ''
            
            debit_amount = self._parse_amount(debit_str) if debit_str else None
            credit_amount = self._parse_amount(credit_str) if credit_str else None
            balance = self._parse_amount(balance_str) if balance_str else 0.0
            
            # Determine transaction type and counterparty
            transaction_type = self._classify_transaction_type(description)
            counterparty = self._extract_counterparty(description, transaction_type)
            
            return {
                'date': transaction_date,
                'description': description.strip(),
                'reference': row[col_mapping.get('reference')] if 'reference' in col_mapping else None,
                'debit': debit_amount,
                'credit': credit_amount,
                'balance': balance,
                'transaction_type': transaction_type,
                'counterparty': counterparty,
                'bank_name': 'New Bank Limited',
                'account_number': self._extract_account_number()
            }
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse transaction row: {e}")
            return None
    
    def _classify_transaction_type(self, description: str) -> TransactionType:
        """Classify transaction based on description."""
        description_upper = description.upper()
        
        if 'UPI' in description_upper:
            return TransactionType.UPI
        elif any(keyword in description_upper for keyword in ['NEFT', 'RTGS']):
            return TransactionType.NEFT
        elif 'ATM' in description_upper:
            return TransactionType.ATM
        elif any(keyword in description_upper for keyword in ['CHQ', 'CHEQUE']):
            return TransactionType.CHEQUE
        elif any(keyword in description_upper for keyword in ['CARD', 'POS']):
            return TransactionType.CARD
        elif 'INTEREST' in description_upper:
            return TransactionType.INTEREST
        elif any(keyword in description_upper for keyword in ['CHARGE', 'FEE']):
            return TransactionType.CHARGES
        else:
            return TransactionType.OTHER
    
    def _extract_counterparty(self, description: str, transaction_type: TransactionType) -> Optional[str]:
        """Extract counterparty information from description."""
        if transaction_type == TransactionType.UPI:
            # Pattern for UPI: UPI/PAYTM-merchant@paytm
            match = re.search(r'UPI/\w+-([^/\s]+)', description)
            return match.group(1) if match else None
            
        elif transaction_type == TransactionType.NEFT:
            # Pattern for NEFT: NEFT-SALARY FROM COMPANY NAME
            match = re.search(r'NEFT-(?:.*?(?:FROM|TO)\s+)?([A-Z\s]+)', description)
            return match.group(1).strip() if match else None
            
        # Add more patterns as needed
        return None
```

### Step 3: Add to Parser Factory

Update `bank_statement_processor/parsers/factory.py`:

```python
from .new_bank import NewBankParser

class ParserFactory:
    """Factory for creating appropriate bank parsers."""
    
    PARSERS = [
        UnionBankParser,
        SBIParser,
        NewBankParser,  # Add your new parser here
    ]
```

### Step 4: Write Comprehensive Tests

Create `tests/unit/test_new_bank.py`:

```python
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from pathlib import Path

from bank_statement_processor.parsers.new_bank import NewBankParser
from bank_statement_processor.models.transaction import TransactionType
from bank_statement_processor.exceptions import PDFReadError


class TestNewBankParser:
    """Test cases for New Bank parser."""
    
    @pytest.fixture
    def sample_pdf_path(self):
        return "tests/fixtures/new_bank_sample.pdf"
    
    @pytest.fixture
    def parser(self, sample_pdf_path):
        return NewBankParser(sample_pdf_path)
    
    @patch('pdfplumber.open')
    def test_bank_detection_positive(self, mock_pdf_open):
        """Test successful bank detection."""
        mock_page = Mock()
        mock_page.extract_text.return_value = "NEW BANK LIMITED Account Statement"
        mock_pdf = Mock()
        mock_pdf.__enter__.return_value.pages = [mock_page]
        mock_pdf_open.return_value = mock_pdf
        
        parser = NewBankParser("test.pdf")
        assert parser.detect_bank() == True
    
    @patch('pdfplumber.open')
    def test_bank_detection_negative(self, mock_pdf_open):
        """Test bank detection with wrong bank."""
        mock_page = Mock()
        mock_page.extract_text.return_value = "Other Bank Statement"
        mock_pdf = Mock()
        mock_pdf.__enter__.return_value.pages = [mock_page]
        mock_pdf_open.return_value = mock_pdf
        
        parser = NewBankParser("test.pdf")
        assert parser.detect_bank() == False
    
    @patch('pdfplumber.open')
    def test_extract_transactions(self, mock_pdf_open):
        """Test transaction extraction."""
        sample_table = [
            ["Date", "Description", "Debit", "Credit", "Balance"],
            ["15/07/2023", "UPI/PAYTM-merchant@paytm", "100.00", "", "2500.00"],
            ["16/07/2023", "NEFT-Salary Credit", "", "5000.00", "7500.00"]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [sample_table]
        mock_pdf = Mock()
        mock_pdf.__enter__.return_value.pages = [mock_page]
        mock_pdf_open.return_value = mock_pdf
        
        parser = NewBankParser("test.pdf")
        transactions = parser.extract_transactions()
        
        assert len(transactions) == 2
        assert transactions[0]['transaction_type'] == TransactionType.UPI
        assert transactions[1]['transaction_type'] == TransactionType.NEFT
    
    def test_transaction_type_classification(self, parser):
        """Test transaction type classification logic."""
        test_cases = [
            ("UPI/PAYTM-merchant@paytm", TransactionType.UPI),
            ("NEFT-Salary Credit", TransactionType.NEFT),
            ("ATM WDL-MAIN BRANCH", TransactionType.ATM),
            ("CHQ NO 123456", TransactionType.CHEQUE),
            ("INTEREST PAID", TransactionType.INTEREST),
        ]
        
        for description, expected_type in test_cases:
            result = parser._classify_transaction_type(description)
            assert result == expected_type
    
    def test_counterparty_extraction(self, parser):
        """Test counterparty extraction."""
        test_cases = [
            ("UPI/PAYTM-merchant@paytm", TransactionType.UPI, "merchant@paytm"),
            ("NEFT-SALARY FROM COMPANY LTD", TransactionType.NEFT, "COMPANY LTD"),
            ("ATM WDL-BRANCH NAME", TransactionType.ATM, None),
        ]
        
        for description, txn_type, expected in test_cases:
            result = parser._extract_counterparty(description, txn_type)
            assert result == expected
```

## Testing Guidelines

### Test Structure

Organize tests in the following structure:

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_union_bank.py  # Parser-specific tests
│   ├── test_sbi.py
│   ├── test_csv_exporter.py
│   └── test_models.py
├── integration/             # Integration tests
│   ├── test_end_to_end.py  # Full workflow tests
│   └── test_cli.py         # CLI interface tests
├── fixtures/                # Test data
│   ├── union_bank_sample.pdf
│   ├── sbi_sample.pdf
│   └── expected_outputs/
└── conftest.py             # Pytest configuration
```

### Writing Effective Tests

#### Unit Test Best Practices

1. **Test one thing at a time**:
   ```python
   def test_amount_parsing_with_commas(self):
       """Test parsing amounts with comma separators."""
       parser = UnionBankParser("dummy.pdf")
       result = parser._parse_amount("1,23,456.78")
       assert result == 123456.78
   ```

2. **Use descriptive test names**:
   ```python
   # Good
   def test_date_parsing_handles_multiple_formats(self):
   
   # Bad
   def test_date(self):
   ```

3. **Mock external dependencies**:
   ```python
   @patch('pdfplumber.open')
   def test_pdf_reading_error_handling(self, mock_pdf_open):
       mock_pdf_open.side_effect = Exception("File corrupted")
       parser = UnionBankParser("corrupted.pdf")
       with pytest.raises(PDFReadError):
           parser.extract_transactions()
   ```

4. **Test edge cases**:
   ```python
   def test_amount_parsing_edge_cases(self):
       parser = UnionBankParser("dummy.pdf")
       
       # Test cases
       assert parser._parse_amount("") is None
       assert parser._parse_amount("0.00") == 0.0
       assert parser._parse_amount("invalid") is None
       assert parser._parse_amount("-100.00") == -100.0
   ```

#### Integration Test Guidelines

```python
class TestEndToEndProcessing:
    """Test complete processing workflow."""
    
    def test_process_union_bank_statement(self, tmp_path):
        """Test processing a complete Union Bank statement."""
        # Setup
        input_pdf = "tests/fixtures/union_bank_complete.pdf"
        output_csv = tmp_path / "output.csv"
        
        # Execute
        from bank_statement_processor.cli import process_statement
        result = process_statement(input_pdf, str(output_csv))
        
        # Verify
        assert result.success
        assert output_csv.exists()
        
        # Check output content
        import pandas as pd
        df = pd.read_csv(output_csv)
        assert len(df) > 0
        assert all(col in df.columns for col in [
            'Date', 'Description', 'Debit', 'Credit', 'Balance'
        ])
```

### Test Coverage Requirements

- **Minimum 80% overall coverage**
- **90%+ for new parsers**
- **100% for critical functions** (amount parsing, date parsing)

Check coverage:

```bash
pytest --cov=bank_statement_processor --cov-report=html
open htmlcov/index.html  # View detailed coverage report
```

### Test Fixtures

Create anonymized test data:

1. **Sample PDFs**: Remove sensitive information
2. **Expected outputs**: CSV files with expected results
3. **Mock data**: For unit tests

Example fixture setup:

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def fixtures_path():
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def union_bank_sample(fixtures_path):
    return fixtures_path / "union_bank_sample.pdf"

@pytest.fixture
def expected_union_bank_output(fixtures_path):
    return fixtures_path / "expected_outputs" / "union_bank_expected.csv"
```

## Pull Request Process

### Before Submitting

1. **Run all tests**:
   ```bash
   pytest -v
   ```

2. **Check code quality**:
   ```bash
   flake8 bank_statement_processor/
   black bank_statement_processor/
   mypy bank_statement_processor/
   ```

3. **Update documentation** if needed

4. **Add entry to CHANGELOG.md**

### PR Description Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Banks/Features Added
- [ ] New bank parser: [Bank Name]
- [ ] New feature: [Feature Description]
- [ ] Bug fix: [Bug Description]

## Testing
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Test coverage maintained above 80%

## Documentation
- [ ] Code is self-documenting with clear variable names
- [ ] Complex functions have docstrings
- [ ] README updated if needed
- [ ] CHANGELOG.md updated

## Checklist
- [ ] Code follows the project's coding standards
- [ ] Self-review completed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Changes generate no new warnings
```

### Review Process

1. **Automated checks** must pass (CI/CD pipeline)
2. **Code review** by maintainers
3. **Testing** on multiple environments
4. **Documentation review**

## Issue Reporting

### Bug Reports

Use this template for bug reports:

```markdown
**Bug Description**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g. macOS, Windows, Linux]
- Python version: [e.g. 3.9.7]
- Package version: [e.g. 1.2.3]

**Sample Data**
If possible, attach anonymized PDF samples or error logs.

**Additional Context**
Any other context about the problem.
```

### Feature Requests

Template for feature requests:

```markdown
**Feature Description**
A clear description of what you want to happen.

**Use Case**
Describe your use case and why this feature would be valuable.

**Proposed Solution**
Describe the solution you'd like.

**Alternatives Considered**
Describe any alternative solutions or features you've considered.

**Additional Context**
Any other context, mockups, or examples.
```

## Documentation

### Code Documentation

- **Docstrings**: All public methods and classes
- **Type hints**: All function signatures
- **Inline comments**: For complex logic only

### User Documentation

When adding features, update:

- `README.md`: Main documentation
- `docs/USAGE.md`: Detailed usage guide
- `CHANGELOG.md`: Version history

### API Documentation

For significant changes, consider updating:

- Method signatures
- Return value descriptions
- Usage examples
- Error conditions

## Development Workflow

### Recommended Git Workflow

1. **Create feature branch**:
   ```bash
   git checkout -b feature/new-bank-parser
   ```

2. **Make small, focused commits**:
   ```bash
   git add specific_file.py
   git commit -m "feat: add basic NewBank parser structure"
   ```

3. **Keep commits atomic** (one logical change per commit)

4. **Rebase before submitting PR** (if needed):
   ```bash
   git rebase main
   ```

### Commit Message Format

Follow conventional commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(parser): add support for HDFC Bank statements

Add HDFC Bank parser with transaction type classification
and counterparty extraction for UPI and NEFT transactions.

Closes #123
```

## Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community discussion
- **Pull Request Comments**: Code-specific discussions

### Maintainer Response Times

- **Bug reports**: Usually within 48 hours
- **Feature requests**: Usually within 1 week
- **Pull requests**: Usually within 3-5 days

### Development Questions

For development-related questions:

1. Check existing documentation
2. Search closed issues and PRs
3. Create a GitHub Discussion
4. Tag maintainers if urgent

---

Thank you for contributing to Bank Statement Processor! Your contributions help make financial data more accessible to everyone.