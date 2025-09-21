import React, { useEffect, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { apiService } from '../services/api';
import { JobStatus, ProgressUpdate } from '../types/api';
import styles from './ProgressDisplay.module.css';

interface ProgressDisplayProps {
  jobId: string;
  onComplete: () => void;
  onError: (error: string) => void;
}

const ProgressDisplay: React.FC<ProgressDisplayProps> = ({ jobId, onComplete, onError }) => {
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('Initializing...');
  const [status, setStatus] = useState<JobStatus>(JobStatus.PENDING);
  const [isProcessingStarted, setIsProcessingStarted] = useState(false);

  const handleMessage = (data: ProgressUpdate) => {
    setProgress(data.progress);
    setMessage(data.message);
    setStatus(data.status);

    if (data.status === JobStatus.COMPLETED) {
      onComplete();
    } else if (data.status === JobStatus.FAILED) {
      onError(data.message || 'Processing failed');
    }
  };

  const { isConnected, error } = useWebSocket({
    url: apiService.getWebSocketUrl(jobId),
    onMessage: handleMessage,
    onError: (event) => {
      console.error('WebSocket error:', event);
      onError('Connection error');
    }
  });

  useEffect(() => {
    if (isConnected && !isProcessingStarted) {
      // Auto-start processing when WebSocket connects
      apiService.startProcessing(jobId)
        .then(() => {
          setIsProcessingStarted(true);
          setMessage('Processing started...');
        })
        .catch((err) => {
          onError(`Failed to start processing: ${err.message}`);
        });
    }
  }, [isConnected, isProcessingStarted, jobId, onError]);

  const getStatusColor = () => {
    switch (status) {
      case JobStatus.COMPLETED:
        return '#28a745';
      case JobStatus.FAILED:
        return '#dc3545';
      case JobStatus.PROCESSING:
        return '#007bff';
      default:
        return '#6c757d';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case JobStatus.COMPLETED:
        return '✅';
      case JobStatus.FAILED:
        return '❌';
      case JobStatus.PROCESSING:
        return '⚙️';
      default:
        return '⏳';
    }
  };

  return (
    <div className={styles.progressContainer}>
      <div className={styles.statusHeader}>
        <span className={styles.statusIcon}>{getStatusIcon()}</span>
        <h3>Processing Bank Statement</h3>
      </div>

      <div className={styles.progressSection}>
        <div className={styles.progressBarContainer}>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill} 
              style={{ 
                width: `${progress}%`,
                backgroundColor: getStatusColor()
              }}
            ></div>
          </div>
          <div className={styles.progressText}>
            {progress}%
          </div>
        </div>

        <div className={styles.statusMessage}>
          {message}
        </div>

        <div className={styles.connectionStatus}>
          {error ? (
            <span className={styles.error}>❌ Connection Error</span>
          ) : (
            <span className={isConnected ? styles.connected : styles.disconnected}>
              {isConnected ? '🔗 Connected' : '🔌 Connecting...'}
            </span>
          )}
        </div>
      </div>

      {status === JobStatus.PROCESSING && (
        <div className={styles.processingAnimation}>
          <div className={styles.spinner}></div>
        </div>
      )}
    </div>
  );
};

export default ProgressDisplay;