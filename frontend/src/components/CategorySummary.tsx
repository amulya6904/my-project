import React from 'react';
import { TransactionData } from '../types/api';
import { AICategory } from '../state/aiCategories';
import styles from './CategorySummary.module.css';

interface CategorySummaryProps {
  transactions: TransactionData[];
  aiCategories: Record<string, AICategory>;
  manualCategories: Record<string, string>;
  onCategoryFilter: (category: string | null) => void;
  activeFilter: string | null;
}

interface CategoryStats {
  category: string;
  count: number;
  totalDebit: number;
  totalCredit: number;
}

const CategorySummary: React.FC<CategorySummaryProps> = ({
  transactions,
  aiCategories,
  manualCategories,
  onCategoryFilter,
  activeFilter,
}) => {
  // Calculate category statistics
  const categoryStats: Record<string, CategoryStats> = {};

  transactions.forEach((transaction, index) => {
    // Generate a transaction ID (using index as fallback)
    const transactionId = `${transaction.date}-${index}`;
    
    // Manual category takes precedence over AI category
    let category = 'Uncategorized';
    if (manualCategories[transactionId]) {
      category = manualCategories[transactionId];
    } else if (aiCategories[transactionId]) {
      category = aiCategories[transactionId].category;
    }

    if (!categoryStats[category]) {
      categoryStats[category] = {
        category,
        count: 0,
        totalDebit: 0,
        totalCredit: 0,
      };
    }

    categoryStats[category].count += 1;
    categoryStats[category].totalDebit += transaction.debit || 0;
    categoryStats[category].totalCredit += transaction.credit || 0;
  });

  const sortedStats = Object.values(categoryStats).sort((a, b) => b.count - a.count);

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'Income': '#22c55e',
      'Shopping': '#3b82f6',
      'Dining': '#f59e0b',
      'Transportation': '#8b5cf6',
      'Rent': '#ef4444',
      'Utilities': '#06b6d4',
      'Entertainment': '#ec4899',
      'Groceries': '#84cc16',
      'Fees': '#f97316',
      'Transfers': '#6b7280',
      'Others': '#9ca3af',
      'Uncategorized': '#d1d5db',
    };
    return colors[category] || '#9ca3af';
  };

  if (sortedStats.length === 0) {
    return (
      <div className={styles.summaryContainer}>
        <h4>Category Summary</h4>
        <p className={styles.noData}>No categorized transactions available</p>
      </div>
    );
  }

  return (
    <div className={styles.summaryContainer}>
      <div className={styles.summaryHeader}>
        <h4>Category Summary</h4>
        {activeFilter && (
          <button
            className={styles.clearFilter}
            onClick={() => onCategoryFilter(null)}
            title="Clear filter"
          >
            ✕ Clear Filter
          </button>
        )}
      </div>
      
      <div className={styles.categoryGrid}>
        {sortedStats.map((stats) => (
          <div
            key={stats.category}
            className={`${styles.categoryCard} ${
              activeFilter === stats.category ? styles.active : ''
            }`}
            onClick={() => onCategoryFilter(
              activeFilter === stats.category ? null : stats.category
            )}
            style={{ '--category-color': getCategoryColor(stats.category) } as React.CSSProperties}
          >
            <div className={styles.categoryHeader}>
              <span 
                className={styles.categoryBadge}
                style={{ backgroundColor: getCategoryColor(stats.category) }}
              >
                {stats.category}
              </span>
              <span className={styles.transactionCount}>{stats.count} txns</span>
            </div>
            
            <div className={styles.categoryAmounts}>
              {stats.totalDebit > 0 && (
                <div className={styles.debitAmount}>
                  <span className={styles.label}>Debit:</span>
                  <span className={styles.amount}>{formatAmount(stats.totalDebit)}</span>
                </div>
              )}
              {stats.totalCredit > 0 && (
                <div className={styles.creditAmount}>
                  <span className={styles.label}>Credit:</span>
                  <span className={styles.amount}>{formatAmount(stats.totalCredit)}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CategorySummary;
