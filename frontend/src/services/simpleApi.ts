import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface Transaction {
  date: string | null;
  description: string;
  reference: string | null;
  debit: number | null;
  credit: number | null;
  balance: number | null;
  transaction_type: string;
  counterparty: string | null;
  bank_name: string;
  account_number: string;
  // AI categorization fields
  ai_category?: string;
  ai_confidence?: string;
  ai_reasoning?: string;
}

export interface CategoryResult {
  category: string;
  confidence: string;
  reasoning: string;
}

export interface AnalyzeRequest {
  transactions: {
    id: string;
    description: string;
    amount: number;
    transaction_type: string;
    date: string;
  }[];
  provider?: string;
}

export interface AnalyzeResponse {
  success: boolean;
  categories: { [key: string]: CategoryResult };
  summary?: {
    total_transactions: number;
    total_amount: number;
    categorization_rate: number;
    top_categories: Array<{
      category: string;
      amount: number;
      percentage: number;
    }>;
    provider_used: string;
  };
  error?: string;
}

export interface TextSummaryResponse {
  totalIncome: number;
  totalExpenditure: number;
  suggestions: string;
}

export interface ProcessingResult {
  success: boolean;
  filename?: string;
  bank?: string;
  transactions?: Transaction[];
  count?: number;
  message?: string;
  error?: string;
  details?: string;
  supported_banks?: string[];
}

class SimpleApiService {
  constructor() {
    // Set up axios defaults
    axios.defaults.baseURL = API_BASE_URL;

    // Set a longer timeout for file processing
    axios.defaults.timeout = 60000; // 60 seconds
  }

  async uploadAndProcessPdf(file: File, password?: string): Promise<ProcessingResult> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      if (password) {
        formData.append('password', password);
      }

      const response = await axios.post<ProcessingResult>('/api/upload', formData, {
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
      console.error('Upload and processing failed:', error);

      // Handle different types of errors
      if (error.response?.data) {
        return error.response.data;
      }

      return {
        success: false,
        error: 'network_error',
        message: 'Failed to connect to server',
        details: error.message
      };
    }
  }

  async checkHealth(): Promise<{ status: string; message: string }> {
    try {
      const response = await axios.get('/health');
      return response.data;
    } catch (error: any) {
      console.error('Health check failed:', error);
      throw new Error('Server is not responding');
    }
  }

  async getServerInfo(): Promise<any> {
    try {
      const response = await axios.get('/');
      return response.data;
    } catch (error: any) {
      console.error('Failed to get server info:', error);
      throw error;
    }
  }

  async analyzeTransactions(transactions: Transaction[], provider: string = 'mock'): Promise<AnalyzeResponse> {
    try {
      const analysisRequest: AnalyzeRequest = {
        transactions: transactions.map((txn, index) => ({
          id: `txn_${index}`,
          description: txn.description,
          amount: txn.debit ? -txn.debit : (txn.credit || 0),
          transaction_type: txn.transaction_type,
          date: txn.date || new Date().toISOString()
        })),
        provider
      };

      const response = await axios.post<AnalyzeResponse>('/api/analyze', analysisRequest, {
        timeout: 60000 // 60 seconds for AI analysis
      });

      return response.data;
    } catch (error: any) {
      console.error('AI analysis failed:', error);

      if (error.response?.data) {
        return error.response.data;
      }

      return {
        success: false,
        categories: {},
        error: 'Failed to analyze transactions'
      };
    }
  }

  async generateTextSummary(transactions: Transaction[], provider: string = 'mock'): Promise<TextSummaryResponse> {
    try {
      // Compute totals and category breakdown from the same dataset used across the UI
      const toNumber = (v: number | string | null | undefined): number => {
        if (v === null || v === undefined) return 0;
        if (typeof v === 'number') return isFinite(v) ? v : 0;
        if (typeof v === 'string') {
          const parsed = parseFloat(v.replace(/[,\s]/g, ''));
          return isNaN(parsed) ? 0 : parsed;
        }
        return 0;
      };

      let totalIncome = 0;
      let totalExpenditure = 0;
      const categoryAccumulator: Record<string, number> = {};

      transactions.forEach((t) => {
        const debit = Math.max(0, toNumber(t.debit as any));
        const credit = Math.max(0, toNumber(t.credit as any));
        const category = (t.ai_category || (t as any).category || 'Others') as string;

        // Income is positive inflow (credits)
        totalIncome += credit;

        // Expenditure is outflow (debits)
        totalExpenditure += debit;

        // Track category-wise spend (expenditure only)
        if (debit > 0) {
          categoryAccumulator[category] = (categoryAccumulator[category] || 0) + debit;
        }
      });

      const payload = {
        provider,
        totals: {
          total_income: Math.round((totalIncome + Number.EPSILON) * 100) / 100,
          total_expenditure: Math.round((totalExpenditure + Number.EPSILON) * 100) / 100,
          potential_savings:
            Math.round(((totalIncome - totalExpenditure) + Number.EPSILON) * 100) / 100,
        },
        category_breakdown: categoryAccumulator,
        // Also include light transaction sample (optional) for additional context
        transactions: transactions.map((t) => ({
          date: t.date,
          debit: t.debit,
          credit: t.credit,
          category: t.ai_category || (t as any).category || null,
          description: t.description,
        })),
      };

      const response = await axios.post<TextSummaryResponse>('/analyze/summary', payload, {
        timeout: 60000
      });
      return response.data;
    } catch (error: any) {
      console.error('LLM summary generation failed:', error);
      throw error;
    }
  }
}

export const simpleApiService = new SimpleApiService();