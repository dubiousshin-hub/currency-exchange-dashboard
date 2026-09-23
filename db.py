"""
Database layer for storing and retrieving exchange rate data.

This module handles:
1. Creating the database schema
2. Storing new exchange rate snapshots
3. Computing derived metrics from historical data
4. Querying historical data
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import statistics

DATABASE_FILE = "exchange_rates.db"
ROLLING_WINDOW = 7  # Number of past data points to use for rolling metrics


def get_db_connection():
    """
    Get a database connection.
    
    WAL mode (Write-Ahead Logging) allows better concurrency:
    instead of locking the entire database, writes go to a separate log file.
    This helps when multiple processes might access the database.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    conn.execute("PRAGMA journal_mode=WAL")  # Enable Write-Ahead Logging
    return conn


def init_db():
    """
    Create the database schema if it doesn't exist.
    
    We create one table: `snapshots`
    - id: unique identifier for each snapshot
    - timestamp: when this data was fetched
    - base: base currency (e.g., "USD")
    - currency_pair: target currency (e.g., "EUR")
    - rate: the exchange rate at that time
    
    Why two separate columns for currency pair instead of one rate JSON column?
    - It makes querying much easier (can filter by currency)
    - Allows indexing by currency pair
    - Normalizes the data (no repeated base currency info)
    
    The combination of (base, currency_pair, timestamp) allows us to:
    1. Find the most recent rate for any pair
    2. Find all historical rates for a pair
    3. Compute rolling averages for a specific pair
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            base TEXT NOT NULL,
            currency_pair TEXT NOT NULL,
            rate REAL NOT NULL
        )
    """)
    
    # Create indexes for faster queries
    # These speed up lookups by (base, currency_pair, timestamp)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_timestamp_pair 
        ON snapshots(timestamp, base, currency_pair)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pair
        ON snapshots(base, currency_pair)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON snapshots(timestamp)
    """)
    
    conn.commit()
    conn.close()


def store_snapshot(timestamp: datetime, base: str, rates: Dict[str, float]):
    """
    Store a snapshot of exchange rates.
    
    Args:
        timestamp: When this data was fetched (datetime object)
        base: Base currency code (e.g., "USD")
        rates: Dictionary mapping currency codes to rates
               e.g., {"EUR": 0.92, "GBP": 0.81}
    
    Example:
        >>> store_snapshot(
        ...     datetime.now(),
        ...     "USD",
        ...     {"EUR": 0.92, "GBP": 0.81}
        ... )
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # For each currency in the rates dict, insert a row
    for currency, rate in rates.items():
        cursor.execute("""
            INSERT INTO snapshots (timestamp, base, currency_pair, rate)
            VALUES (?, ?, ?, ?)
        """, (timestamp.isoformat(), base, currency, rate))
    
    conn.commit()
    conn.close()


def get_latest_snapshot(base: str = "USD") -> Optional[Dict]:
    """
    Get the most recent snapshot and its derived metrics.
    
    Returns a dictionary with:
    {
        "timestamp": "2025-09-22T10:30:00",
        "base": "USD",
        "rates": {"EUR": 0.92, "GBP": 0.81},
        "metrics": {
            "EUR": {
                "change_absolute": 0.01,
                "change_percent": 1.1,
                "rolling_avg_7": 0.915,
                "min_7": 0.89,
                "max_7": 0.93
            },
            ...
        }
    }
    
    Returns None if no data exists.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find the most recent timestamp for this base currency
    cursor.execute("""
        SELECT DISTINCT timestamp FROM snapshots
        WHERE base = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (base,))
    
    result = cursor.fetchone()
    if not result:
        conn.close()
        return None
    
    latest_timestamp = result[0]
    
    # Get all rates at this timestamp
    cursor.execute("""
        SELECT currency_pair, rate FROM snapshots
        WHERE base = ? AND timestamp = ?
        ORDER BY currency_pair
    """, (base, latest_timestamp))
    
    rates = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Compute metrics for each currency
    metrics = {}
    for currency in rates:
        metrics[currency] = compute_metrics(base, currency)
    
    conn.close()
    
    return {
        "timestamp": latest_timestamp,
        "base": base,
        "rates": rates,
        "metrics": metrics
    }


def get_history(
    base: str = "USD",
    currencies: Optional[List[str]] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Get historical snapshots.
    
    Args:
        base: Base currency
        currencies: List of specific currencies to filter by (optional)
                   If None, returns all currencies
        limit: Maximum number of snapshots to return
    
    Returns a list of snapshots, most recent first.
    Each snapshot is: {"timestamp": "...", "base": "USD", "rates": {...}}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build the query
    query = "SELECT DISTINCT timestamp FROM snapshots WHERE base = ?"
    params = [base]
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    timestamps = [row[0] for row in cursor.fetchall()]
    
    # For each timestamp, get all rates
    history = []
    for ts in timestamps:
        if currencies:
            # Filter to specific currencies
            placeholders = ",".join(["?" for _ in currencies])
            cursor.execute(f"""
                SELECT currency_pair, rate FROM snapshots
                WHERE base = ? AND timestamp = ? AND currency_pair IN ({placeholders})
                ORDER BY currency_pair
            """, [base, ts] + currencies)
        else:
            # Get all currencies
            cursor.execute("""
                SELECT currency_pair, rate FROM snapshots
                WHERE base = ? AND timestamp = ?
                ORDER BY currency_pair
            """, (base, ts))
        
        rates = {row[0]: row[1] for row in cursor.fetchall()}
        if rates:  # Only add if we found data
            history.append({
                "timestamp": ts,
                "base": base,
                "rates": rates
            })
    
    conn.close()
    return history


def get_rate_history(base: str, currency: str) -> List[Tuple[str, float]]:
    """
    Get all historical rates for a specific currency pair.
    
    Returns list of (timestamp, rate) tuples, ordered by timestamp DESC.
    Used internally for computing rolling metrics.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, rate FROM snapshots
        WHERE base = ? AND currency_pair = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (base, currency, ROLLING_WINDOW * 3))  # Get extra for safety (more than double)
    
    results = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return results


def compute_metrics(base: str, currency: str) -> Dict:
    """
    Compute derived metrics for a currency pair.
    
    Metrics computed:
    1. change_absolute: How much the rate changed from the previous pull
       Example: 0.92 → 0.93 = +0.01
    
    2. change_percent: Percentage change
       Example: 0.92 → 0.93 = +1.09%
       Formula: (current - previous) / previous * 100
    
    3. rolling_avg_N: Average rate over the last N data points
       Useful to see the trend over time, smooths out noise
       Example: [0.90, 0.91, 0.92] → avg = 0.913
    
    4. min_N: Minimum rate over the last N data points
       Useful to see the lowest point in this window
    
    5. max_N: Maximum rate over the last N data points
       Useful to see the highest point in this window
    
    Returns a dictionary with these metrics, or empty dict if insufficient data.
    """
    rate_history = get_rate_history(base, currency)
    
    if not rate_history:
        return {}
    
    # rate_history is ordered DESC, so [0] is most recent
    current_rate = rate_history[0][1]
    
    metrics = {}
    
    # Calculate change from previous
    if len(rate_history) >= 2:
        previous_rate = rate_history[1][1]
        metrics["change_absolute"] = round(current_rate - previous_rate, 6)
        
        # Avoid division by zero
        if previous_rate != 0:
            change_pct = (current_rate - previous_rate) / previous_rate * 100
            metrics["change_percent"] = round(change_pct, 2)
        else:
            metrics["change_percent"] = 0
    else:
        metrics["change_absolute"] = 0
        metrics["change_percent"] = 0
    
    # Rolling window metrics (last N data points)
    window_size = min(ROLLING_WINDOW, len(rate_history))
    window_rates = [rate_history[i][1] for i in range(window_size)]
    
    if window_rates:
        metrics[f"rolling_avg_{ROLLING_WINDOW}"] = round(statistics.mean(window_rates), 6)
        metrics[f"min_{ROLLING_WINDOW}"] = round(min(window_rates), 6)
        metrics[f"max_{ROLLING_WINDOW}"] = round(max(window_rates), 6)
    
    return metrics


def get_all_bases() -> List[str]:
    """Get all base currencies currently in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT base FROM snapshots")
    bases = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return bases


def get_all_currencies_for_base(base: str) -> List[str]:
    """Get all currencies we track for a specific base."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT currency_pair FROM snapshots
        WHERE base = ?
        ORDER BY currency_pair
    """, (base,))
    
    currencies = [row[0] for row in cursor.fetchall()]
    conn.close()
    return currencies


if __name__ == "__main__":
    # Initialize database when running this file directly
    print("Initializing database...")
    init_db()
    print("✓ Database initialized")
