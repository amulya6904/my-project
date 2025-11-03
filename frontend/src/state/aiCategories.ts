import { useState, useCallback } from 'react';
import { aiService, CategoryMapping, TransactionForCategorization } from '../services/ai';

export type AICategory = {
  id: string;
  category: string;
  confidence: number;
};

export type AICategoryState = {
  byId: Record<string, AICategory>;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error?: string;
};

export const useAICategories = () => {
  const [state, setState] = useState<AICategoryState>({
    byId: {},
    status: 'idle',
    error: undefined,
  });

  const fetchForFile = useCallback(async (
    fileId: string,
    bank: string,
    transactions: TransactionForCategorization[]
  ) => {
    setState(prev => ({ ...prev, status: 'loading', error: undefined }));

    try {
      const response = await aiService.categorizeTransactions({
        fileId,
        bank,
        transactions,
      });

      // Convert array to byId mapping
      const byId: Record<string, AICategory> = {};
      response.categories.forEach(category => {
        byId[category.id] = category;
      });

      setState({
        byId,
        status: 'ready',
        error: undefined,
      });
    } catch (error: any) {
      setState(prev => ({
        ...prev,
        status: 'error',
        error: error.message || 'Failed to categorize transactions',
      }));
    }
  }, []);

  const clearCategories = useCallback(() => {
    setState({
      byId: {},
      status: 'idle',
      error: undefined,
    });
  }, []);

  return {
    ...state,
    fetchForFile,
    clearCategories,
  };
};
