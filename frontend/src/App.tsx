import React, { useState } from 'react';
import ErrorBoundary from './components/ErrorBoundary';
import FileUpload from './components/FileUpload';
import ProgressDisplay from './components/ProgressDisplay';
import ResultsTable from './components/ResultsTable';
import { apiService } from './services/api';
import { UploadResponse, ProcessingResponse, JobStatus } from './types/api';
import styles from './App.module.css';

enum AppState {
  UPLOAD = 'upload',
  PROCESSING = 'processing',
  RESULTS = 'results',
  ERROR = 'error'
}

const App: React.FC = () => {
  const [appState, setAppState] = useState<AppState>(AppState.UPLOAD);
  const [currentJob, setCurrentJob] = useState<UploadResponse | null>(null);
  const [processingResults, setProcessingResults] = useState<ProcessingResponse | null>(null);
  const [error, setError] = useState<string>('');

  const handleUploadSuccess = (response: UploadResponse) => {
    setCurrentJob(response);
    setAppState(AppState.PROCESSING);
    setError('');
  };

  const handleUploadError = (errorMessage: string) => {
    setError(errorMessage);
    setAppState(AppState.ERROR);
  };

  const handleProcessingComplete = async () => {
    if (!currentJob) return;

    try {
      const results = await apiService.getResults(currentJob.job_id);
      setProcessingResults(results);
      setAppState(AppState.RESULTS);
    } catch (err: any) {
      setError(err.message || 'Failed to get results');
      setAppState(AppState.ERROR);
    }
  };

  const handleProcessingError = (errorMessage: string) => {
    setError(errorMessage);
    setAppState(AppState.ERROR);
  };

  const handleDownload = () => {
    if (currentJob) {
      const downloadUrl = apiService.getDownloadUrl(currentJob.job_id);
      window.open(downloadUrl, '_blank');
    }
  };

  const handleStartOver = () => {
    // Cleanup current job
    if (currentJob) {
      apiService.cleanupJob(currentJob.job_id);
    }
    
    setCurrentJob(null);
    setProcessingResults(null);
    setError('');
    setAppState(AppState.UPLOAD);
  };

  const renderContent = () => {
    switch (appState) {
      case AppState.UPLOAD:
        return (
          <FileUpload
            onUploadSuccess={handleUploadSuccess}
            onError={handleUploadError}
          />
        );

      case AppState.PROCESSING:
        if (!currentJob) return null;
        return (
          <ProgressDisplay
            jobId={currentJob.job_id}
            onComplete={handleProcessingComplete}
            onError={handleProcessingError}
          />
        );

      case AppState.RESULTS:
        if (!processingResults) return null;
        return (
          <ResultsTable
            transactions={processingResults.transactions}
            bankName={processingResults.bank}
            onDownload={handleDownload}
          />
        );

      case AppState.ERROR:
        return (
          <div className={styles.errorState}>
            <div className={styles.errorIcon}>❌</div>
            <h3>Processing Error</h3>
            <p>{error}</p>
            <button onClick={handleStartOver} className={styles.retryButton}>
              🔄 Try Again
            </button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <ErrorBoundary>
      <div className={styles.app}>
        <header className={styles.appHeader}>
          <div className={styles.container}>
            <h1>🏦 Bank Statement Processor</h1>
            <p>Convert your PDF bank statements to CSV format</p>
          </div>
        </header>

        <main className={styles.appMain}>
          <div className={styles.container}>
            {/* Progress indicators */}
            <div className={styles.progressSteps}>
              <div className={`${styles.step} ${appState === AppState.UPLOAD ? styles.active : (appState === AppState.PROCESSING || appState === AppState.RESULTS) ? styles.completed : ''}`}>
                <span className={styles.stepNumber}>1</span>
                <span className={styles.stepLabel}>Upload PDF</span>
              </div>
              <div className={`${styles.step} ${appState === AppState.PROCESSING ? styles.active : appState === AppState.RESULTS ? styles.completed : ''}`}>
                <span className={styles.stepNumber}>2</span>
                <span className={styles.stepLabel}>Process</span>
              </div>
              <div className={`${styles.step} ${appState === AppState.RESULTS ? styles.active : ''}`}>
                <span className={styles.stepNumber}>3</span>
                <span className={styles.stepLabel}>Results</span>
              </div>
            </div>

            {/* Main content */}
            {renderContent()}

            {/* Action buttons */}
            {appState !== AppState.UPLOAD && appState !== AppState.ERROR && (
              <div className={styles.actions}>
                <button onClick={handleStartOver} className={styles.startOverBtn}>
                  ← Process Another File
                </button>
              </div>
            )}
          </div>
        </main>

        <footer className={styles.appFooter}>
          <div className={styles.container}>
            <p>Supports Union Bank of India and State Bank of India statements</p>
          </div>
        </footer>
      </div>
    </ErrorBoundary>
  );
};

export default App;