"""
Mock categorizer for testing and dry-run purposes.

This module provides a rule-based categorizer that does not require an API key
or network access, making it ideal for testing the analysis pipeline.
"""

import re
from typing import List

from .base_categorizer import BaseCategorizer, CategorizationResult, BatchCategorizationResult, ConfigError
from .models import Transaction, TransactionCategory, ConfidenceLevel, CategorizerConfig


class MockCategorizer(BaseCategorizer):
    """
    A mock transaction categorizer for testing and demonstration.

    This categorizer uses a simple set of hardcoded rules to assign categories
    based on keywords in the transaction description. It does not make any

    network calls and requires no API key.
    """

    def __init__(self, config: CategorizerConfig):
        """Initialize the mock categorizer."""
        # Define simple rules using new consistent categories
        self.rules = {
            r"swiggy|zomato|restaurant|food|pizza|burger|dining": TransactionCategory.DINING,
            r"amazon|flipkart|shopping|store|mall|retail": TransactionCategory.SHOPPING,
            r"uber|ola|taxi|travel|fuel|petrol|metro|bus": TransactionCategory.TRANSPORTATION,
            r"rent|lease|housing|property|mortgage": TransactionCategory.RENT,
            r"salary|interest received|credit|income": TransactionCategory.INCOME,
            r"movie|netflix|spotify|entertainment|cinema|theatre": TransactionCategory.ENTERTAINMENT,
            r"grocery|supermarket|vegetables|milk|bigbasket": TransactionCategory.GROCERIES,
            r"electricity|water|internet|mobile|phone|utility|bill": TransactionCategory.UTILITIES,
            r"pharmacy|medical|hospital|doctor|health": TransactionCategory.HEALTH,
        }
        super().__init__(config)

    def _validate_config(self) -> None:
        """Validate configuration (no-op for mock)."""
        self.logger.info("MockCategorizer: No configuration to validate.")

    def _setup_categorizer(self) -> None:
        """Set up categorizer (no-op for mock)."""
        self.logger.info("MockCategorizer is ready.")

    def _categorize_single_impl(self, transaction: Transaction) -> CategorizationResult:
        """Categorize a single transaction based on rules."""
        description = transaction.description.lower()

        for pattern, category in self.rules.items():
            if re.search(pattern, description):
                return CategorizationResult(
                    transaction_id=f"{transaction.date}_{transaction.description[:20]}",
                    category=category,
                    confidence=ConfidenceLevel.HIGH,
                    reasoning=f"Matched rule: '{pattern}'"
                )

        # Default fallback
        return CategorizationResult(
            transaction_id=f"{transaction.date}_{transaction.description[:20]}",
            category=TransactionCategory.OTHER,
            confidence=ConfidenceLevel.LOW,
            reasoning="No specific rule matched."
        )

    def _categorize_batch_impl(self, transactions: List[Transaction]) -> BatchCategorizationResult:
        """Categorize a batch of transactions using the single implementation."""
        results = [self._categorize_single_impl(txn) for txn in transactions]
        
        return BatchCategorizationResult(
            results=results,
            total_processed=len(transactions),
            successful=len(transactions),
            failed=0
        )

    def health_check(self) -> dict:
        """Perform a health check."""
        return {
            'status': 'healthy',
            'provider': 'mock',
            'api_accessible': True, # Always accessible
        }
