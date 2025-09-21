"""
Edge case tests for bank statement processor.

Tests malformed PDFs, edge case transactions, and CSV export functionality.
"""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import pandas as pd

from src.parsers.base_parser import BaseParser, Transaction, TransactionType, PDFReadError, ParserError
from src.parsers.union_bank_parser import UnionBankParser
from src.parsers.sbi_parser import SBIParser
from src.exporters.csv_exporter import CSVExporter
from src.core.exceptions import InvalidTransactionError


class TestMalformedPDFScenarios:
    """Test handling of malformed or problematic PDF files."""

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_empty_pdf_handling(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of empty PDF files."""
        mock_pdf_context = Mock()
        mock_pdf_context.pages = []
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("empty.pdf")
        
        with pytest.raises(Exception):  # Could be TransactionExtractionError or PDFReadError
            parser.extract_transactions()

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_pdf_missing_tables(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of PDF pages with no tables."""
        mock_page = Mock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("no_tables.pdf")
        
        from src.parsers.base_parser import TransactionExtractionError
        with pytest.raises(TransactionExtractionError, match="No transactions found in PDF"):
            parser.extract_transactions()

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_corrupted_table_data(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of corrupted table data."""
        corrupted_table = [
            ["SI", "Date", "Particulars", "Chq Num", "Withdrawal", "Deposit", "Balance"],
            [None, "Corrupted entry", "", "", "", ""],  # Invalid - no date
            ["", "", "", "", "", ""],  # Invalid - empty row
            ["1", "15-07-2023", "UPI Transfer", "REF123", "100.00", "", "2400.00 Cr"],  # Valid
            ["2", "16-07-2023", None, "REF124", "", "500.00", "2900.00 Cr"]  # Invalid - no description
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [corrupted_table]
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("corrupted.pdf")
        transactions = parser.extract_transactions()
        
        # Should skip corrupted entries and extract valid ones
        assert len(transactions) == 1
        assert transactions[0].date == datetime(2023, 7, 15)
        assert transactions[0].description == "UPI Transfer"

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_password_protected_pdf_wrong_password(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of password-protected PDF with wrong password."""
        mock_pdf_open.side_effect = Exception("File is encrypted")
        
        parser = UnionBankParser("encrypted.pdf", password="wrong_password")
        
        from src.parsers.base_parser import TransactionExtractionError
        with pytest.raises(TransactionExtractionError, match="Cannot extract transactions: File is encrypted"):
            parser.extract_transactions()

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_empty_statement_month(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of statement with no transactions for a month."""
        empty_table = [
            ["SI", "Date", "Particulars", "Chq Num", "Withdrawal", "Deposit", "Balance"],
            ["", "Opening Balance", "", "", "", "", "5000.00 Cr"],
            ["", "Closing Balance", "", "", "", "", "5000.00 Cr"]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [empty_table]
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("empty_month.pdf")
        
        from src.parsers.base_parser import TransactionExtractionError
        with pytest.raises(TransactionExtractionError, match="No transactions found in PDF"):
            parser.extract_transactions()


class TestEdgeCaseTransactions:
    """Test handling of edge case transaction scenarios."""

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_zero_amount_transactions(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of transactions with zero amounts."""
        table_data = [
            ["SI", "Date", "Particulars", "Chq Num", "Withdrawal", "Deposit", "Balance"],
            ["1", "15-07-2023", "Zero amount transfer", "REF123", "0.00", "", "2500.00 Cr"],
            ["2", "16-07-2023", "Zero credit", "REF124", "", "0.00", "2500.00 Cr"]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [table_data]
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("zero_amounts.pdf")
        transactions = parser.extract_transactions()
        
        assert len(transactions) == 2
        assert transactions[0].debit == 0.0
        assert transactions[1].credit == 0.0

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_special_characters_in_description(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of special characters in transaction descriptions."""
        table_data = [
            ["SI", "Date", "Particulars", "Chq Num", "Withdrawal", "Deposit", "Balance"],
            ["1", "15-07-2023", "UPI/PAYTM-@#$%^&*()", "UPI/123456", "100.00", "", "2400.00 Cr"],
            ["2", "16-07-2023", "NEFT-Special Chars éñüñ", "NEFT789", "", "500.00", "2900.00 Cr"]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [table_data]
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("special_chars.pdf")
        transactions = parser.extract_transactions()
        
        assert len(transactions) == 2
        assert "PAYTM-@#$%^&*()" in transactions[0].description
        assert "éñüñ" in transactions[1].description

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_very_large_amounts(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of very large transaction amounts."""
        table_data = [
            ["SI", "Date", "Particulars", "Chq Num", "Withdrawal", "Deposit", "Balance"],
            ["1", "15-07-2023", "Large transfer", "REF123", "9,99,99,999.99", "", "1000.00 Cr"],
            ["2", "16-07-2023", "Large deposit", "REF124", "", "1,00,00,000.00", "1,01,00,000.00 Cr"]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [table_data]
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("large_amounts.pdf")
        transactions = parser.extract_transactions()
        
        assert len(transactions) == 2
        assert transactions[0].debit == 99999999.99
        assert transactions[1].credit == 10000000.00

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_malformed_date_formats(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test handling of various date formats and malformed dates."""
        table_data = [
            ["SI", "Date", "Particulars", "Chq Num", "Withdrawal", "Deposit", "Balance"],
            ["1", "15-07-2023", "Valid date dash format", "REF123", "100.00", "", "2400.00 Cr"],
            ["2", "16-07-2023", "Another valid date", "REF124", "50.00", "", "2350.00 Cr"],
            ["3", "invalid-date", "Invalid date", "REF125", "25.00", "", "2325.00 Cr"],
            ["4", "32/13/2023", "Impossible date", "REF126", "10.00", "", "2315.00 Cr"]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [table_data]
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("malformed_dates.pdf")
        transactions = parser.extract_transactions()
        
        # Should only extract transactions with valid dates
        assert len(transactions) == 2
        assert transactions[0].date == datetime(2023, 7, 15)
        assert transactions[1].date == datetime(2023, 7, 16)

    @patch('pdfplumber.open')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_file', return_value=True)
    @patch('src.parsers.union_bank_parser.UnionBankParser.get_account_number', return_value='****1234')
    def test_mixed_transaction_types(self, mock_get_account_number, mock_is_file, mock_exists, mock_pdf_open):
        """Test detection of various transaction types in one statement."""
        table_data = [
            ["SI", "Date", "Particulars", "Chq Num", "Withdrawal", "Deposit", "Balance"],
            ["1", "15-07-2023", "UPI/PAYTM-merchant@paytm", "UPI/123456", "100.00", "", "2400.00 Cr"],
            ["2", "16-07-2023", "NEFT-Salary Credit", "NEFT789012", "", "50000.00", "52400.00 Cr"],
            ["3", "17-07-2023", "ATM WDL-SBI ATM", "ATM/345", "2000.00", "", "50400.00 Cr"],
            ["4", "18-07-2023", "Bank Charge Applied", "CHG456", "5000.00", "", "45400.00 Cr"],
            ["5", "19-07-2023", "Interest Paid", "INT789", "", "50.00", "45450.00 Cr"]
        ]
        
        mock_page = Mock()
        mock_page.extract_tables.return_value = [table_data]
        mock_page.extract_text.return_value = "Union Bank of India Statement"
        
        mock_pdf_context = Mock()
        mock_pdf_context.pages = [mock_page]
        
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf_context
        mock_pdf.__exit__.return_value = None
        mock_pdf_open.return_value = mock_pdf
        
        parser = UnionBankParser("mixed_types.pdf")
        transactions = parser.extract_transactions()
        
        assert len(transactions) == 5
        assert transactions[0].transaction_type == TransactionType.UPI
        assert transactions[1].transaction_type == TransactionType.TRANSFER
        assert transactions[2].transaction_type == TransactionType.ATM
        assert transactions[3].transaction_type == TransactionType.CHARGE
        assert transactions[4].transaction_type == TransactionType.DEPOSIT


class TestCSVExporterEdgeCases:
    """Test edge cases for CSV export functionality."""

    def test_export_empty_transaction_list(self):
        """Test exporting an empty list of transactions."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        exporter = CSVExporter(output_path)
        
        try:
            # CSVExporter raises CSVExportError for empty transactions
            with pytest.raises(Exception, match="No transactions to export"):
                exporter.export_transactions([])
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_with_missing_fields(self):
        """Test exporting transactions with missing optional fields."""
        transactions = [
            Transaction(
                date=datetime(2023, 7, 15),
                description="Test transaction",
                reference=None,  # Missing reference
                debit=100.0,
                credit=None,
                balance=2400.0,
                transaction_type=TransactionType.OTHER,
                counterparty=None,  # Missing counterparty
                bank_name="Test Bank",
                account_number="123456789"
            )
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        exporter = CSVExporter(output_path)
        
        try:
            exporter.export_transactions(transactions)
            
            df = pd.read_csv(output_path)
            assert len(df) == 1
            assert pd.isna(df.iloc[0]['Reference'])
            assert pd.isna(df.iloc[0]['Counterparty'])
            assert pd.isna(df.iloc[0]['Credit'])
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_with_special_characters(self):
        """Test exporting transactions with special characters in text fields."""
        transactions = [
            Transaction(
                date=datetime(2023, 7, 15),
                description='UPI/PAYTM-"Special" & Characters, éñüñ',
                reference="REF/123,456",
                debit=100.0,
                credit=None,
                balance=2400.0,
                transaction_type=TransactionType.UPI,
                counterparty='merchant@paytm,special"chars',
                bank_name="Test Bank",
                account_number="123456789"
            )
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        exporter = CSVExporter(output_path)
        
        try:
            exporter.export_transactions(transactions)
            
            df = pd.read_csv(output_path)
            assert len(df) == 1
            assert 'Special" & Characters, éñüñ' in df.iloc[0]['Description']
            assert 'merchant@paytm,special"chars' == df.iloc[0]['Counterparty']
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_very_large_dataset(self):
        """Test exporting a large number of transactions."""
        transactions = []
        for i in range(1000):
            transactions.append(
                Transaction(
                    date=datetime(2023, 7, i % 28 + 1),
                    description=f"Transaction {i}",
                    reference=f"REF{i:06d}",
                    debit=float(i),
                    credit=None,
                    balance=10000.0 - float(i),
                    transaction_type=TransactionType.OTHER,
                    counterparty=f"counterparty{i}",
                    bank_name="Test Bank",
                    account_number="123456789"
                )
            )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        exporter = CSVExporter(output_path)
        
        try:
            exporter.export_transactions(transactions)
            
            df = pd.read_csv(output_path)
            assert len(df) == 1000
            assert df.iloc[0]['Description'] == "Transaction 0"
            assert df.iloc[999]['Description'] == "Transaction 999"
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_invalid_output_path(self):
        """Test handling of invalid output paths."""
        transactions = [
            Transaction(
                date=datetime(2023, 7, 15),
                description="Test transaction",
                reference="REF123",
                debit=100.0,
                credit=None,
                balance=2400.0,
                transaction_type=TransactionType.OTHER,
                counterparty="test",
                bank_name="Test Bank",
                account_number="123456789"
            )
        ]
        
        invalid_path = "/nonexistent/directory/output.csv"
        
        with pytest.raises(Exception):
            exporter = CSVExporter(invalid_path)

    def test_export_formatting_precision(self):
        """Test that amounts are formatted with correct precision."""
        transactions = [
            Transaction(
                date=datetime(2023, 7, 15),
                description="Precision test",
                reference="REF123",
                debit=123.456789,  # Should be rounded to 2 decimal places
                credit=None,
                balance=9876.543211,  # Should be rounded to 2 decimal places
                transaction_type=TransactionType.OTHER,
                counterparty="test",
                bank_name="Test Bank",
                account_number="123456789"
            )
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        exporter = CSVExporter(output_path)
        
        try:
            exporter.export_transactions(transactions)
            
            with open(output_path, 'r') as file:
                content = file.read()
                assert "123.46" in content  # Rounded debit
                assert "9876.54" in content  # Rounded balance
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_date_formatting_consistency(self):
        """Test that dates are formatted consistently in CSV output."""
        transactions = [
            Transaction(
                date=datetime(2023, 1, 1),
                description="New Year",
                reference="REF001",
                debit=100.0,
                credit=None,
                balance=2400.0,
                transaction_type=TransactionType.OTHER,
                counterparty="test",
                bank_name="Test Bank",
                account_number="123456789"
            ),
            Transaction(
                date=datetime(2023, 12, 31),
                description="Year End",
                reference="REF002",
                debit=200.0,
                credit=None,
                balance=2200.0,
                transaction_type=TransactionType.OTHER,
                counterparty="test",
                bank_name="Test Bank",
                account_number="123456789"
            )
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_path = f.name
        
        exporter = CSVExporter(output_path)
        
        try:
            exporter.export_transactions(transactions)
            
            df = pd.read_csv(output_path)
            assert df.iloc[0]['Date'] == "2023-01-01"
            assert df.iloc[1]['Date'] == "2023-12-31"
        finally:
            Path(output_path).unlink(missing_ok=True)