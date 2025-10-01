"""Public API for orchestrating PDF processing and CSV export."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..core.exceptions import (
    BankStatementProcessorError,
    ExportError,
    StatementLayoutError,
)
from ..exporters.csv_exporter import CSVExporter, CSVExportError
from ..parsers.base_parser import Transaction, TransactionType
from ..parsers.parser_factory import ParserFactory

logger = logging.getLogger(__name__)


class BankStatementProcessor:
    """Coordinate PDF parsing and CSV export for bank statements."""

    def __init__(self, output_dir: Optional[str] = None) -> None:
        """Create a processor instance.

        Args:
            output_dir: Directory where CSV exports should be written.
        """
        self.output_dir = Path(output_dir) if output_dir else Path(
            tempfile.mkdtemp(prefix="bank_processor_exports_")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_pdf(self, pdf_path: str, password: Optional[str] = None) -> Dict[str, Any]:
        """Parse a PDF bank statement and prepare structured data.

        Args:
            pdf_path: Path to the PDF file.
            password: Optional password for encrypted PDFs.

        Returns:
            Dictionary containing processing results. On success the dictionary
            includes the raw ``Transaction`` objects and JSON serialisable
            versions for API responses. On failure a dictionary containing error
            information is returned instead.
        """
        try:
            parser = ParserFactory.create_parser(pdf_path, password)
            transactions = parser.extract_transactions()

            if not transactions:
                raise StatementLayoutError(
                    pdf_path=pdf_path,
                    missing_elements=["transactions"],
                    bank_name=getattr(parser, "bank_name", "Unknown"),
                )

            try:
                account_number = parser.get_account_number()
            except Exception:  # pragma: no cover - defensive
                account_number = None

            serialized_transactions = [
                self._transaction_to_dict(transaction)
                for transaction in transactions
            ]

            result: Dict[str, Any] = {
                "status": "success",
                "transactions": transactions,
                "transactions_data": serialized_transactions,
                "count": len(transactions),
                "bank": getattr(parser, "bank_name", "Unknown"),
                "account_number": account_number or "Unknown",
            }

            logger.debug(
                "Processed %s with %d transactions using %s",
                pdf_path,
                result["count"],
                parser.__class__.__name__,
            )
            return result

        except BankStatementProcessorError as exc:
            logger.error("Bank processing failed for %s: %s", pdf_path, exc)
            return {
                "status": "error",
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "details": getattr(exc, "details", {}),
            }
        except Exception as exc:  # pragma: no cover - unexpected failure path
            logger.exception("Unexpected error processing PDF %s", pdf_path)
            return {
                "status": "error",
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            }

    def export_to_csv(
        self,
        transactions: List[Transaction],
        bank_name: str,
        account_number: Optional[str] = None,
    ) -> str:
        """Export transactions to a CSV file and return the file path."""
        if not transactions:
            raise ExportError(
                export_path=str(self.output_dir),
                export_format="CSV",
                transaction_count=0,
                original_error=None,
            )

        output_path = self.output_dir / f"transactions_{uuid4().hex}.csv"
        exporter = CSVExporter(str(output_path))

        try:
            exporter.export_with_summary(
                transactions=transactions,
                bank_name=bank_name,
                account_number=account_number or "Unknown",
            )
        except CSVExportError as exc:
            raise ExportError(
                export_path=str(output_path),
                export_format="CSV",
                transaction_count=len(transactions),
                original_error=exc,
            ) from exc

        logger.debug("Exported %d transactions to %s", len(transactions), output_path)
        return str(output_path)

    @staticmethod
    def _transaction_to_dict(transaction: Transaction) -> Dict[str, Any]:
        """Convert a transaction dataclass to a JSON-friendly dictionary."""
        transaction_dict = asdict(transaction)

        date_value = transaction_dict.get("date")
        if isinstance(date_value, datetime):
            transaction_dict["date"] = date_value.isoformat()
        elif date_value is not None:
            transaction_dict["date"] = str(date_value)

        txn_type = transaction_dict.get("transaction_type")
        if isinstance(txn_type, TransactionType):
            transaction_dict["transaction_type"] = txn_type.value
        elif txn_type is not None:
            transaction_dict["transaction_type"] = str(txn_type)

        for key in ("debit", "credit", "balance"):
            value = transaction_dict.get(key)
            if value is not None:
                transaction_dict[key] = float(value)

        return transaction_dict
