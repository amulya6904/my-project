"""
Data models for transaction analysis and categorization.

This module defines the core data structures used throughout the analyzer system,
including transaction representations, category definitions, and analysis results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from decimal import Decimal


class TransactionType(Enum):
    """Transaction type enumeration."""
    UPI = "UPI"
    NEFT = "NEFT"
    RTGS = "RTGS"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CHEQUE = "CHEQUE"
    DEBIT_CARD = "DEBIT_CARD"
    CREDIT_CARD = "CREDIT_CARD"
    FEE = "FEE"
    INTEREST = "INTEREST"
    OTHER = "OTHER"


class TransactionCategory(Enum):
    """Standard transaction categories for classification."""
    # Main expense categories (used by AI categorizer)
    DINING = "Dining"
    SHOPPING = "Shopping"
    GROCERIES = "Groceries"
    TRANSPORTATION = "Transportation"
    UTILITIES = "Utilities"
    HEALTH = "Health"
    ENTERTAINMENT = "Entertainment"
    RENT = "Rent"
    INCOME = "Income"
    OTHER = "Other"

    # Legacy categories for backward compatibility
    FOOD_DINING = "Food & Dining"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    TRAVEL = "Travel"
    INCOME_SALARY = "Income - Salary"
    INCOME_OTHER = "Income - Other"
    TRANSFERS = "Transfers"
    INVESTMENTS = "Investments"
    INSURANCE = "Insurance"
    RENT_MORTGAGE = "Rent & Mortgage"
    FUEL = "Fuel"
    BANKING_FEES = "Banking Fees"
    TAXES = "Taxes"
    DONATIONS = "Donations"
    PERSONAL_CARE = "Personal Care"


class ConfidenceLevel(Enum):
    """Confidence level for categorization results."""
    HIGH = "HIGH"      # >90% confidence
    MEDIUM = "MEDIUM"  # 70-90% confidence
    LOW = "LOW"        # <70% confidence


class TrendDirection(Enum):
    """Trend direction indicators."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class Transaction:
    """
    Represents a bank transaction with all relevant details.

    This is the core data model that will be used for categorization
    and analysis throughout the system.
    """
    date: datetime
    description: str
    reference: Optional[str]
    debit: Optional[Decimal]
    credit: Optional[Decimal]
    balance: Decimal
    transaction_type: TransactionType
    counterparty: Optional[str]
    bank_name: str
    account_number: str

    # Analysis fields
    category: Optional[TransactionCategory] = None
    confidence: Optional[ConfidenceLevel] = None
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def amount(self) -> Decimal:
        """Get the transaction amount (positive for credit, negative for debit)."""
        if self.credit:
            return self.credit
        elif self.debit:
            return -self.debit
        else:
            return Decimal('0')

    @property
    def is_credit(self) -> bool:
        """Check if this is a credit transaction."""
        return self.credit is not None and self.credit > 0

    @property
    def is_debit(self) -> bool:
        """Check if this is a debit transaction."""
        return self.debit is not None and self.debit > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to dictionary for serialization."""
        return {
            'date': self.date.isoformat(),
            'description': self.description,
            'reference': self.reference,
            'debit': str(self.debit) if self.debit else None,
            'credit': str(self.credit) if self.credit else None,
            'balance': str(self.balance),
            'transaction_type': self.transaction_type.value,
            'counterparty': self.counterparty,
            'bank_name': self.bank_name,
            'account_number': self.account_number,
            'category': self.category.value if self.category else None,
            'confidence': self.confidence.value if self.confidence else None,
            'tags': self.tags,
            'notes': self.notes
        }


@dataclass
class CategorizationResult:
    """
    Result of categorizing a single transaction.

    Contains the suggested category, confidence level, and reasoning
    behind the categorization decision.
    """
    transaction_id: str  # Reference to original transaction
    category: TransactionCategory
    confidence: ConfidenceLevel
    reasoning: str
    suggested_tags: List[str] = field(default_factory=list)
    alternative_categories: List[TransactionCategory] = field(default_factory=list)


@dataclass
class BatchCategorizationResult:
    """
    Result of categorizing a batch of transactions.

    Contains results for all transactions in the batch plus
    overall statistics and any errors encountered.
    """
    results: List[CategorizationResult]
    total_processed: int
    successful: int
    failed: int
    errors: List[str] = field(default_factory=list)
    processing_time_seconds: float = 0.0

    # Cache statistics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_saves: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate the success rate as a percentage."""
        if self.total_processed == 0:
            return 0.0
        return (self.successful / self.total_processed) * 100

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests == 0:
            return 0.0
        return (self.cache_hits / total_requests) * 100


@dataclass
class CategorizerConfig:
    """
    Configuration for transaction categorizers.

    Contains settings that affect how categorization is performed,
    including API keys, model parameters, and processing options.
    """
    api_key: str
    model_name: str = "gemini-1.5-flash"
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0
    batch_size: int = 50
    timeout_seconds: int = 30

    # Prompt customization
    use_custom_categories: bool = False
    custom_categories: List[str] = field(default_factory=list)
    include_reasoning: bool = True
    include_alternatives: bool = False

    # Processing options
    parallel_processing: bool = False
    max_concurrent_requests: int = 3


@dataclass
class AnalysisStats:
    """
    Statistics from transaction analysis.

    Provides insights into spending patterns and categorization quality.
    """
    total_transactions: int
    date_range_start: datetime
    date_range_end: datetime

    # Category breakdown
    category_counts: Dict[TransactionCategory, int] = field(default_factory=dict)
    category_amounts: Dict[TransactionCategory, Decimal] = field(default_factory=dict)

    # Confidence breakdown
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0

    # Transaction type breakdown
    credit_count: int = 0
    debit_count: int = 0
    total_credits: Decimal = field(default_factory=lambda: Decimal('0'))
    total_debits: Decimal = field(default_factory=lambda: Decimal('0'))

    @property
    def net_amount(self) -> Decimal:
        """Calculate net amount (credits - debits)."""
        return self.total_credits - self.total_debits

    @property
    def average_confidence(self) -> float:
        """Calculate average confidence level."""
        total = self.high_confidence_count + self.medium_confidence_count + self.low_confidence_count
        if total == 0:
            return 0.0

        weighted_sum = (self.high_confidence_count * 3 +
                       self.medium_confidence_count * 2 +
                       self.low_confidence_count * 1)
        return weighted_sum / (total * 3) * 100  # Convert to percentage