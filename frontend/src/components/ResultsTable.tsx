import React, { useState, useEffect } from 'react';
import { TransactionData } from '../types/api';
import { useAICategories } from '../state/aiCategories';
import CategorySummary from './CategorySummary';
import styles from './ResultsTable.module.css';

interface ResultsTableProps {
  transactions: TransactionData[];
  bankName: string;
  onDownload: () => void;
  jobId?: string;
}

const ResultsTable: React.FC<ResultsTableProps> = ({ transactions, bankName, onDownload, jobId }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [sortField, setSortField] = useState<keyof TransactionData>('date');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [manualCategories, setManualCategories] = useState<Record<string, string>>({});
  
  const aiCategories = useAICategories();

  // Predefined categories for manual selection
  const predefinedCategories = [
    'Shopping',
    'Dining', 
    'Transportation',
    'Groceries',
    'Rent',
    'Utilities',
    'Income',
    'Fees',
    'Transfers',
    'Others'
  ];
  
  const itemsPerPage = 10;

  // Auto-trigger AI categorization when transactions are available
  useEffect(() => {
    if (transactions.length > 0 && jobId && aiCategories.status === 'idle') {
      handleAnalyzeWithAI();
    }
  }, [transactions, jobId, aiCategories.status]);

  const handleAnalyzeWithAI = async () => {
    if (!jobId || transactions.length === 0) return;
    
    setIsAnalyzing(true);
    try {
      const transactionsForCategorization = transactions.map((transaction, index) => ({
        id: `${transaction.date}-${index}`,
        date: transaction.date,
        description: transaction.description,
        debit: transaction.debit,
        credit: transaction.credit,
      }));
      
      await aiCategories.fetchForFile(jobId, bankName, transactionsForCategorization);
    } catch (error) {
      console.error('Failed to analyze transactions:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Filter transactions by category if filter is active
  const filteredTransactions = categoryFilter
    ? transactions.filter((transaction, index) => {
        const transactionId = `${transaction.date}-${index}`;
        const effectiveCategory = getEffectiveCategory(transactionId);
        return effectiveCategory?.category === categoryFilter;
      })
    : transactions;

  // Sort transactions
  const sortedTransactions = [...filteredTransactions].sort((a, b) => {
    const aValue = a[sortField];
    const bValue = b[sortField];
    
    if (aValue === null || aValue === undefined) return 1;
    if (bValue === null || bValue === undefined) return -1;
    
    let comparison = 0;
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      comparison = aValue.localeCompare(bValue);
    } else if (typeof aValue === 'number' && typeof bValue === 'number') {
      comparison = aValue - bValue;
    } else {
      comparison = String(aValue).localeCompare(String(bValue));
    }
    
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  // Paginate transactions
  const totalPages = Math.ceil(sortedTransactions.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedTransactions = sortedTransactions.slice(startIndex, startIndex + itemsPerPage);

  const handleSort = (field: keyof TransactionData) => {
    if (field === sortField) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const formatAmount = (amount?: number) => {
    if (amount === null || amount === undefined) return '-';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-IN');
    } catch {
      return dateStr;
    }
  };

  const getSortIcon = (field: keyof TransactionData) => {
    if (field !== sortField) return '↕️';
    return sortDirection === 'asc' ? '⬆️' : '⬇️';
  };

  const handleManualCategoryChange = (transactionId: string, category: string) => {
    setManualCategories(prev => ({
      ...prev,
      [transactionId]: category
    }));
  };

  const getEffectiveCategory = (transactionId: string) => {
    // Manual category takes precedence over AI category
    if (manualCategories[transactionId]) {
      return {
        category: manualCategories[transactionId],
        confidence: 1.0,
        isManual: true
      };
    }
    
    const aiCategory = aiCategories.byId[transactionId];
    if (aiCategory) {
      return {
        category: aiCategory.category,
        confidence: aiCategory.confidence,
        isManual: false
      };
    }
    
    return null;
  };

  const generateEnhancedCSV = () => {
    const headers = [
      'Date', 'Description', 'Reference', 'Debit', 'Credit', 'Balance',
      'Type', 'Counterparty', 'AI Category', 'Manual Category', 'Final Category'
    ];

    const rows = transactions.map((transaction, index) => {
      const transactionId = `${transaction.date}-${index}`;
      const effectiveCategory = getEffectiveCategory(transactionId);
      const aiCategory = aiCategories.byId[transactionId];
      const manualCategory = manualCategories[transactionId];

      return [
        transaction.date || '',
        transaction.description || '',
        transaction.reference || '',
        transaction.debit || '',
        transaction.credit || '',
        transaction.balance || '',
        transaction.transaction_type || '',
        transaction.counterparty || '',
        aiCategory?.category || '',
        manualCategory || '',
        effectiveCategory?.category || ''
      ];
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    // Create and download the file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${bankName}_transactions_with_categories.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getCategoryBadge = (transaction: TransactionData, index: number) => {
    const transactionId = `${transaction.date}-${index}`;
    const effectiveCategory = getEffectiveCategory(transactionId);
    
    if (aiCategories.status === 'loading') {
      return <div className={styles.categorySkeleton}></div>;
    }
    
    if (!effectiveCategory) {
      return <span className={styles.categoryBadge}>—</span>;
    }

    const { category, confidence, isManual } = effectiveCategory;
    
    // If AI assigned "Others" and no manual override, show dropdown
    if (category === 'Others' && !isManual) {
      return (
        <select
          className={styles.categoryDropdown}
          value="Others"
          onChange={(e) => handleManualCategoryChange(transactionId, e.target.value)}
          title="Select a category"
        >
          <option value="Others">Others</option>
          {predefinedCategories.filter(cat => cat !== 'Others').map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      );
    }
    
    // Show badge for all other cases
    const confidenceText = `Confidence: ${Math.round(confidence * 100)}%`;
    const isLowConfidence = confidence < 0.5 && !isManual;
    
    return (
      <span 
        className={`${styles.categoryBadge} ${styles[category.toLowerCase()]} ${
          isLowConfidence ? styles.lowConfidence : ''
        } ${isManual ? styles.manualCategory : ''}`}
        title={isManual ? 'Manually selected' : `${confidenceText}${isLowConfidence ? ' (low)' : ''}`}
      >
        {isManual && '✓ '}{category}{isLowConfidence ? ' (low)' : ''}
      </span>
    );
  };

  return (
    <div className={styles.resultsContainer}>
      <div className={styles.resultsHeader}>
        <div className={styles.resultsInfo}>
          <h3>Processing Results</h3>
          <div className={styles.summary}>
            <span className={styles.bankName}>{bankName}</span>
            <span className={styles.transactionCount}>{transactions.length} transactions</span>
          </div>
        </div>
        <div className={styles.headerActions}>
          <button 
            className={`${styles.analyzeBtn} ${isAnalyzing ? styles.loading : ''}`}
            onClick={handleAnalyzeWithAI}
            disabled={isAnalyzing || transactions.length === 0}
          >
            {isAnalyzing ? '🔄 Analyzing...' : '🤖 Analyze with AI'}
          </button>
          <div className={styles.downloadGroup}>
            <button className={styles.downloadBtn} onClick={onDownload}>
              📥 Download CSV
            </button>
            {(Object.keys(manualCategories).length > 0 || aiCategories.status === 'ready') && (
              <button 
                className={styles.downloadEnhancedBtn} 
                onClick={generateEnhancedCSV}
                title="Download CSV with AI and manual categories"
              >
                📊 Download with Categories
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Category Summary */}
      {aiCategories.status === 'ready' && Object.keys(aiCategories.byId).length > 0 && (
        <CategorySummary
          transactions={transactions}
          aiCategories={aiCategories.byId}
          manualCategories={manualCategories}
          onCategoryFilter={setCategoryFilter}
          activeFilter={categoryFilter}
        />
      )}

      <div className={styles.tableContainer}>
        <table className={styles.resultsTable}>
          <thead>
            <tr>
              <th onClick={() => handleSort('date')} className={styles.sortable}>
                Date {getSortIcon('date')}
              </th>
              <th onClick={() => handleSort('description')} className={styles.sortable}>
                Description {getSortIcon('description')}
              </th>
              <th onClick={() => handleSort('transaction_type')} className={styles.sortable}>
                Type {getSortIcon('transaction_type')}
              </th>
              <th onClick={() => handleSort('debit')} className={`${styles.sortable} ${styles.amount}`}>
                Debit {getSortIcon('debit')}
              </th>
              <th onClick={() => handleSort('credit')} className={`${styles.sortable} ${styles.amount}`}>
                Credit {getSortIcon('credit')}
              </th>
              <th onClick={() => handleSort('balance')} className={`${styles.sortable} ${styles.amount}`}>
                Balance {getSortIcon('balance')}
              </th>
              <th>AI Category</th>
              <th>Reference</th>
            </tr>
          </thead>
          <tbody>
            {paginatedTransactions.map((transaction, index) => {
              // Calculate the original index for AI category lookup
              const originalIndex = transactions.findIndex(t => 
                t.date === transaction.date && 
                t.description === transaction.description &&
                t.debit === transaction.debit &&
                t.credit === transaction.credit
              );
              
              return (
              <tr key={`${transaction.date}-${index}`}>
                <td className={styles.date}>{formatDate(transaction.date)}</td>
                <td className={styles.description} title={transaction.description}>
                  {transaction.description}
                </td>
                <td className={styles.type}>
                  <span className={`${styles.typeBadge} ${styles[transaction.transaction_type.toLowerCase()]}`}>
                    {transaction.transaction_type}
                  </span>
                </td>
                <td className={`${styles.amount} ${styles.debit}`}>
                  {transaction.debit ? formatAmount(transaction.debit) : '-'}
                </td>
                <td className={`${styles.amount} ${styles.credit}`}>
                  {transaction.credit ? formatAmount(transaction.credit) : '-'}
                </td>
                <td className={`${styles.amount} ${styles.balance}`}>
                  {formatAmount(transaction.balance)}
                </td>
                <td className={styles.aiCategory}>
                  {getCategoryBadge(transaction, originalIndex)}
                </td>
                <td className={styles.reference} title={transaction.reference || ''}>
                  {transaction.reference || '-'}
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button 
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
          >
            ← Previous
          </button>
          
          <span className={styles.pageInfo}>
            Page {currentPage} of {totalPages}
          </span>
          
          <button 
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
};

export default ResultsTable;