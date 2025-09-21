"""
Abstract base class for transaction categorizers.

This module defines the interface that all transaction categorizers must implement,
providing a consistent API for categorizing transactions regardless of the
underlying LLM or service being used.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .models import (
    Transaction,
    CategorizationResult,
    BatchCategorizationResult,
    CategorizerConfig,
    TransactionCategory,
    ConfidenceLevel
)


class CategorizationError(Exception):
    """Base exception for categorization errors."""
    pass


class APIError(CategorizationError):
    """Raised when there's an error with the LLM API."""
    pass


class ConfigError(CategorizationError):
    """Raised when there's an error with categorizer configuration."""
    pass


class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""
    pass


class BaseCategorizer(ABC):
    """
    Abstract base class for transaction categorizers.

    This class defines the interface that all categorizer implementations
    must follow, ensuring consistency across different LLM providers.

    Subclasses must implement:
    - _categorize_single_impl: Core logic for categorizing one transaction
    - _categorize_batch_impl: Core logic for categorizing multiple transactions
    - _validate_config: Configuration validation logic
    """

    def __init__(self, config: CategorizerConfig):
        """
        Initialize the categorizer with configuration.

        Args:
            config: Configuration object containing API keys and settings

        Raises:
            ConfigError: If configuration is invalid
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._validate_config()
        self._setup_categorizer()

    @abstractmethod
    def _validate_config(self) -> None:
        """
        Validate the configuration.

        Raises:
            ConfigError: If configuration is invalid
        """
        pass

    @abstractmethod
    def _setup_categorizer(self) -> None:
        """
        Set up the categorizer (e.g., initialize API client).

        This method is called after configuration validation.
        """
        pass

    def categorize_single(self, transaction: Transaction) -> CategorizationResult:
        """
        Categorize a single transaction.

        Args:
            transaction: Transaction to categorize

        Returns:
            CategorizationResult: The categorization result

        Raises:
            CategorizationError: If categorization fails
        """
        try:
            self.logger.debug(f"Categorizing transaction: {transaction.description}")
            result = self._categorize_single_impl(transaction)
            self.logger.debug(f"Categorized as: {result.category.value} "
                             f"(confidence: {result.confidence.value})")
            return result

        except Exception as e:
            self.logger.error(f"Failed to categorize transaction: {e}")
            if isinstance(e, CategorizationError):
                raise
            raise CategorizationError(f"Unexpected error during categorization: {e}") from e

    def categorize_batch(self, transactions: List[Transaction]) -> BatchCategorizationResult:
        """
        Categorize a batch of transactions.

        Args:
            transactions: List of transactions to categorize

        Returns:
            BatchCategorizationResult: Results for all transactions

        Raises:
            CategorizationError: If batch processing fails entirely
        """
        if not transactions:
            return BatchCategorizationResult(
                results=[],
                total_processed=0,
                successful=0,
                failed=0
            )

        self.logger.info(f"Processing batch of {len(transactions)} transactions")

        try:
            # Use batch implementation if available, otherwise process individually
            if hasattr(self, '_categorize_batch_impl'):
                return self._categorize_batch_impl(transactions)
            else:
                return self._process_batch_individually(transactions)

        except Exception as e:
            self.logger.error(f"Batch categorization failed: {e}")
            if isinstance(e, CategorizationError):
                raise
            raise CategorizationError(f"Batch processing failed: {e}") from e

    def _process_batch_individually(self, transactions: List[Transaction]) -> BatchCategorizationResult:
        """
        Process transactions individually when no batch implementation exists.

        Args:
            transactions: List of transactions to process

        Returns:
            BatchCategorizationResult: Combined results
        """
        results = []
        errors = []
        successful = 0
        failed = 0

        for i, transaction in enumerate(transactions):
            try:
                result = self._categorize_single_impl(transaction)
                results.append(result)
                successful += 1
            except Exception as e:
                self.logger.warning(f"Failed to categorize transaction {i}: {e}")
                errors.append(f"Transaction {i}: {str(e)}")
                failed += 1

        return BatchCategorizationResult(
            results=results,
            total_processed=len(transactions),
            successful=successful,
            failed=failed,
            errors=errors
        )

    @abstractmethod
    def _categorize_single_impl(self, transaction: Transaction) -> CategorizationResult:
        """
        Implementation-specific logic for categorizing a single transaction.

        Args:
            transaction: Transaction to categorize

        Returns:
            CategorizationResult: The categorization result

        Raises:
            CategorizationError: If categorization fails
        """
        pass

    def _categorize_batch_impl(self, transactions: List[Transaction]) -> BatchCategorizationResult:
        """
        Implementation-specific logic for batch categorization.

        This method is optional. If not implemented, transactions will be
        processed individually.

        Args:
            transactions: List of transactions to categorize

        Returns:
            BatchCategorizationResult: Results for all transactions

        Raises:
            CategorizationError: If batch processing fails
        """
        return self._process_batch_individually(transactions)

    def get_available_categories(self) -> List[TransactionCategory]:
        """
        Get the list of available categories.

        Returns:
            List[TransactionCategory]: Available categories
        """
        if self.config.use_custom_categories and self.config.custom_categories:
            # Map custom category strings to enum values if possible
            categories = []
            for cat_name in self.config.custom_categories:
                try:
                    category = TransactionCategory(cat_name)
                    categories.append(category)
                except ValueError:
                    self.logger.warning(f"Unknown category: {cat_name}")
            return categories
        else:
            return list(TransactionCategory)

    def _create_categorization_prompt(self, transaction: Transaction) -> str:
        """
        Create a prompt for categorizing a transaction.

        Args:
            transaction: Transaction to create prompt for

        Returns:
            str: The categorization prompt
        """
        categories = self.get_available_categories()
        category_list = ", ".join([cat.value for cat in categories])

        prompt = f"""
Categorize the following bank transaction:

Transaction Details:
- Date: {transaction.date.strftime('%Y-%m-%d')}
- Description: {transaction.description}
- Amount: {transaction.amount}
- Type: {transaction.transaction_type.value}
- Counterparty: {transaction.counterparty or 'Unknown'}

Available Categories: {category_list}

Please respond with a JSON object containing:
- category: The most appropriate category from the available categories
- confidence: HIGH, MEDIUM, or LOW
- reasoning: Brief explanation of why this category was chosen
"""

        if self.config.include_alternatives:
            prompt += "- alternatives: Up to 2 alternative categories (optional)\n"

        if self.config.include_reasoning:
            prompt += "\nProvide clear reasoning based on the transaction description and amount."

        return prompt.strip()

    def _parse_category_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response into a structured format.

        Args:
            response: Raw response from LLM

        Returns:
            Dict[str, Any]: Parsed response

        Raises:
            CategorizationError: If response cannot be parsed
        """
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                # Fallback: try to parse the entire response as JSON
                return json.loads(response)

        except json.JSONDecodeError as e:
            raise CategorizationError(f"Failed to parse LLM response: {e}") from e

    def _create_result_from_response(
        self,
        transaction: Transaction,
        response_data: Dict[str, Any]
    ) -> CategorizationResult:
        """
        Create a CategorizationResult from parsed response data.

        Args:
            transaction: Original transaction
            response_data: Parsed response from LLM

        Returns:
            CategorizationResult: Structured result

        Raises:
            CategorizationError: If response data is invalid
        """
        try:
            # Parse category
            category_str = response_data.get('category', '').strip()
            try:
                category = TransactionCategory(category_str)
            except ValueError:
                self.logger.warning(f"Unknown category '{category_str}', using OTHER")
                category = TransactionCategory.OTHER

            # Parse confidence
            confidence_str = response_data.get('confidence', 'LOW').upper()
            try:
                confidence = ConfidenceLevel(confidence_str)
            except ValueError:
                self.logger.warning(f"Unknown confidence '{confidence_str}', using LOW")
                confidence = ConfidenceLevel.LOW

            # Get reasoning
            reasoning = response_data.get('reasoning', 'No reasoning provided')

            # Parse alternatives if present
            alternatives = []
            if 'alternatives' in response_data:
                for alt_str in response_data['alternatives']:
                    try:
                        alt_category = TransactionCategory(alt_str)
                        alternatives.append(alt_category)
                    except ValueError:
                        self.logger.warning(f"Unknown alternative category: {alt_str}")

            return CategorizationResult(
                transaction_id=f"{transaction.date}_{transaction.description[:20]}",
                category=category,
                confidence=confidence,
                reasoning=reasoning,
                alternative_categories=alternatives
            )

        except KeyError as e:
            raise CategorizationError(f"Missing required field in response: {e}") from e
        except Exception as e:
            raise CategorizationError(f"Failed to create result: {e}") from e

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the categorizer.

        Returns:
            Dict[str, Any]: Health check results
        """
        return {
            'status': 'healthy',
            'config_valid': True,
            'api_accessible': True,  # Override in subclasses
            'categories_count': len(self.get_available_categories())
        }