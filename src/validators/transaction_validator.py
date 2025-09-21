"""Transaction data validation utilities."""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..parsers.base_parser import Transaction, TransactionType


class ValidationLevel(Enum):
    """Validation strictness levels."""
    STRICT = "strict"      # Fail on any validation error
    MODERATE = "moderate"  # Allow minor issues, flag major ones
    LENIENT = "lenient"    # Accept most data, only flag critical errors


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    CRITICAL = "critical"  # Transaction should be rejected
    WARNING = "warning"    # Transaction has issues but can be processed
    INFO = "info"          # Minor issues or suggestions


@dataclass
class ValidationIssue:
    """Represents a validation issue found in transaction data."""
    field: str
    severity: ValidationSeverity
    message: str
    suggested_fix: Optional[str] = None
    original_value: Any = None
    suggested_value: Any = None


@dataclass
class ValidationResult:
    """Result of transaction validation."""
    is_valid: bool
    issues: List[ValidationIssue]
    corrected_transaction: Optional[Transaction] = None
    
    @property
    def has_critical_issues(self) -> bool:
        """Check if validation result has critical issues."""
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation result has warnings."""
        return any(issue.severity == ValidationSeverity.WARNING for issue in self.issues)


class TransactionValidator:
    """Validator for transaction data integrity and consistency."""
    
    # Validation rules configuration
    MIN_AMOUNT = 0.01
    MAX_AMOUNT = 10_00_00_000.00  # 10 crores
    MIN_BALANCE = -50_00_000.00   # -50 lakhs (reasonable overdraft limit)
    MAX_BALANCE = 100_00_00_000.00  # 100 crores
    
    # Date range validation (transactions shouldn't be too old or future)
    MAX_TRANSACTION_AGE_DAYS = 365 * 10  # 10 years
    MAX_FUTURE_DAYS = 1  # 1 day in future allowed
    
    # Description validation
    MIN_DESCRIPTION_LENGTH = 3
    MAX_DESCRIPTION_LENGTH = 200
    
    # Reference number patterns
    VALID_REFERENCE_PATTERNS = [
        r'^[A-Z0-9]{6,20}$',  # Alphanumeric reference
        r'^\d{6,15}$',        # Numeric reference
        r'^UPI\d{10,}$',      # UPI reference
        r'^CHQ\d{6,}$',       # Cheque reference
    ]
    
    @classmethod
    def validate_transaction(cls, transaction: Transaction, 
                           validation_level: ValidationLevel = ValidationLevel.MODERATE,
                           context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a single transaction.
        
        Args:
            transaction: Transaction to validate
            validation_level: Strictness level for validation
            context: Additional context for validation (e.g., previous balance)
            
        Returns:
            ValidationResult containing validation outcome and issues
        """
        issues = []
        corrected_transaction = None
        
        # Validate each field
        issues.extend(cls._validate_date(transaction.date, validation_level))
        issues.extend(cls._validate_description(transaction.description, validation_level))
        issues.extend(cls._validate_amounts(transaction, validation_level))
        issues.extend(cls._validate_balance(transaction.balance, validation_level))
        issues.extend(cls._validate_reference(transaction.reference, validation_level))
        issues.extend(cls._validate_transaction_type(transaction.transaction_type, validation_level))
        issues.extend(cls._validate_counterparty(transaction.counterparty, validation_level))
        issues.extend(cls._validate_bank_info(transaction, validation_level))
        
        # Cross-field validation
        issues.extend(cls._validate_amount_consistency(transaction, validation_level))
        
        # Context-based validation
        if context:
            issues.extend(cls._validate_with_context(transaction, context, validation_level))
        
        # Determine if transaction is valid based on validation level
        is_valid = cls._determine_validity(issues, validation_level)
        
        # Create corrected transaction if needed and possible
        if not is_valid and validation_level != ValidationLevel.STRICT:
            corrected_transaction = cls._attempt_correction(transaction, issues)
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            corrected_transaction=corrected_transaction
        )
    
    @classmethod
    def validate_transaction_batch(cls, transactions: List[Transaction],
                                 validation_level: ValidationLevel = ValidationLevel.MODERATE) -> List[ValidationResult]:
        """Validate a batch of transactions with cross-transaction checks.
        
        Args:
            transactions: List of transactions to validate
            validation_level: Strictness level for validation
            
        Returns:
            List of validation results
        """
        results = []
        previous_balance = None
        
        # Sort transactions by date for sequential validation
        sorted_transactions = sorted(transactions, key=lambda t: t.date)
        
        for i, transaction in enumerate(sorted_transactions):
            # Prepare context
            context = {
                'transaction_index': i,
                'total_transactions': len(sorted_transactions),
                'previous_balance': previous_balance,
                'is_batch_validation': True
            }
            
            # Validate individual transaction
            result = cls.validate_transaction(transaction, validation_level, context)
            results.append(result)
            
            # Update previous balance for next iteration
            if result.is_valid or result.corrected_transaction:
                effective_transaction = result.corrected_transaction or transaction
                previous_balance = effective_transaction.balance
        
        # Additional batch-level validations
        cls._validate_batch_consistency(results, validation_level)
        
        return results
    
    @classmethod
    def _validate_date(cls, date: datetime, validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate transaction date."""
        issues = []
        
        if not isinstance(date, datetime):
            issues.append(ValidationIssue(
                field="date",
                severity=ValidationSeverity.CRITICAL,
                message="Date must be a datetime object",
                original_value=date
            ))
            return issues
        
        now = datetime.now()
        
        # Check if date is too far in the past
        min_date = now - timedelta(days=cls.MAX_TRANSACTION_AGE_DAYS)
        if date < min_date:
            severity = ValidationSeverity.WARNING if validation_level == ValidationLevel.LENIENT else ValidationSeverity.CRITICAL
            issues.append(ValidationIssue(
                field="date",
                severity=severity,
                message=f"Transaction date is too old: {date.strftime('%Y-%m-%d')}",
                original_value=date
            ))
        
        # Check if date is in the future
        max_date = now + timedelta(days=cls.MAX_FUTURE_DAYS)
        if date > max_date:
            issues.append(ValidationIssue(
                field="date",
                severity=ValidationSeverity.CRITICAL,
                message=f"Transaction date is in the future: {date.strftime('%Y-%m-%d')}",
                original_value=date
            ))
        
        return issues
    
    @classmethod
    def _validate_description(cls, description: str, validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate transaction description."""
        issues = []
        
        if not description or not isinstance(description, str):
            issues.append(ValidationIssue(
                field="description",
                severity=ValidationSeverity.CRITICAL,
                message="Description is required and must be a string",
                original_value=description
            ))
            return issues
        
        description = description.strip()
        
        # Check length
        if len(description) < cls.MIN_DESCRIPTION_LENGTH:
            issues.append(ValidationIssue(
                field="description",
                severity=ValidationSeverity.WARNING,
                message=f"Description is too short ({len(description)} chars, minimum {cls.MIN_DESCRIPTION_LENGTH})",
                original_value=description
            ))
        
        if len(description) > cls.MAX_DESCRIPTION_LENGTH:
            severity = ValidationSeverity.WARNING if validation_level == ValidationLevel.LENIENT else ValidationSeverity.CRITICAL
            issues.append(ValidationIssue(
                field="description",
                severity=severity,
                message=f"Description is too long ({len(description)} chars, maximum {cls.MAX_DESCRIPTION_LENGTH})",
                original_value=description,
                suggested_value=description[:cls.MAX_DESCRIPTION_LENGTH]
            ))
        
        # Check for suspicious patterns
        if re.search(r'[<>{}|\\\[\]^~`]', description):
            issues.append(ValidationIssue(
                field="description",
                severity=ValidationSeverity.WARNING,
                message="Description contains suspicious special characters",
                original_value=description
            ))
        
        return issues
    
    @classmethod
    def _validate_amounts(cls, transaction: Transaction, validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate transaction amounts."""
        issues = []
        
        # At least one of debit or credit should be present
        if transaction.debit is None and transaction.credit is None:
            issues.append(ValidationIssue(
                field="amounts",
                severity=ValidationSeverity.CRITICAL,
                message="Either debit or credit amount must be specified"
            ))
            return issues
        
        # Both debit and credit shouldn't be present simultaneously
        if transaction.debit is not None and transaction.credit is not None:
            if validation_level == ValidationLevel.STRICT:
                issues.append(ValidationIssue(
                    field="amounts",
                    severity=ValidationSeverity.CRITICAL,
                    message="Transaction cannot have both debit and credit amounts"
                ))
            else:
                issues.append(ValidationIssue(
                    field="amounts",
                    severity=ValidationSeverity.WARNING,
                    message="Transaction has both debit and credit amounts, this is unusual"
                ))
        
        # Validate individual amounts
        for amount_field, amount_value in [("debit", transaction.debit), ("credit", transaction.credit)]:
            if amount_value is not None:
                if not isinstance(amount_value, (int, float)):
                    issues.append(ValidationIssue(
                        field=amount_field,
                        severity=ValidationSeverity.CRITICAL,
                        message=f"{amount_field.capitalize()} amount must be a number",
                        original_value=amount_value
                    ))
                    continue
                
                if amount_value <= 0:
                    issues.append(ValidationIssue(
                        field=amount_field,
                        severity=ValidationSeverity.CRITICAL,
                        message=f"{amount_field.capitalize()} amount must be positive",
                        original_value=amount_value
                    ))
                
                if amount_value < cls.MIN_AMOUNT:
                    issues.append(ValidationIssue(
                        field=amount_field,
                        severity=ValidationSeverity.WARNING,
                        message=f"{amount_field.capitalize()} amount is very small: {amount_value}",
                        original_value=amount_value
                    ))
                
                if amount_value > cls.MAX_AMOUNT:
                    issues.append(ValidationIssue(
                        field=amount_field,
                        severity=ValidationSeverity.CRITICAL,
                        message=f"{amount_field.capitalize()} amount exceeds maximum limit: {amount_value}",
                        original_value=amount_value
                    ))
        
        return issues
    
    @classmethod
    def _validate_balance(cls, balance: float, validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate balance amount."""
        issues = []
        
        if balance is None:
            issues.append(ValidationIssue(
                field="balance",
                severity=ValidationSeverity.CRITICAL,
                message="Balance is required",
                original_value=balance
            ))
            return issues
        
        if not isinstance(balance, (int, float)):
            issues.append(ValidationIssue(
                field="balance",
                severity=ValidationSeverity.CRITICAL,
                message="Balance must be a number",
                original_value=balance
            ))
            return issues
        
        if balance < cls.MIN_BALANCE:
            severity = ValidationSeverity.WARNING if validation_level == ValidationLevel.LENIENT else ValidationSeverity.CRITICAL
            issues.append(ValidationIssue(
                field="balance",
                severity=severity,
                message=f"Balance is extremely low: {balance}",
                original_value=balance
            ))
        
        if balance > cls.MAX_BALANCE:
            issues.append(ValidationIssue(
                field="balance",
                severity=ValidationSeverity.WARNING,
                message=f"Balance is very high: {balance}",
                original_value=balance
            ))
        
        return issues
    
    @classmethod
    def _validate_reference(cls, reference: Optional[str], validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate reference number."""
        issues = []
        
        if reference is None:
            if validation_level == ValidationLevel.STRICT:
                issues.append(ValidationIssue(
                    field="reference",
                    severity=ValidationSeverity.WARNING,
                    message="Reference number is missing"
                ))
            return issues
        
        if not isinstance(reference, str):
            issues.append(ValidationIssue(
                field="reference",
                severity=ValidationSeverity.WARNING,
                message="Reference must be a string",
                original_value=reference
            ))
            return issues
        
        reference = reference.strip()
        
        # Check if reference matches common patterns
        is_valid_format = any(re.match(pattern, reference, re.IGNORECASE) 
                             for pattern in cls.VALID_REFERENCE_PATTERNS)
        
        if not is_valid_format and validation_level != ValidationLevel.LENIENT:
            issues.append(ValidationIssue(
                field="reference",
                severity=ValidationSeverity.INFO,
                message=f"Reference number format is unusual: {reference}",
                original_value=reference
            ))
        
        return issues
    
    @classmethod
    def _validate_transaction_type(cls, transaction_type: TransactionType, 
                                 validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate transaction type."""
        issues = []
        
        if not isinstance(transaction_type, TransactionType):
            issues.append(ValidationIssue(
                field="transaction_type",
                severity=ValidationSeverity.CRITICAL,
                message="Transaction type must be a valid TransactionType enum",
                original_value=transaction_type
            ))
        
        return issues
    
    @classmethod
    def _validate_counterparty(cls, counterparty: Optional[str], 
                             validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate counterparty information."""
        issues = []
        
        if counterparty is not None:
            if not isinstance(counterparty, str):
                issues.append(ValidationIssue(
                    field="counterparty",
                    severity=ValidationSeverity.WARNING,
                    message="Counterparty must be a string",
                    original_value=counterparty
                ))
            elif len(counterparty.strip()) < 2:
                issues.append(ValidationIssue(
                    field="counterparty",
                    severity=ValidationSeverity.INFO,
                    message="Counterparty name is very short",
                    original_value=counterparty
                ))
        
        return issues
    
    @classmethod
    def _validate_bank_info(cls, transaction: Transaction, 
                          validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate bank and account information."""
        issues = []
        
        if not transaction.bank_name or not isinstance(transaction.bank_name, str):
            issues.append(ValidationIssue(
                field="bank_name",
                severity=ValidationSeverity.CRITICAL,
                message="Bank name is required and must be a string",
                original_value=transaction.bank_name
            ))
        
        if not transaction.account_number or not isinstance(transaction.account_number, str):
            issues.append(ValidationIssue(
                field="account_number",
                severity=ValidationSeverity.CRITICAL,
                message="Account number is required and must be a string",
                original_value=transaction.account_number
            ))
        elif len(transaction.account_number) < 4:
            issues.append(ValidationIssue(
                field="account_number",
                severity=ValidationSeverity.WARNING,
                message="Account number seems too short",
                original_value=transaction.account_number
            ))
        
        return issues
    
    @classmethod
    def _validate_amount_consistency(cls, transaction: Transaction, 
                                   validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate consistency between amounts and transaction type."""
        issues = []
        
        # Check if transaction type matches amount types
        if transaction.transaction_type in [TransactionType.ATM, TransactionType.CHARGE] and transaction.credit is not None:
            issues.append(ValidationIssue(
                field="amount_consistency",
                severity=ValidationSeverity.WARNING,
                message=f"{transaction.transaction_type.value} transactions typically don't have credit amounts"
            ))
        
        if transaction.transaction_type == TransactionType.DEPOSIT and transaction.debit is not None:
            issues.append(ValidationIssue(
                field="amount_consistency",
                severity=ValidationSeverity.WARNING,
                message="Deposit transactions typically don't have debit amounts"
            ))
        
        return issues
    
    @classmethod
    def _validate_with_context(cls, transaction: Transaction, context: Dict[str, Any],
                             validation_level: ValidationLevel) -> List[ValidationIssue]:
        """Validate transaction with additional context."""
        issues = []
        
        # Validate balance continuity if previous balance is available
        if 'previous_balance' in context and context['previous_balance'] is not None:
            previous_balance = context['previous_balance']
            expected_balance = previous_balance
            
            if transaction.credit:
                expected_balance += transaction.credit
            if transaction.debit:
                expected_balance -= transaction.debit
            
            balance_diff = abs(transaction.balance - expected_balance)
            tolerance = max(0.01, abs(expected_balance) * 0.001)  # 0.1% tolerance
            
            if balance_diff > tolerance:
                severity = ValidationSeverity.WARNING if validation_level == ValidationLevel.LENIENT else ValidationSeverity.CRITICAL
                issues.append(ValidationIssue(
                    field="balance_continuity",
                    severity=severity,
                    message=f"Balance doesn't match expected value. Expected: {expected_balance}, Actual: {transaction.balance}",
                    original_value=transaction.balance,
                    suggested_value=expected_balance
                ))
        
        return issues
    
    @classmethod
    def _validate_batch_consistency(cls, results: List[ValidationResult], 
                                  validation_level: ValidationLevel) -> None:
        """Validate consistency across batch of transactions."""
        # This could include checks like:
        # - Duplicate transaction detection
        # - Date sequence validation
        # - Balance trend analysis
        # For now, this is a placeholder for future enhancements
        pass
    
    @classmethod
    def _determine_validity(cls, issues: List[ValidationIssue], 
                          validation_level: ValidationLevel) -> bool:
        """Determine if transaction is valid based on issues and validation level."""
        if validation_level == ValidationLevel.STRICT:
            return len(issues) == 0
        elif validation_level == ValidationLevel.MODERATE:
            return not any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
        else:  # LENIENT
            critical_issues = [issue for issue in issues if issue.severity == ValidationSeverity.CRITICAL]
            # Allow some critical issues in lenient mode, but not all types
            critical_field_issues = {issue.field for issue in critical_issues}
            blocking_fields = {'date', 'amounts', 'balance', 'bank_name', 'account_number'}
            return not critical_field_issues.intersection(blocking_fields)
    
    @classmethod
    def _attempt_correction(cls, transaction: Transaction, 
                          issues: List[ValidationIssue]) -> Optional[Transaction]:
        """Attempt to correct transaction based on validation issues."""
        # This is a placeholder for auto-correction logic
        # In a full implementation, this would attempt to fix issues
        # where suggested_value is provided
        return None