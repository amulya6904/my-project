"""
Visualization module for transaction analysis reports.

This module provides comprehensive chart generation capabilities for spending
analysis including pie charts, bar charts, line graphs, and heatmaps using
matplotlib and seaborn with customizable styling and export options.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from decimal import Decimal
import warnings

# Suppress matplotlib warnings
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Patch
    import seaborn as sns
    import numpy as np
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False
    plt = None
    sns = None
    np = None

from .models import TransactionCategory, TrendDirection
from .analyzer import AnalysisReport
from .processors import CategorySummary, MonthlyBreakdown, TrendAnalysis


class VisualizationError(Exception):
    """Error in visualization generation."""
    pass


class SpendingVisualizer:
    """
    Comprehensive visualization generator for spending analysis.

    Creates publication-quality charts for financial analysis including
    category distributions, spending trends, and comparative analysis.
    """

    def __init__(self, style: str = "default", figsize: Tuple[float, float] = (12, 8)):
        """
        Initialize the visualizer.

        Args:
            style: Matplotlib/Seaborn style ("default", "dark", "minimal", "presentation")
            figsize: Default figure size as (width, height)

        Raises:
            VisualizationError: If visualization libraries are not available
        """
        if not HAS_VISUALIZATION:
            raise VisualizationError(
                "Visualization libraries not available. "
                "Install with: pip install matplotlib seaborn"
            )

        self.style = style
        self.figsize = figsize
        self.logger = logging.getLogger(self.__class__.__name__)

        # Configure plotting style
        self._setup_plotting_style()

        # Color schemes for different chart types
        self.color_schemes = {
            'category': ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
                        '#DDA0DD', '#98D8C8', '#FFA07A', '#F7DC6F', '#BB8FCE'],
            'trend_up': '#27AE60',
            'trend_down': '#E74C3C',
            'trend_stable': '#95A5A6',
            'trend_volatile': '#F39C12',
            'income': '#27AE60',
            'expense': '#E74C3C',
            'balance': '#3498DB'
        }

    def _setup_plotting_style(self) -> None:
        """Configure matplotlib and seaborn styling."""
        if self.style == "dark":
            plt.style.use('dark_background')
            sns.set_palette("bright")
        elif self.style == "minimal":
            sns.set_style("whitegrid")
            sns.set_palette("muted")
        elif self.style == "presentation":
            sns.set_style("white")
            sns.set_palette("deep")
        else:  # default
            sns.set_style("whitegrid")
            sns.set_palette("Set2")

        # Configure font and layout
        plt.rcParams.update({
            'figure.figsize': self.figsize,
            'font.size': 11,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 11,
            'figure.titlesize': 16
        })

    def create_category_pie_chart(
        self,
        category_summaries: Dict[TransactionCategory, CategorySummary],
        title: str = "Spending by Category",
        save_path: Optional[Path] = None,
        show_percentages: bool = True,
        min_percentage: float = 2.0
    ) -> Optional[Path]:
        """
        Create a pie chart showing spending distribution by category.

        Args:
            category_summaries: Category breakdown data
            title: Chart title
            save_path: Optional path to save chart
            show_percentages: Whether to show percentage labels
            min_percentage: Minimum percentage to show separately (others grouped)

        Returns:
            Optional[Path]: Path to saved chart if save_path provided
        """
        if not category_summaries:
            self.logger.warning("No category data provided for pie chart")
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        # Prepare data
        categories = []
        amounts = []
        colors = []
        total_amount = sum(summary.total_amount for summary in category_summaries.values())

        # Group small categories into "Others"
        other_amount = Decimal('0')
        other_categories = []

        for i, (category, summary) in enumerate(
            sorted(category_summaries.items(), key=lambda x: x[1].total_amount, reverse=True)
        ):
            percentage = float((summary.total_amount / total_amount) * 100)

            if percentage >= min_percentage or len(categories) < 5:  # Always show top 5
                categories.append(category.value)
                amounts.append(float(summary.total_amount))
                colors.append(self.color_schemes['category'][i % len(self.color_schemes['category'])])
            else:
                other_amount += summary.total_amount
                other_categories.append(category.value)

        # Add "Others" if there are grouped categories
        if other_amount > 0:
            categories.append(f"Others ({len(other_categories)})")
            amounts.append(float(other_amount))
            colors.append('#BDC3C7')

        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            amounts,
            labels=categories,
            colors=colors,
            autopct='%1.1f%%' if show_percentages else None,
            startangle=90,
            explode=[0.05] * len(amounts)  # Slight separation for all wedges
        )

        # Enhance text appearance
        if show_percentages:
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_weight('bold')
                autotext.set_fontsize(10)

        # Set title and styling
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)

        # Add legend with amounts
        legend_labels = [
            f"{cat}: ₹{amt:,.0f}" for cat, amt in zip(categories, amounts)
        ]
        ax.legend(legend_labels, loc='center left', bbox_to_anchor=(1, 0.5))

        plt.tight_layout()

        # Save if path provided
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Pie chart saved to {save_path}")

        plt.close()
        return save_path

    def create_monthly_bar_chart(
        self,
        monthly_breakdowns: List[MonthlyBreakdown],
        title: str = "Monthly Spending Comparison",
        save_path: Optional[Path] = None,
        show_top_categories: int = 5
    ) -> Optional[Path]:
        """
        Create a grouped bar chart showing monthly spending by category.

        Args:
            monthly_breakdowns: Monthly breakdown data
            title: Chart title
            save_path: Optional path to save chart
            show_top_categories: Number of top categories to show

        Returns:
            Optional[Path]: Path to saved chart if save_path provided
        """
        if not monthly_breakdowns:
            self.logger.warning("No monthly data provided for bar chart")
            return None

        fig, ax = plt.subplots(figsize=(max(len(monthly_breakdowns) * 2, 10), 8))

        # Find top categories across all months
        category_totals = {}
        for breakdown in monthly_breakdowns:
            for category, amount in breakdown.category_totals.items():
                category_totals[category] = category_totals.get(category, Decimal('0')) + amount

        top_categories = sorted(
            category_totals.keys(),
            key=lambda x: category_totals[x],
            reverse=True
        )[:show_top_categories]

        # Prepare data for plotting
        months = [breakdown.month.strftime('%b %Y') for breakdown in monthly_breakdowns]

        # Create data matrix
        data_matrix = []
        for category in top_categories:
            category_amounts = []
            for breakdown in monthly_breakdowns:
                amount = breakdown.category_totals.get(category, Decimal('0'))
                category_amounts.append(float(amount))
            data_matrix.append(category_amounts)

        # Create grouped bar chart
        x = np.arange(len(months))
        width = 0.8 / len(top_categories)

        for i, (category, amounts) in enumerate(zip(top_categories, data_matrix)):
            offset = (i - len(top_categories) / 2 + 0.5) * width
            bars = ax.bar(
                x + offset,
                amounts,
                width,
                label=category.value,
                color=self.color_schemes['category'][i % len(self.color_schemes['category'])],
                alpha=0.8
            )

            # Add value labels on bars
            for bar, amount in zip(bars, amounts):
                if amount > 0:
                    height = bar.get_height()
                    ax.annotate(f'₹{amount:,.0f}',
                               xy=(bar.get_x() + bar.get_width() / 2, height),
                               xytext=(0, 3),
                               textcoords="offset points",
                               ha='center', va='bottom',
                               fontsize=8, rotation=90)

        # Styling
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Month', fontsize=12, fontweight='bold')
        ax.set_ylabel('Amount (₹)', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=45, ha='right')

        # Format y-axis
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.0f}'))

        # Legend
        ax.legend(loc='upper left', bbox_to_anchor=(1, 1))

        # Grid
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        # Save if path provided
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Bar chart saved to {save_path}")

        plt.close()
        return save_path

    def create_spending_trend_line_chart(
        self,
        monthly_breakdowns: List[MonthlyBreakdown],
        category_trends: Optional[Dict[TransactionCategory, TrendAnalysis]] = None,
        title: str = "Spending Trends Over Time",
        save_path: Optional[Path] = None,
        show_categories: Optional[List[TransactionCategory]] = None
    ) -> Optional[Path]:
        """
        Create a line chart showing spending trends over time.

        Args:
            monthly_breakdowns: Monthly breakdown data
            category_trends: Optional trend analysis data
            title: Chart title
            save_path: Optional path to save chart
            show_categories: Specific categories to show (default: top 3)

        Returns:
            Optional[Path]: Path to saved chart if save_path provided
        """
        if not monthly_breakdowns:
            self.logger.warning("No monthly data provided for trend chart")
            return None

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10),
                                       gridspec_kw={'height_ratios': [3, 1]})

        # Determine categories to show
        if show_categories is None:
            # Find top 3 categories by total spending
            category_totals = {}
            for breakdown in monthly_breakdowns:
                for category, amount in breakdown.category_totals.items():
                    category_totals[category] = category_totals.get(category, Decimal('0')) + amount

            show_categories = sorted(
                category_totals.keys(),
                key=lambda x: category_totals[x],
                reverse=True
            )[:3]

        # Prepare data
        months = [breakdown.month for breakdown in monthly_breakdowns]
        month_labels = [breakdown.month.strftime('%b %Y') for breakdown in monthly_breakdowns]

        # Plot category trends
        for i, category in enumerate(show_categories):
            amounts = []
            for breakdown in monthly_breakdowns:
                amount = breakdown.category_totals.get(category, Decimal('0'))
                amounts.append(float(amount))

            color = self.color_schemes['category'][i % len(self.color_schemes['category'])]

            # Main trend line
            ax1.plot(months, amounts, marker='o', linewidth=2.5,
                    label=category.value, color=color, markersize=6)

            # Add trend direction indicator if available
            if category_trends and category in category_trends:
                trend = category_trends[category]
                if trend.direction == TrendDirection.INCREASING:
                    ax1.plot(months, amounts, linestyle='--', alpha=0.3, color=color)
                elif trend.direction == TrendDirection.DECREASING:
                    ax1.plot(months, amounts, linestyle=':', alpha=0.3, color=color)

        # Styling for main chart
        ax1.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax1.set_ylabel('Amount (₹)', fontsize=12, fontweight='bold')
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.0f}'))
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper left')

        # Format x-axis
        ax1.set_xticks(months[::max(1, len(months)//6)])  # Show at most 6 labels
        ax1.set_xticklabels([m.strftime('%b %Y') for m in months[::max(1, len(months)//6)]],
                           rotation=45, ha='right')

        # Plot total spending trend in subplot
        total_spending = [float(breakdown.total_spending) for breakdown in monthly_breakdowns]
        ax2.fill_between(months, total_spending, alpha=0.3, color=self.color_schemes['expense'])
        ax2.plot(months, total_spending, linewidth=2, color=self.color_schemes['expense'])

        ax2.set_title('Total Monthly Spending', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Total (₹)', fontsize=10)
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.0f}'))
        ax2.grid(True, alpha=0.3)

        # Format x-axis for subplot
        ax2.set_xticks(months[::max(1, len(months)//6)])
        ax2.set_xticklabels([m.strftime('%b %Y') for m in months[::max(1, len(months)//6)]],
                           rotation=45, ha='right')

        plt.tight_layout()

        # Save if path provided
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Trend chart saved to {save_path}")

        plt.close()
        return save_path

    def create_summary_dashboard(
        self,
        report: AnalysisReport,
        save_path: Optional[Path] = None,
        title: str = "Spending Analysis Dashboard"
    ) -> Optional[Path]:
        """
        Create a comprehensive dashboard with multiple visualizations.

        Args:
            report: Complete analysis report
            save_path: Optional path to save dashboard
            title: Dashboard title

        Returns:
            Optional[Path]: Path to saved dashboard if save_path provided
        """
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle(title, fontsize=20, fontweight='bold', y=0.95)

        # Create grid layout
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # 1. Category pie chart (top-left)
        ax1 = fig.add_subplot(gs[0, 0])
        if report.category_summaries:
            categories = list(report.category_summaries.keys())[:6]  # Top 6
            amounts = [float(report.category_summaries[cat].total_amount) for cat in categories]
            colors = self.color_schemes['category'][:len(categories)]

            wedges, texts, autotexts = ax1.pie(amounts, labels=[cat.value for cat in categories],
                                               colors=colors, autopct='%1.1f%%', startangle=90)
            ax1.set_title('Spending by Category', fontweight='bold')

        # 2. Monthly trend (top-middle and top-right)
        ax2 = fig.add_subplot(gs[0, 1:])
        if report.monthly_breakdowns:
            months = [b.month for b in report.monthly_breakdowns]
            amounts = [float(b.total_spending) for b in report.monthly_breakdowns]

            ax2.plot(months, amounts, marker='o', linewidth=2, color=self.color_schemes['expense'])
            ax2.fill_between(months, amounts, alpha=0.3, color=self.color_schemes['expense'])
            ax2.set_title('Monthly Spending Trend', fontweight='bold')
            ax2.set_ylabel('Amount (₹)')
            ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.0f}'))

        # 3. Top categories bar chart (middle row)
        ax3 = fig.add_subplot(gs[1, :])
        if report.top_spending_categories:
            categories = [cat.value for cat, _ in report.top_spending_categories[:8]]
            amounts = [float(amount) for _, amount in report.top_spending_categories[:8]]

            bars = ax3.barh(categories, amounts, color=self.color_schemes['category'][:len(categories)])
            ax3.set_title('Top Spending Categories', fontweight='bold')
            ax3.set_xlabel('Amount (₹)')
            ax3.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x:,.0f}'))

            # Add value labels
            for bar, amount in zip(bars, amounts):
                width = bar.get_width()
                ax3.text(width, bar.get_y() + bar.get_height()/2, f'₹{amount:,.0f}',
                        ha='left', va='center', fontweight='bold')

        # 4. Financial summary (bottom-left)
        ax4 = fig.add_subplot(gs[2, 0])
        ax4.axis('off')

        summary_text = f"""
Financial Summary
━━━━━━━━━━━━━━━
Total Income: ₹{report.total_income:,.0f}
Total Spending: ₹{report.total_spending:,.0f}
Net Amount: ₹{report.net_amount:,.0f}
Transactions: {report.total_transactions:,}

Period: {report.date_range.start_date.strftime('%b %Y')} - {report.date_range.end_date.strftime('%b %Y')}
Duration: {report.date_range.duration_days()} days
        """
        ax4.text(0.05, 0.95, summary_text.strip(), transform=ax4.transAxes, fontsize=10,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.5))

        # 5. Category insights (bottom-middle)
        ax5 = fig.add_subplot(gs[2, 1])
        ax5.axis('off')

        insights_text = "Top Category Insights\n━━━━━━━━━━━━━━━━━━\n"
        for i, (category, summary) in enumerate(list(report.category_summaries.items())[:5]):
            insights_text += f"{i+1}. {category.value}\n"
            insights_text += f"   ₹{summary.total_amount:,.0f} ({summary.percentage_of_total:.1f}%)\n"
            insights_text += f"   {summary.transaction_count} transactions\n\n"

        ax5.text(0.05, 0.95, insights_text.strip(), transform=ax5.transAxes, fontsize=9,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.5))

        # 6. Trend indicators (bottom-right)
        ax6 = fig.add_subplot(gs[2, 2])
        ax6.axis('off')

        trend_text = "Trend Analysis\n━━━━━━━━━━━━━\n"
        if report.category_trends:
            for category, trend in list(report.category_trends.items())[:4]:
                icon = {"increasing": "↗", "decreasing": "↘", "stable": "→", "volatile": "↕"}
                trend_icon = icon.get(trend.direction.value, "→")
                trend_text += f"{trend_icon} {category.value}\n"
                trend_text += f"   {trend.percentage_change:+.1f}%\n\n"

        ax6.text(0.05, 0.95, trend_text.strip(), transform=ax6.transAxes, fontsize=9,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.5))

        # Save if path provided
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Dashboard saved to {save_path}")

        plt.close()
        return save_path

    def generate_all_charts(
        self,
        report: AnalysisReport,
        output_dir: Union[str, Path],
        file_prefix: str = "spending_analysis"
    ) -> Dict[str, Path]:
        """
        Generate all chart types for a report.

        Args:
            report: Analysis report
            output_dir: Output directory for charts
            file_prefix: Prefix for chart filenames

        Returns:
            Dict[str, Path]: Mapping of chart type to saved path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_charts = {}

        try:
            # Category pie chart
            pie_path = output_dir / f"{file_prefix}_categories.png"
            saved_charts["pie"] = self.create_category_pie_chart(
                report.category_summaries, save_path=pie_path
            )

            # Monthly bar chart
            bar_path = output_dir / f"{file_prefix}_monthly.png"
            saved_charts["bar"] = self.create_monthly_bar_chart(
                report.monthly_breakdowns, save_path=bar_path
            )

            # Trend line chart
            trend_path = output_dir / f"{file_prefix}_trends.png"
            saved_charts["trend"] = self.create_spending_trend_line_chart(
                report.monthly_breakdowns, report.category_trends, save_path=trend_path
            )

            # Dashboard
            dashboard_path = output_dir / f"{file_prefix}_dashboard.png"
            saved_charts["dashboard"] = self.create_summary_dashboard(
                report, save_path=dashboard_path
            )

            self.logger.info(f"Generated {len(saved_charts)} charts in {output_dir}")

        except Exception as e:
            self.logger.error(f"Error generating charts: {e}")
            raise VisualizationError(f"Chart generation failed: {e}") from e

        return {k: v for k, v in saved_charts.items() if v is not None}