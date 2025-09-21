export enum JobStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed"
}

export interface UploadResponse {
  job_id: string;
  filename: string;
  size: number;
  status: JobStatus;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  message?: string;
  error?: string;
  created_at: string;
  completed_at?: string;
}

export interface TransactionData {
  date: string;
  description: string;
  reference?: string;
  debit?: number;
  credit?: number;
  balance: number;
  transaction_type: string;
  counterparty?: string;
}

export interface ProcessingResponse {
  job_id: string;
  status: JobStatus;
  transactions: TransactionData[];
  count: number;
  bank: string;
  csv_url?: string;
  error?: string;
}

export interface ProgressUpdate {
  job_id: string;
  progress: number;
  message: string;
  status: JobStatus;
}

export interface ErrorResponse {
  error: string;
  detail?: string;
  job_id?: string;
}