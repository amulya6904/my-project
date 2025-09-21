"""
Gemini AI implementation of transaction categorizer.

This module implements the BaseCategorizer interface using Google's Gemini AI
to categorize bank transactions. It includes batch processing, retry logic,
and optimized prompting for accurate transaction categorization.
"""

import json
import time
import asyncio
from typing import List, Dict, Any, Optional
import logging
from decimal import Decimal

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import retry

from .base_categorizer import BaseCategorizer, APIError, ConfigError, RateLimitError
from .models import (
    Transaction,
    CategorizationResult,
    BatchCategorizationResult,
    CategorizerConfig,
    TransactionCategory,
    ConfidenceLevel
)
from .cache import TransactionCache


class GeminiCategorizer(BaseCategorizer):
    """
    Gemini AI-powered transaction categorizer.

    Uses Google's Gemini models to categorize transactions with high accuracy.
    Supports both single and batch processing with intelligent retry logic.
    """

    def __init__(self, config: CategorizerConfig, cache: Optional[TransactionCache] = None):
        """
        Initialize Gemini categorizer.

        Args:
            config: Configuration with API key and settings
            cache: Optional cache instance for storing results
        """
        self.client: Optional[genai.GenerativeModel] = None
        self.cache = cache
        super().__init__(config)

    def _validate_config(self) -> None:
        """
        Validate Gemini-specific configuration.

        Raises:
            ConfigError: If configuration is invalid
        """
        if not self.config.api_key:
            raise ConfigError("Gemini API key is required")

        if not self.config.model_name:
            raise ConfigError("Model name is required")

        if self.config.temperature < 0 or self.config.temperature > 1:
            raise ConfigError("Temperature must be between 0 and 1")

        if self.config.batch_size <= 0 or self.config.batch_size > 100:
            raise ConfigError("Batch size must be between 1 and 100")

    def _setup_categorizer(self) -> None:
        """Set up Gemini AI client and model."""
        try:
            self.logger.info("[DIAGNOSTIC] Setting up GeminiCategorizer.")
            if self.config.api_key:
                self.logger.info("[DIAGNOSTIC] API key is present.")
            else:
                self.logger.error("[DIAGNOSTIC] API key is MISSING.")

            genai.configure(api_key=self.config.api_key)

            generation_config = GenerationConfig(
                temperature=self.config.temperature,
                top_p=0.95,
                top_k=40,
                max_output_tokens=2048,
                response_mime_type="application/json"
            )

            self.client = genai.GenerativeModel(
                model_name=self.config.model_name,
                generation_config=generation_config
            )

            self.logger.info(f"Initialized Gemini categorizer with model: {self.config.model_name}")

        except Exception as e:
            raise ConfigError(f"Failed to setup Gemini client: {e}") from e

    def _categorize_single_impl(self, transaction: Transaction) -> CategorizationResult:
        """
        Categorize a single transaction using Gemini with caching.

        Args:
            transaction: Transaction to categorize

        Returns:
            CategorizationResult: Categorization result

        Raises:
            APIError: If Gemini API call fails
        """
        # Check cache first
        if self.cache:
            cached_result = self.cache.get_categorization(transaction)
            if cached_result:
                self.logger.debug(f"Cache hit for transaction: {transaction.description}")
                return cached_result

        # Cache miss - call API
        prompt = self._create_single_transaction_prompt(transaction)

        try:
            response = self._call_gemini_with_retry(prompt)
            response_data = self._parse_gemini_response(response)
            result = self._create_result_from_response(transaction, response_data)

            # Store in cache
            if self.cache:
                self.cache.store_categorization(transaction, result)

            return result

        except Exception as e:
            self.logger.error(f"Failed to categorize transaction: {e}")
            if isinstance(e, (APIError, RateLimitError)):
                raise
            raise APIError(f"Unexpected error during categorization: {e}") from e

    def _categorize_batch_impl(self, transactions: List[Transaction]) -> BatchCategorizationResult:
        """
        Categorize multiple transactions in batches using Gemini with caching.

        Args:
            transactions: List of transactions to categorize

        Returns:
            BatchCategorizationResult: Results for all transactions
        """
        self.logger.info("[DIAGNOSTIC] Entering GeminiCategorizer._categorize_batch_impl.")
        start_time = time.time()
        all_results = []
        all_errors = []
        successful = 0
        failed = 0
        cache_hits = 0
        cache_misses = 0
        cache_saves = 0

        # Pre-categorize credits as Income
        debit_transactions = []
        for transaction in transactions:
            if transaction.is_credit:
                result = CategorizationResult(
                    transaction_id=f"{transaction.date}_{transaction.description[:20]}",
                    category=TransactionCategory.INCOME,
                    confidence=ConfidenceLevel.HIGH,
                    reasoning="Transaction is a credit and is categorized as Income."
                )
                all_results.append(result)
                successful += 1
            else:
                debit_transactions.append(transaction)

        # Separate cached and uncached transactions
        uncached_transactions = []
        cached_results = []

        if self.cache:
            for transaction in debit_transactions:
                cached_result = self.cache.get_categorization(transaction)
                if cached_result:
                    cached_results.append(cached_result)
                    cache_hits += 1
                    successful += 1
                else:
                    uncached_transactions.append(transaction)
                    cache_misses += 1
        else:
            self.logger.info("[DIAGNOSTIC] No cache provided.")
            uncached_transactions = debit_transactions
            cache_misses = len(debit_transactions)

        self.logger.info(f"[DIAGNOSTIC] Cache hits: {cache_hits}, Cache misses: {cache_misses}")
        all_results.extend(cached_results)

        # Process uncached transactions in batches
        if uncached_transactions:
            self.logger.info(f"[DIAGNOSTIC] Processing {len(uncached_transactions)} uncached transactions.")
            for i in range(0, len(uncached_transactions), self.config.batch_size):
                batch = uncached_transactions[i:i + self.config.batch_size]
                self.logger.debug(f"Processing batch {i//self.config.batch_size + 1} "
                                 f"({len(batch)} uncached transactions)")

                try:
                    batch_results = self._process_transaction_batch(batch)
                    all_results.extend(batch_results)
                    successful += len(batch_results)

                    # Cache the results
                    if self.cache:
                        for j, result in enumerate(batch_results):
                            if self.cache.store_categorization(batch[j], result):
                                cache_saves += 1

                except Exception as e:
                    self.logger.error(f"Batch {i//self.config.batch_size + 1} failed: {e}")
                    all_errors.append(f"Batch {i//self.config.batch_size + 1}: {str(e)}")
                    failed += len(batch)

                    # If batch processing fails, try individual processing as fallback
                    if self.config.max_retries > 0:
                        self.logger.info("Attempting individual processing as fallback")
                        for transaction in batch:
                            try:
                                result = self._categorize_single_impl(transaction)
                                all_results.append(result)
                                successful += 1
                                failed -= 1
                                if self.cache and self.cache.store_categorization(transaction, result):
                                    cache_saves += 1
                            except Exception as individual_error:
                                self.logger.warning(f"Individual processing also failed: {individual_error}")

        processing_time = time.time() - start_time
        self.logger.info("[DIAGNOSTIC] Exiting GeminiCategorizer._categorize_batch_impl.")

        return BatchCategorizationResult(
            results=all_results,
            total_processed=len(transactions),
            successful=successful,
            failed=failed,
            errors=all_errors,
            processing_time_seconds=processing_time,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_saves=cache_saves
        )

    def _process_transaction_batch(self, transactions: List[Transaction]) -> List[CategorizationResult]:
        """
        Process a batch of transactions with Gemini, including rule-based fallback.

        Args:
            transactions: Batch of transactions

        Returns:
            List[CategorizationResult]: Results for the batch

        Raises:
            APIError: If batch processing fails
        """
        results = []
        ai_needed_transactions = []
        ai_needed_indices = []

        # First pass: use rule-based categorization for obvious cases
        for i, transaction in enumerate(transactions):
            rule_category = self._rule_based_category(transaction)
            if rule_category:
                result = CategorizationResult(
                    transaction_id=f"{transaction.date}_{transaction.description[:20]}",
                    category=rule_category,
                    confidence=ConfidenceLevel.HIGH,
                    reasoning=f"Rule-based categorization based on transaction description"
                )
                results.append(result)
            else:
                # Need AI categorization
                ai_needed_transactions.append(transaction)
                ai_needed_indices.append(i)
                results.append(None)  # Placeholder

        self.logger.info(f"Rule-based categorization handled {len(transactions) - len(ai_needed_transactions)} transactions")

        # Second pass: AI categorization for remaining transactions
        if ai_needed_transactions:
            try:
                prompt = self._create_batch_transaction_prompt(ai_needed_transactions)
                response = self._call_gemini_with_retry(prompt)
                response_data = self._parse_batch_response(response)
                ai_results = self._create_batch_results(ai_needed_transactions, response_data)

                # Insert AI results back into the correct positions
                for idx, ai_result in enumerate(ai_results):
                    original_idx = ai_needed_indices[idx]
                    results[original_idx] = ai_result

            except Exception as e:
                self.logger.warning(f"AI categorization failed, using fallback: {e}")
                # Fallback to "Others" for AI failures
                for idx in ai_needed_indices:
                    if results[idx] is None:
                        results[idx] = CategorizationResult(
                            transaction_id=f"{transactions[idx].date}_{transactions[idx].description[:20]}",
                            category=TransactionCategory.OTHER,
                            confidence=ConfidenceLevel.LOW,
                            reasoning="AI categorization failed, using fallback"
                        )

        return [r for r in results if r is not None]

    def _rule_based_category(self, transaction: Transaction) -> Optional[TransactionCategory]:
        """
        Apply rule-based categorization for common merchants and patterns.

        Args:
            transaction: Transaction to categorize

        Returns:
            TransactionCategory or None if no rule matches
        """
        description = transaction.description.lower()
        self.logger.info(f"[RULE-BASED] Checking: '{transaction.description}' → '{description}'")

        # Dining patterns
        dining_keywords = ['swiggy', 'zomato', 'restaurant', 'cafe', 'food', 'pizza', 'burger',
                          'dominos', 'kfc', 'mcdonals', 'subway', 'starbucks', 'chai', 'biryani']
        matched_dining = [kw for kw in dining_keywords if kw in description]
        if matched_dining:
            self.logger.info(f"[RULE-BASED] ✓ DINING match: {matched_dining}")
            return TransactionCategory.DINING

        # Transportation patterns
        transport_keywords = ['uber', 'ola', 'fuel', 'petrol', 'diesel', 'cab', 'taxi', 'metro',
                             'bus', 'train', 'flight', 'airline', 'parking', 'toll']
        matched_transport = [kw for kw in transport_keywords if kw in description]
        if matched_transport:
            self.logger.info(f"[RULE-BASED] ✓ TRANSPORTATION match: {matched_transport}")
            return TransactionCategory.TRANSPORTATION

        # Rent patterns
        rent_keywords = ['rent', 'lease', 'housing', 'flat', 'apartment', 'property']
        matched_rent = [kw for kw in rent_keywords if kw in description]
        if matched_rent:
            self.logger.info(f"[RULE-BASED] ✓ RENT match: {matched_rent}")
            return TransactionCategory.RENT

        # Shopping patterns
        shopping_keywords = ['amazon', 'flipkart', 'myntra', 'ajio', 'nykaa', 'shopping', 'mall',
                           'store', 'market', 'retail', 'fashion', 'clothing', 'electronics']
        matched_shopping = [kw for kw in shopping_keywords if kw in description]
        if matched_shopping:
            self.logger.info(f"[RULE-BASED] ✓ SHOPPING match: {matched_shopping}")
            return TransactionCategory.SHOPPING

        # Entertainment patterns
        entertainment_keywords = ['netflix', 'prime', 'spotify', 'hotstar', 'movie', 'cinema',
                                'theatre', 'game', 'entertainment', 'youtube', 'subscription']
        matched_entertainment = [kw for kw in entertainment_keywords if kw in description]
        if matched_entertainment:
            self.logger.info(f"[RULE-BASED] ✓ ENTERTAINMENT match: {matched_entertainment}")
            return TransactionCategory.ENTERTAINMENT

        # Groceries patterns
        grocery_keywords = ['grocery', 'supermarket', 'bigbasket', 'grofers', 'blinkit', 'dunzo',
                           'vegetables', 'fruits', 'milk', 'bread', 'rice', 'dal']
        matched_grocery = [kw for kw in grocery_keywords if kw in description]
        if matched_grocery:
            self.logger.info(f"[RULE-BASED] ✓ GROCERIES match: {matched_grocery}")
            return TransactionCategory.GROCERIES

        # Utilities patterns
        utility_keywords = ['electricity', 'water', 'gas', 'internet', 'broadband', 'mobile',
                          'phone', 'telecom', 'utility', 'bill', 'recharge']
        matched_utility = [kw for kw in utility_keywords if kw in description]
        if matched_utility:
            self.logger.info(f"[RULE-BASED] ✓ UTILITIES match: {matched_utility}")
            return TransactionCategory.UTILITIES

        # Health patterns
        health_keywords = ['pharmacy', 'medical', 'hospital', 'doctor', 'clinic', 'medicine',
                          'health', 'apollo', 'medplus', '1mg', 'netmeds']
        matched_health = [kw for kw in health_keywords if kw in description]
        if matched_health:
            self.logger.info(f"[RULE-BASED] ✓ HEALTH match: {matched_health}")
            return TransactionCategory.HEALTH

        self.logger.info(f"[RULE-BASED] ✗ No rule match found for: '{description}'")
        return None

    def _create_single_transaction_prompt(self, transaction: Transaction) -> str:
        """Create an optimized prompt for single transaction categorization."""

        prompt = f"""Categorize this Indian bank transaction into EXACTLY one category:

**CATEGORIES:**
Dining, Transportation, Shopping, Entertainment, Rent, Groceries, Utilities, Health, Income, Other

**TRANSACTION:**
- Description: "{transaction.description}"
- Amount: ₹{abs(transaction.amount)}
- Direction: {'Credit' if transaction.is_credit else 'Debit'}
- Type: {transaction.transaction_type.value}

**RULES:**
- Credits → "Income"
- Debits → appropriate expense category
- Look for merchant names/keywords

Return JSON:
{{
  "category": "exact category name",
  "confidence": "HIGH|MEDIUM|LOW",
  "reasoning": "brief explanation"
}}"""
        return prompt.strip()

    def _create_batch_transaction_prompt(self, transactions: List[Transaction]) -> str:
        """Create an optimized prompt for batch transaction categorization."""
        self.logger.info("[DIAGNOSTIC] Creating batch transaction prompt.")

        transaction_list = []
        for i, txn in enumerate(transactions):
            transaction_list.append(f"""
  {{
    "id": {i},
    "date": "{txn.date.strftime('%Y-%m-%d')}",
    "description": "{txn.description}",
    "amount": {abs(txn.amount)},
    "type": "{txn.transaction_type.value}",
    "direction": "{'Credit' if txn.is_credit else 'Debit'}",
    "counterparty": "{txn.counterparty or 'Unknown'}"
  }}""")

        prompt = f"""You are an expert at categorizing Indian bank transactions. Analyze each transaction and categorize it EXACTLY into one of these categories:

**CATEGORIES (use exact spelling):**
- Dining (restaurants, food delivery, cafes)
- Transportation (uber, ola, fuel, flights, metro)
- Shopping (amazon, flipkart, retail stores, clothing)
- Entertainment (netflix, movies, games, streaming)
- Rent (housing payments, property rent)
- Groceries (supermarkets, grocery stores, food items)
- Utilities (electricity, internet, phone bills, recharge)
- Health (pharmacy, hospitals, medical expenses)
- Income (ALL credit transactions - salary, transfers IN)
- Other (anything that doesn't fit above categories)

**RULES:**
1. Credits (money IN) → "Income" category ALWAYS
2. Debits (money OUT) → appropriate expense category
3. Look for merchant names, keywords in description
4. Return JSON array with id, category, confidence, reasoning

**EXAMPLES:**
```json
[
  {{"id": 0, "category": "Dining", "confidence": "HIGH", "reasoning": "Zomato is a food delivery service"}},
  {{"id": 1, "category": "Income", "confidence": "HIGH", "reasoning": "Credit transaction categorized as Income"}},
  {{"id": 2, "category": "Transportation", "confidence": "HIGH", "reasoning": "Uber ride service payment"}}
]
```

**TRANSACTIONS TO CATEGORIZE:**
```json
[{','.join(transaction_list)}]
```

Return ONLY the JSON array (no markdown, no explanations):"""

        self.logger.debug(f"[DIAGNOSTIC] Full prompt:\n{prompt}")
        return prompt.strip()

    def _call_gemini_with_retry(self, prompt: str) -> str:
        """
        Call Gemini API with exponential backoff retry.

        Args:
            prompt: The prompt to send

        Returns:
            str: The response text

        Raises:
            APIError: If all retries fail
            RateLimitError: If rate limits are consistently hit
        """
        self.logger.info("[AI-CATEGORIZATION] Calling Gemini API...")
        self.logger.debug(f"[AI-CATEGORIZATION] Prompt sent:\n{prompt}")
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.generate_content(prompt)

                if not response or not response.text:
                    self.logger.error("[AI-CATEGORIZATION] ✗ Empty response from Gemini")
                    raise APIError("Empty response from Gemini")

                self.logger.info(f"[AI-CATEGORIZATION] ✓ Raw response from Gemini:\n{response.text}")
                return response.text.strip()

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check for rate limiting
                if 'quota' in error_str or 'rate limit' in error_str:
                    if attempt == self.config.max_retries:
                        raise RateLimitError("Rate limit exceeded") from e
                    else:
                        # Exponential backoff for rate limits
                        delay = self.config.retry_delay * (2 ** attempt)
                        self.logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue

                # Check for other recoverable errors
                if any(term in error_str for term in ['timeout', 'connection', 'network']):
                    if attempt < self.config.max_retries:
                        delay = self.config.retry_delay * (1.5 ** attempt)
                        self.logger.warning(f"Network error, retrying in {delay}s (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue

                # Non-recoverable error
                raise APIError(f"Gemini API error: {e}") from e

        # All retries exhausted
        raise APIError(f"All retries exhausted. Last error: {last_exception}") from last_exception

    def _parse_gemini_response(self, response: str) -> Dict[str, Any]:
        """
        Parse Gemini's JSON response.

        Args:
            response: Raw response from Gemini

        Returns:
            Dict[str, Any]: Parsed response

        Raises:
            APIError: If response cannot be parsed
        """
        try:
            # Clean up response (remove markdown code blocks if present)
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]

            return json.loads(cleaned_response.strip())

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Gemini response: {response}")
            raise APIError(f"Invalid JSON response from Gemini: {e}") from e

    def _parse_batch_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse Gemini's batch JSON response.

        Args:
            response: Raw batch response from Gemini

        Returns:
            List[Dict[str, Any]]: Parsed response array

        Raises:
            APIError: If response cannot be parsed
        """
        self.logger.info("[DIAGNOSTIC] Parsing batch response.")
        try:
            # Clean up response
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            self.logger.debug(f"[DIAGNOSTIC] Cleaned response for parsing:\n{cleaned_response}")
            parsed = json.loads(cleaned_response.strip())

            if not isinstance(parsed, list):
                raise APIError("Batch response must be a JSON array")

            return parsed

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse batch response: {response}")
            raise APIError(f"Invalid batch JSON response from Gemini: {e}") from e

    def _create_batch_results(
        self,
        transactions: List[Transaction],
        response_data: List[Dict[str, Any]]
    ) -> List[CategorizationResult]:
        """
        Create results from batch response data.

        Args:
            transactions: Original transactions
            response_data: Parsed batch response

        Returns:
            List[CategorizationResult]: Results for each transaction
        """
        results = []

        for i, transaction in enumerate(transactions):
            try:
                # Find matching response by ID
                txn_response = None
                for resp in response_data:
                    if resp.get('id') == i:
                        txn_response = resp
                        break

                if txn_response is None:
                    self.logger.warning(f"No response found for transaction {i}")
                    # Create a default result
                    results.append(CategorizationResult(
                        transaction_id=f"{transaction.date}_{transaction.description[:20]}",
                        category=TransactionCategory.OTHER,
                        confidence=ConfidenceLevel.LOW,
                        reasoning="No categorization response received"
                    ))
                    continue

                result = self._create_result_from_response(transaction, txn_response)
                results.append(result)

            except Exception as e:
                self.logger.warning(f"Failed to create result for transaction {i}: {e}")
                results.append(CategorizationResult(
                    transaction_id=f"{transaction.date}_{transaction.description[:20]}",
                    category=TransactionCategory.OTHER,
                    confidence=ConfidenceLevel.LOW,
                    reasoning=f"Error processing response: {str(e)}"
                ))

        return results

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check including API connectivity.

        Returns:
            Dict[str, Any]: Health check results
        """
        base_health = super().health_check()

        try:
            # Test API with a simple request
            test_response = self.client.generate_content(
                "Respond with a single word: 'healthy'"
            )

            api_accessible = bool(test_response and test_response.text)
            api_response_time = 1.0  # Simplified for this implementation

            base_health.update({
                'api_accessible': api_accessible,
                'api_response_time': api_response_time,
                'model_name': self.config.model_name,
                'batch_size': self.config.batch_size
            })

        except Exception as e:
            self.logger.warning(f"API health check failed: {e}")
            base_health.update({
                'api_accessible': False,
                'api_error': str(e)
            })

        return base_health