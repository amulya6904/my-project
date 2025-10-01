import React, { useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Line
} from 'recharts';
import type { AnalyzeResponse, Transaction } from '../services/simpleApi';

interface LocationState {
  transactions?: Transaction[];
  aiSummary?: AnalyzeResponse['summary'];
  aiCategories?: AnalyzeResponse['categories'];
}

const PIE_COLORS = [
  '#2563eb',
  '#10b981',
  '#f97316',
  '#8b5cf6',
  '#ec4899',
  '#0ea5e9',
  '#facc15',
  '#64748b'
];

const CATEGORY_MATCHERS = [
  { label: 'Income', keywords: ['income', 'salary', 'credit', 'deposit', 'refund'] },
  { label: 'Shopping', keywords: ['shopping', 'retail', 'amazon', 'flipkart', 'store', 'mall'] },
  { label: 'Food & Dining', keywords: ['food', 'dining', 'restaurant', 'cafe', 'eatery', 'swiggy', 'zomato'] },
  { label: 'Transportation', keywords: ['fuel', 'transport', 'metro', 'uber', 'ola', 'flight', 'travel'] },
  { label: 'Utilities & Bills', keywords: ['utility', 'bill', 'electric', 'water', 'phone', 'internet', 'recharge'] },
  { label: 'Healthcare', keywords: ['medical', 'hospital', 'pharmacy', 'health', 'clinic'] },
  { label: 'Entertainment', keywords: ['movie', 'entertainment', 'netflix', 'prime', 'hotstar', 'subscription'] },
  { label: 'Savings & Investments', keywords: ['investment', 'mutual', 'sip', 'fixed', 'rd', 'fd', 'insurance'] }
];

const normalizeNumber = (value: number | string | null | undefined): number => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0;
  }

  if (typeof value === 'string') {
    const parsed = parseFloat(value.replace(/[,\s]/g, ''));
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  return 0;
};

const inferCategory = (transaction: Transaction): string => {
  if (transaction.ai_category) {
    return transaction.ai_category;
  }

  const sourceText = `${transaction.transaction_type || ''} ${transaction.description || ''}`.toLowerCase();

  if (normalizeNumber(transaction.credit) > 0 || sourceText.includes('income')) {
    return 'Income';
  }

  for (const matcher of CATEGORY_MATCHERS) {
    if (matcher.keywords.some((keyword) => sourceText.includes(keyword))) {
      return matcher.label;
    }
  }

  return 'Others';
};

const formatCurrency = (value: number): string =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value);

const ReportPage: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { transactions = [], aiSummary } = (state || {}) as LocationState;

  useEffect(() => {
    if (!transactions || transactions.length === 0) {
      navigate('/', { replace: true });
    }
  }, [transactions, navigate]);

  const totalTransactions = transactions.length;
  const categorizedTransactions = useMemo(
    () => transactions.filter((txn) => Boolean(txn.ai_category)).length,
    [transactions]
  );

  const dailyExpenditureData = useMemo(() => {
    const totalsByDate = new Map<string, number>();

    transactions.forEach((txn) => {
      if (!txn.date) {
        return;
      }

      const parsed = new Date(txn.date);
      if (Number.isNaN(parsed.getTime())) {
        return;
      }

      const key = parsed.toISOString().split('T')[0];
      const spent = normalizeNumber(txn.debit);

      if (spent <= 0) {
        return;
      }

      totalsByDate.set(key, (totalsByDate.get(key) || 0) + spent);
    });

    return Array.from(totalsByDate.entries())
      .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
      .map(([date, total]) => ({
        date,
        label: new Date(date).toLocaleDateString('en-IN', {
          month: 'short',
          day: 'numeric'
        }),
        totalSpent: Math.round((total + Number.EPSILON) * 100) / 100
      }));
  }, [transactions]);

  const categoryDistributionData = useMemo(() => {
    const categoryTotals = new Map<string, number>();

    transactions.forEach((txn) => {
      const category = inferCategory(txn);
      const amount = category === 'Income'
        ? normalizeNumber(txn.credit)
        : normalizeNumber(txn.debit) || Math.abs(Math.min(normalizeNumber(txn.credit), 0));

      if (amount <= 0) {
        return;
      }

      categoryTotals.set(category, (categoryTotals.get(category) || 0) + amount);
    });

    return Array.from(categoryTotals.entries())
      .map(([name, value]) => ({
        name,
        value: Math.round((value + Number.EPSILON) * 100) / 100
      }))
      .sort((a, b) => b.value - a.value);
  }, [transactions]);

  const insights = useMemo(() => {
    if (!aiSummary) {
      return {
        pros: [],
        cons: [],
        recommendations: []
      };
    }

    const pros: string[] = [];
    const cons: string[] = [];
    const recommendations: string[] = [];

    if (aiSummary.categorization_rate !== undefined) {
      if (aiSummary.categorization_rate >= 80) {
        pros.push(`AI categorized ${aiSummary.categorization_rate.toFixed(1)}% of transactions accurately.`);
      } else {
        cons.push(
          `Only ${aiSummary.categorization_rate.toFixed(1)}% of transactions were confidently categorized.`
        );
        recommendations.push('Review uncategorized entries to improve future AI insights.');
      }
    }

    if (aiSummary.top_categories && aiSummary.top_categories.length > 0) {
      const categoryNames = aiSummary.top_categories
        .slice(0, 3)
        .map((item) => `${item.category} (${item.percentage.toFixed(1)}%)`)
        .join(', ');

      pros.push(`Top spending areas identified: ${categoryNames}.`);

      const primaryCategory = aiSummary.top_categories[0];
      if (primaryCategory) {
        recommendations.push(
          `Set a budget alert for ${primaryCategory.category} which accounts for ${primaryCategory.percentage.toFixed(1)}% of tracked spend.`
        );
      }
    }

    if (aiSummary.total_amount && aiSummary.total_amount > 0) {
      pros.push(`Total amount analyzed: ${formatCurrency(aiSummary.total_amount)}.`);
    }

    if (categorizedTransactions < totalTransactions) {
      cons.push(
        `${totalTransactions - categorizedTransactions} transaction${
          totalTransactions - categorizedTransactions === 1 ? '' : 's'
        } need manual categorization.`
      );
    }

    if (aiSummary.provider_used) {
      pros.push(`Insights generated with ${aiSummary.provider_used}.`);
    }

    if (recommendations.length === 0 && totalTransactions > 0) {
      recommendations.push('Maintain consistent narration details to keep AI categorizations precise.');
    }

    return { pros, cons, recommendations };
  }, [aiSummary, categorizedTransactions, totalTransactions]);

  if (!transactions || transactions.length === 0) {
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-100 py-10 px-4">
      <div className="mx-auto flex max-w-6xl flex-col gap-10">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-indigo-500">AI insights</p>
            <h1 className="text-3xl font-bold text-slate-800">Analysis Report</h1>
            <p className="text-sm text-slate-500">Comprehensive view of your categorized transactions</p>
          </div>
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center justify-center rounded-full bg-white px-4 py-2 text-sm font-medium text-indigo-600 shadow hover:bg-indigo-50"
          >
            ← Back to dashboard
          </button>
        </header>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl bg-white/90 p-4 shadow">
            <p className="text-xs uppercase tracking-wider text-slate-400">Transactions analyzed</p>
            <p className="mt-2 text-2xl font-semibold text-slate-800">{totalTransactions}</p>
          </div>
          <div className="rounded-2xl bg-white/90 p-4 shadow">
            <p className="text-xs uppercase tracking-wider text-slate-400">AI categorized</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-600">{categorizedTransactions}</p>
            <p className="text-xs text-slate-500">
              {totalTransactions > 0
                ? `${Math.round((categorizedTransactions / totalTransactions) * 100)}% coverage`
                : 'No data'}
            </p>
          </div>
          <div className="rounded-2xl bg-white/90 p-4 shadow">
            <p className="text-xs uppercase tracking-wider text-slate-400">Top category</p>
            <p className="mt-2 text-2xl font-semibold text-indigo-600">
              {categoryDistributionData[0]?.name || 'N/A'}
            </p>
            {categoryDistributionData[0] && (
              <p className="text-xs text-slate-500">
                {formatCurrency(categoryDistributionData[0].value)} spent
              </p>
            )}
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-3xl border border-indigo-50 bg-white/80 p-6 shadow">
            <h2 className="mb-4 text-lg font-semibold text-slate-700">Daily expenditure</h2>
            <div className="h-72">
              {dailyExpenditureData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dailyExpenditureData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="label" stroke="#6b7280" />
                    <YAxis stroke="#6b7280" />
                    <Tooltip
                      formatter={(value: number) => formatCurrency(value)}
                      labelFormatter={(value) => value}
                    />
                    <Line type="monotone" dataKey="totalSpent" stroke="#4f46e5" strokeWidth={3} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-2xl bg-slate-50 text-sm text-slate-500">
                  No expenditure data available
                </div>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-indigo-50 bg-white/80 p-6 shadow">
            <h2 className="mb-4 text-lg font-semibold text-slate-700">Spending by category</h2>
            <div className="h-72">
              {categoryDistributionData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={categoryDistributionData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {categoryDistributionData.map((entry, index) => (
                        <Cell key={`slice-${entry.name}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name) => [formatCurrency(value), name as string]}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-2xl bg-slate-50 text-sm text-slate-500">
                  No category distribution available
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="space-y-6 rounded-3xl border border-dashed border-indigo-200 bg-white/70 p-6 shadow">
          <div className="flex flex-col gap-2">
            <h2 className="text-lg font-semibold text-slate-700">AI summary</h2>
            {aiSummary?.provider_used && (
              <p className="text-xs uppercase tracking-wide text-indigo-500">
                Generated by {aiSummary.provider_used}
              </p>
            )}
            {!aiSummary && (
              <p className="text-sm text-slate-500">
                Run the AI analysis on the dashboard to unlock pros, cons, and personalized recommendations.
              </p>
            )}
          </div>

          {aiSummary && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-emerald-600">Pros</h3>
                <ul className="list-inside list-disc space-y-2 text-sm text-slate-600">
                  {insights.pros.length > 0 ? (
                    insights.pros.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li className="italic text-slate-400">No pros detected yet.</li>
                  )}
                </ul>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-rose-600">Cons</h3>
                <ul className="list-inside list-disc space-y-2 text-sm text-slate-600">
                  {insights.cons.length > 0 ? (
                    insights.cons.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li className="italic text-slate-400">No concerns flagged.</li>
                  )}
                </ul>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-indigo-600">Recommendations</h3>
                <ul className="list-inside list-disc space-y-2 text-sm text-slate-600">
                  {insights.recommendations.length > 0 ? (
                    insights.recommendations.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li className="italic text-slate-400">No recommendations available.</li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default ReportPage;
