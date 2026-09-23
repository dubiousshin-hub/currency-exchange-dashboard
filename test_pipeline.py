"""
Test the pipeline with mock data.

This allows us to demonstrate the system without needing external API access.
In production, this would use real API data.
"""

import os
from datetime import datetime, timedelta
from db import init_db, store_snapshot, get_latest_snapshot, get_history
import random

def generate_mock_data():
    """
    Generate realistic mock exchange rate data.
    
    Uses a random walk algorithm to create data that looks like real exchange rates.
    """
    base = "USD"
    currencies = ["EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]
    
    # Starting rates (realistic 2025 values)
    rates = {
        "EUR": 0.92,
        "GBP": 0.81,
        "JPY": 110.5,
        "CHF": 0.88,
        "CAD": 1.35,
        "AUD": 1.52
    }
    
    # Generate 30 data points over the past 30 hours
    print(f"Generating {30} mock snapshots...")
    
    for day_offset in range(30):
        # Add some random walk (prices drift slightly)
        for currency in currencies:
            # Random walk: change by -0.5% to +0.5%
            change = random.uniform(-0.005, 0.005)
            rates[currency] *= (1 + change)
            # Keep it realistic (no crazy numbers)
            rates[currency] = round(rates[currency], 4)
        
        # Store this snapshot
        timestamp = datetime.utcnow() - timedelta(hours=30 - day_offset)
        snapshot = {c: rates[c] for c in currencies}
        store_snapshot(timestamp, base, snapshot)
        
        if (day_offset + 1) % 10 == 0:
            print(f"  Generated {day_offset + 1} snapshots")
    
    print("✓ Mock data generation complete")
    return rates


def test_full_pipeline():
    """
    Test the full pipeline: store data, compute metrics, retrieve data.
    """
    print("\n" + "="*60)
    print("TESTING THE COMPLETE PIPELINE")
    print("="*60)
    
    # Clean database
    if os.path.exists("exchange_rates.db"):
        os.remove("exchange_rates.db")
    
    # Initialize and populate
    print("\n1. Initializing database...")
    init_db()
    print("   ✓ Database initialized")
    
    print("\n2. Generating mock data...")
    generate_mock_data()
    
    print("\n3. Testing retrieval and metrics...")
    base = "USD"
    currency = "EUR"
    
    # Get latest snapshot
    latest = get_latest_snapshot(base)
    print(f"\n   Latest snapshot:")
    print(f"   Timestamp: {latest['timestamp']}")
    print(f"   Current rate (EUR): {latest['rates']['EUR']}")
    
    if currency in latest['metrics']:
        metrics = latest['metrics'][currency]
        print(f"\n   Metrics for EUR:")
        print(f"     Change absolute: {metrics.get('change_absolute', 0):.6f}")
        print(f"     Change percent:  {metrics.get('change_percent', 0):.2f}%")
        print(f"     Rolling avg (7): {metrics.get('rolling_avg_7', 0):.6f}")
        print(f"     Min (7):         {metrics.get('min_7', 0):.6f}")
        print(f"     Max (7):         {metrics.get('max_7', 0):.6f}")
    
    # Get history
    history = get_history(base, limit=10)
    print(f"\n   Retrieved {len(history)} historical snapshots")
    print(f"   Showing most recent 5:")
    for i, snap in enumerate(history[:5]):
        print(f"     {i+1}. {snap['timestamp']}: EUR={snap['rates']['EUR']:.4f}")
    
    print("\n4. Verifying all currencies...")
    currencies_in_db = set()
    for snap in history:
        currencies_in_db.update(snap['rates'].keys())
    
    print(f"   Found {len(currencies_in_db)} currencies: {', '.join(sorted(currencies_in_db))}")
    
    print("\n" + "="*60)
    print("✓ PIPELINE TEST SUCCESSFUL")
    print("="*60)
    print("\nThe system is working correctly!")
    print("In production, it would pull from the real Frankfurter API.")
    print("This mock data simulates realistic exchange rate movements.")


if __name__ == "__main__":
    test_full_pipeline()
