import re
from typing import Dict, Any

class SmartCategorizer:
    """Rule-based categorizer with keyword matching"""

    def __init__(self):
        # Define keyword patterns for each category
        self.patterns = {
            'Dining': [
                'swiggy', 'zomato', 'food', 'restaurant', 'cafe', 'coffee',
                'pizza', 'burger', 'kfc', 'mcdonald', 'dominos', 'subway',
                'eat', 'dining', 'meal', 'breakfast', 'lunch', 'dinner'
            ],
            'Transportation': [
                'uber', 'ola', 'rapido', 'taxi', 'cab', 'fuel', 'petrol',
                'diesel', 'parking', 'toll', 'metro', 'bus', 'train',
                'railway', 'irctc', 'flight', 'airline'
            ],
            'Shopping': [
                'amazon', 'flipkart', 'myntra', 'ajio', 'mall', 'store',
                'mart', 'bazaar', 'retail', 'purchase', 'buy', 'shop'
            ],
            'Entertainment': [
                'netflix', 'prime', 'hotstar', 'spotify', 'movie', 'cinema',
                'pvr', 'inox', 'game', 'play', 'entertainment'
            ],
            'Rent': [
                'rent', 'lease', 'landlord', 'house', 'flat', 'apartment',
                'housing', 'accommodation'
            ],
            'Utilities': [
                'electricity', 'water', 'gas', 'internet', 'broadband',
                'mobile', 'phone', 'bill', 'recharge'
            ]
        }

    def categorize_transaction(self, transaction: Dict[str, Any]) -> str:
        """
        Categorize a single transaction
        Credits → Income
        Debits → Pattern matching
        """
        # Check if it's income (credit transaction)
        if transaction.get('credit') and float(transaction.get('credit', 0)) > 0:
            return 'Income'

        # For debits, check description against patterns
        description = str(transaction.get('description', '')).lower()

        # Check each category's keywords
        for category, keywords in self.patterns.items():
            for keyword in keywords:
                if keyword in description:
                    return category

        # Default to Others if no match
        return 'Others'

    def categorize_batch(self, transactions: list) -> Dict[str, str]:
        """Categorize multiple transactions"""
        results = {}
        for i, tx in enumerate(transactions):
            results[str(i)] = self.categorize_transaction(tx)
        return results