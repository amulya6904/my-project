# Usage Guide

This comprehensive guide covers all aspects of using the Bank Statement Processor tool.

## Table of Contents

- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Command Reference](#command-reference)
- [Real-World Examples](#real-world-examples)
- [Output Format](#output-format)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Installation Steps

1. **Install from PyPI** (recommended):
   ```bash
   pip install bank-statement-processor
   ```

2. **Install from source**:
   ```bash
   git clone <repository-url>
   cd bank-statement-processor
   pip install -e .
   ```

3. **Verify installation**:
   ```bash
   bank-processor --help
   ```

## Basic Usage

### Your First Statement Processing

Let's process a Union Bank statement:

```bash
# Download or save your PDF statement as 'statement.pdf'
bank-processor process statement.pdf
```

This creates `transactions.csv` with all extracted transactions.

### Quick Verification

Check what bank the tool detects:

```bash
bank-processor detect statement.pdf
# Output: Union Bank of India
```

## Command Reference

### `bank-processor process`

Extract transactions from a single PDF statement.

**Syntax:**
```bash
bank-processor process <pdf_file> [OPTIONS]
```

**Options:**
- `-o, --output TEXT`: Output CSV file path (default: transactions.csv)
- `-p, --password TEXT`: PDF password for encrypted files
- `-f, --format [csv|json]`: Output format (default: csv)
- `-v, --verbose`: Enable detailed output
- `--help`: Show help message

**Examples:**

```bash
# Basic usage
bank-processor process july2023.pdf

# Custom output file
bank-processor process july2023.pdf -o july_transactions.csv

# Password-protected PDF
bank-processor process encrypted.pdf -p mypassword

# JSON output format
bank-processor process statement.pdf -f json -o transactions.json

# Verbose output (see processing details)
bank-processor process statement.pdf -v
```

### `bank-processor batch`

Process multiple PDF statements in a directory.

**Syntax:**
```bash
bank-processor batch <directory> [OPTIONS]
```

**Options:**
- `-o, --output-dir TEXT`: Output directory for CSV files
- `-p, --password TEXT`: Common password for all PDFs
- `--pattern TEXT`: File pattern to match (default: *.pdf)
- `-v, --verbose`: Enable detailed output
- `--help`: Show help message

**Examples:**

```bash
# Process all PDFs in statements folder
bank-processor batch statements/

# Specify output directory
bank-processor batch statements/ -o csv_output/

# Process with common password
bank-processor batch statements/ -p commonpassword

# Process specific file pattern
bank-processor batch statements/ --pattern "union_*.pdf"

# Verbose batch processing
bank-processor batch statements/ -v
```

### `bank-processor detect`

Identify which bank a PDF statement belongs to.

**Syntax:**
```bash
bank-processor detect <pdf_file> [OPTIONS]
```

**Options:**
- `-p, --password TEXT`: PDF password for encrypted files
- `-v, --verbose`: Show detection details
- `--help`: Show help message

**Examples:**

```bash
# Basic bank detection
bank-processor detect statement.pdf

# With password
bank-processor detect encrypted.pdf -p mypassword

# Verbose detection (show matching patterns)
bank-processor detect statement.pdf -v
```

## Real-World Examples

### Example 1: Monthly Statement Processing

Process your monthly Union Bank statement:

```bash
# Step 1: Verify the bank
bank-processor detect union_bank_july2023.pdf
# Output: Union Bank of India

# Step 2: Process the statement
bank-processor process union_bank_july2023.pdf -o july2023_transactions.csv

# Step 3: Check the output
head july2023_transactions.csv
```

**Sample Output:**
```csv
Date,Description,Reference,Debit,Credit,Balance,Type,Counterparty,Bank
2023-07-01,UPI/GPAY-merchant@paytm,UPI/312345678901,150.00,,4850.00,UPI,merchant@paytm,Union Bank of India
2023-07-02,NEFT-SALARY CREDIT,NEFT202307020001,,25000.00,29850.00,NEFT,COMPANY LIMITED,Union Bank of India
2023-07-03,ATM WDL-UNION BANK ATM,ATM/000123,2000.00,,27850.00,ATM,UNION BANK ATM,Union Bank of India
```

### Example 2: Batch Processing Multiple Months

Process 6 months of statements at once:

```bash
# Directory structure:
# statements/
#   ├── jan2023.pdf
#   ├── feb2023.pdf
#   ├── mar2023.pdf
#   ├── apr2023.pdf
#   ├── may2023.pdf
#   └── jun2023.pdf

# Process all at once
bank-processor batch statements/ -o csv_files/ -v

# Result:
# csv_files/
#   ├── jan2023.csv
#   ├── feb2023.csv
#   ├── mar2023.csv
#   ├── apr2023.csv
#   ├── may2023.csv
#   └── jun2023.csv
```

### Example 3: Password-Protected Business Statements

Process encrypted business account statements:

```bash
# All statements have the same password
bank-processor batch business_statements/ -p "BusinessPass123" -o business_csv/

# Individual file with password
bank-processor process confidential_statement.pdf -p "SecretPass" -o confidential.csv
```

### Example 4: Different Banks Mixed

Process statements from different banks:

```bash
# Check what banks you have
for file in statements/*.pdf; do
    echo "File: $file"
    bank-processor detect "$file"
    echo
done

# Output:
# File: statements/union_july.pdf
# Union Bank of India
#
# File: statements/sbi_july.pdf
# State Bank of India

# Process all together
bank-processor batch statements/ -o mixed_output/
```

## Output Format

### CSV Structure

The tool generates standardized CSV files with the following columns:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| Date | Date (YYYY-MM-DD) | Transaction date | 2023-07-15 |
| Description | Text | Full transaction description | UPI/PAYTM-merchant@paytm |
| Reference | Text | Bank reference number | UPI/312345678901 |
| Debit | Decimal | Debit amount (empty if credit) | 100.00 |
| Credit | Decimal | Credit amount (empty if debit) | 500.00 |
| Balance | Decimal | Account balance after transaction | 2500.00 |
| Type | Text | Transaction type classification | UPI |
| Counterparty | Text | Extracted payee/payer name | merchant@paytm |
| Bank | Text | Bank name | Union Bank of India |

### Transaction Type Classifications

The tool automatically classifies transactions:

- **UPI**: Unified Payments Interface transactions
- **NEFT**: National Electronic Funds Transfer
- **RTGS**: Real Time Gross Settlement
- **ATM**: ATM withdrawals and deposits
- **CHEQUE**: Cheque clearances
- **CARD**: Debit/credit card transactions
- **INTEREST**: Interest credits/debits
- **CHARGES**: Bank charges and fees
- **OTHER**: Unclassified transactions

### Counterparty Extraction

The tool intelligently extracts counterparty information:

```csv
Description,Counterparty
UPI/PAYTM-merchant@paytm,merchant@paytm
NEFT-SALARY FROM ABC COMPANY,ABC COMPANY
ATM WDL-SBI ATM MUMBAI,SBI ATM MUMBAI
CHQ NO 000123 CLEARED,
IMPS-TRANSFER TO JOHN DOE,JOHN DOE
```

## Advanced Features

### Custom Output Formats

#### JSON Output

```bash
bank-processor process statement.pdf -f json -o transactions.json
```

Sample JSON output:
```json
[
  {
    "date": "2023-07-01",
    "description": "UPI/PAYTM-merchant@paytm",
    "reference": "UPI/312345678901",
    "debit": 100.00,
    "credit": null,
    "balance": 2400.00,
    "transaction_type": "UPI",
    "counterparty": "merchant@paytm",
    "bank_name": "Union Bank of India"
  }
]
```

### Verbose Output

Use `-v` flag for detailed processing information:

```bash
bank-processor process statement.pdf -v
```

Sample verbose output:
```
INFO: Processing file: statement.pdf
INFO: Detected bank: Union Bank of India
INFO: Found 3 pages in PDF
INFO: Processing page 1/3
INFO: Found 2 tables on page 1
INFO: Extracted 15 transactions from page 1
INFO: Processing page 2/3
INFO: Found 1 table on page 2
INFO: Extracted 12 transactions from page 2
INFO: Processing page 3/3
INFO: Found 1 table on page 3
INFO: Extracted 8 transactions from page 3
INFO: Total transactions extracted: 35
INFO: Saved to: transactions.csv
SUCCESS: Processing completed successfully
```

### Pattern Matching for Batch Processing

Process only specific file patterns:

```bash
# Only Union Bank statements
bank-processor batch statements/ --pattern "union_*.pdf"

# Only statements from 2023
bank-processor batch statements/ --pattern "*2023*.pdf"

# Only July statements
bank-processor batch statements/ --pattern "*july*.pdf"
```

## Troubleshooting

### Common Error Messages

#### "Failed to read PDF: File is encrypted"

**Problem**: PDF requires a password.

**Solution**:
```bash
bank-processor process statement.pdf -p yourpassword
```

#### "Bank not detected"

**Problem**: PDF format not recognized.

**Solutions**:
1. Check if bank is supported:
   ```bash
   bank-processor detect statement.pdf -v
   ```

2. Ensure PDF is a transaction statement, not summary

3. Try opening PDF manually to verify it's valid

#### "No transactions found"

**Problem**: PDF doesn't contain recognizable transaction tables.

**Solutions**:
1. Use verbose mode to see what's detected:
   ```bash
   bank-processor process statement.pdf -v
   ```

2. Check if statement period has transactions

3. Ensure PDF is complete (not truncated)

#### "Permission denied" when writing output

**Problem**: Cannot write to output location.

**Solutions**:
```bash
# Specify different output location
bank-processor process statement.pdf -o ~/Desktop/transactions.csv

# Check directory permissions
ls -la output_directory/
```

### Performance Issues

#### Large PDF Files

For statements with many pages:

```bash
# Monitor progress with verbose output
bank-processor process large_statement.pdf -v

# Process page by page if needed (contact support for large files)
```

#### Memory Issues

If processing very large files:

1. Close other applications
2. Process files individually instead of batch
3. Use system with more RAM (4GB+ recommended)

### Debug Mode

For developers or advanced troubleshooting:

```bash
# Set debug environment
export BANK_PROCESSOR_DEBUG=1
bank-processor process statement.pdf -v
```

## FAQ

### General Questions

**Q: Which banks are supported?**

A: Currently Union Bank of India and State Bank of India. More banks are added based on user requests.

**Q: Can I process password-protected PDFs?**

A: Yes, use the `-p` flag with the password.

**Q: What file formats are supported?**

A: Only PDF files. The PDF must contain selectable text (not scanned images).

**Q: Is my data secure?**

A: Yes, all processing is done locally. No data is sent to external servers.

### Processing Questions

**Q: Why are some transactions missing?**

A: This can happen if:
- Transaction format is non-standard
- PDF quality is poor
- Statement is incomplete

Use verbose mode (`-v`) to see processing details.

**Q: Can I merge multiple statements?**

A: Yes, process each separately and combine the CSV files:

```bash
# Process individually
bank-processor process jan2023.pdf -o jan.csv
bank-processor process feb2023.pdf -o feb.csv

# Combine (Linux/Mac)
cat jan.csv feb.csv > combined.csv

# Or use batch processing
bank-processor batch statements/ -o csv_files/
```

**Q: How accurate is transaction type detection?**

A: Very accurate for standard transaction patterns. Accuracy depends on:
- Bank's description format
- Transaction type (UPI > NEFT > Others)
- Statement quality

**Q: Can I customize the output format?**

A: Currently supports CSV and JSON. For custom formats, process the CSV/JSON output with other tools.

### Technical Questions

**Q: What Python version is required?**

A: Python 3.9 or higher.

**Q: Can I use this in my own Python scripts?**

A: Yes, import and use the library:

```python
from bank_statement_processor import UnionBankParser

parser = UnionBankParser("statement.pdf")
if parser.detect_bank():
    transactions = parser.extract_transactions()
```

**Q: How can I add support for a new bank?**

A: See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed instructions on adding new bank parsers.

**Q: Is there an API version?**

A: Currently only command-line interface. API version is planned for future releases.

---

For more help, create an issue on GitHub or check the main documentation.