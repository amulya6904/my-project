"""CSV export functionality for bank transactions."""

import csv
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import asdict

from ..parsers.base_parser import Transaction


class CSVExportError(Exception):
    """Raised when CSV export fails."""
    pass


class CSVExporter:
    """Utility class for exporting transaction data to CSV format."""
    
    # Default CSV column headers matching the required format
    DEFAULT_HEADERS = [
        'Date',
        'Description', 
        'Reference',
        'Debit',
        'Credit',
        'Balance',
        'Type',
        'Counterparty',
        'Bank'
    ]
    
    # Extended headers for more detailed export
    EXTENDED_HEADERS = [
        'Date',
        'Description',
        'Reference',
        'Debit',
        'Credit',
        'Balance',
        'Type',
        'Counterparty',
        'Bank',
        'Account_Number',
        'Transaction_ID',
        'Parsed_At'
    ]
    
    def __init__(self, output_path: str, include_extended_fields: bool = False):
        """Initialize CSV exporter.
        
        Args:
            output_path: Path where CSV file will be saved
            include_extended_fields: Whether to include extended transaction fields
            
        Raises:
            CSVExportError: If output path is invalid
        """
        self.output_path = Path(output_path)
        self.include_extended_fields = include_extended_fields
        self.headers = self.EXTENDED_HEADERS if include_extended_fields else self.DEFAULT_HEADERS
        
        # Validate output directory
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.output_path.exists() and not self.output_path.is_file():
            raise CSVExportError(f"Output path is not a file: {self.output_path}")
    
    def export_transactions(self, transactions: List[Transaction], 
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Export transactions to CSV file.
        
        Args:
            transactions: List of transactions to export
            metadata: Optional metadata to include in file header
            
        Raises:
            CSVExportError: If export fails
        """
        if not transactions:
            raise CSVExportError("No transactions to export")
        
        try:
            with open(self.output_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Write metadata header if provided
                if metadata:
                    self._write_metadata_header(csvfile, metadata)
                
                # Create CSV writer
                writer = csv.DictWriter(csvfile, fieldnames=self.headers)
                writer.writeheader()
                
                # Write transaction data
                for transaction in transactions:
                    row_data = self._transaction_to_row(transaction)
                    writer.writerow(row_data)
                    
        except IOError as e:
            raise CSVExportError(f"Cannot write to CSV file {self.output_path}: {str(e)}") from e
        except Exception as e:
            raise CSVExportError(f"CSV export failed: {str(e)}") from e
    
    def append_transactions(self, transactions: List[Transaction]) -> None:
        """Append transactions to existing CSV file.
        
        Args:
            transactions: List of transactions to append
            
        Raises:
            CSVExportError: If append operation fails
        """
        if not transactions:
            return
        
        # Check if file exists and has headers
        file_exists = self.output_path.exists() and self.output_path.stat().st_size > 0
        
        try:
            with open(self.output_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.headers)
                
                # Write header if file is new or empty
                if not file_exists:
                    writer.writeheader()
                
                # Write transaction data
                for transaction in transactions:
                    row_data = self._transaction_to_row(transaction)
                    writer.writerow(row_data)
                    
        except IOError as e:
            raise CSVExportError(f"Cannot append to CSV file {self.output_path}: {str(e)}") from e
        except Exception as e:
            raise CSVExportError(f"CSV append failed: {str(e)}") from e
    
    def export_with_summary(self, transactions: List[Transaction], 
                          bank_name: str, account_number: str) -> Dict[str, Any]:
        """Export transactions with summary statistics.
        
        Args:
            transactions: List of transactions to export
            bank_name: Bank name for summary
            account_number: Account number for summary
            
        Returns:
            Dictionary containing export statistics
            
        Raises:
            CSVExportError: If export fails
        """
        if not transactions:
            raise CSVExportError("No transactions to export")
        
        # Calculate summary statistics
        total_transactions = len(transactions)
        total_debits = sum(t.debit for t in transactions if t.debit is not None)
        total_credits = sum(t.credit for t in transactions if t.credit is not None)
        date_range = (min(t.date for t in transactions), max(t.date for t in transactions))
        
        # Prepare metadata
        metadata = {
            'bank_name': bank_name,
            'account_number': account_number,
            'total_transactions': total_transactions,
            'total_debits': total_debits,
            'total_credits': total_credits,
            'date_from': date_range[0].strftime('%Y-%m-%d'),
            'date_to': date_range[1].strftime('%Y-%m-%d'),
            'exported_at': datetime.now().isoformat()
        }
        
        # Export transactions
        self.export_transactions(transactions, metadata)
        
        return {
            'file_path': str(self.output_path),
            'transactions_exported': total_transactions,
            'total_debit_amount': total_debits,
            'total_credit_amount': total_credits,
            'date_range': f"{date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}",
            'file_size_bytes': self.output_path.stat().st_size
        }
    
    def _write_metadata_header(self, csvfile, metadata: Dict[str, Any]) -> None:
        """Write metadata as comments at the top of CSV file.
        
        Args:
            csvfile: Open CSV file handle
            metadata: Metadata dictionary to write
        """
        csvfile.write("# Bank Statement Export\n")
        csvfile.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        for key, value in metadata.items():
            if value is not None:
                csvfile.write(f"# {key}: {value}\n")
        
        csvfile.write("#\n")  # Separator line
    
    def _transaction_to_row(self, transaction: Transaction) -> Dict[str, Any]:
        """Convert transaction object to CSV row dictionary.
        
        Args:
            transaction: Transaction to convert
            
        Returns:
            Dictionary mapping CSV headers to values
        """
        # Format date
        date_str = transaction.date.strftime('%Y-%m-%d') if transaction.date else ''
        
        # Format amounts (empty string for None values)
        debit_str = f"{transaction.debit:.2f}" if transaction.debit is not None else ''
        credit_str = f"{transaction.credit:.2f}" if transaction.credit is not None else ''
        balance_str = f"{transaction.balance:.2f}" if transaction.balance is not None else ''
        
        # Base row data
        row_data = {
            'Date': date_str,
            'Description': transaction.description or '',
            'Reference': transaction.reference or '',
            'Debit': debit_str,
            'Credit': credit_str,
            'Balance': balance_str,
            'Type': transaction.transaction_type.value if transaction.transaction_type else '',
            'Counterparty': transaction.counterparty or '',
            'Bank': transaction.bank_name or ''
        }
        
        # Add extended fields if requested
        if self.include_extended_fields:
            row_data.update({
                'Account_Number': transaction.account_number or '',
                'Transaction_ID': getattr(transaction, 'transaction_id', ''),
                'Parsed_At': datetime.now().isoformat()
            })
        
        return row_data
    
    @classmethod
    def export_to_string(cls, transactions: List[Transaction], 
                        include_extended_fields: bool = False) -> str:
        """Export transactions to CSV string.
        
        Args:
            transactions: List of transactions to export
            include_extended_fields: Whether to include extended fields
            
        Returns:
            CSV data as string
            
        Raises:
            CSVExportError: If export fails
        """
        if not transactions:
            return ""
        
        import io
        
        output = io.StringIO()
        headers = cls.EXTENDED_HEADERS if include_extended_fields else cls.DEFAULT_HEADERS
        
        try:
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            exporter = cls.__new__(cls)  # Create instance without __init__
            exporter.include_extended_fields = include_extended_fields
            exporter.headers = headers
            
            for transaction in transactions:
                row_data = exporter._transaction_to_row(transaction)
                writer.writerow(row_data)
            
            return output.getvalue()
            
        except Exception as e:
            raise CSVExportError(f"String export failed: {str(e)}") from e
        finally:
            output.close()
    
    @classmethod
    def validate_export_data(cls, transactions: List[Transaction]) -> List[str]:
        """Validate transactions before export.
        
        Args:
            transactions: List of transactions to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not transactions:
            errors.append("No transactions to export")
            return errors
        
        for i, transaction in enumerate(transactions):
            if not isinstance(transaction, Transaction):
                errors.append(f"Transaction {i} is not a Transaction object")
                continue
            
            if not transaction.date:
                errors.append(f"Transaction {i} missing date")
            
            if not transaction.description:
                errors.append(f"Transaction {i} missing description")
            
            if transaction.balance is None:
                errors.append(f"Transaction {i} missing balance")
            
            if transaction.debit is None and transaction.credit is None:
                errors.append(f"Transaction {i} missing both debit and credit amounts")
        
        return errors
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """Get statistics about the exported CSV file.
        
        Returns:
            Dictionary containing file statistics
            
        Raises:
            CSVExportError: If file doesn't exist or can't be read
        """
        if not self.output_path.exists():
            raise CSVExportError(f"Export file does not exist: {self.output_path}")
        
        try:
            with open(self.output_path, 'r', encoding='utf-8') as csvfile:
                # Count lines (excluding metadata comments)
                line_count = 0
                data_lines = 0
                
                for line in csvfile:
                    line_count += 1
                    if not line.startswith('#') and line.strip():
                        data_lines += 1
                
                # Subtract 1 for header row
                transaction_count = max(0, data_lines - 1)
                
            file_size = self.output_path.stat().st_size
            modified_time = datetime.fromtimestamp(self.output_path.stat().st_mtime)
            
            return {
                'file_path': str(self.output_path),
                'file_size_bytes': file_size,
                'total_lines': line_count,
                'transaction_count': transaction_count,
                'last_modified': modified_time.isoformat(),
                'headers_used': self.headers.copy()
            }
            
        except IOError as e:
            raise CSVExportError(f"Cannot read export file: {str(e)}") from e