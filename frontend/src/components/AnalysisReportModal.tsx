import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import { AnalyzeResponse, Transaction } from '../services/simpleApi';

interface AnalysisReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  transactions: Transaction[];
  aiAnalysis: AnalyzeResponse | null;
}

interface InsightSummary {
  pros: string[];
  cons: string[];
  recommendations: string[];
}

const COLORS = ['#0ea5e9', '#a855f7', '#f97316', '#22c55e', '#ef4444', '#14b8a6'];

const formatDateLabel = (dateStr: string) => {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) {
    return dateStr;
  }
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

const generateFallbackInsights = (transactions: Transaction[]): InsightSummary => {
  const totalIncome = transactions.reduce((sum, txn) => sum + (txn.credit || 0), 0);
  const totalExpense = transactions.reduce((sum, txn) => sum + (txn.debit || 0), 0);
  const balanceTrend = totalIncome - totalExpense;

  const pros: string[] = [];
  const cons: string[] = [];
  const recommendations: string[] = [];

  if (totalIncome > 0) {
    pros.push(`Consistent income inflow of ${totalIncome.toFixed(2)} detected.`);
  }
  if (totalExpense < totalIncome) {
    pros.push('Spending is within your income range, indicating positive cash flow.');
  }

  if (totalExpense > totalIncome) {
    cons.push('Expenses exceed income which could lead to negative cash flow.');
    recommendations.push('Review discretionary spending categories and set monthly limits.');
  }

  const highestExpense = transactions.reduce<{ category: string; amount: number } | null>((highest, txn) => {
    const amount = txn.debit || 0;
    if (!amount) return highest;
    const category = txn.ai_category || txn.transaction_type || 'Others';
    if (!highest || amount > highest.amount) {
      return { category, amount };
    }
    return highest;
  }, null);

  if (highestExpense) {
    recommendations.push(`Monitor spending in "${highestExpense.category}" which had the single highest transaction.`);
  }

  if (balanceTrend > 0) {
    pros.push('You are saving more than you spend this period.');
    recommendations.push('Consider allocating surplus funds to investments or an emergency fund.');
  }

  if (cons.length === 0) {
    cons.push('No significant overspending patterns detected. Maintain current habits.');
  }

  if (recommendations.length === 0) {
    recommendations.push('Continue tracking your expenses and set category-based budgets to stay on course.');
  }

  return { pros, cons, recommendations };
};

const AnalysisReportModal: React.FC<AnalysisReportModalProps> = ({
  isOpen,
  onClose,
  transactions,
  aiAnalysis
}) => {
  const spendingByDate = useMemo(() => {
    const aggregation = transactions.reduce<Record<string, number>>((acc, txn) => {
      if (!txn.date) return acc;
      const dateKey = new Date(txn.date).toISOString().slice(0, 10);
      const amount = txn.debit || 0;
      acc[dateKey] = (acc[dateKey] || 0) + amount;
      return acc;
    }, {});

    return Object.entries(aggregation)
      .map(([date, amount]) => ({ date, amount: Number(amount.toFixed(2)) }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  }, [transactions]);

  const spendingByCategory = useMemo(() => {
    const aggregation = transactions.reduce<Record<string, number>>((acc, txn) => {
      const category = txn.ai_category || txn.transaction_type || (txn.credit ? 'Income' : 'Others');
      const amount = txn.debit || txn.credit || 0;
      acc[category] = (acc[category] || 0) + amount;
      return acc;
    }, {});

    return Object.entries(aggregation).map(([name, value]) => ({
      name,
      value: Number(value.toFixed(2))
    }));
  }, [transactions]);

  const insightSummary: InsightSummary = useMemo(() => {
    if (aiAnalysis?.insights) {
      return aiAnalysis.insights;
    }
    return generateFallbackInsights(transactions);
  }, [aiAnalysis, transactions]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h3 className="text-xl font-semibold text-slate-900">AI Analysis Report</h3>
          <button
            onClick={onClose}
            className="rounded-full border border-slate-200 px-3 py-1 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
          >
            Close
          </button>
        </div>

        <div className="grid gap-6 px-6 py-6 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h4 className="mb-3 text-base font-semibold text-slate-800">Daily Expenditure</h4>
            {spendingByDate.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={spendingByDate}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" />
                  <XAxis dataKey="date" tickFormatter={formatDateLabel} tick={{ fill: '#475569' }} />
                  <YAxis tick={{ fill: '#475569' }} />
                  <Tooltip
                    formatter={(value: number) => [`₹${value.toLocaleString()}`, 'Spent']}
                    labelFormatter={(label) => formatDateLabel(label)}
                  />
                  <Line type="monotone" dataKey="amount" stroke="#2563eb" strokeWidth={3} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-slate-500">No expenditure data available.</p>
            )}
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h4 className="mb-3 text-base font-semibold text-slate-800">Spending by Category</h4>
            {spendingByCategory.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={spendingByCategory} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100}>
                    {spendingByCategory.map((entry, index) => (
                      <Cell key={`cell-${entry.name}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, name: string) => [`₹${Number(value).toLocaleString()}`, name]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-slate-500">No category data available.</p>
            )}
          </div>
        </div>

        <div className="border-t border-slate-200 bg-slate-50 px-6 py-6">
          <div className="grid gap-6 md:grid-cols-3">
            <div>
              <h5 className="mb-2 text-sm font-semibold uppercase tracking-wide text-emerald-600">Pros</h5>
              <ul className="space-y-2 text-sm text-slate-600">
                {insightSummary.pros.map((item, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="mt-1 inline-flex h-2 w-2 flex-none rounded-full bg-emerald-400"></span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h5 className="mb-2 text-sm font-semibold uppercase tracking-wide text-rose-600">Cons</h5>
              <ul className="space-y-2 text-sm text-slate-600">
                {insightSummary.cons.map((item, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="mt-1 inline-flex h-2 w-2 flex-none rounded-full bg-rose-400"></span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h5 className="mb-2 text-sm font-semibold uppercase tracking-wide text-indigo-600">Recommendations</h5>
              <ul className="space-y-2 text-sm text-slate-600">
                {insightSummary.recommendations.map((item, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="mt-1 inline-flex h-2 w-2 flex-none rounded-full bg-indigo-400"></span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalysisReportModal;
