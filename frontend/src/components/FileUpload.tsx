import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { apiService } from '../services/api';
import { UploadResponse, JobStatus } from '../types/api';
import styles from './FileUpload.module.css';

interface FileUploadProps {
  onUploadSuccess: (response: UploadResponse) => void;
  onError: (error: string) => void;
  disabled?: boolean;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess, onError, disabled = false }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) {
      onError('No files selected');
      return;
    }

    const file = acceptedFiles[0];
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      onError('Please select a PDF file');
      return;
    }

    // Validate file size (50MB max)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      onError('File size must be less than 50MB');
      return;
    }

    try {
      setUploading(true);
      setUploadProgress(0);

      // Ensure we have a token
      if (!apiService.isAuthenticated()) {
        await apiService.getDemoToken();
      }

      const response = await apiService.uploadFile(file);

      if (response.status !== JobStatus.COMPLETED) {
        const errorMessage = response.error || 'Processing failed. Please try another statement.';
        onError(errorMessage);
        return;
      }

      onUploadSuccess(response);
    } catch (error: any) {
      onError(error.message || 'Upload failed');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  }, [onUploadSuccess, onError]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: false,
    disabled: disabled || uploading
  });

  return (
    <div className={styles.uploadContainer}>
      <div
        {...getRootProps()}
        className={`${styles.dropzone} ${isDragActive ? styles.active : ''} ${disabled || uploading ? styles.disabled : ''}`}
      >
        <input {...getInputProps()} />
        
        {uploading ? (
          <div className={styles.uploadProgress}>
            <div className={styles.spinner}></div>
            <p>Uploading PDF...</p>
            {uploadProgress > 0 && (
              <div className={styles.progressBar}>
                <div 
                  className={styles.progressFill} 
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            )}
          </div>
        ) : (
          <div className={styles.uploadContent}>
            <div className={styles.uploadIcon}>📄</div>
            <h3>Drop PDF bank statement here</h3>
            <p>or click to select file</p>
            <div className={styles.fileInfo}>
              <small>Supports: Union Bank, SBI • Max size: 50MB</small>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FileUpload;