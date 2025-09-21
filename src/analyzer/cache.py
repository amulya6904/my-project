"""
SQLite-based caching system for transaction categorization results.

This module provides persistent caching of categorization results to reduce
API calls and improve performance. Uses hash-based keys for efficient lookups
and includes automatic cleanup of old entries.
"""

import sqlite3
import hashlib
import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from threading import Lock

from .models import Transaction, CategorizationResult, TransactionCategory, ConfidenceLevel


@dataclass
class CacheStats:
    """Statistics for cache performance."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    entries_count: int = 0
    database_size_kb: float = 0.0
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100


class TransactionCache:
    """
    SQLite-based cache for transaction categorization results.

    Provides fast lookups using hash-based keys and automatic cleanup
    of old entries based on configurable retention policies.
    """

    def __init__(
        self,
        cache_file: Path = None,
        max_age_days: int = 30,
        max_entries: int = 10000,
        cleanup_interval_hours: int = 24
    ):
        """
        Initialize the transaction cache.

        Args:
            cache_file: Path to SQLite database file
            max_age_days: Maximum age of cache entries in days
            max_entries: Maximum number of cache entries
            cleanup_interval_hours: Hours between automatic cleanup
        """
        self.cache_file = cache_file or Path.home() / ".bank_analyzer" / "cache.db"
        self.max_age_days = max_age_days
        self.max_entries = max_entries
        self.cleanup_interval_hours = cleanup_interval_hours
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = Lock()

        # Ensure cache directory exists
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._initialize_database()
        self._last_cleanup = datetime.now()

    def _initialize_database(self) -> None:
        """Initialize the SQLite database with required tables."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS categorization_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_hash TEXT UNIQUE NOT NULL,
                    transaction_data TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transaction_hash
                ON categorization_cache(transaction_hash)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON categorization_cache(created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_accessed_at
                ON categorization_cache(accessed_at)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a thread-safe database connection."""
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.cache_file),
                timeout=30.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _generate_transaction_hash(self, transaction: Transaction) -> str:
        """
        Generate a unique hash for a transaction.

        Uses key transaction fields to create a consistent hash that
        identifies similar transactions across different statement imports.

        Args:
            transaction: Transaction to hash

        Returns:
            str: Hexadecimal hash string
        """
        # Create a normalized representation for hashing
        normalized_data = {
            'description': transaction.description.lower().strip(),
            'amount': str(abs(transaction.amount)),
            'type': transaction.transaction_type.value,
            'counterparty': (transaction.counterparty or '').lower().strip()
        }

        # Create hash from normalized data
        hash_string = json.dumps(normalized_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()

    def get_categorization(self, transaction: Transaction) -> Optional[CategorizationResult]:
        """
        Get cached categorization for a transaction.

        Args:
            transaction: Transaction to look up

        Returns:
            Optional[CategorizationResult]: Cached result if found, None otherwise
        """
        with self._lock:
            transaction_hash = self._generate_transaction_hash(transaction)

            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT category, confidence, reasoning, access_count
                        FROM categorization_cache
                        WHERE transaction_hash = ?
                    """, (transaction_hash,))

                    row = cursor.fetchone()
                    if row:
                        # Update access statistics
                        conn.execute("""
                            UPDATE categorization_cache
                            SET accessed_at = CURRENT_TIMESTAMP,
                                access_count = access_count + 1
                            WHERE transaction_hash = ?
                        """, (transaction_hash,))
                        conn.commit()

                        # Convert to result object
                        try:
                            category = TransactionCategory(row['category'])
                            confidence = ConfidenceLevel(row['confidence'])
                        except ValueError as e:
                            self.logger.warning(f"Invalid cached data: {e}")
                            return None

                        return CategorizationResult(
                            transaction_id=f"{transaction.date}_{transaction.description[:20]}",
                            category=category,
                            confidence=confidence,
                            reasoning=row['reasoning']
                        )

            except sqlite3.Error as e:
                self.logger.error(f"Failed to retrieve cached result: {e}")

            return None

    def store_categorization(
        self,
        transaction: Transaction,
        result: CategorizationResult
    ) -> bool:
        """
        Store a categorization result in the cache.

        Args:
            transaction: Original transaction
            result: Categorization result to store

        Returns:
            bool: True if stored successfully, False otherwise
        """
        with self._lock:
            transaction_hash = self._generate_transaction_hash(transaction)

            try:
                # Store transaction data for debugging/analysis
                transaction_data = json.dumps({
                    'date': transaction.date.isoformat(),
                    'description': transaction.description,
                    'amount': str(transaction.amount),
                    'type': transaction.transaction_type.value
                })

                with self._get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO categorization_cache
                        (transaction_hash, transaction_data, category, confidence, reasoning)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        transaction_hash,
                        transaction_data,
                        result.category.value,
                        result.confidence.value,
                        result.reasoning
                    ))
                    conn.commit()

                self.logger.debug(f"Cached categorization for transaction: {transaction.description}")
                return True

            except sqlite3.Error as e:
                self.logger.error(f"Failed to store cached result: {e}")
                return False

    def get_stats(self) -> CacheStats:
        """
        Get cache performance statistics.

        Returns:
            CacheStats: Current cache statistics
        """
        try:
            with self._get_connection() as conn:
                # Get basic counts
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as entries_count,
                        SUM(access_count) as total_requests,
                        SUM(CASE WHEN access_count > 1 THEN access_count - 1 ELSE 0 END) as cache_hits,
                        MIN(created_at) as oldest_entry,
                        MAX(created_at) as newest_entry
                    FROM categorization_cache
                """)

                row = cursor.fetchone()

                # Get database file size
                try:
                    db_size_kb = self.cache_file.stat().st_size / 1024
                except (OSError, AttributeError):
                    db_size_kb = 0.0

                # Parse datetime strings
                oldest_entry = None
                newest_entry = None
                if row['oldest_entry']:
                    try:
                        oldest_entry = datetime.fromisoformat(row['oldest_entry'])
                    except ValueError:
                        pass
                if row['newest_entry']:
                    try:
                        newest_entry = datetime.fromisoformat(row['newest_entry'])
                    except ValueError:
                        pass

                return CacheStats(
                    total_requests=row['total_requests'] or 0,
                    cache_hits=row['cache_hits'] or 0,
                    cache_misses=(row['total_requests'] or 0) - (row['cache_hits'] or 0),
                    entries_count=row['entries_count'] or 0,
                    database_size_kb=db_size_kb,
                    oldest_entry=oldest_entry,
                    newest_entry=newest_entry
                )

        except sqlite3.Error as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return CacheStats()

    def cleanup_old_entries(self, force: bool = False) -> int:
        """
        Clean up old cache entries based on age and count limits.

        Args:
            force: Force cleanup regardless of cleanup interval

        Returns:
            int: Number of entries removed
        """
        with self._lock:
            now = datetime.now()

            # Check if cleanup is needed
            if not force:
                time_since_cleanup = now - self._last_cleanup
                if time_since_cleanup < timedelta(hours=self.cleanup_interval_hours):
                    return 0

            removed_count = 0

            try:
                with self._get_connection() as conn:
                    # Remove entries older than max_age_days
                    cutoff_date = now - timedelta(days=self.max_age_days)
                    cursor = conn.execute("""
                        DELETE FROM categorization_cache
                        WHERE created_at < ?
                    """, (cutoff_date.isoformat(),))
                    removed_count += cursor.rowcount

                    # If still over max_entries, remove oldest entries
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM categorization_cache
                    """)
                    current_count = cursor.fetchone()[0]

                    if current_count > self.max_entries:
                        entries_to_remove = current_count - self.max_entries
                        cursor = conn.execute("""
                            DELETE FROM categorization_cache
                            WHERE id IN (
                                SELECT id FROM categorization_cache
                                ORDER BY accessed_at ASC, created_at ASC
                                LIMIT ?
                            )
                        """, (entries_to_remove,))
                        removed_count += cursor.rowcount

                    conn.commit()

                    # Update vacuum to reclaim space
                    conn.execute("VACUUM")

                self._last_cleanup = now
                if removed_count > 0:
                    self.logger.info(f"Cleaned up {removed_count} old cache entries")

            except sqlite3.Error as e:
                self.logger.error(f"Failed to cleanup cache: {e}")

            return removed_count

    def clear_cache(self) -> bool:
        """
        Clear all cache entries.

        Returns:
            bool: True if cleared successfully, False otherwise
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM categorization_cache")
                    conn.execute("VACUUM")
                    conn.commit()

                self.logger.info("Cache cleared successfully")
                return True

            except sqlite3.Error as e:
                self.logger.error(f"Failed to clear cache: {e}")
                return False

    def export_cache_data(self) -> List[Dict[str, Any]]:
        """
        Export all cache data for analysis or backup.

        Returns:
            List[Dict[str, Any]]: All cache entries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT transaction_hash, transaction_data, category, confidence,
                           reasoning, created_at, accessed_at, access_count
                    FROM categorization_cache
                    ORDER BY created_at DESC
                """)

                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            self.logger.error(f"Failed to export cache data: {e}")
            return []