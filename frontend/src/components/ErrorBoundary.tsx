import React, { Component, ReactNode } from 'react';
import styles from './ErrorBoundary.module.css';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className={styles.errorBoundary}>
          <div className={styles.errorContent}>
            <h2>⚠️ Something went wrong</h2>
            <p>An unexpected error occurred. Please refresh the page and try again.</p>
            <details className={styles.errorDetails}>
              <summary>Error Details</summary>
              <pre>{this.state.error?.stack}</pre>
            </details>
            <button 
              onClick={() => window.location.reload()}
              className={styles.retryButton}
            >
              🔄 Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;