"""
Transaction Analysis Module

This module provides comprehensive transaction categorization and spending analysis
capabilities using LLM-powered categorization and advanced data processing.

Key Components:
- BaseCategorizer: Abstract interface for all categorizers
- GeminiCategorizer: Google Gemini AI implementation
- SpendingAnalyzer: Main analysis engine with CSV processing
- TransactionCache: SQLite-based caching system
- ConfigManager: TOML-based configuration management
- Data processors: Cleaning, aggregation, and trend analysis
- Comprehensive error handling and retry logic

Example Usage:
    ```python
    from src.analyzer import SpendingAnalyzer, GeminiCategorizer, ConfigManager, TransactionCache
    from pathlib import Path

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_config()

    # Initialize cache
    cache = TransactionCache()

    # Initialize categorizer with cache
    categorizer_config = config.get_categorizer_config()
    categorizer = GeminiCategorizer(categorizer_config, cache)

    # Initialize analyzer
    analyzer = SpendingAnalyzer(categorizer, cache, config)

    # Analyze CSV file
    transactions, report = analyzer.analyze_csv("bank_statement.csv")

    # Get insights
    insights = analyzer.get_spending_insights(report)
    print(f"Total spending: {insights['summary']['total_spending']}")
    print(f"Savings rate: {insights['summary']['savings_rate']:.1f}%")

    # Export report
    analyzer.export_report(report, "analysis_report.json")
    ```
"""

from .models import (
    # Core data models
    Transaction,
    CategorizationResult,
    BatchCategorizationResult,
    AnalysisStats,

    # Configuration
    CategorizerConfig,

    # Enums
    TransactionType,
    TransactionCategory,
    ConfidenceLevel
)

from .base_categorizer import (
    # Abstract base class
    BaseCategorizer,

    # Exceptions
    CategorizationError,
    APIError,
    ConfigError,
    RateLimitError
)

# Conditionally import GeminiCategorizer
try:
    from .gemini_categorizer import GeminiCategorizer
except ImportError:
    # GeminiCategorizer requires google.generativeai which may not be installed
    GeminiCategorizer = None

# Cache and configuration
from .cache import TransactionCache
from .config import ConfigManager, AnalyzerConfig, ProviderType

# Analysis engine and processors
from .analyzer import SpendingAnalyzer, AnalysisReport
from .processors import (
    CategorySummary,
    MonthlyBreakdown,
    TrendAnalysis,
    OutlierResult,
    DateRange,
    TrendDirection,
    TimeFrameType
)

# Visualization and reporting
from .visualizer import SpendingVisualizer, VisualizationError
from .templates import ReportFormatter
from .cli import AnalyzerCLI

# Public API
__all__ = [
    # Data models
    'Transaction',
    'CategorizationResult',
    'BatchCategorizationResult',
    'AnalysisStats',

    # Configuration
    'CategorizerConfig',
    'AnalyzerConfig',
    'ConfigManager',
    'ProviderType',

    # Enums
    'TransactionType',
    'TransactionCategory',
    'ConfidenceLevel',
    'TrendDirection',
    'TimeFrameType',

    # Abstract base
    'BaseCategorizer',

    # Implementations
    'GeminiCategorizer',

    # Cache
    'TransactionCache',

    # Analysis engine
    'SpendingAnalyzer',
    'AnalysisReport',

    # Processors and results
    'CategorySummary',
    'MonthlyBreakdown',
    'TrendAnalysis',
    'OutlierResult',
    'DateRange',

    # Visualization and reporting
    'SpendingVisualizer',
    'VisualizationError',
    'ReportFormatter',
    'AnalyzerCLI',

    # Exceptions
    'CategorizationError',
    'APIError',
    'ConfigError',
    'RateLimitError'
]

# Version info
__version__ = "0.1.0"
__author__ = "Bank Statement Processor Team"