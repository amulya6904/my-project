"""Command-line interface for Bank Statement Processor."""

import sys
import logging
import signal
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

import click
from tqdm import tqdm

from .parsers.parser_factory import ParserFactory
from .exporters.csv_exporter import CSVExporter
from .core.exceptions import (
    BankStatementProcessorError,
    UnsupportedBankError,
    PasswordProtectedPDFError,
    StatementLayoutError,
    InvalidTransactionError,
    PDFProcessingError,
    ExportError,
    format_error_for_user
)
from .analyzer.cli import cli as analyze_cli

# Global variable to handle Ctrl+C gracefully
interrupted = False

def signal_handler(signum, frame):
    """Handle Ctrl+C interruption gracefully."""
    global interrupted
    interrupted = True
    click.echo("\n\n⚠️  Process interrupted by user. Cleaning up...", err=True)
    sys.exit(1)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)


def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug flag.
    
    Args:
        debug: Enable debug level logging
    """
    level = logging.DEBUG if debug else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # Set specific loggers
    if not debug:
        # Reduce noise from libraries in non-debug mode
        logging.getLogger('pdfplumber').setLevel(logging.WARNING)
        logging.getLogger('PIL').setLevel(logging.WARNING)


def prompt_for_password(pdf_path: str, attempts: int = 3) -> Optional[str]:
    """Prompt user for PDF password with retry logic.
    
    Args:
        pdf_path: Path to the password-protected PDF
        attempts: Number of attempts allowed
        
    Returns:
        Password if provided, None if cancelled
    """
    click.echo(f"📄 PDF is password protected: {Path(pdf_path).name}")
    
    for attempt in range(attempts):
        try:
            if attempt > 0:
                click.echo(f"❌ Incorrect password. Attempt {attempt + 1}/{attempts}")
            
            password = click.prompt(
                "🔐 Enter PDF password (or press Ctrl+C to cancel)",
                type=str,
                hide_input=True
            )
            return password
            
        except (KeyboardInterrupt, click.Abort):
            click.echo("\n⚠️  Password prompt cancelled.", err=True)
            return None
    
    click.echo(f"❌ Failed to unlock PDF after {attempts} attempts.", err=True)
    return None


def display_success_summary(result: Dict[str, Any], command: str) -> None:
    """Display success summary based on command type.
    
    Args:
        result: Result dictionary from processing
        command: Command that was executed
    """
    if command == 'process':
        click.echo("\n✅ Processing completed successfully!")
        click.echo(f"📊 Transactions exported: {result.get('transactions_exported', 0)}")
        click.echo(f"💾 Output file: {result.get('file_path', 'N/A')}")
        click.echo(f"📅 Date range: {result.get('date_range', 'N/A')}")
        
        if 'total_debit_amount' in result:
            click.echo(f"💸 Total debits: ₹{result['total_debit_amount']:.2f}")
        if 'total_credit_amount' in result:
            click.echo(f"💰 Total credits: ₹{result['total_credit_amount']:.2f}")
            
    elif command == 'batch':
        click.echo("\n✅ Batch processing completed!")
        click.echo(f"📁 Files processed: {result.get('files_processed', 0)}")
        click.echo(f"📊 Total transactions: {result.get('total_transactions', 0)}")
        click.echo(f"⚠️  Failed files: {result.get('failed_files', 0)}")
        
        if result.get('summary_file'):
            click.echo(f"📋 Summary report: {result['summary_file']}")


@click.group()
@click.option(
    '--debug', 
    is_flag=True, 
    help='Enable debug logging for troubleshooting'
)
@click.version_option(version='1.0.0', prog_name='Bank Statement Processor')
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Bank Statement Processor - Extract transaction data from Indian bank PDFs.
    
    Supported banks: Union Bank of India, State Bank of India
    
    Examples:
    
        # Process a single PDF
        bank-processor process statement.pdf --output transactions.csv
        
        # Process all PDFs in a directory
        bank-processor batch statements/ --output-dir results/
        
        # Check if a PDF is supported
        bank-processor validate statement.pdf
    """
    ctx.ensure_object(dict)
    
    # Setup logging
    # setup_logging(debug)
    ctx.obj['debug'] = debug
    
    if debug:
        click.echo("🐛 Debug mode enabled", err=True)


@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--output', '-o',
    required=True,
    type=click.Path(path_type=Path),
    help='Output CSV file path'
)
@click.option(
    '--password', '-p',
    help='PDF password if document is encrypted'
)
@click.option(
    '--analyze',
    is_flag=True,
    help='Run AI analysis after conversion'
)
@click.option(
    '--api-key',
    help='API key for the analysis provider (e.g., Gemini)'
)
@click.option(
    '--provider',
    default='gemini',
    help='The analysis provider to use'
)
@click.pass_context
def process(
    ctx: click.Context, 
    pdf_path: Path, 
    output: Path, 
    password: Optional[str], 
    analyze: bool,
    api_key: Optional[str],
    provider: str
) -> None:
    """Process a single PDF bank statement and export to CSV.    
    PDF_PATH: Path to the bank statement PDF file
    
    Examples:    
        # Basic usage
        bank-processor process statement.pdf -o transactions.csv
        
        # With password-protected PDF
        bank-processor process statement.pdf -o transactions.csv -p mypassword

        # With AI analysis
        bank-processor process statement.pdf -o tx.csv --analyze --api-key <YOUR_API_KEY>
    """
    setup_logging(ctx.obj['debug'])
    try:
        click.echo(f"📄 Processing: {pdf_path.name}")
        
        current_password = password
        parser = None
        
        # Attempt to create parser with password handling
        while parser is None:
            try:
                parser = ParserFactory.create_parser(str(pdf_path), current_password)
                break
                
            except PasswordProtectedPDFError as e:
                if current_password is not None:
                    # Password was provided but incorrect
                    click.echo("❌ Provided password is incorrect.")
                
                # Prompt for password
                current_password = prompt_for_password(str(pdf_path))
                if current_password is None:
                    return  # User cancelled
                    
        click.echo(f"🏦 Detected bank: {parser.bank_name}")
        
        # Extract transactions
        with click.progressbar(
            length=100, 
            label="🔍 Extracting transactions",
            show_percent=True
        ) as bar:
            bar.update(30)  # Simulate progress
            transactions = parser.extract_transactions()
            bar.update(70)  # Complete progress
        
        if not transactions:
            click.echo("⚠️  No transactions found in the PDF.", err=True)
            sys.exit(1)
        
        # Export to CSV
        click.echo(f"📝 Exporting {len(transactions)} transactions...")
        exporter = CSVExporter(str(output))
        
        result = exporter.export_with_summary(
            transactions=transactions,
            bank_name=parser.bank_name,
            account_number=getattr(parser, 'account_number', 'Unknown')
        )
        
        # Display success summary
        display_success_summary(result, 'process')

        # Run analysis if requested
        if analyze:
            _run_analysis(ctx, output, provider, api_key)

    except BankStatementProcessorError as e:
        click.echo(format_error_for_user(e), err=True)
        sys.exit(1)
    except Exception as e:
        if ctx.obj.get('debug'):
            raise  # Re-raise in debug mode for full traceback
        click.echo(f"❌ Unexpected error: {str(e)}", err=True)
        click.echo("💡 Use --debug flag for detailed error information", err=True)
        sys.exit(1)


def _run_analysis(ctx: click.Context, csv_file: Path, provider: str, api_key: Optional[str]):
    """Helper to run the analysis step."""
    click.echo("\n🔍 Starting AI analysis...")
    
    try:
        # Lazy import the analyzer CLI entrypoint
        from .analyzer.cli import run_analysis
        import os

        # Determine API key, preferring CLI option over environment variable
        final_api_key = api_key or os.environ.get('BANK_ANALYZER_GEMINI_API_KEY')

        if not final_api_key:
            click.echo(
                "❌ Error: --api-key is required for analysis, or set BANK_ANALYZER_GEMINI_API_KEY environment variable.",
                err=True
            )
            return

        output_dir = f"{csv_file.stem}_analysis"
        
        run_analysis(
            csv_file=str(csv_file),
            output_dir=output_dir,
            provider=provider,
            api_key=final_api_key,
            generate_charts=True
        )
        
        click.echo("✅ Analysis completed successfully!")
        click.echo(f"📊 Analysis results saved to: {output_dir}/")

    except ImportError:
        click.echo("❌ Analysis module not found. Please ensure it is installed correctly.", err=True)
    except Exception as e:
        click.echo(f"⚠️  Analysis failed: {str(e)}", err=True)
        if ctx.obj.get('debug'):
            raise



@cli.command()
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    '--output-dir', '-o',
    required=True,
    type=click.Path(path_type=Path),
    help='Output directory for CSV files'
)
@click.option(
    '--password', '-p',
    help='Common password for all encrypted PDFs'
)
@click.option(
    '--continue-on-error',
    is_flag=True,
    help='Continue processing other files if one fails'
)
@click.pass_context
def batch(ctx: click.Context, input_dir: Path, output_dir: Path, 
          password: Optional[str], continue_on_error: bool) -> None:
    """Process all PDF files in a directory and export to CSV files.
    
    INPUT_DIR: Directory containing PDF bank statements
    
    Examples:
    
        # Process all PDFs in statements/ directory
        bank-processor batch statements/ -o results/
        
        # Continue on errors and use common password
        bank-processor batch statements/ -o results/ -p secret --continue-on-error
    """
    setup_logging(ctx.obj['debug'])
    global interrupted
    
    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all PDF files
        pdf_files = list(input_dir.glob('*.pdf')) + list(input_dir.glob('*.PDF'))
        
        if not pdf_files:
            click.echo(f"⚠️  No PDF files found in {input_dir}", err=True)
            sys.exit(1)
        
        click.echo(f"📁 Found {len(pdf_files)} PDF files to process")
        
        # Processing statistics
        results = {
            'files_processed': 0,
            'total_transactions': 0,
            'failed_files': 0,
            'failures': [],
            'successes': []
        }
        
        # Process files with progress bar
        with tqdm(pdf_files, desc="🔄 Processing PDFs", unit="file") as pbar:
            for pdf_file in pbar:
                if interrupted:
                    break
                
                pbar.set_description(f"🔄 Processing {pdf_file.name}")
                
                try:
                    # Create parser
                    parser = ParserFactory.create_parser(str(pdf_file), password)
                    
                    # Extract transactions
                    transactions = parser.extract_transactions()
                    
                    if transactions:
                        # Generate output filename
                        csv_filename = pdf_file.stem + '.csv'
                        csv_path = output_dir / csv_filename
                        
                        # Export to CSV
                        exporter = CSVExporter(str(csv_path))
                        export_result = exporter.export_with_summary(
                            transactions=transactions,
                            bank_name=parser.bank_name,
                            account_number=getattr(parser, 'account_number', 'Unknown')
                        )
                        
                        # Update statistics
                        results['files_processed'] += 1
                        results['total_transactions'] += len(transactions)
                        results['successes'].append({
                            'file': pdf_file.name,
                            'bank': parser.bank_name,
                            'transactions': len(transactions),
                            'output': csv_filename
                        })
                        
                    else:
                        raise StatementLayoutError(
                            pdf_path=str(pdf_file),
                            missing_elements=['transactions'],
                            bank_name=getattr(parser, 'bank_name', 'Unknown')
                        )
                
                except PasswordProtectedPDFError:
                    if password is None:
                        # Prompt for password for this specific file
                        file_password = prompt_for_password(str(pdf_file))
                        if file_password:
                            # Retry with the provided password
                            try:
                                parser = ParserFactory.create_parser(str(pdf_file), file_password)
                                transactions = parser.extract_transactions()
                                
                                if transactions:
                                    csv_filename = pdf_file.stem + '.csv'
                                    csv_path = output_dir / csv_filename
                                    
                                    exporter = CSVExporter(str(csv_path))
                                    export_result = exporter.export_with_summary(
                                        transactions=transactions,
                                        bank_name=parser.bank_name,
                                        account_number=getattr(parser, 'account_number', 'Unknown')
                                    )
                                    
                                    results['files_processed'] += 1
                                    results['total_transactions'] += len(transactions)
                                    results['successes'].append({
                                        'file': pdf_file.name,
                                        'bank': parser.bank_name,
                                        'transactions': len(transactions),
                                        'output': csv_filename
                                    })
                                    continue
                            except Exception as retry_error:
                                results['failed_files'] += 1
                                results['failures'].append({
                                    'file': pdf_file.name,
                                    'error': str(retry_error)
                                })
                        else:
                            results['failed_files'] += 1
                            results['failures'].append({
                                'file': pdf_file.name,
                                'error': 'Password required but not provided'
                            })
                    else:
                        results['failed_files'] += 1
                        results['failures'].append({
                            'file': pdf_file.name,
                            'error': 'Incorrect password'
                        })
                        
                except BankStatementProcessorError as e:
                    results['failed_files'] += 1
                    results['failures'].append({
                        'file': pdf_file.name,
                        'error': str(e)
                    })
                    
                    if not continue_on_error:
                        click.echo(f"\n❌ Processing failed for {pdf_file.name}")
                        click.echo(format_error_for_user(e), err=True)
                        click.echo("💡 Use --continue-on-error to skip failed files", err=True)
                        sys.exit(1)
                
                except Exception as e:
                    results['failed_files'] += 1
                    error_msg = str(e) if not ctx.obj.get('debug') else f"{type(e).__name__}: {str(e)}"
                    results['failures'].append({
                        'file': pdf_file.name,
                        'error': error_msg
                    })
                    
                    if not continue_on_error:
                        if ctx.obj.get('debug'):
                            raise
                        click.echo(f"\n❌ Unexpected error processing {pdf_file.name}: {str(e)}", err=True)
                        click.echo("💡 Use --continue-on-error to skip failed files or --debug for details", err=True)
                        sys.exit(1)
        
        # Generate summary report
        summary_file = output_dir / 'batch_summary.txt'
        _generate_batch_summary(results, summary_file)
        results['summary_file'] = str(summary_file)
        
        # Display results
        display_success_summary(results, 'batch')
        
        # Show failures if any
        if results['failures']:
            click.echo(f"\n⚠️  {len(results['failures'])} files failed to process:")
            for failure in results['failures'][:5]:  # Show first 5
                click.echo(f"   • {failure['file']}: {failure['error']}")
            if len(results['failures']) > 5:
                click.echo(f"   ... and {len(results['failures']) - 5} more (see summary report)")
        
    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Batch processing interrupted by user.", err=True)
        sys.exit(1)
    except Exception as e:
        if ctx.obj.get('debug'):
            raise
        click.echo(f"❌ Batch processing failed: {str(e)}", err=True)
        sys.exit(1)


def _generate_batch_summary(results: Dict[str, Any], summary_file: Path) -> None:
    """Generate a detailed batch processing summary report.
    
    Args:
        results: Processing results dictionary
        summary_file: Path to save the summary report
    """
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("# Bank Statement Processor - Batch Summary\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Summary Statistics\n")
        f.write(f"Files processed successfully: {results['files_processed']}\n")
        f.write(f"Failed files: {results['failed_files']}\n")
        f.write(f"Total transactions extracted: {results['total_transactions']}\n\n")
        
        if results['successes']:
            f.write("## Successfully Processed Files\n")
            for success in results['successes']:
                f.write(f"- {success['file']} ({success['bank']}) -> {success['output']} "
                       f"[{success['transactions']} transactions]\n")
            f.write("\n")
        
        if results['failures']:
            f.write("## Failed Files\n")
            for failure in results['failures']:
                f.write(f"- {failure['file']}: {failure['error']}\n")
            f.write("\n")


@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--password', '-p',
    help='PDF password if document is encrypted'
)
@click.pass_context
def validate(ctx: click.Context, pdf_path: Path, password: Optional[str]) -> None:
    """Check if a PDF bank statement is supported and display compatibility information.
    
    PDF_PATH: Path to the bank statement PDF file
    
    Examples:
    
        # Check PDF compatibility
        bank-processor validate statement.pdf
        
        # Check password-protected PDF
        bank-processor validate statement.pdf -p mypassword
    """
    setup_logging(ctx.obj['debug'])
    try:
        click.echo(f"🔍 Validating: {pdf_path.name}")
        
        # Try to detect bank type
        bank_name = ParserFactory.detect_bank_type(str(pdf_path), password)
        
        if bank_name:
            click.echo(f"✅ PDF is supported!")
            click.echo(f"🏦 Detected bank: {bank_name}")
            
            # Try to create parser for additional validation
            try:
                parser = ParserFactory.create_parser(str(pdf_path), password)
                click.echo(f"📄 Parser: {parser.__class__.__name__}")
                click.echo(f"🔧 Status: Ready for processing")
                
                # Try to extract a sample to verify structure
                try:
                    transactions = parser.extract_transactions()
                    if transactions:
                        click.echo(f"📊 Sample validation: Found {len(transactions)} transactions")
                        
                        # Show date range if available
                        dates = [t.date for t in transactions if t.date]
                        if dates:
                            min_date = min(dates).strftime('%Y-%m-%d')
                            max_date = max(dates).strftime('%Y-%m-%d')
                            click.echo(f"📅 Date range: {min_date} to {max_date}")
                    else:
                        click.echo("⚠️  Warning: No transactions found (empty statement?)")
                        
                except Exception as e:
                    click.echo(f"⚠️  Warning: Could not extract transactions - {str(e)}")
                    
            except PasswordProtectedPDFError:
                if password is None:
                    click.echo("🔐 PDF is password-protected")
                    click.echo("💡 Use -p option to provide password for full validation")
                else:
                    click.echo("❌ Provided password is incorrect")
                    sys.exit(1)
                    
        else:
            click.echo("❌ PDF is not supported")
            
            # Show supported banks
            supported_banks = ParserFactory.get_supported_banks()
            if supported_banks:
                click.echo(f"\n🏦 Currently supported banks:")
                for bank in supported_banks:
                    click.echo(f"   • {bank}")
            
            click.echo(f"\n💡 This could mean:")
            click.echo(f"   • The PDF is not a bank statement")
            click.echo(f"   • The bank is not yet supported")
            click.echo(f"   • The PDF format has changed")
            
            sys.exit(1)
            
    except PasswordProtectedPDFError as e:
        if password is None:
            # Prompt for password
            prompted_password = prompt_for_password(str(pdf_path))
            if prompted_password:
                # Retry validation with password
                ctx.invoke(validate, pdf_path=pdf_path, password=prompted_password)
                return
        click.echo(format_error_for_user(e), err=True)
        sys.exit(1)
        
    except BankStatementProcessorError as e:
        click.echo(format_error_for_user(e), err=True)
        sys.exit(1)
        
    except Exception as e:
        if ctx.obj.get('debug'):
            raise
        click.echo(f"❌ Validation failed: {str(e)}", err=True)
        click.echo("💡 Use --debug flag for detailed error information", err=True)
        sys.exit(1)





# Add the analyze command group to the main CLI
cli.add_command(analyze_cli)

if __name__ == '__main__':
    cli()