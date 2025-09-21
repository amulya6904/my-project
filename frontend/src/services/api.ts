import axios from 'axios';
import {
  UploadResponse,
  JobStatusResponse,
  ProcessingResponse,
  ErrorResponse
} from '../types/api';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ApiService {
  private token: string | null = null;

  constructor() {
    // Try to get token from localStorage
    this.token = localStorage.getItem('auth_token');
    
    // Set up axios defaults
    axios.defaults.baseURL = API_BASE_URL;
    
    // Add token to requests if available
    axios.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });

    // Handle token expiration
    axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          this.clearToken();
          window.location.reload();
        }
        return Promise.reject(error);
      }
    );
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
  }

  isAuthenticated(): boolean {
    return !!this.token;
  }

  async getDemoToken(): Promise<string> {
    try {
      const response = await axios.get('/demo-token');
      const token = response.data.access_token;
      this.setToken(token);
      return token;
    } catch (error) {
      console.error('Failed to get demo token:', error);
      throw error;
    }
  }

  async uploadFile(file: File): Promise<UploadResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post<UploadResponse>('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            console.log(`Upload progress: ${progress}%`);
          }
        },
      });

      return response.data;
    } catch (error: any) {
      console.error('Upload failed:', error);
      throw new Error(error.response?.data?.detail || 'Upload failed');
    }
  }

  async startProcessing(jobId: string, password?: string): Promise<void> {
    try {
      const data = password ? { password } : {};
      await axios.post(`/process/${jobId}`, data);
    } catch (error: any) {
      console.error('Processing start failed:', error);
      throw new Error(error.response?.data?.detail || 'Failed to start processing');
    }
  }

  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    try {
      const response = await axios.get<JobStatusResponse>(`/status/${jobId}`);
      return response.data;
    } catch (error: any) {
      console.error('Status check failed:', error);
      throw new Error(error.response?.data?.detail || 'Failed to get job status');
    }
  }

  async getResults(jobId: string): Promise<ProcessingResponse> {
    try {
      const response = await axios.get<ProcessingResponse>(`/results/${jobId}`);
      return response.data;
    } catch (error: any) {
      console.error('Results fetch failed:', error);
      throw new Error(error.response?.data?.detail || 'Failed to get results');
    }
  }

  getDownloadUrl(jobId: string): string {
    return `${API_BASE_URL}/download/${jobId}?token=${this.token}`;
  }

  getWebSocketUrl(jobId: string): string {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = API_BASE_URL.replace('http://', '').replace('https://', '');
    return `${wsProtocol}//${wsHost}/ws/progress/${jobId}`;
  }

  async cleanupJob(jobId: string): Promise<void> {
    try {
      await axios.delete(`/jobs/${jobId}`);
    } catch (error: any) {
      console.error('Job cleanup failed:', error);
      // Don't throw error for cleanup failures
    }
  }
}

export const apiService = new ApiService();