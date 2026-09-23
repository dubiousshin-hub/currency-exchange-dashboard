"""
Unit tests for metrics calculations.

This is where we ensure the math is correct. It's easy to get percentage changes,
rolling averages, and min/max calculations subtly wrong, so comprehensive testing
is crucial.

Testing strategy:
1. Test each metric in isolation
2. Test edge cases (single data point, empty, etc.)
3. Test with realistic data
4. Test that the values make intuitive sense

Run tests with:
    pytest test_metrics.py -v
"""

import pytest
import sqlite3
import os
from datetime import datetime, timedelta
from db import (
    init_db,
    store_snapshot,
    compute_metrics,
    get_rate_history,
    get_latest_snapshot,
    DATABASE_FILE,
    ROLLING_WINDOW
)


@pytest.fixture
def setup_test_db():
    """
    Fixture that creates a fresh test database for each test.
    
    What's a fixture?
    - It's a piece of setup/teardown code that runs before each test
    - Ensures each test starts with a clean slate
    - Prevents tests from interfering with each other
    """
    # Remove any existing test database
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
    
    # Initialize fresh database
    init_db()
    
    yield  # Run the test
    
    # Cleanup after test
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)


class TestMetricsBasics:
    """Test basic metric calculations."""
    
    def test_change_calculation_positive(self, setup_test_db):
        """
        Test percentage change calculation with positive change.
        
        Scenario:
        - Pull 1: EUR/USD = 0.90
        - Pull 2: EUR/USD = 0.92
        
        Expected:
        - Absolute change: 0.92 - 0.90 = 0.02
        - Percent change: (0.02 / 0.90) * 100 = 2.22%
        """
        base = "USD"
        currency = "EUR"
        
        # First pull: EUR = 0.90
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), base, {currency: 0.90})
        
        # Second pull: EUR = 0.92
        store_snapshot(datetime(2025, 1, 1, 11, 0, 0), base, {currency: 0.92})
        
        # Get metrics after second pull
        metrics = compute_metrics(base, currency)
        
        assert metrics["change_absolute"] == 0.02
        assert metrics["change_percent"] == pytest.approx(2.22, abs=0.01)
    
    def test_change_calculation_negative(self, setup_test_db):
        """
        Test percentage change calculation with negative change.
        
        Scenario:
        - Pull 1: EUR/USD = 0.95
        - Pull 2: EUR/USD = 0.90
        
        Expected:
        - Absolute change: 0.90 - 0.95 = -0.05
        - Percent change: (-0.05 / 0.95) * 100 = -5.26%
        """
        base = "USD"
        currency = "EUR"
        
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), base, {currency: 0.95})
        store_snapshot(datetime(2025, 1, 1, 11, 0, 0), base, {currency: 0.90})
        
        metrics = compute_metrics(base, currency)
        
        assert metrics["change_absolute"] == pytest.approx(-0.05, abs=0.001)
        assert metrics["change_percent"] == pytest.approx(-5.26, abs=0.01)
    
    def test_change_with_single_data_point(self, setup_test_db):
        """
        Test that change is 0 when only one data point exists.
        
        There's no "previous" value to compare to, so:
        - Change absolute: 0
        - Change percent: 0
        """
        base = "USD"
        currency = "EUR"
        
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), base, {currency: 0.92})
        
        metrics = compute_metrics(base, currency)
        
        assert metrics["change_absolute"] == 0
        assert metrics["change_percent"] == 0
    
    def test_rolling_average_basic(self, setup_test_db):
        """
        Test rolling average calculation.
        
        Scenario:
        - Pull 1: 0.90
        - Pull 2: 0.92
        - Pull 3: 0.94
        
        Expected rolling average of last 3: (0.90 + 0.92 + 0.94) / 3 = 0.9200
        """
        base = "USD"
        currency = "EUR"
        
        rates = [0.90, 0.92, 0.94]
        for i, rate in enumerate(rates):
            store_snapshot(
                datetime(2025, 1, 1, 10 + i, 0, 0),
                base,
                {currency: rate}
            )
        
        metrics = compute_metrics(base, currency)
        
        expected_avg = sum(rates) / len(rates)
        assert metrics[f"rolling_avg_{ROLLING_WINDOW}"] == pytest.approx(expected_avg, abs=0.001)
    
    def test_min_max_calculation(self, setup_test_db):
        """
        Test min/max tracking.
        
        Scenario:
        - Rates: [0.88, 0.92, 0.90, 0.95, 0.89]
        
        Expected:
        - Min: 0.88
        - Max: 0.95
        """
        base = "USD"
        currency = "EUR"
        
        rates = [0.88, 0.92, 0.90, 0.95, 0.89]
        for i, rate in enumerate(rates):
            store_snapshot(
                datetime(2025, 1, 1, 10 + i, 0, 0),
                base,
                {currency: rate}
            )
        
        metrics = compute_metrics(base, currency)
        
        # The rolling window uses the last ROLLING_WINDOW points
        # If ROLLING_WINDOW >= 5, we use all 5 points
        # If ROLLING_WINDOW < 5, we use only the most recent ROLLING_WINDOW points
        window_rates = rates[-min(ROLLING_WINDOW, len(rates)):]
        
        assert metrics[f"min_{ROLLING_WINDOW}"] == min(window_rates)
        assert metrics[f"max_{ROLLING_WINDOW}"] == max(window_rates)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_no_data(self, setup_test_db):
        """Test that metrics are empty when no data exists."""
        base = "USD"
        currency = "EUR"
        
        metrics = compute_metrics(base, currency)
        
        assert metrics == {}
    
    def test_zero_rate_change_percent(self, setup_test_db):
        """
        Test that change_percent doesn't divide by zero.
        
        Edge case: If the previous rate is 0, we should handle it gracefully.
        In practice, exchange rates shouldn't be 0, but we need to handle it.
        """
        base = "USD"
        currency = "EUR"
        
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), base, {currency: 0.0})
        store_snapshot(datetime(2025, 1, 1, 11, 0, 0), base, {currency: 0.92})
        
        metrics = compute_metrics(base, currency)
        
        # Should return 0 instead of crashing (division by zero)
        assert metrics["change_percent"] == 0
    
    def test_multiple_currencies(self, setup_test_db):
        """
        Test that we can track multiple currencies independently.
        
        One snapshot might have multiple rates:
        {EUR: 0.92, GBP: 0.81, JPY: 110.5}
        """
        base = "USD"
        
        snapshot1 = {
            "EUR": 0.90,
            "GBP": 0.80,
            "JPY": 110.0
        }
        snapshot2 = {
            "EUR": 0.92,
            "GBP": 0.82,
            "JPY": 111.0
        }
        
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), base, snapshot1)
        store_snapshot(datetime(2025, 1, 1, 11, 0, 0), base, snapshot2)
        
        # Each currency should have independent metrics
        eur_metrics = compute_metrics(base, "EUR")
        gbp_metrics = compute_metrics(base, "GBP")
        jpy_metrics = compute_metrics(base, "JPY")
        
        assert eur_metrics["change_absolute"] == 0.02
        assert gbp_metrics["change_absolute"] == 0.02
        assert jpy_metrics["change_absolute"] == 1.0
    
    def test_very_large_change(self, setup_test_db):
        """
        Test handling of very large percentage changes.
        
        Scenario: Currency crashes from 1.00 to 0.01 (99% drop)
        """
        base = "USD"
        currency = "EUR"
        
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), base, {currency: 1.00})
        store_snapshot(datetime(2025, 1, 1, 11, 0, 0), base, {currency: 0.01})
        
        metrics = compute_metrics(base, currency)
        
        assert metrics["change_absolute"] == pytest.approx(-0.99, abs=0.001)
        assert metrics["change_percent"] == pytest.approx(-99.0, abs=0.1)
    
    def test_many_data_points(self, setup_test_db):
        """
        Test that rolling window correctly limits to ROLLING_WINDOW points.
        
        Scenario: We have 20 data points, but the rolling window should only
        consider the most recent ROLLING_WINDOW (7 by default).
        """
        base = "USD"
        currency = "EUR"
        
        # Create 20 data points (one per hour, spanning multiple days)
        rates = [0.90 + (i * 0.01) for i in range(20)]
        base_time = datetime(2025, 1, 1, 0, 0, 0)
        for i, rate in enumerate(rates):
            # Add i hours to the base time
            ts = base_time + timedelta(hours=i)
            store_snapshot(ts, base, {currency: rate})
        
        metrics = compute_metrics(base, currency)
        
        # The rolling average should only use the last ROLLING_WINDOW points
        last_n = rates[-ROLLING_WINDOW:]
        expected_avg = sum(last_n) / len(last_n)
        
        assert metrics[f"rolling_avg_{ROLLING_WINDOW}"] == pytest.approx(expected_avg, abs=0.001)
        assert metrics[f"min_{ROLLING_WINDOW}"] == min(last_n)
        assert metrics[f"max_{ROLLING_WINDOW}"] == max(last_n)


class TestRealWorldScenarios:
    """Test with realistic data patterns."""
    
    def test_realistic_market_movement(self, setup_test_db):
        """
        Test with realistic market movement pattern:
        - Steady appreciation
        - Then a small dip
        - Then recovery
        
        This is a realistic pattern for exchange rates.
        """
        base = "USD"
        currency = "EUR"
        
        # Realistic rates over time (USD weakening = EUR getting stronger)
        rates = [0.920, 0.921, 0.922, 0.921, 0.923, 0.924, 0.923, 0.925]
        
        for i, rate in enumerate(rates):
            store_snapshot(
                datetime(2025, 1, 1, 10 + i, 0, 0),
                base,
                {currency: rate}
            )
        
        metrics = compute_metrics(base, currency)
        
        # After all pulls, EUR should show positive change overall
        assert metrics["change_absolute"] > 0
        assert metrics["change_percent"] > 0
        
        # Min and max should bound the actual values
        window_rates = rates[-ROLLING_WINDOW:]
        assert metrics[f"min_{ROLLING_WINDOW}"] == min(window_rates)
        assert metrics[f"max_{ROLLING_WINDOW}"] == max(window_rates)
    
    def test_volatile_currency(self, setup_test_db):
        """
        Test with volatile currency (high fluctuations).
        
        This tests that our calculations handle volatility without errors.
        """
        base = "USD"
        currency = "BTC"  # Crypto is volatile!
        
        # Bitcoin-like volatility
        rates = [45000, 44500, 46000, 43000, 47000, 45500, 48000, 46500]
        
        for i, rate in enumerate(rates):
            store_snapshot(
                datetime(2025, 1, 1, 10 + i, 0, 0),
                base,
                {currency: rate}
            )
        
        metrics = compute_metrics(base, currency)
        
        # Should handle without errors
        assert "change_absolute" in metrics
        assert "change_percent" in metrics
        assert f"rolling_avg_{ROLLING_WINDOW}" in metrics
    
    def test_steady_rate(self, setup_test_db):
        """
        Test when rate is completely flat (no change).
        
        Scenario: Rate stays at exactly 0.92 for 5 pulls
        """
        base = "USD"
        currency = "EUR"
        
        for i in range(5):
            store_snapshot(
                datetime(2025, 1, 1, 10 + i, 0, 0),
                base,
                {currency: 0.92}
            )
        
        metrics = compute_metrics(base, currency)
        
        # Everything should be 0 or the constant value
        assert metrics["change_absolute"] == 0
        assert metrics["change_percent"] == 0
        assert metrics[f"rolling_avg_{ROLLING_WINDOW}"] == 0.92
        assert metrics[f"min_{ROLLING_WINDOW}"] == 0.92
        assert metrics[f"max_{ROLLING_WINDOW}"] == 0.92


class TestDataIntegrity:
    """Test that data is correctly stored and retrieved."""
    
    def test_rate_history_ordering(self, setup_test_db):
        """
        Test that rate history is returned in correct order (newest first).
        
        This is important for computing metrics: the first element should be
        the most recent rate, and the second should be the previous rate.
        """
        base = "USD"
        currency = "EUR"
        
        rates = [0.90, 0.91, 0.92]
        for i, rate in enumerate(rates):
            store_snapshot(
                datetime(2025, 1, 1, 10 + i, 0, 0),
                base,
                {currency: rate}
            )
        
        history = get_rate_history(base, currency)
        
        # History should be DESC (newest first)
        assert history[0][1] == 0.92  # Most recent
        assert history[1][1] == 0.91
        assert history[2][1] == 0.90  # Oldest
    
    def test_timestamp_precision(self, setup_test_db):
        """
        Test that timestamps are stored and retrieved with proper precision.
        """
        base = "USD"
        currency = "EUR"
        
        ts = datetime(2025, 1, 1, 10, 30, 45)
        store_snapshot(ts, base, {currency: 0.92})
        
        snapshot = get_latest_snapshot(base)
        
        # Should match (may lose microseconds depending on implementation)
        assert snapshot["timestamp"] == ts.isoformat()
    
    def test_multiple_bases(self, setup_test_db):
        """
        Test that different base currencies are tracked independently.
        
        E.g., USD→EUR and EUR→USD should be separate.
        """
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), "USD", {"EUR": 0.92})
        store_snapshot(datetime(2025, 1, 1, 10, 0, 0), "EUR", {"USD": 1.09})
        
        usd_snapshot = get_latest_snapshot("USD")
        eur_snapshot = get_latest_snapshot("EUR")
        
        assert usd_snapshot["base"] == "USD"
        assert eur_snapshot["base"] == "EUR"
        assert usd_snapshot["rates"]["EUR"] == 0.92
        assert eur_snapshot["rates"]["USD"] == 1.09


if __name__ == "__main__":
    # Run tests with: pytest test_metrics.py -v
    # Or run this file directly: python test_metrics.py
    pytest.main([__file__, "-v"])
