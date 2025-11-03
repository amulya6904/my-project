import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface TransactionForCategorization {
  id: string;
  date: string;
  description: string;
  debit?: number;
  credit?: number;
}

export interface CategorizeRequest {
  fileId: string;
  bank: string;
  transactions: TransactionForCategorization[];
}

export interface CategoryMapping {
  id: string;
  category: string;
  confidence: number;
}

export interface CategorizeResponse {
  categories: CategoryMapping[];
}

class AIService {
  async categorizeTransactions(payload: CategorizeRequest): Promise<CategorizeResponse> {
    try {
      const response = await axios.post<CategorizeResponse>(
        `${API_BASE_URL}/api/ai/categorize`,
        payload,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
      return response.data;
    } catch (error: any) {
      console.error('AI categorization failed:', error);
      throw new Error(error.response?.data?.detail || 'Failed to categorize transactions');
    }
  }
}

export const aiService = new AIService();
