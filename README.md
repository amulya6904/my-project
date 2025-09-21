# Bank Statement Processor

A powerful command-line tool for extracting transaction data from Indian bank PDF statements and converting them to standardized CSV format.

## ✨ Features

- **Multi-Bank Support**: Union Bank of India and State Bank of India
- **Intelligent Parsing**: Automatically detects bank type and extracts transactions
- **Transaction Classification**: Identifies UPI, NEFT, ATM, cheques, and other transaction types
- **Counterparty Detection**: Extracts merchant/payee information from descriptions
- **CSV Export**: Clean, standardized CSV output for analysis
- **Batch Processing**: Process multiple statements at once
- **Error Handling**: Robust handling of malformed PDFs and edge cases

## 📋 Requirements

- Python 3.9 or higher
- pip package manager

## 🚀 Installation

### From Source (Development)

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd bank-statement-processor
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install in development mode:**
   ```bash
   pip install -e .
   ```

### Using pip (Once Published)

```bash
pip install bank-statement-processor
```

## 🚀 Quick Start

### Process a Single Statement

```bash
bank-processor process statement.pdf --output transactions.csv
```

### Process Password-Protected PDF

```bash
bank-processor process statement.pdf --password mypassword --output transactions.csv
```

### Batch Process Multiple Files

```bash
bank-processor batch statements/ --output-dir csv_files/
```

### Detect Bank Type

```bash
bank-processor detect statement.pdf
```

## 📊 Detailed Usage

### Command Line Interface

The tool provides several commands for different use cases:

#### `process` - Process Single Statement

Extract transactions from a single PDF statement:

```bash
bank-processor process [PDF_FILE] [OPTIONS]
```

**Options:**
- `--output, -o`: Output CSV file path (default: `transactions.csv`)
- `--password, -p`: PDF password if encrypted
- `--verbose, -v`: Enable verbose output
- `--format`: Output format (csv, json) - default: csv

**Examples:**

```bash
# Basic usage
bank-processor process union_bank_jul2023.pdf

# Specify output file
bank-processor process statement.pdf -o july_transactions.csv

# Password-protected PDF
bank-processor process statement.pdf -p mypassword

# Verbose output
bank-processor process statement.pdf -v
```

#### `batch` - Process Multiple Statements

Process all PDF files in a directory:

```bash
bank-processor batch [DIRECTORY] [OPTIONS]
```

**Options:**
- `--output-dir, -o`: Output directory for CSV files
- `--password, -p`: Common password for all PDFs
- `--pattern`: File pattern to match (default: `*.pdf`)
- `--verbose, -v`: Enable verbose output

**Examples:**

```bash
# Process all PDFs in statements folder
bank-processor batch statements/ -o output/

# Process with common password
bank-processor batch statements/ -p password123

# Process only specific pattern
bank-processor batch statements/ --pattern "union_bank_*.pdf"
```

#### `detect` - Detect Bank Type

Identify which bank a PDF statement belongs to:

```bash
bank-processor detect [PDF_FILE] [OPTIONS]
```

**Options:**
- `--password, -p`: PDF password if encrypted

**Examples:**

```bash
# Detect bank type
bank-processor detect statement.pdf
# Output: Union Bank of India

# Detect with password
bank-processor detect statement.pdf -p mypassword
```

### Output Format

The CSV output contains standardized columns:

| Column | Description | Example |
|--------|-------------|---------|
| Date | Transaction date | 2023-07-15 |
| Description | Transaction description | UPI/PAYTM-merchant@paytm |
| Reference | Reference number | UPI/123456789 |
| Debit | Debit amount (if applicable) | 100.00 |
| Credit | Credit amount (if applicable) | 500.00 |
| Balance | Account balance after transaction | 2500.00 |
| Type | Transaction type | UPI, NEFT, ATM, CHEQUE, etc. |
| Counterparty | Extracted payee/merchant name | merchant@paytm |
| Bank | Bank name | Union Bank of India |

### Sample Output

```csv
Date,Description,Reference,Debit,Credit,Balance,Type,Counterparty,Bank
2023-07-01,UPI/PAYTM-merchant@paytm,UPI/123456789,100.00,,2400.00,UPI,merchant@paytm,Union Bank of India
2023-07-02,NEFT-Salary Credit,NEFT567890,,50000.00,52400.00,NEFT,Company Ltd,Union Bank of India
2023-07-03,ATM WDL-SBI ATM,ATM/789012,2000.00,,50400.00,ATM,SBI ATM,Union Bank of India
```

## 🏦 Supported Banks

### Currently Supported

- **Union Bank of India** - Statement formats from 2020 onwards
- **State Bank of India** - Standard PDF statements

### Bank-Specific Features

#### Union Bank of India
- Detects UPI transactions with merchant information
- Extracts NEFT/RTGS reference numbers
- Handles both savings and current account formats

#### State Bank of India
- Processes standard SBI statement layouts
- Extracts transaction codes and references
- Handles various date formats used by SBI

## 🔧 Troubleshooting

### Common Issues

#### 1. "Failed to read PDF" Error

**Problem**: PDF file is corrupted, password-protected, or not a valid bank statement.

**Solutions:**
- Verify the PDF can be opened manually
- Check if PDF is password-protected and provide password
- Ensure PDF is a bank statement (not scan/image)

```bash
# Try with password
bank-processor process statement.pdf -p yourpassword

# Check if file is valid
bank-processor detect statement.pdf
```

#### 2. "No transactions found" Warning

**Problem**: PDF doesn't contain recognizable transaction tables.

**Solutions:**
- Ensure PDF is a transaction statement (not just account summary)
- Check if the statement period contains transactions
- Verify bank is supported

```bash
# Run with verbose output to see what's detected
bank-processor process statement.pdf -v
```

#### 3. "Bank not detected" Error

**Problem**: PDF format not recognized or unsupported bank.

**Solutions:**
- Check supported banks list
- Ensure PDF is a standard bank statement format
- File an issue for new bank support

#### 4. Incorrect Transaction Parsing

**Problem**: Some transactions are parsed incorrectly or missing.

**Solutions:**
- Check if statement format is standard
- Report specific cases for improvement
- Use verbose mode to see parsing details

### Performance Issues

#### Large PDF Files

For statements with many pages or transactions:

```bash
# Use verbose mode to monitor progress
bank-processor process large_statement.pdf -v

# Process in smaller batches if needed
bank-processor batch monthly_statements/ -v
```

#### Memory Usage

If processing very large files:
- Ensure sufficient RAM (recommend 4GB+ available)
- Process files individually rather than in large batches
- Close other applications to free memory

### Getting Help

1. **Check verbose output**: Use `-v` flag to see detailed processing information
2. **Validate input**: Ensure PDF is a valid bank statement
3. **Check logs**: Look for error messages in the output
4. **Report issues**: Create GitHub issues with sample data (anonymized)

#### Example Debug Session

```bash
# Step 1: Detect bank
bank-processor detect problem_statement.pdf -v

# Step 2: Try processing with verbose output
bank-processor process problem_statement.pdf -v

# Step 3: Check if password needed
bank-processor process problem_statement.pdf -p password -v
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bank_statement_processor

# Run specific test files
pytest tests/unit/test_union_bank.py
pytest tests/integration/test_end_to_end.py

# Run with verbose output
pytest -v
```

## 🛠️ Development

### Setting Up Development Environment

1. Clone and install as described in installation
2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Run pre-commit hooks:
   ```bash
   pre-commit install
   ```

### Running Tests

```bash
# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# All tests with coverage
pytest --cov=bank_statement_processor --cov-report=html
```

### Code Quality

```bash
# Lint code
flake8 bank_statement_processor/

# Format code
black bank_statement_processor/

# Type checking
mypy bank_statement_processor/
```

## > Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Adding New Banks

1. Create parser class inheriting from `BaseParser`
2. Implement `detect_bank()` and `extract_transactions()` methods
3. Add comprehensive tests
4. Update documentation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

## 📅 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

---

**Made with d for the Indian banking community**