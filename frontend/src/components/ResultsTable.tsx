import React, { useState } from 'react';
import { TransactionData } from '../types/api';
import styles from './ResultsTable.module.css';

interface ResultsTableProps {
  transactions: TransactionData[];
  bankName: string;
  onDownload: () => void;
}

const ResultsTable: React.FC<ResultsTableProps> = ({ transactions, bankName, onDownload }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [sortField, setSortField] = useState<keyof TransactionData>('date');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  
  const itemsPerPage = 10;

  // Sort transactions
  const sortedTransactions = [...transactions].sort((a, b) => {
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
        <button className={styles.downloadBtn} onClick={onDownload}>
          📥 Download CSV
        </button>
      </div>

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
              <th>Reference</th>
            </tr>
          </thead>
          <tbody>
            {paginatedTransactions.map((transaction, index) => (
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
                <td className={styles.reference} title={transaction.reference || ''}>
                  {transaction.reference || '-'}
                </td>
              </tr>
            ))}
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