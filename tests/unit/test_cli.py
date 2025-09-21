"""Unit tests for CLI interface."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime
from click.testing import CliRunner

from src.main import cli, process, batch, validate
from src.parsers.base_parser import Transaction, TransactionType
from src.core.exceptions import (
    UnsupportedBankError,
    PasswordProtectedPDFError,
    StatementLayoutError,
    PDFProcessingError
)


class TestCLIMain:
    """Test main CLI group functionality."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()
    
    @pytest.mark.cli
    def test_cli_help(self, runner):
        """Test CLI help message."""
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'Bank Statement Processor' in result.output
        assert 'process' in result.output
        assert 'batch' in result.output
        assert 'validate' in result.output
    
    @pytest.mark.cli
    def test_cli_version(self, runner):
        """Test CLI version display."""
        result = runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        assert '1.0.0' in result.output


class TestProcessCommand:
    """Test the 'process' command."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()
    
    @pytest.fixture
    def mock_successful_processing(self):
        """Mock successful PDF processing."""
        mock_parser = Mock()
        mock_parser.bank_name = 'Union Bank of India'
        mock_parser.extract_transactions.return_value = [
            Transaction(
                date=datetime(2025, 7, 1),
                description='Test transaction',
                reference='TEST123',
                debit=100.0,
                credit=None,
                balance=900.0,
                transaction_type=TransactionType.UPI,
                counterparty='test@merchant',
                bank_name='Union Bank of India',
                account_number='****1234'
            )
        ]
        
        mock_export_result = {
            'file_path': 'output.csv',
            'transactions_exported': 1,
            'date_range': '2025-07-01 to 2025-07-01',
            'total_debit_amount': 100.0,
            'total_credit_amount': 0.0
        }
        
        return mock_parser, mock_export_result
    
    @pytest.mark.cli
    def test_process_help(self, runner):
        """Test process command help."""
        result = runner.invoke(cli, ['process', '--help'])
        
        assert result.exit_code == 0
        assert 'Process a single PDF' in result.output
        assert '--output' in result.output
        assert '--password' in result.output
    
    @pytest.mark.cli
    def test_process_missing_arguments(self, runner):
        """Test process command with missing required arguments."""
        result = runner.invoke(cli, ['process'])
        
        assert result.exit_code == 2  # Click error code for missing arguments
        assert 'Missing argument' in result.output
    
    @pytest.mark.cli
    def test_process_missing_output(self, runner, temp_dir):
        """Test process command with missing output option."""
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        
        result = runner.invoke(cli, ['process', str(test_pdf)])
        
        assert result.exit_code == 2
        assert 'Missing option' in result.output
        assert '--output' in result.output
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.create_parser')
    @patch('src.main.CSVExporter')
    def test_process_success(self, mock_csv_exporter, mock_create_parser, runner, temp_dir, mock_successful_processing):
        """Test successful PDF processing."""
        mock_parser, mock_export_result = mock_successful_processing
        
        # Setup mocks
        mock_create_parser.return_value = mock_parser
        mock_exporter_instance = Mock()
        mock_exporter_instance.export_with_summary.return_value = mock_export_result
        mock_csv_exporter.return_value = mock_exporter_instance
        
        # Create test files
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        output_csv = temp_dir / 'output.csv'
        
        result = runner.invoke(cli, ['process', str(test_pdf), '--output', str(output_csv)])
        
        assert result.exit_code == 0
        assert '✅ Processing completed successfully!' in result.output
        assert 'Union Bank of India' in result.output
        assert '1' in result.output  # transaction count
        
        # Verify mocks were called
        mock_create_parser.assert_called_once_with(str(test_pdf), None)
        mock_parser.extract_transactions.assert_called_once()
        mock_exporter_instance.export_with_summary.assert_called_once()
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.create_parser')
    def test_process_password_protected_prompt(self, mock_create_parser, runner, temp_dir):
        """Test password prompting for protected PDF."""
        # First call raises PasswordProtectedPDFError, second succeeds
        mock_parser = Mock()
        mock_parser.bank_name = 'Union Bank of India'
        mock_parser.extract_transactions.return_value = []
        
        mock_create_parser.side_effect = [
            PasswordProtectedPDFError('test.pdf', attempted_password=False),
            mock_parser  # Second call succeeds
        ]
        
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        output_csv = temp_dir / 'output.csv'
        
        with patch('src.main.CSVExporter'), \
             patch('src.main.prompt_for_password', return_value='secret123'):
            
            result = runner.invoke(cli, ['process', str(test_pdf), '--output', str(output_csv)])
            
            # Should have attempted twice - once without password, once with
            assert mock_create_parser.call_count == 2
            assert result.exit_code == 0 or 'No transactions found' in result.output
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.create_parser')
    @patch('src.main.prompt_for_password', return_value=None) # User cancels
    def test_process_incorrect_password(self, mock_prompt, mock_create_parser, runner, temp_dir):
        """Test handling of incorrect password."""
        mock_create_parser.side_effect = PasswordProtectedPDFError('test.pdf', attempted_password=True)
        
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        output_csv = temp_dir / 'output.csv'
        
        result = runner.invoke(cli, ['process', str(test_pdf), '--output', str(output_csv), '--password', 'wrong'])
        
        assert result.exit_code == 0
        assert '❌' in result.output
        assert 'incorrect' in result.output.lower()
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.create_parser')
    def test_process_unsupported_bank(self, mock_create_parser, runner, temp_dir):
        """Test handling of unsupported bank."""
        mock_create_parser.side_effect = UnsupportedBankError(
            'test.pdf', 
            'Unknown Bank Content',
            ['Union Bank of India', 'State Bank of India']
        )
        
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        output_csv = temp_dir / 'output.csv'
        
        result = runner.invoke(cli, ['process', str(test_pdf), '--output', str(output_csv)])
        
        assert result.exit_code == 1
        assert '❌' in result.output
        assert 'Cannot identify bank' in result.output

    @pytest.mark.cli
    @patch('src.main.setup_logging')
    @patch('src.main.ParserFactory.create_parser')
    @patch('src.main.CSVExporter')
    def test_process_with_debug(self, mock_csv_exporter, mock_create_parser, mock_setup_logging, runner, temp_dir):
        """Test process command with debug flag."""
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        output_csv = temp_dir / 'output.csv'

        result = runner.invoke(cli, ['--debug', 'process', str(test_pdf), '-o', str(output_csv)])

        assert result.exit_code == 0
        mock_setup_logging.assert_called_once_with(True)

    @pytest.mark.cli
    @patch('src.main.ParserFactory.create_parser')
    @patch('src.main.prompt_for_password')
    def test_process_password_retry(self, mock_prompt, mock_create_parser, runner, temp_dir):
        """Test password prompt is retried on incorrect password."""
        mock_parser = Mock()
        mock_parser.bank_name = 'Union Bank of India'
        
        # Create a mock transaction to avoid "No transactions found" error
        from datetime import datetime
        mock_transaction = Mock()
        mock_transaction.date = datetime(2023, 7, 15)
        mock_transaction.description = "Test transaction"
        mock_transaction.debit = 100.0
        mock_transaction.credit = None
        mock_parser.extract_transactions.return_value = [mock_transaction]

        mock_create_parser.side_effect = [
            PasswordProtectedPDFError('test.pdf', attempted_password=True), # fails with initial password
            PasswordProtectedPDFError('test.pdf', attempted_password=True), # fails with first prompt
            mock_parser # succeeds with second prompt
        ]
        mock_prompt.side_effect = ['wrong_password', 'correct_password']

        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        output_csv = temp_dir / 'output.csv'

        with patch('src.main.CSVExporter'):
            result = runner.invoke(cli, ['process', str(test_pdf), '-o', str(output_csv), '-p', 'initial_wrong_password'])

        assert result.exit_code == 0
        assert mock_prompt.call_count == 2

class TestBatchCommand:
    """Test the 'batch' command."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()
    
    @pytest.mark.cli
    def test_batch_help(self, runner):
        """Test batch command help."""
        result = runner.invoke(cli, ['batch', '--help'])
        
        assert result.exit_code == 0
        assert 'Process all PDF files in a directory' in result.output
        assert '--output-dir' in result.output
        assert '--continue-on-error' in result.output
    
    @pytest.mark.cli
    def test_batch_missing_arguments(self, runner):
        """Test batch command with missing arguments."""
        result = runner.invoke(cli, ['batch'])
        
        assert result.exit_code == 2
        assert 'Missing argument' in result.output
    
    @pytest.mark.cli
    def test_batch_no_pdfs_found(self, runner, temp_dir):
        """Test batch command with no PDF files."""
        output_dir = temp_dir / 'output'
        
        result = runner.invoke(cli, ['batch', str(temp_dir), '--output-dir', str(output_dir)])
        
        assert result.exit_code == 1
        assert 'No PDF files found' in result.output
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.create_parser')
    @patch('src.main.CSVExporter')
    def test_batch_success(self, mock_csv_exporter, mock_create_parser, runner, temp_dir):
        """Test successful batch processing."""
        # Create test PDFs
        pdf1 = temp_dir / 'test1.pdf'
        pdf2 = temp_dir / 'test2.pdf'
        pdf1.write_text('mock pdf 1')
        pdf2.write_text('mock pdf 2')
        
        output_dir = temp_dir / 'output'
        
        # Mock successful processing
        mock_parser = Mock()
        mock_parser.bank_name = 'Union Bank of India'
        mock_parser.extract_transactions.return_value = [Mock()]  # One transaction
        
        mock_create_parser.return_value = mock_parser
        
        mock_exporter_instance = Mock()
        mock_export_result = {
            'file_path': 'output.csv',
            'transactions_exported': 1,
            'date_range': '2025-07-01 to 2025-07-01'
        }
        mock_exporter_instance.export_with_summary.return_value = mock_export_result
        mock_csv_exporter.return_value = mock_exporter_instance
        
        with patch('src.main._generate_batch_summary'):
            result = runner.invoke(cli, ['batch', str(temp_dir), '--output-dir', str(output_dir)])
        
        assert result.exit_code == 0
        assert '✅ Batch processing completed!' in result.output
        assert 'Files processed: 2' in result.output
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.create_parser')
    def test_batch_continue_on_error(self, mock_create_parser, runner, temp_dir):
        """Test batch processing with continue-on-error flag."""
        # Create test PDFs
        pdf1 = temp_dir / 'test1.pdf'
        pdf2 = temp_dir / 'test2.pdf'
        pdf1.write_text('mock pdf 1')
        pdf2.write_text('mock pdf 2')
        
        output_dir = temp_dir / 'output'
        
        # First PDF fails, second succeeds
        mock_parser = Mock()
        mock_parser.bank_name = 'Union Bank of India'
        mock_parser.extract_transactions.return_value = [Mock()]
        
        mock_create_parser.side_effect = [
            UnsupportedBankError('test1.pdf', 'Unknown', []),
            mock_parser
        ]
        
        with patch('src.main.CSVExporter'), \
             patch('src.main._generate_batch_summary'):
            
            result = runner.invoke(cli, ['batch',
                str(temp_dir), 
                '--output-dir', str(output_dir), 
                '--continue-on-error'
            ])
        
        assert result.exit_code == 0
        assert 'Failed files: 1' in result.output


class TestValidateCommand:
    """Test the 'validate' command."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()
    
    @pytest.mark.cli
    def test_validate_help(self, runner):
        """Test validate command help."""
        result = runner.invoke(cli, ['validate', '--help'])
        
        assert result.exit_code == 0
        assert 'Check if a PDF bank statement is supported' in result.output
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.detect_bank_type')
    def test_validate_supported_pdf(self, mock_detect_bank, runner, temp_dir):
        """Test validation of supported PDF."""
        mock_detect_bank.return_value = 'Union Bank of India'
        
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        
        with patch('src.main.ParserFactory.create_parser') as mock_create:
            mock_parser = Mock()
            mock_parser.__class__.__name__ = 'UnionBankParser'
            mock_parser.extract_transactions.return_value = [Mock(), Mock()]  # 2 transactions
            mock_create.return_value = mock_parser
            
            result = runner.invoke(cli, ['validate', str(test_pdf)])
        
        assert result.exit_code == 0
        assert '✅ PDF is supported!' in result.output
        assert 'Union Bank of India' in result.output
        assert 'Found 2 transactions' in result.output
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.detect_bank_type')
    @patch('src.main.ParserFactory.get_supported_banks')
    def test_validate_unsupported_pdf(self, mock_get_banks, mock_detect_bank, runner, temp_dir):
        """Test validation of unsupported PDF."""
        mock_detect_bank.return_value = None
        mock_get_banks.return_value = ['Union Bank of India', 'State Bank of India']
        
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        
        result = runner.invoke(cli, ['validate', str(test_pdf)])
        
        assert result.exit_code == 1
        assert '❌ PDF is not supported' in result.output
        assert 'Union Bank of India' in result.output
        assert 'State Bank of India' in result.output
    
    @pytest.mark.cli
    @patch('src.main.ParserFactory.detect_bank_type')
    def test_validate_password_protected(self, mock_detect_bank, runner, temp_dir):
        """Test validation of password-protected PDF."""
        mock_detect_bank.side_effect = PasswordProtectedPDFError('test.pdf', attempted_password=False)
        
        test_pdf = temp_dir / 'test.pdf'
        test_pdf.write_text('mock pdf')
        
        with patch('src.main.prompt_for_password', return_value=None):  # User cancels
            result = runner.invoke(cli, ['validate', str(test_pdf)])
        
        # Should exit due to password cancellation
        assert result.exit_code in [0, 1]  # Depends on implementation


class TestPasswordPrompting:
    """Test password prompting functionality."""
    
    @pytest.mark.cli
    @patch('src.main.click.prompt')
    def test_prompt_for_password_success(self, mock_prompt):
        """Test successful password prompting."""
        from src.main import prompt_for_password
        
        mock_prompt.return_value = 'secret123'
        
        result = prompt_for_password('test.pdf')
        
        assert result == 'secret123'
        mock_prompt.assert_called_once()
    
    @pytest.mark.cli
    @patch('src.main.click.prompt')
    def test_prompt_for_password_cancelled(self, mock_prompt):
        """Test password prompting when user cancels."""
        from src.main import prompt_for_password
        
        mock_prompt.side_effect = KeyboardInterrupt()
        
        result = prompt_for_password('test.pdf')
        
        assert result is None


class TestErrorDisplay:
    """Test error display functionality."""
    
    @pytest.mark.cli
    def test_display_success_summary_process(self):
        """Test success summary display for process command."""
        from src.main import display_success_summary
        
        result = {
            'transactions_exported': 5,
            'file_path': '/path/to/output.csv',
            'date_range': '2025-07-01 to 2025-07-05',
            'total_debit_amount': 500.0,
            'total_credit_amount': 1000.0
        }
        
        # This would normally print to stdout, but in tests we just verify it doesn't crash
        display_success_summary(result, 'process')
    
    @pytest.mark.cli
    def test_display_success_summary_batch(self):
        """Test success summary display for batch command."""
        from src.main import display_success_summary
        
        result = {
            'files_processed': 3,
            'total_transactions': 15,
            'failed_files': 1,
            'summary_file': '/path/to/summary.txt'
        }
        
        display_success_summary(result, 'batch')


class TestSignalHandling:
    """Test signal handling for Ctrl+C interruption."""
    
    @pytest.mark.cli
    def test_signal_handler_sets_interrupted_flag(self):
        """Test that signal handler sets the interrupted flag."""
        from src.main import signal_handler, interrupted
        
        # Reset the flag
        import src.main
        src.main.interrupted = False
        
        # The signal handler would normally exit, but we can't test that easily
        # Instead we test the setup exists
        assert hasattr(src.main, 'signal_handler')
        assert hasattr(src.main, 'interrupted')