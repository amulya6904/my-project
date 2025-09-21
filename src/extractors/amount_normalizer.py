"""Amount parsing and normalization utilities."""

import re
from typing import Optional, Tuple, Union
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from enum import Enum


class AmountType(Enum):
    """Types of amount values."""
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    BALANCE = "BALANCE"


class CurrencyType(Enum):
    """Supported currency types."""
    INR = "INR"
    USD = "USD"
    EUR = "EUR"


class AmountParsingError(Exception):
    """Raised when amount cannot be parsed."""
    pass


class AmountNormalizer:
    """Utility class for parsing and normalizing monetary amounts."""
    
    # Currency symbols mapping
    CURRENCY_SYMBOLS = {
        '₹': CurrencyType.INR,
        'Rs': CurrencyType.INR,
        'INR': CurrencyType.INR,
        '$': CurrencyType.USD,
        'USD': CurrencyType.USD,
        '€': CurrencyType.EUR,
        'EUR': CurrencyType.EUR,
    }
    
    # Amount patterns for different formats
    AMOUNT_PATTERNS = {
        # Indian format: 1,23,456.78 or 12,34,567.89
        'indian_comma': r'(\d{1,3}(?:,\d{2})*(?:,\d{3})*(?:\.\d{1,2})?)',
        
        # Western format: 1,234,567.89
        'western_comma': r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)',
        
        # Simple format: 1234567.89 or 1234567
        'simple': r'(\d+(?:\.\d{1,2})?)',
        
        # Scientific notation: 1.23E+06
        'scientific': r'(\d+\.?\d*[eE][+-]?\d+)',
    }
    
    # Credit/Debit indicators
    CREDIT_INDICATORS = ['cr', 'credit', '+', 'deposit']
    DEBIT_INDICATORS = ['dr', 'debit', '-', 'withdrawal', 'wd']
    
    @classmethod
    def parse_amount(cls, amount_str: str, amount_type: AmountType = AmountType.CREDIT) -> Optional[float]:
        """Parse amount string to float.
        
        Args:
            amount_str: Amount string to parse
            amount_type: Type of amount for context
            
        Returns:
            Float amount or None if cannot be parsed
            
        Raises:
            AmountParsingError: If amount format is invalid
        """
        if not amount_str or not isinstance(amount_str, str):
            return None
        
        try:
            # Clean the amount string
            cleaned_amount = cls._clean_amount_string(amount_str)
            
            if not cleaned_amount:
                return None
            
            # Try to extract amount using different patterns
            parsed_amount = cls._extract_numeric_amount(cleaned_amount)
            
            if parsed_amount is None:
                return None
            
            # Handle credit/debit indicators
            is_negative = cls._has_debit_indicator(amount_str)
            
            if is_negative and amount_type != AmountType.BALANCE:
                parsed_amount = -abs(parsed_amount)
            
            return float(parsed_amount)
            
        except Exception as e:
            if amount_str.strip():  # Only raise error for non-empty strings
                raise AmountParsingError(f"Cannot parse amount '{amount_str}': {str(e)}") from e
            return None
    
    @classmethod
    def parse_balance_with_indicator(cls, balance_str: str) -> Tuple[Optional[float], bool]:
        """Parse balance string with Cr/Dr indicator.
        
        Args:
            balance_str: Balance string with potential Cr/Dr suffix
            
        Returns:
            Tuple of (amount, is_credit) where is_credit indicates if balance is credit
        """
        if not balance_str:
            return None, True
        
        # Check for credit/debit indicators
        is_credit = not cls._has_debit_indicator(balance_str)
        
        # Parse the numeric amount
        amount = cls.parse_amount(balance_str, AmountType.BALANCE)
        
        if amount is not None:
            # Make amount positive and let the indicator determine sign
            amount = abs(amount)
            if not is_credit:
                amount = -amount
        
        return amount, is_credit
    
    @classmethod
    def _clean_amount_string(cls, amount_str: str) -> str:
        """Clean amount string by removing unnecessary characters.
        
        Args:
            amount_str: Raw amount string
            
        Returns:
            Cleaned amount string
        """
        # Remove leading/trailing whitespace
        cleaned = amount_str.strip()
        
        # Remove currency symbols (keep for pattern matching)
        for symbol in cls.CURRENCY_SYMBOLS.keys():
            cleaned = cleaned.replace(symbol, ' ')
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Remove parentheses (sometimes used for negative amounts)
        cleaned = cleaned.replace('(', '').replace(')', '')
        
        return cleaned
    
    @classmethod
    def _extract_numeric_amount(cls, cleaned_str: str) -> Optional[Decimal]:
        """Extract numeric amount from cleaned string.
        
        Args:
            cleaned_str: Cleaned amount string
            
        Returns:
            Decimal amount or None if cannot be extracted
        """
        # Try each pattern in order of preference
        for pattern_name, pattern in cls.AMOUNT_PATTERNS.items():
            matches = re.findall(pattern, cleaned_str)
            
            if matches:
                # Take the first (usually largest) match
                amount_match = matches[0]
                
                try:
                    # Convert to decimal
                    if pattern_name in ['indian_comma', 'western_comma']:
                        # Remove commas
                        numeric_str = amount_match.replace(',', '')
                    else:
                        numeric_str = amount_match
                    
                    # Handle scientific notation
                    if pattern_name == 'scientific':
                        return Decimal(float(numeric_str))
                    
                    return Decimal(numeric_str)
                    
                except (DecimalException, ValueError):
                    continue
        
        return None
    
    @classmethod
    def _has_debit_indicator(cls, amount_str: str) -> bool:
        """Check if amount string has debit indicators.
        
        Args:
            amount_str: Amount string to check
            
        Returns:
            True if has debit indicators
        """
        amount_lower = amount_str.lower().strip()
        
        # Check for explicit debit indicators
        for indicator in cls.DEBIT_INDICATORS:
            if indicator in amount_lower:
                return True
        
        # Check if amount is in parentheses (accounting notation for negative)
        if amount_str.strip().startswith('(') and amount_str.strip().endswith(')'):
            return True
        
        # Check for minus sign
        if '-' in amount_str and amount_str.strip().startswith('-'):
            return True
        
        return False
    
    @classmethod
    def format_amount(cls, amount: Union[float, Decimal], currency: CurrencyType = CurrencyType.INR, 
                     decimal_places: int = 2) -> str:
        """Format amount for display.
        
        Args:
            amount: Amount to format
            currency: Currency type
            decimal_places: Number of decimal places
            
        Returns:
            Formatted amount string
        """
        if amount is None:
            return ""
        
        # Convert to Decimal for precise formatting
        if isinstance(amount, float):
            decimal_amount = Decimal(str(amount))
        else:
            decimal_amount = amount
        
        # Round to specified decimal places
        decimal_amount = decimal_amount.quantize(
            Decimal('0.' + '0' * decimal_places), 
            rounding=ROUND_HALF_UP
        )
        
        # Format with commas
        formatted = f"{decimal_amount:,.{decimal_places}f}"
        
        # Add currency symbol
        currency_symbol = cls._get_currency_symbol(currency)
        
        if currency == CurrencyType.INR:
            return f"₹{formatted}"
        else:
            return f"{currency_symbol}{formatted}"
    
    @classmethod
    def _get_currency_symbol(cls, currency: CurrencyType) -> str:
        """Get currency symbol for given currency type.
        
        Args:
            currency: Currency type
            
        Returns:
            Currency symbol
        """
        symbol_map = {
            CurrencyType.INR: '₹',
            CurrencyType.USD: '$',
            CurrencyType.EUR: '€',
        }
        return symbol_map.get(currency, '')
    
    @classmethod
    def validate_amount_range(cls, amount: float, min_amount: float = 0.01, 
                            max_amount: float = 10_00_00_000.00) -> bool:
        """Validate if amount is within reasonable range.
        
        Args:
            amount: Amount to validate
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount
            
        Returns:
            True if amount is valid
        """
        if amount is None:
            return False
        
        abs_amount = abs(amount)
        return min_amount <= abs_amount <= max_amount
    
    @classmethod
    def normalize_indian_amount(cls, amount_str: str) -> Optional[float]:
        """Specifically handle Indian banking amount formats.
        
        Args:
            amount_str: Amount string in Indian format
            
        Returns:
            Normalized float amount
        """
        if not amount_str:
            return None
        
        # Handle Indian lakhs and crores notation
        amount_lower = amount_str.lower().strip()
        
        # Check for lakh notation
        if 'lakh' in amount_lower or 'lac' in amount_lower:
            numeric_part = re.search(r'([\d,.]+)', amount_str)
            if numeric_part:
                base_amount = cls.parse_amount(numeric_part.group(1))
                if base_amount is not None:
                    return base_amount * 100000  # 1 lakh = 100,000
        
        # Check for crore notation
        if 'crore' in amount_lower or 'cr' in amount_lower:
            numeric_part = re.search(r'([\d,.]+)', amount_str)
            if numeric_part:
                base_amount = cls.parse_amount(numeric_part.group(1))
                if base_amount is not None:
                    return base_amount * 10000000  # 1 crore = 10,000,000
        
        # Regular amount parsing
        return cls.parse_amount(amount_str)
    
    @classmethod
    def detect_currency(cls, amount_str: str) -> CurrencyType:
        """Detect currency from amount string.
        
        Args:
            amount_str: Amount string containing currency indicators
            
        Returns:
            Detected currency type, defaults to INR
        """
        if not amount_str:
            return CurrencyType.INR
        
        amount_upper = amount_str.upper()
        
        for symbol, currency in cls.CURRENCY_SYMBOLS.items():
            if symbol.upper() in amount_upper:
                return currency
        
        # Default to INR for Indian banking context
        return CurrencyType.INR