"""
Data processing utilities for transaction analysis.

This module provides comprehensive data processing capabilities including
cleaning, filtering, aggregation, trend analysis, and outlier detection
for bank transaction data.
"""

import re
import statistics
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
import logging

from .models import (
    Transaction,
    TransactionCategory,
    TransactionType,
    ConfidenceLevel,
    AnalysisStats,
    TrendDirection
)


class TimeFrameType(Enum):
    """Time frame types for analysis."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"





@dataclass
class DateRange:
    """Date range specification."""
    start_date: datetime
    end_date: datetime

    def contains(self, date: datetime) -> bool:
        """Check if date falls within range."""
        return self.start_date <= date <= self.end_date

    def duration_days(self) -> int:
        """Get duration in days."""
        return (self.end_date - self.start_date).days + 1


@dataclass
class CategorySummary:
    """Summary statistics for a transaction category."""
    category: TransactionCategory
    transaction_count: int
    total_amount: Decimal
    average_amount: Decimal
    min_amount: Decimal
    max_amount: Decimal
    median_amount: Decimal
    percentage_of_total: float
    top_merchants: List[Tuple[str, int, Decimal]] = field(default_factory=list)  # (name, count, amount)


@dataclass
class MonthlyBreakdown:
    """Monthly spending breakdown."""
    month: datetime  # First day of month
    category_totals: Dict[TransactionCategory, Decimal] = field(default_factory=dict)
    total_spending: Decimal = field(default_factory=lambda: Decimal('0'))
    transaction_count: int = 0
    average_transaction: Decimal = field(default_factory=lambda: Decimal('0'))


@dataclass
class TrendAnalysis:
    """Trend analysis results."""
    category: TransactionCategory
    direction: TrendDirection
    monthly_amounts: List[Decimal]
    percentage_change: float
    correlation_coefficient: float
    is_seasonal: bool = False
    peak_months: List[int] = field(default_factory=list)  # Month numbers (1-12)


@dataclass
class OutlierResult:
    """Outlier detection result."""
    transaction: Transaction
    z_score: float
    is_outlier: bool
    outlier_type: str  # "high" or "low"


class TransactionCleaner:
    """Utility class for cleaning and normalizing transaction data."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # Common patterns for cleaning
        self.upi_pattern = re.compile(r'UPI[/-].*?[/-](\w+)', re.IGNORECASE)
        self.merchant_patterns = {
            'swiggy': re.compile(r'swiggy|swig', re.IGNORECASE),
            'zomato': re.compile(r'zomato|zmt', re.IGNORECASE),
            'paytm': re.compile(r'paytm|ptm', re.IGNORECASE),
            'amazon': re.compile(r'amazon|amzn', re.IGNORECASE),
            'flipkart': re.compile(r'flipkart|fkrt', re.IGNORECASE),
            'uber': re.compile(r'uber', re.IGNORECASE),
            'ola': re.compile(r'ola', re.IGNORECASE),
        }

    def clean_description(self, description: str) -> str:
        """Clean and normalize transaction description."""
        if not description:
            return ""

        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', description.strip())

        # Remove common bank codes and references
        cleaned = re.sub(r'[A-Z0-9]{6,}', '', cleaned)
        cleaned = re.sub(r'\d{10,}', '', cleaned)  # Remove long numbers

        return cleaned.strip()

    def extract_merchant_name(self, transaction: Transaction) -> Optional[str]:
        """Extract merchant name from transaction details."""
        sources = [
            transaction.description,
            transaction.counterparty or "",
            transaction.reference or ""
        ]

        full_text = " ".join(sources).lower()

        # Check for known merchants first
        for merchant, pattern in self.merchant_patterns.items():
            if pattern.search(full_text):
                return merchant.title()

        # Extract from UPI reference
        if transaction.transaction_type == TransactionType.UPI:
            upi_match = self.upi_pattern.search(transaction.description)
            if upi_match:
                return upi_match.group(1).title()

        # Extract from counterparty
        if transaction.counterparty:
            # Remove common suffixes
            merchant = re.sub(r'@\w+', '', transaction.counterparty)
            merchant = re.sub(r'[0-9]', '', merchant).strip()
            if len(merchant) > 2:
                return merchant.title()

        return None

    def normalize_amount(self, amount: Decimal, precision: int = 2) -> Decimal:
        """Normalize amount to specified precision."""
        return amount.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)

    def is_valid_transaction(self, transaction: Transaction) -> bool:
        """Validate transaction data."""
        try:
            # Check required fields
            if not transaction.description or not transaction.date:
                return False

            # Check amount validity
            if not (transaction.debit or transaction.credit):
                return False

            # Check for reasonable amounts (not negative or extremely large)
            amount = abs(transaction.amount)
            if amount <= 0 or amount > Decimal('10000000'):  # 1 crore limit
                return False

            return True

        except Exception as e:
            self.logger.warning(f"Error validating transaction: {e}")
            return False


class DateProcessor:
    """Utility class for date-related processing."""

    @staticmethod
    def filter_by_date_range(
        transactions: List[Transaction],
        date_range: DateRange
    ) -> List[Transaction]:
        """Filter transactions by date range."""
        return [
            txn for txn in transactions
            if date_range.contains(txn.date)
        ]

    @staticmethod
    def get_month_boundaries(date: datetime) -> Tuple[datetime, datetime]:
        """Get start and end dates for the month containing the given date."""
        start_of_month = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get first day of next month
        if start_of_month.month == 12:
            next_month = start_of_month.replace(year=start_of_month.year + 1, month=1)
        else:
            next_month = start_of_month.replace(month=start_of_month.month + 1)

        # End of current month is one microsecond before next month
        end_of_month = next_month - timedelta(microseconds=1)

        return start_of_month, end_of_month

    @staticmethod
    def group_by_month(transactions: List[Transaction]) -> Dict[datetime, List[Transaction]]:
        """Group transactions by month."""
        monthly_groups = defaultdict(list)

        for transaction in transactions:
            month_start, _ = DateProcessor.get_month_boundaries(transaction.date)
            monthly_groups[month_start].append(transaction)

        return dict(monthly_groups)

    @staticmethod
    def get_date_range_from_transactions(transactions: List[Transaction]) -> DateRange:
        """Extract date range from transaction list."""
        if not transactions:
            now = datetime.now()
            return DateRange(now, now)

        dates = [txn.date for txn in transactions]
        return DateRange(min(dates), max(dates))


class CategoryAggregator:
    """Utility class for category-based aggregations."""

    def __init__(self, cleaner: Optional[TransactionCleaner] = None):
        self.cleaner = cleaner or TransactionCleaner()
        self.logger = logging.getLogger(self.__class__.__name__)

    def aggregate_by_category(
        self,
        transactions: List[Transaction],
        include_credits: bool = False
    ) -> Dict[TransactionCategory, CategorySummary]:
        """Aggregate transactions by category."""
        category_data = defaultdict(list)
        total_spending = Decimal('0')

        # Group transactions by category
        for txn in transactions:
            if not txn.category:
                continue

            # Skip credits unless explicitly included
            if txn.is_credit and not include_credits:
                continue

            amount = abs(txn.amount)
            category_data[txn.category].append((txn, amount))
            total_spending += amount

        # Create summaries
        summaries = {}
        for category, txn_list in category_data.items():
            amounts = [amount for _, amount in txn_list]
            transactions_in_cat = [txn for txn, _ in txn_list]

            if not amounts:
                continue

            total_amount = sum(amounts)
            percentage = float((total_amount / total_spending) * 100) if total_spending > 0 else 0.0

            # Get top merchants for this category
            top_merchants = self._get_top_merchants(transactions_in_cat)

            summaries[category] = CategorySummary(
                category=category,
                transaction_count=len(amounts),
                total_amount=total_amount,
                average_amount=total_amount / len(amounts),
                min_amount=min(amounts),
                max_amount=max(amounts),
                median_amount=Decimal(str(statistics.median(amounts))),
                percentage_of_total=percentage,
                top_merchants=top_merchants
            )

        return summaries

    def _get_top_merchants(
        self,
        transactions: List[Transaction],
        limit: int = 5
    ) -> List[Tuple[str, int, Decimal]]:
        """Get top merchants by transaction count and amount."""
        merchant_stats = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})

        for txn in transactions:
            merchant = self.cleaner.extract_merchant_name(txn) or 'Unknown'
            merchant_stats[merchant]['count'] += 1
            merchant_stats[merchant]['amount'] += abs(txn.amount)

        # Sort by amount first, then by count
        sorted_merchants = sorted(
            merchant_stats.items(),
            key=lambda x: (x[1]['amount'], x[1]['count']),
            reverse=True
        )

        return [
            (merchant, stats['count'], stats['amount'])
            for merchant, stats in sorted_merchants[:limit]
        ]

    def get_monthly_breakdown(
        self,
        transactions: List[Transaction]
    ) -> List[MonthlyBreakdown]:
        """Get monthly spending breakdown."""
        monthly_groups = DateProcessor.group_by_month(transactions)
        breakdowns = []

        for month_start in sorted(monthly_groups.keys()):
            month_transactions = monthly_groups[month_start]

            # Filter out credits for spending analysis
            spending_transactions = [txn for txn in month_transactions if txn.is_debit]

            category_totals = defaultdict(lambda: Decimal('0'))
            total_spending = Decimal('0')

            for txn in spending_transactions:
                if txn.category:
                    amount = abs(txn.amount)
                    category_totals[txn.category] += amount
                    total_spending += amount

            average_transaction = (
                total_spending / len(spending_transactions)
                if spending_transactions else Decimal('0')
            )

            breakdowns.append(MonthlyBreakdown(
                month=month_start,
                category_totals=dict(category_totals),
                total_spending=total_spending,
                transaction_count=len(spending_transactions),
                average_transaction=average_transaction
            ))

        return breakdowns


class TrendAnalyzer:
    """Utility class for trend analysis."""

    def analyze_category_trends(
        self,
        monthly_breakdowns: List[MonthlyBreakdown],
        min_months: int = 3
    ) -> Dict[TransactionCategory, TrendAnalysis]:
        """Analyze spending trends by category."""
        if len(monthly_breakdowns) < min_months:
            return {}

        # Collect monthly amounts by category
        category_monthly_data = defaultdict(list)

        for breakdown in monthly_breakdowns:
            for category in TransactionCategory:
                amount = breakdown.category_totals.get(category, Decimal('0'))
                category_monthly_data[category].append(float(amount))

        trends = {}
        for category, amounts in category_monthly_data.items():
            # Skip categories with no spending
            if sum(amounts) == 0:
                continue

            trend = self._analyze_trend(category, amounts, monthly_breakdowns)
            if trend:
                trends[category] = trend

        return trends

    def _analyze_trend(
        self,
        category: TransactionCategory,
        amounts: List[float],
        monthly_breakdowns: List[MonthlyBreakdown]
    ) -> Optional[TrendAnalysis]:
        """Analyze trend for a specific category."""
        if len(amounts) < 3:
            return None

        try:
            # Calculate correlation coefficient with time
            time_indices = list(range(len(amounts)))
            correlation = self._pearson_correlation(time_indices, amounts)

            # Determine trend direction
            direction = self._determine_trend_direction(amounts, correlation)

            # Calculate percentage change (first vs last non-zero values)
            first_nonzero = next((x for x in amounts if x > 0), 0)
            last_nonzero = next((x for x in reversed(amounts) if x > 0), 0)

            percentage_change = 0.0
            if first_nonzero > 0:
                percentage_change = ((last_nonzero - first_nonzero) / first_nonzero) * 100

            # Detect seasonality
            is_seasonal, peak_months = self._detect_seasonality(amounts, monthly_breakdowns)

            return TrendAnalysis(
                category=category,
                direction=direction,
                monthly_amounts=[Decimal(str(amt)) for amt in amounts],
                percentage_change=percentage_change,
                correlation_coefficient=correlation,
                is_seasonal=is_seasonal,
                peak_months=peak_months
            )

        except Exception as e:
            logging.getLogger(self.__class__.__name__).warning(
                f"Error analyzing trend for {category.value}: {e}"
            )
            return None

    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        try:
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(y)

            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))

            sum_sq_x = sum((x[i] - mean_x) ** 2 for i in range(len(x)))
            sum_sq_y = sum((y[i] - mean_y) ** 2 for i in range(len(y)))

            denominator = (sum_sq_x * sum_sq_y) ** 0.5

            if denominator == 0:
                return 0.0

            return numerator / denominator

        except (statistics.StatisticsError, ZeroDivisionError):
            return 0.0

    def _determine_trend_direction(
        self,
        amounts: List[float],
        correlation: float
    ) -> TrendDirection:
        """Determine trend direction based on correlation and volatility."""
        if abs(correlation) < 0.3:
            # Check volatility
            if len(amounts) > 1:
                try:
                    std_dev = statistics.stdev(amounts)
                    mean_amount = statistics.mean(amounts)
                    cv = std_dev / mean_amount if mean_amount > 0 else 0

                    if cv > 0.5:  # High coefficient of variation
                        return TrendDirection.VOLATILE
                except statistics.StatisticsError:
                    pass

            return TrendDirection.STABLE
        elif correlation > 0.3:
            return TrendDirection.INCREASING
        else:
            return TrendDirection.DECREASING

    def _detect_seasonality(
        self,
        amounts: List[float],
        monthly_breakdowns: List[MonthlyBreakdown]
    ) -> Tuple[bool, List[int]]:
        """Detect seasonal patterns and peak months."""
        if len(amounts) < 12:  # Need at least a year of data
            return False, []

        # Group by month number
        month_totals = defaultdict(list)
        for i, breakdown in enumerate(monthly_breakdowns):
            month_num = breakdown.month.month
            month_totals[month_num].append(amounts[i])

        # Calculate average for each month
        month_averages = {}
        for month_num, values in month_totals.items():
            if values:
                month_averages[month_num] = statistics.mean(values)

        if len(month_averages) < 6:  # Need data for at least half the months
            return False, []

        # Find peak months (top 25%)
        sorted_months = sorted(month_averages.items(), key=lambda x: x[1], reverse=True)
        peak_count = max(1, len(sorted_months) // 4)
        peak_months = [month for month, _ in sorted_months[:peak_count]]

        # Check if there's significant variation between months
        try:
            values = list(month_averages.values())
            if len(values) > 1:
                std_dev = statistics.stdev(values)
                mean_val = statistics.mean(values)
                cv = std_dev / mean_val if mean_val > 0 else 0

                # Consider seasonal if coefficient of variation > 0.2
                is_seasonal = cv > 0.2
                return is_seasonal, peak_months if is_seasonal else []
        except statistics.StatisticsError:
            pass

        return False, []


class OutlierDetector:
    """Utility class for outlier detection in transactions."""

    def detect_outliers(
        self,
        transactions: List[Transaction],
        z_threshold: float = 2.5,
        by_category: bool = True
    ) -> List[OutlierResult]:
        """Detect outliers using z-score method."""
        if len(transactions) < 3:
            return []

        outliers = []

        if by_category:
            # Group by category and detect outliers within each category
            category_groups = defaultdict(list)
            for txn in transactions:
                if txn.category:
                    category_groups[txn.category].append(txn)

            for category, cat_transactions in category_groups.items():
                if len(cat_transactions) >= 3:
                    cat_outliers = self._detect_outliers_in_group(
                        cat_transactions, z_threshold
                    )
                    outliers.extend(cat_outliers)
        else:
            # Detect outliers across all transactions
            outliers = self._detect_outliers_in_group(transactions, z_threshold)

        return outliers

    def _detect_outliers_in_group(
        self,
        transactions: List[Transaction],
        z_threshold: float
    ) -> List[OutlierResult]:
        """Detect outliers within a group of transactions."""
        if len(transactions) < 3:
            return []

        amounts = [float(abs(txn.amount)) for txn in transactions]

        try:
            mean_amount = statistics.mean(amounts)
            std_dev = statistics.stdev(amounts)

            if std_dev == 0:
                return []  # No variation, no outliers

            outliers = []
            for i, (txn, amount) in enumerate(zip(transactions, amounts)):
                z_score = (amount - mean_amount) / std_dev

                if abs(z_score) > z_threshold:
                    outlier_type = "high" if z_score > 0 else "low"
                    outliers.append(OutlierResult(
                        transaction=txn,
                        z_score=z_score,
                        is_outlier=True,
                        outlier_type=outlier_type
                    ))

            return outliers

        except statistics.StatisticsError:
            return []