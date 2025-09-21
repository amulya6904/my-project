"""
Command-line interface for bank statement analysis.

This module provides a comprehensive CLI for the bank statement analyzer
with progress tracking, multiple output formats, and batch processing
capabilities.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
import click
from decimal import Decimal

# Progress bar support
try:
    from tqdm import tqdm
    HAS_PROGRESS_BAR = True
except ImportError:
    HAS_PROGRESS_BAR = False
    tqdm = None

from .analyzer import SpendingAnalyzer, AnalysisReport, CSVParsingError
from .cache import TransactionCache
from .config import ConfigManager, ConfigError, ProviderType
# Conditionally import GeminiCategorizer
try:
    from .gemini_categorizer import GeminiCategorizer
except ImportError:
    GeminiCategorizer = None
from .mock_categorizer import MockCategorizer
from .visualizer import SpendingVisualizer, VisualizationError, HAS_VISUALIZATION
from .templates import ReportFormatter
from .processors import DateRange
from .base_categorizer import CategorizationError, APIError
from contextlib import contextmanager


class AnalyzerCLI:
    """
    Command-line interface for the bank statement analyzer.

    Provides comprehensive CLI functionality with progress tracking,
    multiple output formats, and batch processing capabilities.
    """

    def __init__(self):
        self.logger = self._setup_logging()
        self.config_manager = None
        self.config = None

    def _setup_logging(self, level: str = "INFO") -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        return logging.getLogger(self.__class__.__name__)

    def _load_config(self, config_file: Optional[Path] = None, skip_validation: bool = False) -> None:
        """Load configuration from file."""
        try:
            self.config_manager = ConfigManager(config_file)
            if skip_validation:
                # For mock provider, skip validation
                self.config = self.config_manager._config
                self.logger.info("Configuration loaded (validation skipped for mock provider)")
            else:
                self.config = self.config_manager.load_config(create_if_missing=True)
                self.logger.info("Configuration loaded successfully")
        except ConfigError as e:
            click.echo(f"Configuration error: {e}", err=True)
            sys.exit(1)

    def _create_analyzer_components(
        self,
        provider: Optional[str] = None,
        use_cache: bool = True,
        cache_file: Optional[Path] = None
    ) -> Tuple[SpendingAnalyzer, Optional[TransactionCache]]:
        """Create analyzer and cache components."""
        # Initialize cache if requested
        cache = None
        if use_cache and self.config.cache.enabled:
            try:
                cache_path = cache_file or self.config.cache.cache_file
                cache = TransactionCache(
                    cache_file=cache_path,
                    max_age_days=self.config.cache.max_age_days,
                    max_entries=self.config.cache.max_entries,
                    cleanup_interval_hours=self.config.cache.cleanup_interval_hours
                )
                self.logger.info("Cache initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize cache: {e}")
                cache = None

        # Determine provider
        if provider:
            try:
                provider_type = ProviderType(provider.lower())
            except ValueError:
                if provider.lower() == 'mock':
                    provider_type = 'mock'
                else:
                    raise ValueError(f"Unknown provider: {provider}")
        else:
            provider_type = self.config.default_provider

        # Check if provider is available
        if provider_type != 'mock' and not self.config_manager.is_provider_available(provider_type):
            available = [p.value for p in self.config.providers.keys()
                        if self.config_manager.is_provider_available(p)]
            raise ValueError(
                f"Provider '{provider_type.value}' is not available. "
                f"Available providers: {', '.join(available)}"
            )

        # Create categorizer
        if provider_type == 'mock':
            # Create minimal config for mock provider
            from .models import CategorizerConfig
            categorizer_config = CategorizerConfig(
                api_key="mock_key",
                model_name="mock-model",
                temperature=0.1,
                max_retries=1,
                retry_delay=0.1,
                batch_size=10,
                timeout_seconds=5
            )
            categorizer = MockCategorizer(categorizer_config)
        else:
            categorizer_config = self.config.get_categorizer_config(provider_type)
            if provider_type == ProviderType.GEMINI:
                if GeminiCategorizer is None:
                    raise ValueError("GeminiCategorizer not available - missing google.generativeai dependency")
                categorizer = GeminiCategorizer(categorizer_config, cache)
            else:
                # Future: Add support for other providers
                raise ValueError(f"Provider '{provider_type.value}' not yet implemented")

        # Create analyzer
        analyzer = SpendingAnalyzer(categorizer, cache, self.config)

        return analyzer, cache

    def _parse_date_range(self, date_range: Optional[str]) -> Optional[DateRange]:
        """Parse date range string."""
        if not date_range:
            return None

        try:
            if "to" in date_range.lower():
                start_str, end_str = date_range.split("to", 1)
            elif "," in date_range:
                start_str, end_str = date_range.split(",", 1)
            else:
                raise ValueError("Date range format should be 'YYYY-MM-DD to YYYY-MM-DD'")

            start_date = datetime.strptime(start_str.strip(), '%Y-%m-%d')
            end_date = datetime.strptime(end_str.strip(), '%Y-%m-%d')

            return DateRange(start_date, end_date)

        except ValueError as e:
            raise ValueError(f"Invalid date range format: {e}")

    @contextmanager
    def _show_progress(self, description: str, total: Optional[int] = None):
        """Create progress bar if available."""
        if HAS_PROGRESS_BAR and total:
            with tqdm(total=total, desc=description, unit="transactions") as pbar:
                yield pbar
        else:
            click.echo(f"{description}...")
            yield None

    def analyze_single_file(
        self,
        csv_file: Path,
        output_dir: Path,
        provider: Optional[str] = None,
        config_file: Optional[Path] = None,
        date_range: Optional[str] = None,
        output_formats: List[str] = None,
        generate_charts: bool = True,
        use_cache: bool = True,
        cache_file: Optional[Path] = None,
        verbose: bool = False
    ) -> bool:
        """
        Analyze a single CSV file.

        Args:
            csv_file: Path to CSV file
            output_dir: Output directory
            provider: LLM provider to use
            config_file: Configuration file path
            date_range: Date range filter
            output_formats: List of output formats
            generate_charts: Whether to generate charts
            use_cache: Whether to use caching
            cache_file: Cache file path
            verbose: Verbose logging

        Returns:
            bool: Success status
        """
        if verbose:
            self.logger.setLevel(logging.DEBUG)

        try:
            # Load configuration (skip for mock provider)
            if provider != 'mock':
                self._load_config(config_file)
            else:
                # Create minimal config for mock provider
                from .config import AnalyzerConfig, CacheConfig, ProviderType
                self.config = AnalyzerConfig()
                self.logger.info("Using minimal config for mock provider")

            # Parse date range
            parsed_date_range = self._parse_date_range(date_range)

            # Create analyzer components
            analyzer, cache = self._create_analyzer_components(provider, use_cache, cache_file)

            # Analyze CSV
            click.echo(f"Analyzing {csv_file.name}...")

            with self._show_progress("Processing transactions", None) as pbar:
                transactions, report = analyzer.analyze_csv(
                    csv_file,
                    date_range=parsed_date_range,
                    categorize=True,
                    generate_report=True
                )

            if not report:
                click.echo("Analysis failed - no report generated", err=True)
                return False

            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate reports
            self._generate_reports(report, output_dir, output_formats or ["text"])

            # Generate charts
            if generate_charts and HAS_VISUALIZATION:
                self._generate_charts(report, output_dir)

            # Print summary
            self._print_summary(report)

            click.echo(f"✓ Analysis completed. Results saved to {output_dir}")
            return True

        except (CSVParsingError, CategorizationError, ConfigError) as e:
            click.echo(f"Error: {e}", err=True)
            return False
        except Exception as e:
            self.logger.exception("Unexpected error during analysis")
            click.echo(f"Unexpected error: {e}", err=True)
            return False

    def analyze_batch(
        self,
        csv_files: List[Path],
        output_dir: Path,
        provider: Optional[str] = None,
        config_file: Optional[Path] = None,
        date_range: Optional[str] = None,
        output_formats: List[str] = None,
        generate_charts: bool = True,
        use_cache: bool = True,
        cache_file: Optional[Path] = None,
        verbose: bool = False
    ) -> bool:
        """
        Analyze multiple CSV files in batch.

        Args:
            csv_files: List of CSV files
            output_dir: Output directory
            provider: LLM provider to use
            config_file: Configuration file path
            date_range: Date range filter
            output_formats: List of output formats
            generate_charts: Whether to generate charts
            use_cache: Whether to use caching
            cache_file: Cache file path
            verbose: Verbose logging

        Returns:
            bool: Success status
        """
        if verbose:
            self.logger.setLevel(logging.DEBUG)

        success_count = 0
        total_files = len(csv_files)

        try:
            # Load configuration once
            self._load_config(config_file)

            # Parse date range
            parsed_date_range = self._parse_date_range(date_range)

            # Create analyzer components once
            analyzer, cache = self._create_analyzer_components(provider, use_cache, cache_file)

            click.echo(f"Processing {total_files} files...")

            # Process each file
            with self._show_progress("Files processed", total_files) as pbar:
                for i, csv_file in enumerate(csv_files, 1):
                    try:
                        click.echo(f"\n[{i}/{total_files}] Processing {csv_file.name}")

                        # Analyze CSV
                        transactions, report = analyzer.analyze_csv(
                            csv_file,
                            date_range=parsed_date_range,
                            categorize=True,
                            generate_report=True
                        )

                        if report:
                            # Create file-specific output directory
                            file_output_dir = output_dir / csv_file.stem
                            file_output_dir.mkdir(parents=True, exist_ok=True)

                            # Generate reports
                            self._generate_reports(report, file_output_dir, output_formats or ["text"])

                            # Generate charts
                            if generate_charts and HAS_VISUALIZATION:
                                self._generate_charts(report, file_output_dir)

                            success_count += 1
                            click.echo(f"  ✓ Success - {len(transactions)} transactions analyzed")
                        else:
                            click.echo(f"  ✗ Failed - no report generated")

                    except Exception as e:
                        click.echo(f"  ✗ Error: {e}")
                        continue

                    finally:
                        if pbar:
                            pbar.update(1)

            # Generate combined summary
            if success_count > 0:
                self._generate_batch_summary(output_dir, success_count, total_files)

            click.echo(f"\nBatch processing completed:")
            click.echo(f"  Successful: {success_count}/{total_files}")
            click.echo(f"  Results saved to: {output_dir}")

            return success_count > 0

        except Exception as e:
            self.logger.exception("Unexpected error during batch processing")
            click.echo(f"Batch processing failed: {e}", err=True)
            return False

    def validate_configuration(
        self,
        provider: Optional[str] = None,
        config_file: Optional[Path] = None,
        verbose: bool = False
    ) -> bool:
        """
        Validate the analyzer configuration and API connectivity.
        """
        if verbose:
            self.logger.setLevel(logging.DEBUG)

        click.echo("🔍 Validating analyzer configuration...")

        try:
            # Load configuration
            self._load_config(config_file)
            click.echo("  ✓ Configuration file loaded successfully.")

            # Determine provider
            provider_name = provider or self.config.default_provider.value
            click.echo(f"  ℹ️  Using provider: {provider_name}")

            # Create components to trigger validation
            analyzer, _ = self._create_analyzer_components(provider_name, use_cache=False)
            click.echo("  ✓ Categorizer initialized.")

            # Perform health check
            click.echo("  - Performing health check...")
            health = analyzer.categorizer.health_check()

            if health.get('api_accessible'):
                click.echo("  ✓ API health check successful.")
            else:
                click.echo(f"  ✗ API health check failed: {health.get('error', 'Unknown error')}", err=True)
                return False
            
            click.echo("\n✅ Configuration is valid and API is accessible.")
            return True

        except (ConfigError, CategorizationError, ValueError) as e:
            click.echo(f"\n❌ Validation failed: {e}", err=True)
            return False
        except Exception as e:
            self.logger.exception("Unexpected error during validation")
            click.echo(f"\n❌ Unexpected error: {e}", err=True)
            return False

    def _generate_reports(self, report: AnalysisReport, output_dir: Path, formats: List[str]) -> None:
        """Generate reports in specified formats."""
        formatter = ReportFormatter()

        for fmt in formats:
            try:
                if fmt.lower() == "text":
                    output_file = output_dir / "analysis_report.txt"
                    formatter.export_report(report, output_file, "text", detailed=True)

                elif fmt.lower() == "markdown":
                    output_file = output_dir / "analysis_report.md"
                    formatter.export_report(
                        report, output_file, "markdown",
                        include_charts=True, chart_dir="charts"
                    )

                elif fmt.lower() == "html":
                    output_file = output_dir / "analysis_report.html"
                    formatter.export_report(
                        report, output_file, "html",
                        template_style="modern", include_charts=True, chart_dir="charts"
                    )

                elif fmt.lower() == "json":
                    output_file = output_dir / "analysis_report.json"
                    formatter.export_report(report, output_file, "json")

                else:
                    self.logger.warning(f"Unknown format: {fmt}")

            except Exception as e:
                self.logger.error(f"Failed to generate {fmt} report: {e}")

    def _generate_charts(self, report: AnalysisReport, output_dir: Path) -> None:
        """Generate visualization charts."""
        try:
            visualizer = SpendingVisualizer()
            charts_dir = output_dir / "charts"
            charts_dir.mkdir(exist_ok=True)

            saved_charts = visualizer.generate_all_charts(report, charts_dir)
            self.logger.info(f"Generated {len(saved_charts)} charts")

        except VisualizationError as e:
            self.logger.warning(f"Chart generation failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error generating charts: {e}")

    def _print_summary(self, report: AnalysisReport) -> None:
        """Print analysis summary to console."""
        click.echo("\n" + "=" * 50)
        click.echo("ANALYSIS SUMMARY")
        click.echo("=" * 50)

        # Basic metrics
        click.echo(f"Total Transactions: {report.total_transactions:,}")
        click.echo(f"Total Income:       ₹{report.total_income:,.2f}")
        click.echo(f"Total Spending:     ₹{report.total_spending:,.2f}")
        click.echo(f"Net Amount:         ₹{report.net_amount:,.2f}")

        if report.total_income > 0:
            savings_rate = float((report.net_amount / report.total_income) * 100)
            click.echo(f"Savings Rate:       {savings_rate:.1f}%")

        # Top categories
        if report.top_spending_categories:
            click.echo(f"\nTop 3 Spending Categories:")
            for i, (category, amount) in enumerate(report.top_spending_categories[:3], 1):
                percentage = float((amount / report.total_spending) * 100) if report.total_spending > 0 else 0
                click.echo(f"  {i}. {category.value}: ₹{amount:,.2f} ({percentage:.1f}%)")

        # Categorization quality
        cat_stats = report.categorization_stats
        click.echo(f"\nCategorization Rate: {cat_stats.get('categorization_rate', 0):.1f}%")

        # Cache performance
        if report.cache_stats:
            cache_stats = report.cache_stats
            if isinstance(cache_stats, dict):
                hit_rate = cache_stats.get('hit_rate', 0)
                click.echo(f"Cache Hit Rate:     {hit_rate:.1f}%")

    def _generate_batch_summary(self, output_dir: Path, success_count: int, total_count: int) -> None:
        """Generate batch processing summary."""
        summary_file = output_dir / "batch_summary.txt"

        with open(summary_file, 'w') as f:
            f.write("BATCH PROCESSING SUMMARY\n")
            f.write("=" * 30 + "\n\n")
            f.write(f"Processing Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Files: {total_count}\n")
            f.write(f"Successful: {success_count}\n")
            f.write(f"Failed: {total_count - success_count}\n")
            f.write(f"Success Rate: {(success_count/total_count)*100:.1f}%\n\n")

            # List processed directories
            f.write("Processed Files:\n")
            f.write("-" * 15 + "\n")
            for item in output_dir.iterdir():
                if item.is_dir() and item.name != "charts":
                    f.write(f"  {item.name}/\n")


# Click CLI Commands
@click.group(name="analyze")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Configuration file path")
@click.pass_context
def cli(ctx, verbose, config):
    """Bank statement analysis commands."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config'] = config
    ctx.obj['cli'] = AnalyzerCLI()


@cli.command()
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), default="analysis_output", help="Output directory")
@click.option("--provider", "-p", type=click.Choice(["gemini", "mock"]), help="LLM provider")
@click.option("--date-range", "-d", help="Date range (YYYY-MM-DD to YYYY-MM-DD)")
@click.option("--format", "-f", "formats", multiple=True, type=click.Choice(["text", "markdown", "html", "json"]), default=["text"], help="Output formats")
@click.option("--no-charts", is_flag=True, help="Skip chart generation")
@click.option("--no-cache", is_flag=True, help="Disable caching")
@click.option("--cache-file", type=click.Path(path_type=Path), help="Custom cache file path")
@click.pass_context
def single(ctx, csv_file, output, provider, date_range, formats, no_charts, no_cache, cache_file):
    """Analyze a single CSV file."""
    cli_instance = ctx.obj['cli']
    success = cli_instance.analyze_single_file(
        csv_file=csv_file,
        output_dir=output,
        provider=provider,
        config_file=ctx.obj['config'],
        date_range=date_range,
        output_formats=list(formats),
        generate_charts=not no_charts,
        use_cache=not no_cache,
        cache_file=cache_file,
        verbose=ctx.obj['verbose']
    )
    sys.exit(0 if success else 1)


@cli.command()
@click.argument("csv_files", nargs=-1, type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", "-o", type=click.Path(path_type=Path), default="batch_analysis", help="Output directory")
@click.option("--provider", "-p", type=click.Choice(["gemini", "mock"]), help="LLM provider")
@click.option("--date-range", "-d", help="Date range (YYYY-MM-DD to YYYY-MM-DD)")
@click.option("--format", "-f", "formats", multiple=True, type=click.Choice(["text", "markdown", "html", "json"]), default=["text"], help="Output formats")
@click.option("--no-charts", is_flag=True, help="Skip chart generation")
@click.option("--no-cache", is_flag=True, help="Disable caching")
@click.option("--cache-file", type=click.Path(path_type=Path), help="Custom cache file path")
@click.pass_context
def batch(ctx, csv_files, output, provider, date_range, formats, no_charts, no_cache, cache_file):
    """Analyze multiple CSV files in batch."""
    cli_instance = ctx.obj['cli']
    success = cli_instance.analyze_batch(
        csv_files=list(csv_files),
        output_dir=output,
        provider=provider,
        config_file=ctx.obj['config'],
        date_range=date_range,
        output_formats=list(formats),
        generate_charts=not no_charts,
        use_cache=not no_cache,
        cache_file=cache_file,
        verbose=ctx.obj['verbose']
    )
    sys.exit(0 if success else 1)


@cli.command()
@click.option("--provider", "-p", type=click.Choice(["gemini", "mock"]), help="Provider to validate")
@click.pass_context
def validate_config(ctx, provider):
    """Validate analyzer configuration and API connectivity."""
    cli_instance = ctx.obj['cli']
    success = cli_instance.validate_configuration(
        provider=provider,
        config_file=ctx.obj['config'],
        verbose=ctx.obj['verbose']
    )
    sys.exit(0 if success else 1)



@cli.command()
@click.option("--cache-file", type=click.Path(path_type=Path), help="Cache file path")
@click.pass_context
def cache_stats(ctx, cache_file):
    """Show cache statistics."""
    try:
        cache = TransactionCache(cache_file) if cache_file else TransactionCache()
        stats = cache.get_stats()

        click.echo("CACHE STATISTICS")
        click.echo("=" * 16)
        click.echo(f"Total Entries:    {stats.entries_count:,}")
        click.echo(f"Total Requests:   {stats.total_requests:,}")
        click.echo(f"Cache Hits:       {stats.cache_hits:,}")
        click.echo(f"Cache Misses:     {stats.cache_misses:,}")
        click.echo(f"Hit Rate:         {stats.hit_rate:.1f}%")
        click.echo(f"Database Size:    {stats.database_size_kb:.1f} KB")

        if stats.oldest_entry:
            click.echo(f"Oldest Entry:     {stats.oldest_entry.strftime('%Y-%m-%d %H:%M')}")
        if stats.newest_entry:
            click.echo(f"Newest Entry:     {stats.newest_entry.strftime('%Y-%m-%d %H:%M')}")

    except Exception as e:
        click.echo(f"Error accessing cache: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--cache-file", type=click.Path(path_type=Path), help="Cache file path")
@click.confirmation_option(prompt="This will clear all cached data. Continue?")
@click.pass_context
def clear_cache(ctx, cache_file):
    """Clear cache data."""
    try:
        cache = TransactionCache(cache_file) if cache_file else TransactionCache()
        if cache.clear_cache():
            click.echo("✓ Cache cleared successfully")
        else:
            click.echo("✗ Failed to clear cache", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error clearing cache: {e}", err=True)
        sys.exit(1)


# Simplified interface for main CLI integration
def run_analysis(
    csv_file: str,
    output_dir: str,
    provider: str,
    api_key: str,
    generate_charts: bool = True
) -> None:
    """Simplified analysis function for main CLI integration.

    Args:
        csv_file: Path to CSV file with transaction data
        output_dir: Directory to save analysis results
        provider: LLM provider name (currently only 'gemini')
        api_key: API key for the LLM provider
        generate_charts: Whether to generate visualization charts

    Raises:
        ValueError: If input parameters are invalid
        FileNotFoundError: If CSV file doesn't exist
        Exception: For any analysis errors
    """
    import os
    from pathlib import Path

    # Set API key in environment for compatibility
    if provider.lower() == 'gemini':
        os.environ['GEMINI_API_KEY'] = api_key

    # Convert paths
    csv_path = Path(csv_file)
    output_path = Path(output_dir)

    # Create CLI instance and run analysis
    cli_instance = AnalyzerCLI()

    success = cli_instance.analyze_single_file(
        csv_file=csv_path,
        output_dir=output_path,
        provider=provider,
        config_file=None,
        date_range=None,
        output_formats=["text", "markdown"],
        generate_charts=generate_charts,
        use_cache=True,
        cache_file=None,
        verbose=False
    )

    if not success:
        raise Exception("Analysis failed - check logs for details")


if __name__ == "__main__":
    cli()