"""
Main analysis engine for transaction categorization and spending analysis.

This module provides the SpendingAnalyzer class which orchestrates the entire
analysis pipeline from CSV reading through categorization to comprehensive
spending insights and report generation.
"""

import csv
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import json

from .models import (
    Transaction,
    TransactionType,
    TransactionCategory,
    ConfidenceLevel,
    AnalysisStats,
    BatchCategorizationResult
)
from .base_categorizer import BaseCategorizer, CategorizationError
from .cache import TransactionCache
from .config import ConfigManager, AnalyzerConfig
from .processors import (
    TransactionCleaner,
    CategoryAggregator,
    DateProcessor,
    TrendAnalyzer,
    OutlierDetector,
    DateRange,
    CategorySummary,
    MonthlyBreakdown,
    TrendAnalysis,
    OutlierResult
)


@dataclass
class AnalysisReport:
    """Comprehensive analysis report."""
    # Basic statistics
    total_transactions: int
    date_range: DateRange
    total_spending: Decimal
    total_income: Decimal
    net_amount: Decimal

    # Category analysis
    category_summaries: Dict[TransactionCategory, CategorySummary]
    top_spending_categories: List[Tuple[TransactionCategory, Decimal]]

    # Monthly analysis
    monthly_breakdowns: List[MonthlyBreakdown]
    monthly_averages: Dict[str, Decimal]  # "spending", "income", "transactions"

    # Trend analysis
    category_trends: Dict[TransactionCategory, TrendAnalysis]

    # Outlier detection
    outliers: List[OutlierResult]

    # Categorization quality
    categorization_stats: Dict[str, Any]

    # Cache performance (if applicable)
    cache_stats: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        def decimal_to_str(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif hasattr(obj, '__dict__'):
                return {k: decimal_to_str(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, (list, tuple)):
                return [decimal_to_str(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: decimal_to_str(v) for k, v in obj.items()}
            else:
                return obj

        return decimal_to_str(self.__dict__)


class CSVParsingError(Exception):
    """Error in CSV parsing."""
    pass


class SpendingAnalyzer:
    """
    Main analysis engine for transaction categorization and spending analysis.

    Orchestrates the entire analysis pipeline including:
    - CSV reading and validation
    - Transaction categorization using LLMs
    - Comprehensive spending analysis
    - Trend detection and outlier analysis
    - Report generation
    """

    def __init__(
        self,
        categorizer: BaseCategorizer,
        cache: Optional[TransactionCache] = None,
        config: Optional[AnalyzerConfig] = None
    ):
        """
        Initialize the spending analyzer.

        Args:
            categorizer: Transaction categorizer instance
            cache: Optional cache for storing results
            config: Optional configuration (will load default if not provided)
        """
        self.categorizer = categorizer
        self.cache = cache
        self.config = config or ConfigManager().get_config()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize processors
        self.cleaner = TransactionCleaner()
        self.aggregator = CategoryAggregator(self.cleaner)
        self.trend_analyzer = TrendAnalyzer()
        self.outlier_detector = OutlierDetector()

    def analyze_csv(
        self,
        csv_file: Union[str, Path],
        date_range: Optional[DateRange] = None,
        categorize: bool = True,
        generate_report: bool = True
    ) -> Tuple[List[Transaction], Optional[AnalysisReport]]:
        """
        Analyze transactions from a CSV file.

        Args:
            csv_file: Path to CSV file
            date_range: Optional date range filter
            categorize: Whether to categorize transactions
            generate_report: Whether to generate analysis report

        Returns:
            Tuple of (transactions, analysis_report)

        Raises:
            CSVParsingError: If CSV cannot be parsed
            CategorizationError: If categorization fails
        """
        self.logger.info(f"Starting analysis of {csv_file}")

        # Read and validate CSV
        transactions = self._read_csv(csv_file)
        self.logger.info(f"Loaded {len(transactions)} transactions from CSV")

        # Apply date filter if specified
        if date_range:
            transactions = DateProcessor.filter_by_date_range(transactions, date_range)
            self.logger.info(f"Filtered to {len(transactions)} transactions in date range")

        # Clean and validate transactions
        transactions = self._clean_transactions(transactions)
        self.logger.info(f"Cleaned data: {len(transactions)} valid transactions")

        if not transactions:
            self.logger.warning("No valid transactions found")
            return [], None

        # Categorize transactions if requested
        if categorize:
            transactions = self._categorize_transactions(transactions)

        # Generate analysis report if requested
        report = None
        if generate_report:
            report = self._generate_analysis_report(transactions)

        self.logger.info("Analysis completed successfully")
        return transactions, report

    def _read_csv(self, csv_file: Union[str, Path]) -> List[Transaction]:
        """
        Read transactions from CSV file.

        Expected CSV format:
        Date,Description,Reference,Debit,Credit,Balance,Type,Counterparty,Bank

        Args:
            csv_file: Path to CSV file

        Returns:
            List[Transaction]: Parsed transactions

        Raises:
            CSVParsingError: If CSV cannot be parsed
        """
        csv_path = Path(csv_file)
        if not csv_path.exists():
            raise CSVParsingError(f"CSV file not found: {csv_path}")

        transactions = []

        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                # Detect delimiter
                sample = file.read(1024)
                file.seek(0)

                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter

                reader = csv.DictReader(file, delimiter=delimiter)

                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    try:
                        transaction = self._parse_csv_row(row)
                        if transaction:
                            transactions.append(transaction)
                    except Exception as e:
                        self.logger.warning(f"Error parsing row {row_num}: {e}")
                        continue

        except Exception as e:
            raise CSVParsingError(f"Failed to read CSV file: {e}") from e

        return transactions

    def _parse_csv_row(self, row: Dict[str, str]) -> Optional[Transaction]:
        """
        Parse a single CSV row into a Transaction object.

        Args:
            row: CSV row as dictionary

        Returns:
            Optional[Transaction]: Parsed transaction or None if invalid
        """
        try:
            # Parse date
            date_str = row.get('Date', '').strip()
            if not date_str:
                return None

            # Try multiple date formats
            date_formats = [
                '%Y-%m-%d',
                '%d/%m/%Y',
                '%d-%m-%Y',
                '%m/%d/%Y',
                '%Y-%m-%d %H:%M:%S'
            ]

            date = None
            for fmt in date_formats:
                try:
                    date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

            if date is None:
                self.logger.warning(f"Could not parse date: {date_str}")
                return None

            # Parse amounts
            debit_str = row.get('Debit', '').strip()
            credit_str = row.get('Credit', '').strip()
            balance_str = row.get('Balance', '').strip()

            debit = self._parse_amount(debit_str) if debit_str else None
            credit = self._parse_amount(credit_str) if credit_str else None
            balance = self._parse_amount(balance_str) if balance_str else Decimal('0')

            # Parse transaction type
            type_str = row.get('Type', '').strip().upper()
            try:
                transaction_type = TransactionType(type_str) if type_str else TransactionType.OTHER
            except ValueError:
                transaction_type = TransactionType.OTHER

            # Create transaction
            transaction = Transaction(
                date=date,
                description=row.get('Description', '').strip(),
                reference=row.get('Reference', '').strip() or None,
                debit=debit,
                credit=credit,
                balance=balance,
                transaction_type=transaction_type,
                counterparty=row.get('Counterparty', '').strip() or None,
                bank_name=row.get('Bank', 'Unknown').strip(),
                account_number=row.get('Account', '****0000').strip()
            )

            return transaction

        except Exception as e:
            self.logger.warning(f"Error parsing CSV row: {e}")
            return None

    def _parse_amount(self, amount_str: str) -> Decimal:
        """
        Parse amount string to Decimal.

        Args:
            amount_str: Amount string (may contain currency symbols, commas)

        Returns:
            Decimal: Parsed amount

        Raises:
            InvalidOperation: If amount cannot be parsed
        """
        if not amount_str:
            return Decimal('0')

        # Clean amount string
        cleaned = amount_str.replace(',', '').replace('₹', '').replace('Rs', '').strip()

        # Handle negative amounts in parentheses
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]

        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError) as e:
            raise InvalidOperation(f"Cannot parse amount: {amount_str}") from e

    def _clean_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Clean and validate transactions.

        Args:
            transactions: Raw transactions

        Returns:
            List[Transaction]: Cleaned valid transactions
        """
        cleaned = []

        for transaction in transactions:
            if self.cleaner.is_valid_transaction(transaction):
                # Clean description
                transaction.description = self.cleaner.clean_description(transaction.description)

                # Normalize amounts
                if transaction.debit:
                    transaction.debit = self.cleaner.normalize_amount(transaction.debit)
                if transaction.credit:
                    transaction.credit = self.cleaner.normalize_amount(transaction.credit)
                transaction.balance = self.cleaner.normalize_amount(transaction.balance)

                cleaned.append(transaction)

        return cleaned

    def _categorize_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Categorize transactions using the configured categorizer.

        Args:
            transactions: Transactions to categorize

        Returns:
            List[Transaction]: Transactions with categories assigned
        """
        self.logger.info(f"[DIAGNOSTIC] Entering _categorize_transactions for {len(transactions)} transactions.")
        self.logger.info(f"[DIAGNOSTIC] Categorizer type: {type(self.categorizer).__name__}")

        try:
            # Use batch categorization for efficiency
            result = self.categorizer.categorize_batch(transactions)

            self.logger.info(
                f"Categorization completed: {result.successful} successful, "
                f"{result.failed} failed, {result.success_rate:.1f}% success rate"
            )

            if hasattr(result, 'cache_hits'):
                self.logger.info(
                    f"Cache performance: {result.cache_hits} hits, "
                    f"{result.cache_misses} misses, {result.cache_hit_rate:.1f}% hit rate"
                )

            # Apply categorization results to transactions
            result_map = {res.transaction_id: res for res in result.results}

            for transaction in transactions:
                txn_id = f"{transaction.date}_{transaction.description[:20]}"
                if txn_id in result_map:
                    categorization = result_map[txn_id]
                    transaction.category = categorization.category
                    transaction.confidence = categorization.confidence
                    transaction.notes = categorization.reasoning
            
            self.logger.info("[DIAGNOSTIC] Exiting _categorize_transactions.")
            return transactions

        except Exception as e:
            self.logger.error(f"Categorization failed: {e}")
            raise CategorizationError(f"Failed to categorize transactions: {e}") from e

    def _generate_analysis_report(self, transactions: List[Transaction]) -> AnalysisReport:
        """
        Generate comprehensive analysis report.

        Args:
            transactions: Categorized transactions

        Returns:
            AnalysisReport: Complete analysis report
        """
        self.logger.info("Generating analysis report")

        # Basic statistics
        date_range = DateProcessor.get_date_range_from_transactions(transactions)

        spending_transactions = [txn for txn in transactions if txn.is_debit]
        income_transactions = [txn for txn in transactions if txn.is_credit]

        total_spending = sum(abs(txn.amount) for txn in spending_transactions)
        total_income = sum(abs(txn.amount) for txn in income_transactions)
        net_amount = total_income - total_spending

        # Category analysis
        category_summaries = self.aggregator.aggregate_by_category(transactions)
        top_spending_categories = sorted(
            [(cat, summary.total_amount) for cat, summary in category_summaries.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Monthly analysis
        monthly_breakdowns = self.aggregator.get_monthly_breakdown(transactions)
        monthly_averages = self._calculate_monthly_averages(monthly_breakdowns, income_transactions)

        # Trend analysis
        category_trends = self.trend_analyzer.analyze_category_trends(monthly_breakdowns)

        # Outlier detection
        outliers = self.outlier_detector.detect_outliers(spending_transactions)

        # Categorization statistics
        categorization_stats = self._calculate_categorization_stats(transactions)

        # Cache statistics (if available)
        cache_stats = None
        if self.cache:
            cache_stats = self.cache.get_stats().to_dict() if hasattr(self.cache.get_stats(), 'to_dict') else None

        report = AnalysisReport(
            total_transactions=len(transactions),
            date_range=date_range,
            total_spending=total_spending,
            total_income=total_income,
            net_amount=net_amount,
            category_summaries=category_summaries,
            top_spending_categories=top_spending_categories,
            monthly_breakdowns=monthly_breakdowns,
            monthly_averages=monthly_averages,
            category_trends=category_trends,
            outliers=outliers,
            categorization_stats=categorization_stats,
            cache_stats=cache_stats
        )

        self.logger.info("Analysis report generated successfully")
        return report

    def _calculate_monthly_averages(
        self,
        monthly_breakdowns: List[MonthlyBreakdown],
        income_transactions: List[Transaction]
    ) -> Dict[str, Decimal]:
        """Calculate monthly averages."""
        if not monthly_breakdowns:
            return {"spending": Decimal('0'), "income": Decimal('0'), "transactions": Decimal('0')}

        # Group income by month
        monthly_income = defaultdict(lambda: Decimal('0'))
        income_by_month = DateProcessor.group_by_month(income_transactions)

        for month_start, txns in income_by_month.items():
            monthly_income[month_start] = sum(abs(txn.amount) for txn in txns)

        # Calculate averages
        total_spending = sum(breakdown.total_spending for breakdown in monthly_breakdowns)
        total_income = sum(monthly_income[breakdown.month] for breakdown in monthly_breakdowns)
        total_transactions = sum(breakdown.transaction_count for breakdown in monthly_breakdowns)

        num_months = len(monthly_breakdowns)

        return {
            "spending": total_spending / num_months if num_months > 0 else Decimal('0'),
            "income": total_income / num_months if num_months > 0 else Decimal('0'),
            "transactions": Decimal(str(total_transactions)) / num_months if num_months > 0 else Decimal('0')
        }

    def _calculate_categorization_stats(self, transactions: List[Transaction]) -> Dict[str, Any]:
        """Calculate categorization quality statistics."""
        categorized = [txn for txn in transactions if txn.category]

        if not transactions:
            return {"categorization_rate": 0.0, "confidence_breakdown": {}}

        categorization_rate = len(categorized) / len(transactions) * 100

        # Confidence breakdown
        confidence_counts = defaultdict(int)
        for txn in categorized:
            if txn.confidence:
                confidence_counts[txn.confidence.value] += 1

        return {
            "categorization_rate": categorization_rate,
            "total_categorized": len(categorized),
            "confidence_breakdown": dict(confidence_counts)
        }

    def export_report(
        self,
        report: AnalysisReport,
        output_file: Union[str, Path],
        format_type: str = "json"
    ) -> None:
        """
        Export analysis report to file.

        Args:
            report: Analysis report to export
            output_file: Output file path
            format_type: Export format ("json", "csv")

        Raises:
            ValueError: If format type is unsupported
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type.lower() == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

        self.logger.info(f"Report exported to {output_path}")

    def get_spending_insights(self, report: AnalysisReport) -> Dict[str, Any]:
        """
        Extract key spending insights from analysis report.

        Args:
            report: Analysis report

        Returns:
            Dict[str, Any]: Key insights and recommendations
        """
        insights = {
            "summary": {
                "total_spending": str(report.total_spending),
                "total_income": str(report.total_income),
                "net_savings": str(report.net_amount),
                "savings_rate": float((report.net_amount / report.total_income) * 100) if report.total_income > 0 else 0.0
            },
            "top_categories": [
                {"category": cat.value, "amount": str(amount), "percentage": float((amount / report.total_spending) * 100)}
                for cat, amount in report.top_spending_categories[:5]
            ],
            "recommendations": []
        }

        # Generate recommendations
        if report.total_spending > report.total_income:
            insights["recommendations"].append("Consider reducing expenses as spending exceeds income")

        # Find categories with increasing trends
        for category, trend in report.category_trends.items():
            if trend.direction.value == "increasing" and trend.percentage_change > 20:
                insights["recommendations"].append(
                    f"{category.value} spending increased by {trend.percentage_change:.1f}% - consider monitoring"
                )

        # Flag high-value outliers
        high_outliers = [o for o in report.outliers if o.outlier_type == "high" and o.z_score > 3]
        if high_outliers:
            insights["recommendations"].append(
                f"Found {len(high_outliers)} unusually high transactions - review for accuracy"
            )

        return insights