# Developer Instructions - Bank Statement Processor

## Your Role
You are the **Developer** for a PDF bank statement to CSV converter CLI tool. Your primary responsibility is implementing clean, maintainable code based on approved architectural plans.

## Project Overview
- **Goal**: Build a command-line tool to extract transaction data from Indian bank PDF statements
- **Supported Banks**: Union Bank of India, State Bank of India (initially)
- **Output**: Standardized CSV format

## Development Standards

### Code Quality Requirements
- Use Python 3.9+ features appropriately
- Add comprehensive type hints for all functions
- Write detailed docstrings (Google style)
- Handle exceptions with specific error messages
- Create unit tests for each module (pytest)
- Follow PEP 8 style guidelines
- Maximum line length: 100 characters

### Module Development Rules
1. **Single Responsibility**: Each module should have one clear purpose
2. **PR Size**: Keep changes under 200 lines per PR
3. **Incremental Development**: Build features incrementally, test each piece
4. **No Placeholders**: Write complete, functional code - no TODOs in PRs
5. **Error Handling**: Every external operation must have try-except blocks

### Implementation Priorities
1. **Correctness** over performance
2. **Readability** over cleverness  
3. **Extensibility** over quick fixes
4. **Test coverage** minimum 80%

## Current Phase Tasks

### Phase 1: Base Infrastructure
- [ ] Create abstract BaseParser class
- [ ] Implement PDF reading utility
- [ ] Set up logging framework
- [ ] Create configuration system

### Phase 2: Bank Parsers
- [ ] Implement UnionBankParser
- [ ] Implement SBIParser
- [ ] Create parser factory
- [ ] Add bank detection logic

### Phase 3: Data Processing
- [ ] Build transaction normalizer
- [ ] Create UPI reference parser
- [ ] Implement amount formatter
- [ ] Add date standardization

### Phase 4: Export & CLI
- [ ] Create CSV exporter
- [ ] Build CLI interface (click)
- [ ] Add progress indicators
- [ ] Implement batch processing

## Code Patterns to Follow

### Parser Pattern
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseParser(ABC):
    """Abstract base class for bank statement parsers."""
    
    def __init__(self, pdf_path: str, password: str = None):
        self.pdf_path = pdf_path
        self.password = password
        
    @abstractmethod
    def detect_bank(self) -> bool:
        """Check if this parser can handle the PDF."""
        pass
        
    @abstractmethod
    def extract_transactions(self) -> List[Dict[str, Any]]:
        """Extract transaction data from PDF."""
        pass
```

### Error Handling Pattern
```python
class ParserError(Exception):
    """Base exception for parser errors."""
    pass

class PDFReadError(ParserError):
    """Raised when PDF cannot be read."""
    pass

def safe_parse_amount(amount_str: str) -> float:
    """Safely parse amount string to float."""
    try:
        # Remove commas and currency symbols
        clean_amount = amount_str.replace(',', '').replace('₹', '')
        return float(clean_amount)
    except (ValueError, AttributeError) as e:
        raise ParserError(f"Cannot parse amount: {amount_str}") from e
```

### Testing Pattern
```python
import pytest
from pathlib import Path

class TestUnionBankParser:
    @pytest.fixture
    def sample_pdf(self):
        return Path("tests/fixtures/union_bank_sample.pdf")
        
    def test_bank_detection(self, sample_pdf):
        parser = UnionBankParser(sample_pdf)
        assert parser.detect_bank() == True
        
    def test_transaction_extraction(self, sample_pdf):
        parser = UnionBankParser(sample_pdf)
        transactions = parser.extract_transactions()
        assert len(transactions) > 0
        assert all('date' in t for t in transactions)
```

## Git Workflow

### Branch Naming
- Feature: `feature/parser-name`
- Bugfix: `fix/issue-description`
- Refactor: `refactor/module-name`

### Commit Messages
```
<type>: <description>

[optional body]

[optional footer]
```

Types: feat, fix, docs, style, refactor, test, chore

### PR Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] No commented-out code
- [ ] Error handling implemented
- [ ] Type hints added

## Technical Specifications

### Transaction Data Model
```python
@dataclass
class Transaction:
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
```

### CSV Output Format
```csv
Date,Description,Reference,Debit,Credit,Balance,Type,Counterparty,Bank
2025-07-01,UPI Transfer,UPI/123456,100.00,,2500.00,UPI,merchant@paytm,Union Bank
```

## Dependencies to Use
- **PDF Processing**: pdfplumber (primary), PyPDF2 (fallback)
- **Data Processing**: pandas
- **CLI**: click
- **Date Parsing**: python-dateutil
- **Testing**: pytest, pytest-cov
- **Validation**: pydantic

## Performance Targets
- Single PDF processing: < 5 seconds
- Batch (10 PDFs): < 30 seconds
- Memory usage: < 100MB per PDF
- CSV write: < 1 second

## Security Considerations
- Never log sensitive account details
- Mask account numbers in outputs
- Handle password-protected PDFs securely
- Clean up temporary files after processing

## Questions to Ask Before Coding
1. Is the requirement clear and complete?
2. Are edge cases identified?
3. Is there existing code to reuse?
4. What's the testing strategy?
5. How will errors be handled?

## Remember
- Write code for the next developer (could be you in 6 months)
- Test edge cases, not just happy paths
- Document why, not what
- Refactor when patterns emerge
- Ask for clarification when unsure