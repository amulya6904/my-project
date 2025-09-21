"""
Report template system for transaction analysis.

This module provides comprehensive report generation capabilities including
text summaries, markdown exports, JSON exports, and HTML reports with
customizable templates and formatting options.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal
from dataclasses import asdict

from .analyzer import AnalysisReport
from .models import TransactionCategory, ConfidenceLevel
from .processors import TrendDirection, CategorySummary, MonthlyBreakdown


class ReportFormatter:
    """
    Comprehensive report formatter with multiple output formats.

    Supports text, markdown, JSON, and HTML report generation with
    customizable templates and styling options.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def generate_text_summary(self, report: AnalysisReport, detailed: bool = False) -> str:
        """
        Generate a text summary report.

        Args:
            report: Analysis report
            detailed: Whether to include detailed breakdowns

        Returns:
            str: Formatted text report
        """
        lines = []
        lines.append("=" * 60)
        lines.append("BANK STATEMENT ANALYSIS REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Basic summary
        lines.append("FINANCIAL SUMMARY")
        lines.append("-" * 20)
        lines.append(f"Analysis Period: {report.date_range.start_date.strftime('%b %d, %Y')} - {report.date_range.end_date.strftime('%b %d, %Y')}")
        lines.append(f"Duration: {report.date_range.duration_days()} days")
        lines.append(f"Total Transactions: {report.total_transactions:,}")
        lines.append("")
        lines.append(f"Total Income:    ₹{report.total_income:>12,.2f}")
        lines.append(f"Total Spending:  ₹{report.total_spending:>12,.2f}")
        lines.append(f"Net Amount:      ₹{report.net_amount:>12,.2f}")

        # Calculate savings rate
        if report.total_income > 0:
            savings_rate = float((report.net_amount / report.total_income) * 100)
            lines.append(f"Savings Rate:    {savings_rate:>12.1f}%")
        lines.append("")

        # Top spending categories
        lines.append("TOP SPENDING CATEGORIES")
        lines.append("-" * 25)
        for i, (category, amount) in enumerate(report.top_spending_categories[:10], 1):
            percentage = float((amount / report.total_spending) * 100) if report.total_spending > 0 else 0
            lines.append(f"{i:2d}. {category.value:<25} ₹{amount:>10,.2f} ({percentage:>5.1f}%)")
        lines.append("")

        if detailed:
            # Monthly breakdown
            lines.append("MONTHLY BREAKDOWN")
            lines.append("-" * 18)
            for breakdown in report.monthly_breakdowns[-6:]:  # Last 6 months
                month_str = breakdown.month.strftime('%b %Y')
                lines.append(f"{month_str:<10} ₹{breakdown.total_spending:>12,.2f} ({breakdown.transaction_count:>3d} txns)")
            lines.append("")

            # Categorization quality
            lines.append("CATEGORIZATION QUALITY")
            lines.append("-" * 23)
            cat_stats = report.categorization_stats
            lines.append(f"Categorization Rate: {cat_stats.get('categorization_rate', 0):.1f}%")
            lines.append(f"Total Categorized: {cat_stats.get('total_categorized', 0):,}")

            confidence_breakdown = cat_stats.get('confidence_breakdown', {})
            if confidence_breakdown:
                lines.append("Confidence Distribution:")
                for confidence, count in confidence_breakdown.items():
                    lines.append(f"  {confidence:<8}: {count:>6,}")
            lines.append("")

            # Trend analysis
            if report.category_trends:
                lines.append("SPENDING TRENDS")
                lines.append("-" * 15)
                trend_icons = {
                    "increasing": "↗ UP  ",
                    "decreasing": "↘ DOWN",
                    "stable": "→ FLAT",
                    "volatile": "↕ VLTL"
                }

                for category, trend in list(report.category_trends.items())[:8]:
                    icon = trend_icons.get(trend.direction.value, "→ FLAT")
                    lines.append(f"{icon} {category.value:<20} {trend.percentage_change:>+6.1f}%")
                lines.append("")

            # Outliers
            if report.outliers:
                lines.append("UNUSUAL TRANSACTIONS")
                lines.append("-" * 20)
                high_outliers = [o for o in report.outliers if o.outlier_type == "high"][:5]
                for outlier in high_outliers:
                    txn = outlier.transaction
                    lines.append(f"₹{abs(txn.amount):>8,.2f} - {txn.description[:35]}")
                    lines.append(f"          {txn.date.strftime('%b %d')} | Z-score: {outlier.z_score:.1f}")
                lines.append("")

        # Cache performance
        if report.cache_stats:
            lines.append("CACHE PERFORMANCE")
            lines.append("-" * 17)
            cache_stats = report.cache_stats
            if isinstance(cache_stats, dict):
                hit_rate = cache_stats.get('hit_rate', 0)
                lines.append(f"Cache Hit Rate: {hit_rate:.1f}%")
                lines.append(f"Total Entries: {cache_stats.get('entries_count', 0):,}")
            lines.append("")

        lines.append("=" * 60)
        lines.append(f"Report generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        lines.append("Generated by Bank Statement Analyzer")
        lines.append("=" * 60)

        return "\n".join(lines)

    def generate_markdown_report(
        self,
        report: AnalysisReport,
        include_charts: bool = False,
        chart_dir: Optional[str] = None
    ) -> str:
        """
        Generate a markdown report.

        Args:
            report: Analysis report
            include_charts: Whether to include chart references
            chart_dir: Directory containing charts (relative path)

        Returns:
            str: Markdown formatted report
        """
        md = []

        # Title and metadata
        md.append("# Bank Statement Analysis Report")
        md.append("")
        md.append(f"**Analysis Period:** {report.date_range.start_date.strftime('%B %d, %Y')} - {report.date_range.end_date.strftime('%B %d, %Y')}")
        md.append(f"**Duration:** {report.date_range.duration_days()} days")
        md.append(f"**Total Transactions:** {report.total_transactions:,}")
        md.append(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        md.append("")

        # Executive Summary
        md.append("## Executive Summary")
        md.append("")

        savings_rate = float((report.net_amount / report.total_income) * 100) if report.total_income > 0 else 0
        md.append("| Metric | Amount |")
        md.append("|--------|--------|")
        md.append(f"| Total Income | ₹{report.total_income:,.2f} |")
        md.append(f"| Total Spending | ₹{report.total_spending:,.2f} |")
        md.append(f"| Net Amount | ₹{report.net_amount:,.2f} |")
        md.append(f"| Savings Rate | {savings_rate:.1f}% |")
        md.append("")

        # Charts section
        if include_charts and chart_dir:
            md.append("## Visual Analysis")
            md.append("")

            chart_files = [
                ("spending_analysis_dashboard.png", "Complete Dashboard", "Comprehensive overview of spending patterns"),
                ("spending_analysis_categories.png", "Category Distribution", "Spending breakdown by category"),
                ("spending_analysis_monthly.png", "Monthly Comparison", "Month-to-month spending comparison"),
                ("spending_analysis_trends.png", "Spending Trends", "Spending trends over time")
            ]

            for filename, title, description in chart_files:
                chart_path = f"{chart_dir}/{filename}" if chart_dir else filename
                md.append(f"### {title}")
                md.append(f"{description}")
                md.append(f"![{title}]({chart_path})")
                md.append("")

        # Top Categories
        md.append("## Top Spending Categories")
        md.append("")
        md.append("| Rank | Category | Amount | Percentage |")
        md.append("|------|----------|--------|------------|")

        for i, (category, amount) in enumerate(report.top_spending_categories[:10], 1):
            percentage = float((amount / report.total_spending) * 100) if report.total_spending > 0 else 0
            md.append(f"| {i} | {category.value} | ₹{amount:,.2f} | {percentage:.1f}% |")
        md.append("")

        # Monthly Analysis
        md.append("## Monthly Analysis")
        md.append("")
        md.append("| Month | Total Spending | Transactions | Avg per Transaction |")
        md.append("|-------|----------------|--------------|---------------------|")

        for breakdown in report.monthly_breakdowns[-12:]:  # Last 12 months
            month_str = breakdown.month.strftime('%b %Y')
            avg_txn = breakdown.average_transaction
            md.append(f"| {month_str} | ₹{breakdown.total_spending:,.2f} | {breakdown.transaction_count} | ₹{avg_txn:,.2f} |")
        md.append("")

        # Detailed Category Analysis
        md.append("## Detailed Category Analysis")
        md.append("")

        for category, summary in sorted(
            report.category_summaries.items(),
            key=lambda x: x[1].total_amount,
            reverse=True
        )[:8]:
            md.append(f"### {category.value}")
            md.append("")
            md.append(f"- **Total Amount:** ₹{summary.total_amount:,.2f}")
            md.append(f"- **Transactions:** {summary.transaction_count}")
            md.append(f"- **Average:** ₹{summary.average_amount:,.2f}")
            md.append(f"- **Range:** ₹{summary.min_amount:,.2f} - ₹{summary.max_amount:,.2f}")
            md.append(f"- **Percentage of Total:** {summary.percentage_of_total:.1f}%")

            if summary.top_merchants:
                md.append("- **Top Merchants:**")
                for merchant, count, amount in summary.top_merchants[:3]:
                    md.append(f"  - {merchant}: ₹{amount:,.2f} ({count} transactions)")
            md.append("")

        # Trend Analysis
        if report.category_trends:
            md.append("## Spending Trends")
            md.append("")
            md.append("| Category | Trend | Change | Correlation |")
            md.append("|----------|-------|--------|-------------|")

            trend_emojis = {
                "increasing": "📈",
                "decreasing": "📉",
                "stable": "➡️",
                "volatile": "📊"
            }

            for category, trend in report.category_trends.items():
                emoji = trend_emojis.get(trend.direction.value, "➡️")
                md.append(f"| {category.value} | {emoji} {trend.direction.value.title()} | {trend.percentage_change:+.1f}% | {trend.correlation_coefficient:.2f} |")
            md.append("")

        # Quality Metrics
        md.append("## Analysis Quality")
        md.append("")
        cat_stats = report.categorization_stats
        md.append(f"- **Categorization Rate:** {cat_stats.get('categorization_rate', 0):.1f}%")
        md.append(f"- **Successfully Categorized:** {cat_stats.get('total_categorized', 0):,} transactions")

        confidence_breakdown = cat_stats.get('confidence_breakdown', {})
        if confidence_breakdown:
            md.append("- **Confidence Distribution:**")
            for confidence, count in confidence_breakdown.items():
                md.append(f"  - {confidence}: {count:,} transactions")
        md.append("")

        # Outliers
        if report.outliers:
            md.append("## Unusual Transactions")
            md.append("")
            md.append("Transactions identified as statistical outliers (Z-score > 2.5):")
            md.append("")
            md.append("| Date | Description | Amount | Z-Score |")
            md.append("|------|-------------|--------|---------|")

            high_outliers = [o for o in report.outliers if o.outlier_type == "high"][:10]
            for outlier in high_outliers:
                txn = outlier.transaction
                md.append(f"| {txn.date.strftime('%b %d')} | {txn.description[:30]}... | ₹{abs(txn.amount):,.2f} | {outlier.z_score:.1f} |")
            md.append("")

        # Footer
        md.append("---")
        md.append("*Generated by Bank Statement Analyzer*")
        md.append("")

        return "\n".join(md)

    def generate_json_export(self, report: AnalysisReport) -> str:
        """
        Generate a JSON export of the analysis report.

        Args:
            report: Analysis report

        Returns:
            str: JSON formatted report
        """
        try:
            # Use the report's built-in to_dict method
            report_dict = report.to_dict()

            # Add metadata
            report_dict['export_metadata'] = {
                'format_version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'generator': 'Bank Statement Analyzer'
            }

            return json.dumps(report_dict, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Error generating JSON export: {e}")
            # Fallback to basic export
            basic_export = {
                'error': str(e),
                'basic_summary': {
                    'total_transactions': report.total_transactions,
                    'total_spending': str(report.total_spending),
                    'total_income': str(report.total_income),
                    'net_amount': str(report.net_amount),
                    'date_range': {
                        'start': report.date_range.start_date.isoformat(),
                        'end': report.date_range.end_date.isoformat()
                    }
                }
            }
            return json.dumps(basic_export, indent=2)

    def generate_html_report(
        self,
        report: AnalysisReport,
        template_style: str = "modern",
        include_charts: bool = True,
        chart_dir: Optional[str] = None
    ) -> str:
        """
        Generate an HTML report with embedded styling.

        Args:
            report: Analysis report
            template_style: Style theme ("modern", "minimal", "dark")
            include_charts: Whether to include chart images
            chart_dir: Directory containing charts

        Returns:
            str: HTML formatted report
        """
        # CSS styles for different themes
        styles = {
            "modern": """
                <style>
                body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }
                h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
                h2 { color: #34495e; border-left: 4px solid #3498db; padding-left: 15px; }
                .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
                .summary-card { background: #ecf0f1; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background: #3498db; color: white; }
                .chart-container { text-align: center; margin: 30px 0; }
                .positive { color: #27ae60; font-weight: bold; }
                .negative { color: #e74c3c; font-weight: bold; }
                .neutral { color: #95a5a6; }
                </style>
            """,
            "minimal": """
                <style>
                body { font-family: Georgia, serif; line-height: 1.8; margin: 40px; color: #333; }
                h1 { border-bottom: 2px solid #333; }
                h2 { color: #555; }
                table { border: 1px solid #ddd; }
                th { background: #f9f9f9; }
                .summary-grid { display: flex; flex-wrap: wrap; gap: 20px; }
                .summary-card { border: 1px solid #ddd; padding: 15px; flex: 1; min-width: 200px; }
                </style>
            """,
            "dark": """
                <style>
                body { font-family: 'Consolas', monospace; background: #2c3e50; color: #ecf0f1; margin: 20px; }
                .container { background: #34495e; padding: 30px; border-radius: 5px; }
                h1 { color: #3498db; }
                h2 { color: #e74c3c; }
                table { background: #2c3e50; }
                th { background: #1abc9c; }
                .summary-card { background: #2c3e50; border: 1px solid #3498db; }
                </style>
            """
        }

        html = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "<title>Bank Statement Analysis Report</title>",
            styles.get(template_style, styles["modern"]),
            "</head>",
            "<body>",
            "<div class='container'>"
        ]

        # Header
        html.append(f"<h1>Bank Statement Analysis Report</h1>")
        html.append(f"<p><strong>Period:</strong> {report.date_range.start_date.strftime('%B %d, %Y')} - {report.date_range.end_date.strftime('%B %d, %Y')}</p>")
        html.append(f"<p><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>")

        # Summary cards
        html.append("<h2>Financial Summary</h2>")
        html.append("<div class='summary-grid'>")

        savings_rate = float((report.net_amount / report.total_income) * 100) if report.total_income > 0 else 0
        net_class = "positive" if report.net_amount >= 0 else "negative"

        cards = [
            ("Total Income", f"₹{report.total_income:,.2f}", "positive"),
            ("Total Spending", f"₹{report.total_spending:,.2f}", "negative"),
            ("Net Amount", f"₹{report.net_amount:,.2f}", net_class),
            ("Savings Rate", f"{savings_rate:.1f}%", net_class),
            ("Transactions", f"{report.total_transactions:,}", "neutral")
        ]

        for title, value, css_class in cards:
            html.append(f"<div class='summary-card'>")
            html.append(f"<h3>{title}</h3>")
            html.append(f"<p class='{css_class}' style='font-size: 1.5em;'>{value}</p>")
            html.append("</div>")

        html.append("</div>")

        # Charts
        if include_charts and chart_dir:
            html.append("<h2>Visual Analysis</h2>")

            chart_files = [
                ("spending_analysis_dashboard.png", "Complete Dashboard"),
                ("spending_analysis_categories.png", "Category Distribution"),
                ("spending_analysis_trends.png", "Spending Trends")
            ]

            for filename, title in chart_files:
                chart_path = f"{chart_dir}/{filename}" if chart_dir else filename
                html.append(f"<div class='chart-container'>")
                html.append(f"<h3>{title}</h3>")
                html.append(f"<img src='{chart_path}' alt='{title}' style='max-width: 100%; height: auto;'>")
                html.append("</div>")

        # Top categories table
        html.append("<h2>Top Spending Categories</h2>")
        html.append("<table>")
        html.append("<tr><th>Rank</th><th>Category</th><th>Amount</th><th>Percentage</th><th>Transactions</th></tr>")

        for i, (category, amount) in enumerate(report.top_spending_categories[:10], 1):
            percentage = float((amount / report.total_spending) * 100) if report.total_spending > 0 else 0
            txn_count = report.category_summaries.get(category, type('obj', (object,), {'transaction_count': 0})).transaction_count
            html.append(f"<tr>")
            html.append(f"<td>{i}</td>")
            html.append(f"<td>{category.value}</td>")
            html.append(f"<td>₹{amount:,.2f}</td>")
            html.append(f"<td>{percentage:.1f}%</td>")
            html.append(f"<td>{txn_count}</td>")
            html.append("</tr>")

        html.append("</table>")

        # Monthly breakdown
        html.append("<h2>Monthly Breakdown</h2>")
        html.append("<table>")
        html.append("<tr><th>Month</th><th>Total Spending</th><th>Transactions</th><th>Average per Transaction</th></tr>")

        for breakdown in report.monthly_breakdowns[-12:]:
            month_str = breakdown.month.strftime('%B %Y')
            html.append("<tr>")
            html.append(f"<td>{month_str}</td>")
            html.append(f"<td>₹{breakdown.total_spending:,.2f}</td>")
            html.append(f"<td>{breakdown.transaction_count}</td>")
            html.append(f"<td>₹{breakdown.average_transaction:,.2f}</td>")
            html.append("</tr>")

        html.append("</table>")

        # Footer
        html.extend([
            "<hr>",
            "<p style='text-align: center; color: #7f8c8d;'><em>Generated by Bank Statement Analyzer</em></p>",
            "</div>",
            "</body>",
            "</html>"
        ])

        return "\n".join(html)

    def export_report(
        self,
        report: AnalysisReport,
        output_path: Union[str, Path],
        format_type: str = "text",
        **kwargs
    ) -> None:
        """
        Export report to file in specified format.

        Args:
            report: Analysis report
            output_path: Output file path
            format_type: Export format ("text", "markdown", "json", "html")
            **kwargs: Additional format-specific arguments

        Raises:
            ValueError: If format type is unsupported
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if format_type.lower() == "text":
                content = self.generate_text_summary(report, **kwargs)
            elif format_type.lower() == "markdown":
                content = self.generate_markdown_report(report, **kwargs)
            elif format_type.lower() == "json":
                content = self.generate_json_export(report)
            elif format_type.lower() == "html":
                content = self.generate_html_report(report, **kwargs)
            else:
                raise ValueError(f"Unsupported format type: {format_type}")

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"Report exported to {output_path} in {format_type} format")

        except Exception as e:
            self.logger.error(f"Failed to export report: {e}")
            raise