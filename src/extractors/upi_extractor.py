"""UPI transaction details extractor."""

import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class UPITransactionType(Enum):
    """Types of UPI transactions."""
    P2P = "P2P"  # Person to Person
    P2M = "P2M"  # Person to Merchant
    COLLECT = "COLLECT"  # Payment request
    MANDATE = "MANDATE"  # Recurring payment


@dataclass
class UPIDetails:
    """Structured UPI transaction details."""
    transaction_id: Optional[str] = None
    reference_id: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_vpa: Optional[str] = None
    customer_vpa: Optional[str] = None
    bank_code: Optional[str] = None
    transaction_type: Optional[UPITransactionType] = None
    original_description: str = ""


class UPIExtractor:
    """Utility class for extracting UPI transaction details."""
    
    # Common UPI patterns
    UPI_PATTERNS = {
        # Standard UPI format: UPI/REF_ID/BANK_CODE/MERCHANT_OR_USER/ADDITIONAL_INFO
        'standard': r'UPI[/-]?(\d+)[/-]([A-Z]{2,4})[/-]([^/\s]+)(?:[/-]([^/\s]*))?',
        
        # UPI with transaction ID
        'with_txn_id': r'UPI[/-]?TXN[/-]?(\d+)[/-]([A-Z]{2,4})[/-]([^/\s]+)',
        
        # UPI collect request
        'collect': r'UPI[/-]?COLLECT[/-]?(\d+)[/-]([A-Z]{2,4})[/-]([^/\s]+)',
        
        # UPI mandate
        'mandate': r'UPI[/-]?MANDATE[/-]?(\d+)[/-]([A-Z]{2,4})[/-]([^/\s]+)',
        
        # Simple UPI reference
        'simple': r'UPI[/-]?(\d+)',
    }
    
    # VPA (Virtual Payment Address) pattern
    VPA_PATTERN = r'([a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+)'
    
    # Bank codes mapping
    BANK_CODES = {
        'SBI': 'State Bank of India',
        'HDFC': 'HDFC Bank',
        'ICICI': 'ICICI Bank',
        'AXIS': 'Axis Bank',
        'KOTAK': 'Kotak Mahindra Bank',
        'PNB': 'Punjab National Bank',
        'BOB': 'Bank of Baroda',
        'CANARA': 'Canara Bank',
        'UBI': 'Union Bank of India',
        'IOB': 'Indian Overseas Bank',
        'PAYTM': 'Paytm Payments Bank',
        'PHONEPE': 'PhonePe',
        'GPAY': 'Google Pay',
        'BHIM': 'BHIM'
    }
    
    # Merchant indicators
    MERCHANT_INDICATORS = [
        'merchant', 'shop', 'store', 'pvt', 'ltd', 'inc', 'corp',
        'restaurant', 'cafe', 'hotel', 'mall', 'supermarket',
        'pharmacy', 'hospital', 'petrol', 'fuel', 'telecom'
    ]
    
    @classmethod
    def extract_upi_details(cls, description: str) -> UPIDetails:
        """Extract UPI details from transaction description.
        
        Args:
            description: Transaction description containing UPI information
            
        Returns:
            UPIDetails object with extracted information
        """
        details = UPIDetails(original_description=description)
        
        # Try each UPI pattern
        for pattern_name, pattern in cls.UPI_PATTERNS.items():
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                cls._parse_upi_match(match, details, pattern_name)
                break
        
        # Extract VPAs (Virtual Payment Addresses)
        vpa_matches = re.findall(cls.VPA_PATTERN, description, re.IGNORECASE)
        if vpa_matches:
            cls._classify_vpas(vpa_matches, details)
        
        # Determine transaction type
        details.transaction_type = cls._determine_transaction_type(description, details)
        
        return details
    
    @classmethod
    def _parse_upi_match(cls, match, details: UPIDetails, pattern_name: str) -> None:
        """Parse regex match based on pattern type.
        
        Args:
            match: Regex match object
            details: UPIDetails object to populate
            pattern_name: Name of the pattern that matched
        """
        groups = match.groups()
        
        if pattern_name in ['standard', 'with_txn_id', 'collect', 'mandate']:
            # Pattern: UPI/REF_ID/BANK_CODE/MERCHANT_OR_USER/ADDITIONAL_INFO
            if len(groups) >= 3:
                details.reference_id = groups[0]
                details.bank_code = groups[1].upper()
                
                # Third group could be merchant or user
                merchant_or_user = groups[2]
                if cls._is_merchant_name(merchant_or_user):
                    details.merchant_name = merchant_or_user
                else:
                    # Could be a user name or VPA
                    if '@' in merchant_or_user:
                        details.customer_vpa = merchant_or_user
                    else:
                        details.merchant_name = merchant_or_user
                        
                # Transaction ID might be in additional info
                if len(groups) >= 4 and groups[3]:
                    if groups[3].isdigit():
                        details.transaction_id = groups[3]
        
        elif pattern_name == 'simple':
            # Simple UPI reference number
            details.reference_id = groups[0]
    
    @classmethod
    def _classify_vpas(cls, vpa_matches: list, details: UPIDetails) -> None:
        """Classify VPAs as merchant or customer VPAs.
        
        Args:
            vpa_matches: List of VPA strings found
            details: UPIDetails object to populate
        """
        for vpa in vpa_matches:
            vpa_lower = vpa.lower()
            
            # Check if VPA belongs to known payment services
            if any(service in vpa_lower for service in ['paytm', 'phonepe', 'gpay', 'bhim']):
                details.merchant_vpa = vpa
            elif any(indicator in vpa_lower for indicator in cls.MERCHANT_INDICATORS):
                details.merchant_vpa = vpa
            else:
                # Assume it's a customer VPA if we don't have one yet
                if not details.customer_vpa:
                    details.customer_vpa = vpa
                else:
                    # If we already have a customer VPA, this might be merchant
                    details.merchant_vpa = vpa
    
    @classmethod
    def _is_merchant_name(cls, name: str) -> bool:
        """Check if name appears to be a merchant name.
        
        Args:
            name: Name to check
            
        Returns:
            True if appears to be merchant name
        """
        name_lower = name.lower()
        
        # Check for merchant indicators
        for indicator in cls.MERCHANT_INDICATORS:
            if indicator in name_lower:
                return True
        
        # Check for business suffixes
        business_suffixes = ['pvt', 'ltd', 'inc', 'corp', 'llp', 'llc']
        for suffix in business_suffixes:
            if name_lower.endswith(suffix):
                return True
        
        # Check for all caps (common for business names)
        if name.isupper() and len(name) > 3:
            return True
        
        return False
    
    @classmethod
    def _determine_transaction_type(cls, description: str, details: UPIDetails) -> UPITransactionType:
        """Determine the type of UPI transaction.
        
        Args:
            description: Original transaction description
            details: Parsed UPI details
            
        Returns:
            UPITransactionType enum value
        """
        desc_lower = description.lower()
        
        # Check for specific transaction type indicators
        if 'collect' in desc_lower or 'request' in desc_lower:
            return UPITransactionType.COLLECT
        
        if 'mandate' in desc_lower or 'recurring' in desc_lower:
            return UPITransactionType.MANDATE
        
        # Check if it's merchant transaction
        if (details.merchant_name and cls._is_merchant_name(details.merchant_name)) or \
           (details.merchant_vpa and any(service in details.merchant_vpa.lower() 
                                       for service in ['paytm', 'phonepe', 'gpay'])):
            return UPITransactionType.P2M
        
        # Default to Person to Person
        return UPITransactionType.P2P
    
    @classmethod
    def extract_merchant_category(cls, description: str) -> Optional[str]:
        """Extract merchant category from description.
        
        Args:
            description: Transaction description
            
        Returns:
            Merchant category if identifiable
        """
        desc_lower = description.lower()
        
        categories = {
            'food': ['restaurant', 'cafe', 'food', 'kitchen', 'pizza', 'burger', 'swiggy', 'zomato'],
            'fuel': ['petrol', 'fuel', 'gas', 'diesel', 'hp', 'ioc', 'bpcl'],
            'retail': ['mall', 'store', 'shop', 'mart', 'supermarket', 'grocery'],
            'transport': ['uber', 'ola', 'metro', 'bus', 'taxi', 'auto'],
            'telecom': ['airtel', 'vodafone', 'jio', 'bsnl', 'telecom', 'mobile'],
            'utility': ['electricity', 'water', 'gas', 'utility', 'bill'],
            'healthcare': ['hospital', 'clinic', 'pharmacy', 'medical', 'doctor'],
            'entertainment': ['movie', 'cinema', 'book', 'bookmyshow', 'netflix'],
        }
        
        for category, keywords in categories.items():
            if any(keyword in desc_lower for keyword in keywords):
                return category
        
        return None
    
    @classmethod
    def format_upi_summary(cls, details: UPIDetails) -> str:
        """Format UPI details into a readable summary.
        
        Args:
            details: UPI transaction details
            
        Returns:
            Formatted summary string
        """
        summary_parts = []
        
        # Transaction type
        if details.transaction_type:
            summary_parts.append(f"Type: {details.transaction_type.value}")
        
        # Reference ID
        if details.reference_id:
            summary_parts.append(f"Ref: {details.reference_id}")
        
        # Bank
        if details.bank_code:
            bank_name = cls.BANK_CODES.get(details.bank_code, details.bank_code)
            summary_parts.append(f"Bank: {bank_name}")
        
        # Merchant or counterparty
        if details.merchant_name:
            summary_parts.append(f"Merchant: {details.merchant_name}")
        elif details.merchant_vpa:
            summary_parts.append(f"To: {details.merchant_vpa}")
        elif details.customer_vpa:
            summary_parts.append(f"From/To: {details.customer_vpa}")
        
        return " | ".join(summary_parts) if summary_parts else "UPI Transaction"
    
    @classmethod
    def is_upi_transaction(cls, description: str) -> bool:
        """Check if description contains UPI transaction indicators.
        
        Args:
            description: Transaction description to check
            
        Returns:
            True if appears to be UPI transaction
        """
        if not description:
            return False
        
        desc_lower = description.lower()
        
        # Direct UPI indicators
        upi_indicators = ['upi', 'unified payments', 'bhim', 'phonepe', 'gpay', 'paytm']
        
        for indicator in upi_indicators:
            if indicator in desc_lower:
                return True
        
        # Check for UPI patterns
        for pattern in cls.UPI_PATTERNS.values():
            if re.search(pattern, description, re.IGNORECASE):
                return True
        
        # Check for VPA pattern
        if re.search(cls.VPA_PATTERN, description, re.IGNORECASE):
            return True
        
        return False