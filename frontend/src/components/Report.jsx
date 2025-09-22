import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';

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

const normalizeNumber = (value) => {
  if (typeof value === 'number') {
    return isFinite(value) ? value : 0;
  }

  if (typeof value === 'string') {
    const parsed = parseFloat(value.replace(/[,\s]/g, ''));
    return isNaN(parsed) ? 0 : parsed;
  }

  return 0;
};

const inferCategory = (transaction) => {
  const sourceText = `${(transaction.ai_category || '')} ${(transaction.transaction_type || '')} ${(transaction.description || '')}`.toLowerCase();

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

const Report = ({ transactions = [] }) => {
  const safeTransactions = useMemo(
    () => (Array.isArray(transactions) ? transactions : []),
    [transactions]
  );

  const dailyExpenditureData = useMemo(() => {
    const totalsByDate = new Map();

    safeTransactions.forEach((txn) => {
      const dateValue = txn?.date ? new Date(txn.date) : null;

      if (!dateValue || Number.isNaN(dateValue.getTime())) {
        return;
      }

      const key = dateValue.toISOString().split('T')[0];
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
  }, [safeTransactions]);

  const categoryDistributionData = useMemo(() => {
    const categoryTotals = new Map();

    safeTransactions.forEach((txn) => {
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
      .map(([name, value]) => ({ name, value: Math.round((value + Number.EPSILON) * 100) / 100 }))
      .sort((a, b) => b.value - a.value);
  }, [safeTransactions]);

  const totalTransactions = safeTransactions.length;

  return (
    <section className="w-full space-y-8 rounded-3xl bg-gradient-to-br from-white/90 to-white/60 p-6 shadow-xl backdrop-blur">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-800">Analysis Report</h2>
          <p className="text-sm text-gray-500">Visual overview of your spending patterns</p>
        </div>
        <span className="text-sm font-medium text-indigo-500">
          {totalTransactions > 0 ? `${totalTransactions} transactions analyzed` : 'No transactions available'}
        </span>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-indigo-50 bg-white/80 p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold text-gray-700">Daily Expenditure</h3>
          <div className="h-64">
            {dailyExpenditureData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyExpenditureData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="label" stroke="#6b7280" />
                  <YAxis stroke="#6b7280" />
                  <Tooltip
                    formatter={(value) =>
                      new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value)
                    }
                  />
                  <Line type="monotone" dataKey="totalSpent" stroke="#4f46e5" strokeWidth={3} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-500">
                No expenditure data available
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-indigo-50 bg-white/80 p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold text-gray-700">Spending by Category</h3>
          <div className="h-64">
            {categoryDistributionData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categoryDistributionData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={2}
                  >
                    {categoryDistributionData.map((entry, index) => (
                      <Cell key={`slice-${entry.name}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value, name) => [
                      new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value),
                      name
                    ]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-500">
                No category distribution available
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-dashed border-indigo-200 bg-white/70 p-6">
        <h3 className="mb-4 text-lg font-semibold text-gray-700">Summary (AI-generated insights coming soon)</h3>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div>
            <h4 className="mb-2 text-base font-semibold text-emerald-600">Pros</h4>
            <ul className="list-inside list-disc space-y-2 text-sm text-gray-600">
              <li className="italic text-gray-400">Awaiting insights from AI assistant.</li>
            </ul>
          </div>
          <div>
            <h4 className="mb-2 text-base font-semibold text-rose-600">Cons</h4>
            <ul className="list-inside list-disc space-y-2 text-sm text-gray-600">
              <li className="italic text-gray-400">Awaiting insights from AI assistant.</li>
            </ul>
          </div>
          <div>
            <h4 className="mb-2 text-base font-semibold text-indigo-600">Recommendations</h4>
            <ul className="list-inside list-disc space-y-2 text-sm text-gray-600">
              <li className="italic text-gray-400">Awaiting insights from AI assistant.</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Report;
