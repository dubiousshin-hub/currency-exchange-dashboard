"""
Data pipeline for fetching exchange rates and storing them.

This script:
1. Fetches current exchange rates from the Frankfurter API
2. Handles failures gracefully (logs error but doesn't crash)
3. Stores the data in the database with a timestamp
4. Can be run manually or on a schedule

Usage:
    python pipeline.py              # Fetch once
    python scheduler.py             # Fetch on a schedule (see scheduler.py)
"""

import requests
from datetime import datetime
import time
from db import init_db, store_snapshot

# Frankfurter API endpoint
API_BASE_URL = "https://api.frankfurter.app/latest"

# Which currencies to track (as targets when base is USD)
# You can modify this list to track other currencies
TARGET_CURRENCIES = ["EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "SEK", "NOK"]

# Base currency to track
BASE_CURRENCY = "USD"

# Timeout for API requests (in seconds)
REQUEST_TIMEOUT = 10


def fetch_exchange_rates(base: str = BASE_CURRENCY, targets: list = None) -> dict:
    """
    Fetch exchange rates from the Frankfurter API.
    
    Args:
        base: Base currency (default "USD")
        targets: List of target currencies (default predefined list)
    
    Returns:
        Dictionary with rates, or None if the request fails
        Example: {"EUR": 0.92, "GBP": 0.81, ...}
    
    Raises:
        requests.RequestException: If the API call fails
    
    Why separate this into its own function?
    - Easier to test
    - Easier to mock in tests
    - Could swap out for a different API later
    - Cleaner separation of concerns
    """
    if targets is None:
        targets = TARGET_CURRENCIES
    
    # Build the query parameters
    # The Frankfurter API expects: /latest?from=USD&to=EUR,GBP,JPY,...
    params = {
        "from": base,
        "to": ",".join(targets)
    }
    
    print(f"Fetching rates for {base} → {targets}...")
    
    try:
        response = requests.get(API_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        
        # Raise an exception if the status code indicates an error
        response.raise_for_status()
        
        data = response.json()
        
        # The API returns something like:
        # {
        #     "amount": 1,
        #     "base": "USD",
        #     "date": "2025-09-22",
        #     "rates": {"EUR": 0.92, "GBP": 0.81, ...}
        # }
        
        return data.get("rates", {})
    
    except requests.exceptions.Timeout:
        raise Exception(f"API request timed out after {REQUEST_TIMEOUT} seconds")
    
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Could not connect to API: {e}")
    
    except requests.exceptions.HTTPError as e:
        raise Exception(f"API returned an error: {e.response.status_code} {e.response.reason}")
    
    except ValueError as e:
        raise Exception(f"Could not parse API response as JSON: {e}")


def run_pull(base: str = BASE_CURRENCY, targets: list = None):
    """
    Run a complete data pull cycle:
    1. Initialize database (if needed)
    2. Fetch data from API
    3. Handle any errors gracefully
    4. Store in database
    
    Args:
        base: Base currency to fetch
        targets: Target currencies to fetch
    
    This function doesn't crash even if the API fails. Instead, it logs the error
    and returns False, allowing the scheduler to retry later.
    
    Example usage:
        >>> success = run_pull()
        >>> if success:
        ...     print("Pull succeeded!")
        ... else:
        ...     print("Pull failed, will retry next cycle")
    """
    if targets is None:
        targets = TARGET_CURRENCIES
    
    print("\n" + "="*60)
    print(f"Starting data pull at {datetime.now().isoformat()}")
    print("="*60)
    
    try:
        # Ensure database exists
        init_db()
        
        # Fetch data from the API
        rates = fetch_exchange_rates(base, targets)
        
        if not rates:
            print("⚠ Warning: API returned empty rates")
            return False
        
        print(f"✓ Successfully fetched {len(rates)} exchange rates")
        print(f"  Rates: {rates}")
        
        # Store in database
        timestamp = datetime.utcnow()
        store_snapshot(timestamp, base, rates)
        
        print(f"✓ Stored snapshot in database at {timestamp.isoformat()}")
        print("✓ Pull succeeded!")
        
        return True
    
    except Exception as e:
        # Log the error but don't crash
        print(f"✗ Pull failed: {e}")
        print("  The dashboard will show the last known good data")
        print("  The pull will be retried on the next schedule cycle")
        return False
    
    finally:
        print("="*60 + "\n")


if __name__ == "__main__":
    # When running this file directly, do a single pull
    success = run_pull()
    
    # Exit with appropriate code (useful for monitoring)
    exit(0 if success else 1)
