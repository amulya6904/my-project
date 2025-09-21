"""
Configuration management system for the analyzer module.

This module provides TOML-based configuration with support for multiple
LLM providers, custom categories, secure API key management, and
default value handling.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python versions
    except ImportError:
        tomllib = None

try:
    import tomlkit  # For writing TOML files
except ImportError:
    tomlkit = None

from .models import CategorizerConfig, TransactionCategory


class ProviderType(Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class CacheConfig:
    """Configuration for caching system."""
    enabled: bool = True
    cache_file: Optional[Path] = None
    max_age_days: int = 30
    max_entries: int = 10000
    cleanup_interval_hours: int = 24


@dataclass
class ProviderConfig:
    """Configuration for a specific LLM provider."""
    api_key: str
    model_name: str
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay: float = 1.0
    batch_size: int = 50
    timeout_seconds: int = 30
    enabled: bool = True

    # Provider-specific settings
    extra_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyzerConfig:
    """Complete analyzer configuration."""
    # Provider settings
    default_provider: ProviderType = ProviderType.GEMINI
    providers: Dict[ProviderType, ProviderConfig] = field(default_factory=dict)

    # Cache settings
    cache: CacheConfig = field(default_factory=CacheConfig)

    # Category settings
    use_custom_categories: bool = False
    custom_categories: List[str] = field(default_factory=list)

    # Processing settings
    include_reasoning: bool = True
    include_alternatives: bool = False
    parallel_processing: bool = False
    max_concurrent_requests: int = 3

    # Logging settings
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    def get_categorizer_config(self, provider: Optional[ProviderType] = None) -> CategorizerConfig:
        """
        Get CategorizerConfig for the specified provider.

        Args:
            provider: Provider type, uses default if None

        Returns:
            CategorizerConfig: Configuration for the categorizer

        Raises:
            ConfigError: If provider is not configured
        """
        provider = provider or self.default_provider

        if provider not in self.providers:
            raise ConfigError(f"Provider {provider.value} is not configured")

        provider_config = self.providers[provider]
        if not provider_config.enabled:
            raise ConfigError(f"Provider {provider.value} is disabled")

        return CategorizerConfig(
            api_key=provider_config.api_key,
            model_name=provider_config.model_name,
            temperature=provider_config.temperature,
            max_retries=provider_config.max_retries,
            retry_delay=provider_config.retry_delay,
            batch_size=provider_config.batch_size,
            timeout_seconds=provider_config.timeout_seconds,
            use_custom_categories=self.use_custom_categories,
            custom_categories=self.custom_categories,
            include_reasoning=self.include_reasoning,
            include_alternatives=self.include_alternatives,
            parallel_processing=self.parallel_processing,
            max_concurrent_requests=self.max_concurrent_requests
        )


class ConfigError(Exception):
    """Configuration-related errors."""
    pass


class ConfigManager:
    """
    Manager for analyzer configuration with TOML support.

    Handles loading, validation, and management of configuration files
    with support for environment variable overrides and secure API key storage.
    """

    DEFAULT_CONFIG_FILENAME = "analyzer.toml"
    ENV_PREFIX = "BANK_ANALYZER_"

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_file: Path to configuration file
        """
        self.config_file = self._resolve_config_file(config_file)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._config: Optional[AnalyzerConfig] = None

    def _resolve_config_file(self, config_file: Optional[Path]) -> Path:
        """
        Resolve configuration file path.

        Searches in order:
        1. Provided path
        2. Current directory
        3. User home directory
        4. System-wide location
        """
        if config_file and config_file.exists():
            return config_file

        search_paths = [
            Path.cwd() / self.DEFAULT_CONFIG_FILENAME,
            Path.home() / f".config/bank-analyzer/{self.DEFAULT_CONFIG_FILENAME}",
            Path.home() / f".bank-analyzer/{self.DEFAULT_CONFIG_FILENAME}",
            Path("/etc/bank-analyzer") / self.DEFAULT_CONFIG_FILENAME
        ]

        for path in search_paths:
            if path.exists():
                return path

        # Return the first path for creation
        return search_paths[1]

    def load_config(self, create_if_missing: bool = True) -> AnalyzerConfig:
        """
        Load configuration from file.

        Args:
            create_if_missing: Create default config if file doesn't exist

        Returns:
            AnalyzerConfig: Loaded configuration

        Raises:
            ConfigError: If configuration cannot be loaded or is invalid
        """
        if tomllib is None:
            raise ConfigError("TOML support not available. Install tomli or upgrade to Python 3.11+")

        if not self.config_file.exists():
            if create_if_missing:
                self.logger.info(f"Creating default configuration at {self.config_file}")
                self._create_default_config()
            else:
                raise ConfigError(f"Configuration file not found: {self.config_file}")

        try:
            with open(self.config_file, "rb") as f:
                config_data = tomllib.load(f)

            self._config = self._parse_config(config_data)
            self._apply_environment_overrides()
            self._validate_config()

            self.logger.info(f"Configuration loaded from {self.config_file}")
            return self._config

        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}") from e

    def _parse_config(self, config_data: Dict[str, Any]) -> AnalyzerConfig:
        """Parse TOML data into AnalyzerConfig object."""
        # Parse providers
        providers = {}
        providers_data = config_data.get("providers", {})

        for provider_name, provider_data in providers_data.items():
            try:
                provider_type = ProviderType(provider_name.lower())
                api_key = provider_data.get("api_key", "")

                # Handle API key from environment
                env_key = f"{self.ENV_PREFIX}{provider_name.upper()}_API_KEY"
                if not api_key and env_key in os.environ:
                    api_key = os.environ[env_key]

                provider_config = ProviderConfig(
                    api_key=api_key,
                    model_name=provider_data.get("model_name", ""),
                    temperature=provider_data.get("temperature", 0.1),
                    max_retries=provider_data.get("max_retries", 3),
                    retry_delay=provider_data.get("retry_delay", 1.0),
                    batch_size=provider_data.get("batch_size", 50),
                    timeout_seconds=provider_data.get("timeout_seconds", 30),
                    enabled=provider_data.get("enabled", True),
                    extra_settings=provider_data.get("extra_settings", {})
                )
                providers[provider_type] = provider_config

            except ValueError:
                self.logger.warning(f"Unknown provider type: {provider_name}")

        # Parse cache configuration
        cache_data = config_data.get("cache", {})
        cache_config = CacheConfig(
            enabled=cache_data.get("enabled", True),
            cache_file=Path(cache_data["cache_file"]) if cache_data.get("cache_file") else None,
            max_age_days=cache_data.get("max_age_days", 30),
            max_entries=cache_data.get("max_entries", 10000),
            cleanup_interval_hours=cache_data.get("cleanup_interval_hours", 24)
        )

        # Parse main configuration
        default_provider_str = config_data.get("default_provider", "gemini")
        try:
            default_provider = ProviderType(default_provider_str.lower())
        except ValueError:
            default_provider = ProviderType.GEMINI
            self.logger.warning(f"Unknown default provider '{default_provider_str}', using gemini")

        # Parse categories
        categories_data = config_data.get("categories", {})
        use_custom = categories_data.get("use_custom_categories", False)
        custom_categories = categories_data.get("custom_categories", [])

        # Parse processing settings
        processing_data = config_data.get("processing", {})

        # Parse logging settings
        logging_data = config_data.get("logging", {})
        log_file_path = None
        if logging_data.get("log_file"):
            log_file_path = Path(logging_data["log_file"])

        return AnalyzerConfig(
            default_provider=default_provider,
            providers=providers,
            cache=cache_config,
            use_custom_categories=use_custom,
            custom_categories=custom_categories,
            include_reasoning=processing_data.get("include_reasoning", True),
            include_alternatives=processing_data.get("include_alternatives", False),
            parallel_processing=processing_data.get("parallel_processing", False),
            max_concurrent_requests=processing_data.get("max_concurrent_requests", 3),
            log_level=logging_data.get("level", "INFO"),
            log_file=log_file_path
        )

    def _apply_environment_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        if not self._config:
            return

        # Override log level
        env_log_level = os.environ.get(f"{self.ENV_PREFIX}LOG_LEVEL")
        if env_log_level:
            self._config.log_level = env_log_level.upper()

        # Override default provider
        env_provider = os.environ.get(f"{self.ENV_PREFIX}DEFAULT_PROVIDER")
        if env_provider:
            try:
                self._config.default_provider = ProviderType(env_provider.lower())
            except ValueError:
                self.logger.warning(f"Invalid provider in environment: {env_provider}")

        # Override cache settings
        env_cache_enabled = os.environ.get(f"{self.ENV_PREFIX}CACHE_ENABLED")
        if env_cache_enabled:
            self._config.cache.enabled = env_cache_enabled.lower() in ('true', '1', 'yes')

    def _validate_config(self) -> None:
        """Validate the loaded configuration."""
        if not self._config:
            raise ConfigError("No configuration loaded")

        # Validate that at least one provider is configured
        if not self._config.providers:
            raise ConfigError("No providers configured")

        # Validate default provider exists and is enabled
        default_provider = self._config.default_provider
        if default_provider not in self._config.providers:
            raise ConfigError(f"Default provider {default_provider.value} not configured")

        if not self._config.providers[default_provider].enabled:
            raise ConfigError(f"Default provider {default_provider.value} is disabled")

        # Validate provider configurations
        for provider_type, provider_config in self._config.providers.items():
            if provider_config.enabled and not provider_config.api_key:
                raise ConfigError(f"API key required for provider {provider_type.value}")

        # Validate custom categories
        if self._config.use_custom_categories:
            if not self._config.custom_categories:
                raise ConfigError("Custom categories enabled but no categories provided")

            # Validate that custom categories are valid
            valid_categories = {cat.value for cat in TransactionCategory}
            for category in self._config.custom_categories:
                if category not in valid_categories:
                    self.logger.warning(f"Custom category '{category}' is not a standard category")

    def _create_default_config(self) -> None:
        """Create a default configuration file."""
        if tomlkit is None:
            raise ConfigError("Cannot create config file. Install tomlkit for TOML writing support")

        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # Create default TOML content
        default_content = self._get_default_toml_content()

        try:
            with open(self.config_file, "w") as f:
                f.write(default_content)
        except Exception as e:
            raise ConfigError(f"Failed to create default config: {e}") from e

    def _get_default_toml_content(self) -> str:
        """Get default TOML configuration content."""
        return '''# Bank Statement Analyzer Configuration
# This file contains settings for the transaction categorization system

# Default LLM provider to use for categorization
default_provider = "gemini"

# LLM Provider Configurations
[providers.gemini]
api_key = ""  # Set your Gemini API key here or use BANK_ANALYZER_GEMINI_API_KEY env var
model_name = "gemini-1.5-flash"
temperature = 0.1
max_retries = 3
retry_delay = 1.0
batch_size = 50
timeout_seconds = 30
enabled = true

[providers.openai]
api_key = ""  # Set your OpenAI API key here or use BANK_ANALYZER_OPENAI_API_KEY env var
model_name = "gpt-3.5-turbo"
temperature = 0.1
max_retries = 3
retry_delay = 1.0
batch_size = 20
timeout_seconds = 30
enabled = false

[providers.anthropic]
api_key = ""  # Set your Anthropic API key here or use BANK_ANALYZER_ANTHROPIC_API_KEY env var
model_name = "claude-3-haiku-20240307"
temperature = 0.1
max_retries = 3
retry_delay = 1.0
batch_size = 10
timeout_seconds = 30
enabled = false

# Cache Configuration
[cache]
enabled = true
# cache_file = "~/.bank_analyzer/cache.db"  # Optional: override default location
max_age_days = 30
max_entries = 10000
cleanup_interval_hours = 24

# Category Configuration
[categories]
use_custom_categories = false
custom_categories = [
    # "Custom Food Category",
    # "Custom Transport Category"
]

# Processing Configuration
[processing]
include_reasoning = true
include_alternatives = false
parallel_processing = false
max_concurrent_requests = 3

# Logging Configuration
[logging]
level = "INFO"
# log_file = "~/.bank_analyzer/analyzer.log"  # Optional: log to file
'''

    def get_config(self) -> AnalyzerConfig:
        """
        Get current configuration, loading if necessary.

        Returns:
            AnalyzerConfig: Current configuration
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def reload_config(self) -> AnalyzerConfig:
        """
        Reload configuration from file.

        Returns:
            AnalyzerConfig: Reloaded configuration
        """
        self._config = None
        return self.load_config()

    def get_cache_config(self) -> CacheConfig:
        """Get cache configuration."""
        return self.get_config().cache

    def is_provider_available(self, provider: ProviderType) -> bool:
        """Check if a provider is configured and enabled."""
        config = self.get_config()
        return (
            provider in config.providers and
            config.providers[provider].enabled and
            bool(config.providers[provider].api_key)
        )