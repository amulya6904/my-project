import React, { useState } from 'react';
import { simpleApiService, ProcessingResult, Transaction, AnalyzeResponse } from './services/simpleApi';
import AnalysisReportModal from './components/AnalysisReportModal';
import styles from './App.module.css';

enum AppState {
  UPLOAD = 'upload',
  PROCESSING = 'processing',
  RESULTS = 'results',
  ERROR = 'error',
  ANALYZING = 'analyzing'
}

const SimpleApp: React.FC = () => {
  const [appState, setAppState] = useState<AppState>(AppState.UPLOAD);
  const [results, setResults] = useState<ProcessingResult | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [password, setPassword] = useState<string>('');

  // AI Analysis state
  const [aiAnalysis, setAiAnalysis] = useState<AnalyzeResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [isReportOpen, setIsReportOpen] = useState<boolean>(false);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert('Please select a PDF file');
      return;
    }

    setAppState(AppState.PROCESSING);

    try {
      // Call the simplified API that processes directly
      const result = await simpleApiService.uploadAndProcessPdf(selectedFile, password || undefined);
      setResults(result);

      if (result.success) {
        setAppState(AppState.RESULTS);
      } else {
        setAppState(AppState.ERROR);
      }
    } catch (error: any) {
      console.error('Processing failed:', error);
      setResults({
        success: false,
        error: 'network_error',
        message: 'Failed to process file',
        details: error.message
      });
      setAppState(AppState.ERROR);
    }
  };

  const handleReset = () => {
    setAppState(AppState.UPLOAD);
    setResults(null);
    setSelectedFile(null);
    setPassword('');
    setAiAnalysis(null);
    setIsAnalyzing(false);
    setIsReportOpen(false);
  };

  const handleAnalyzeWithAI = async (provider: string = 'mock') => {
    if (!results?.transactions) {
      alert('No transactions to analyze');
      return;
    }

    setIsAnalyzing(true);

    try {
      const analysis = await simpleApiService.analyzeTransactions(results.transactions, provider);

      if (analysis.success) {
        setAiAnalysis(analysis);
        // Update transactions with AI categories
        const updatedTransactions = results.transactions.map((txn, index) => {
          const txnId = `txn_${index}`;
          const category = analysis.categories[txnId];

          if (category) {
            return {
              ...txn,
              ai_category: category.category,
              ai_confidence: category.confidence,
              ai_reasoning: category.reasoning
            };
          }
          return txn;
        });

        setResults({
          ...results,
          transactions: updatedTransactions
        });
      } else {
        alert(`AI Analysis failed: ${analysis.error}`);
      }
    } catch (error: any) {
      console.error('AI analysis error:', error);
      alert('Failed to analyze transactions with AI');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const formatCurrency = (amount: number | null): string => {
    if (amount === null) return '-';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR'
    }).format(amount);
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '-';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-IN');
    } catch {
      return dateStr;
    }
  };

  const getCategoryColor = (category: string): string => {
    const colors: { [key: string]: string } = {
      'Food & Dining': '#FF6B6B',
      'Transportation': '#4ECDC4',
      'Shopping': '#45B7D1',
      'Entertainment': '#96CEB4',
      'Healthcare': '#FFEAA7',
      'Utilities': '#DDA0DD',
      'Income - Salary': '#98D8C8',
      'Income - Other': '#A8E6CF',
      'Investments': '#FFB74D',
      'Other': '#B0BEC5'
    };
    return colors[category] || '#B0BEC5';
  };

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <h1>🏦 Bank Statement Processor</h1>
        <p>Upload your PDF bank statements and extract transaction data</p>
      </header>

      <main className={styles.main}>
        {appState === AppState.UPLOAD && (
          <div className={styles.uploadSection}>
            <div className={styles.card}>
              <h2>Upload PDF Bank Statement</h2>
              <div className={styles.uploadForm}>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileSelect}
                  className={styles.fileInput}
                />
                {selectedFile && (
                  <div className={styles.fileInfo}>
                    <p>📄 Selected: {selectedFile.name}</p>
                    <p>Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                )}
                <input
                  type="password"
                  placeholder="PDF password (if required)"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={styles.passwordInput}
                />
                <button
                  onClick={handleUpload}
                  disabled={!selectedFile}
                  className={styles.uploadButton}
                >
                  Upload and Process
                </button>
              </div>
              <div className={styles.supportedBanks}>
                <h3>Supported Banks:</h3>
                <ul>
                  <li>Union Bank of India</li>
                  <li>State Bank of India</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {appState === AppState.PROCESSING && (
          <div className={styles.processingSection}>
            <div className={styles.card}>
              <h2>🔄 Processing PDF...</h2>
              <div className={styles.processingSpinner}>
                <div className={styles.spinner}></div>
              </div>
              <p>Analyzing your bank statement and extracting transaction data...</p>
            </div>
          </div>
        )}

        {appState === AppState.ERROR && results && (
          <div className={styles.errorSection}>
            <div className={styles.card}>
              <h2>❌ Processing Failed</h2>
              <div className={styles.errorDetails}>
                <p><strong>Error:</strong> {results.message}</p>
                {results.details && (
                  <details className={styles.errorDetails}>
                    <summary>Technical Details</summary>
                    <pre>{results.details}</pre>
                  </details>
                )}
                {results.supported_banks && (
                  <div className={styles.supportedBanks}>
                    <h3>Supported Banks:</h3>
                    <ul>
                      {results.supported_banks.map((bank, index) => (
                        <li key={index}>{bank}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <button onClick={handleReset} className={styles.resetButton}>
                Try Again
              </button>
            </div>
          </div>
        )}

      {appState === AppState.RESULTS && results?.success && results.transactions && (
        <div className={styles.resultsSection}>
            <div className={styles.card}>
              <h2>✅ Processing Complete!</h2>
              <div className={styles.resultsSummary}>
                <p><strong>Bank:</strong> {results.bank}</p>
                <p><strong>File:</strong> {results.filename}</p>
                <p><strong>Transactions Found:</strong> {results.count}</p>
                {aiAnalysis?.summary && (
                  <p><strong>AI Analysis:</strong> {aiAnalysis.summary.categorization_rate.toFixed(1)}% categorized with {aiAnalysis.summary.provider_used}</p>
                )}
              </div>

              {/* AI Analysis Button */}
              <div className={styles.aiAnalysisSection}>
                <button
                  onClick={() => handleAnalyzeWithAI('mock')}
                  disabled={isAnalyzing}
                  className={styles.analyzeButton}
                >
                  {isAnalyzing ? '🤖 Analyzing...' : '🤖 Analyze with AI'}
                </button>
                {aiAnalysis?.success && (
                  <div className={styles.aiSummary}>
                    <h4>AI Analysis Summary</h4>
                    <p>Categorization Rate: {aiAnalysis.summary?.categorization_rate.toFixed(1)}%</p>
                    <div className={styles.topCategories}>
                      <strong>Top Categories:</strong>
                      {aiAnalysis.summary?.top_categories.slice(0, 3).map((cat, idx) => (
                        <span key={idx} className={styles.categoryTag} style={{backgroundColor: getCategoryColor(cat.category)}}>
                          {cat.category}: {cat.percentage.toFixed(1)}%
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="mt-4 rounded-lg border border-slate-200 bg-white/70 p-4 shadow-sm">
                  <h5 className="text-sm font-semibold text-slate-700">Need a deeper dive?</h5>
                  <p className="mt-1 text-xs text-slate-500">
                    View charts and AI-generated insights summarizing your spending habits.
                  </p>
                  <button
                    onClick={() => setIsReportOpen(true)}
                    disabled={!results.transactions?.length}
                    className="mt-3 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    📊 Analysis Report
                  </button>
                </div>
              </div>

              <div className={styles.transactionsTable}>
                <h3>Transactions</h3>
                <div className={styles.tableContainer}>
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Reference</th>
                        <th>Debit</th>
                        <th>Credit</th>
                        <th>Balance</th>
                        <th>Category</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.transactions.map((transaction, index) => (
                        <tr key={index}>
                          <td>{formatDate(transaction.date)}</td>
                          <td className={styles.descriptionCell}>
                            {transaction.description}
                            {transaction.counterparty && (
                              <div className={styles.counterparty}>
                                → {transaction.counterparty}
                              </div>
                            )}
                          </td>
                          <td>{transaction.reference || '-'}</td>
                          <td className={styles.debitCell}>
                            {transaction.debit ? formatCurrency(transaction.debit) : '-'}
                          </td>
                          <td className={styles.creditCell}>
                            {transaction.credit ? formatCurrency(transaction.credit) : '-'}
                          </td>
                          <td>{transaction.balance ? formatCurrency(transaction.balance) : '-'}</td>
                          <td className={styles.categoryCell}>
                            {transaction.ai_category ? (
                              <div className={styles.aiCategoryContainer}>
                                <span
                                  className={styles.categoryBadge}
                                  style={{ backgroundColor: getCategoryColor(transaction.ai_category) }}
                                  title={`Confidence: ${transaction.ai_confidence}\nReasoning: ${transaction.ai_reasoning}`}
                                >
                                  {transaction.ai_category}
                                </span>
                                <span className={styles.confidenceBadge}>
                                  {transaction.ai_confidence}
                                </span>
                              </div>
                            ) : (
                              <span className={styles.originalType}>{transaction.transaction_type}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className={styles.actionButtons}>
                <button
                  onClick={() => {
                    if (results.transactions) {
                      const csvContent = convertToCSV(results.transactions);
                      downloadCSV(csvContent, `${results.filename}_transactions.csv`);
                    }
                  }}
                  className={styles.downloadButton}
                >
                  📥 Download CSV
                </button>
                <button onClick={handleReset} className={styles.resetButton}>
                  Process Another File
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      {appState === AppState.RESULTS && (
        <AnalysisReportModal
          isOpen={isReportOpen}
          onClose={() => setIsReportOpen(false)}
          transactions={results?.transactions || []}
          aiAnalysis={aiAnalysis}
        />
      )}
    </div>
  );
};

// Helper function to convert transactions to CSV
const convertToCSV = (transactions: Transaction[]): string => {
  const headers = [
    'Date', 'Description', 'Reference', 'Debit', 'Credit', 'Balance',
    'Type', 'Counterparty', 'Bank', 'Account'
  ];

  const rows = transactions.map(t => [
    t.date || '',
    t.description || '',
    t.reference || '',
    t.debit || '',
    t.credit || '',
    t.balance || '',
    t.transaction_type || '',
    t.counterparty || '',
    t.bank_name || '',
    t.account_number || ''
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
  ].join('\n');

  return csvContent;
};

// Helper function to download CSV
const downloadCSV = (csvContent: string, filename: string): void => {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');

  if (link.download !== undefined) {
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
};

export default SimpleApp;