# Currency Exchange Rate Dashboard - Complete Learning Guide

## Overview

This is a **complete data pipeline + visualization system** built for the intern take-home assignment. Let me walk you through every part and explain the thinking behind each decision.

---

## Part 1: The Big Picture

### What Does This System Do?

```
┌─────────────────────┐
│  Frankfurter API    │  External data source
│ (exchange rates)    │
└──────────┬──────────┘
           │ Fetches data on schedule
           ▼
┌─────────────────────┐
│   Pipeline Script   │  Handles errors gracefully
│ (pipeline.py)       │  If API fails, system keeps running
└──────────┬──────────┘
           │ Stores snapshots with timestamps
           ▼
┌─────────────────────┐
│   SQLite Database   │  Persistent storage
│ (exchange_rates.db) │  Accumulates historical data
└──────────┬──────────┘
           │ Queries for latest + computes metrics
           ▼
┌─────────────────────┐
│   Flask Backend     │  REST API
│   (app.py)          │  Serves JSON to dashboard
└──────────┬──────────┘
           │ HTTP requests
           ▼
┌─────────────────────┐
│   Dashboard UI      │  Browser-based visualization
│  (dashboard.html)   │  Charts, metrics, controls
└─────────────────────┘
```

Each layer has a specific responsibility. This **separation of concerns** makes the system easier to test, debug, and extend.

---

## Part 2: Core Concepts Explained

### Concept 1: Data Snapshots

**Problem**: If you only store "the current EUR rate", you lose history. You can't see trends.

**Solution**: Store every data pull as a timestamped snapshot.

```
Snapshot 1: 2025-09-22 10:00:00
  USD → EUR: 0.92
  USD → GBP: 0.81

Snapshot 2: 2025-09-22 11:00:00
  USD → EUR: 0.93
  USD → GBP: 0.82

Snapshot 3: 2025-09-22 12:00:00
  USD → EUR: 0.91
  USD → GBP: 0.81
```

Over time, these snapshots accumulate. From them, we can compute:
- How much did EUR change from pull 1 to pull 2? (0.92 → 0.93)
- What's the average over the last week?
- What was the minimum and maximum?

**Database Design**:
```
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,           ← When was this data fetched?
    base TEXT,                    ← What's the base currency? (USD)
    currency_pair TEXT,           ← What target? (EUR, GBP, JPY)
    rate REAL                     ← The exchange rate value
)
```

Each row is one rate at one point in time. Multiple rates can share a timestamp (all fetched at the same moment).

### Concept 2: Derived Metrics

**Raw data**: Just numbers (0.92, 0.93, 0.91, ...)

**Derived metrics**: Computed values that show patterns:

1. **Change (Absolute & %)**
   - Absolute: `current - previous`
   - Example: 0.92 → 0.93 = +0.01
   - Percent: `(current - previous) / previous * 100`
   - Example: (0.93 - 0.92) / 0.92 * 100 = +1.09%

2. **Rolling Average**
   - Average of the last N data points
   - Example: Last 7 rates are [0.90, 0.91, 0.92, 0.93, 0.92, 0.91, 0.92]
   - Rolling avg = (0.90 + 0.91 + 0.92 + 0.93 + 0.92 + 0.91 + 0.92) / 7 = 0.913

3. **Min/Max**
   - Lowest and highest in the window
   - Example: Min = 0.90, Max = 0.93

**Why compute these?** They reveal trends. A rolling average smooths noise. Min/max show volatility.

### Concept 3: Error Handling

**Problem**: What if the API is down?

**Bad approach**: Crash and show an error page.

**Good approach**: Log the error, keep the system running, show the last known good data.

```python
def run_pull():
    try:
        # Fetch from API
        rates = fetch_exchange_rates()
        # Store if successful
        store_snapshot(datetime.now(), "USD", rates)
        return True
    except Exception as e:
        # Log error but don't crash
        print(f"Pull failed: {e}")
        return False
        # Dashboard will still show previous data
```

This is called **graceful degradation**. The system is robust.

---

## Part 3: Code Walkthrough

### File 1: `db.py` - Database Layer

**Responsibility**: All database operations.

**Key Functions**:

```python
def init_db():
    """Create the database schema."""
    # Runs once on startup
    # Creates the 'snapshots' table with indexes

def store_snapshot(timestamp, base, rates):
    """Insert new data points."""
    # Example:
    # store_snapshot(
    #     datetime.now(),
    #     "USD",
    #     {"EUR": 0.92, "GBP": 0.81}
    # )
    # Creates multiple rows (one per currency)

def compute_metrics(base, currency):
    """Calculate derived metrics for a currency pair."""
    # Gets historical rates from the database
    # Calculates:
    #   - Change (absolute and %)
    #   - Rolling average (last 7 points)
    #   - Min/Max (last 7 points)
    # Returns a dictionary of metrics

def get_latest_snapshot(base):
    """Get the most recent data point + metrics."""
    # Used by the API to serve the dashboard
```

**The Math** (most likely place for bugs):

```python
# Percentage change
def compute_metrics(base, currency):
    history = get_rate_history(base, currency)
    current_rate = history[0][1]      # Most recent
    previous_rate = history[1][1]     # Previous
    
    change_pct = (current_rate - previous_rate) / previous_rate * 100
    # This is easy to get wrong! Remember:
    # - Divide by PREVIOUS, not current
    # - Multiply by 100 to get percentage
```

### File 2: `pipeline.py` - Data Fetching

**Responsibility**: Pull data from the external API, handle errors, store in database.

**Flow**:

```python
def run_pull():
    """One complete pull cycle."""
    # 1. Ensure database exists
    init_db()
    
    # 2. Fetch from API (with timeout and error handling)
    rates = fetch_exchange_rates("USD", ["EUR", "GBP", ...])
    # Could fail here (API down, network issue, etc.)
    
    # 3. If successful, store
    store_snapshot(datetime.now(), "USD", rates)
    
    # 4. If error, log it but don't crash
    # The dashboard shows previous data
```

**Why a separate file?** So you can:
- Test the pipeline independently
- Replace the API source later
- Run pulls on a schedule

### File 3: `app.py` - Flask Backend API

**Responsibility**: Serve data to the dashboard via REST API.

**Endpoints**:

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `GET /latest` | Current rates + metrics | `{"rates": {"EUR": 0.92}, "metrics": {...}}` |
| `GET /history` | Historical time series | Array of snapshots with dates |
| `GET /pull` | Manually trigger a pull | Useful for testing |
| `GET /status` | System health check | `{"status": "healthy", "records_count": 42}` |

**Why separate from pipeline?** The API can run continuously, serving the dashboard, while pulls happen on a schedule.

### File 4: `dashboard.html` - Frontend

**Responsibility**: Visualize data in the browser.

**What it does**:
1. Auto-refreshes every 10 seconds (fetches from `/latest` and `/history`)
2. Renders a line chart of historical rates
3. Shows current rate and metrics (change %, rolling avg, min/max)
4. Lets you switch between currencies
5. Provides buttons to manually pull data or refresh

**Tech**: Vanilla JavaScript + Chart.js (a charting library).

### File 5: `test_metrics.py` - Automated Tests

**Responsibility**: Verify that metric calculations are correct.

**Why test metrics specifically?** Because they're easy to get wrong:
- Off-by-one errors (using wrong index)
- Wrong division (dividing by current instead of previous)
- Floating-point precision issues

**Test Examples**:

```python
def test_change_calculation_positive():
    """
    Pull 1: EUR = 0.90
    Pull 2: EUR = 0.92
    Expected change: +0.02 absolute, +2.22% percent
    """
    store_snapshot(..., {"EUR": 0.90})
    store_snapshot(..., {"EUR": 0.92})
    
    metrics = compute_metrics("USD", "EUR")
    
    assert metrics["change_absolute"] == 0.02
    assert metrics["change_percent"] == pytest.approx(2.22)

def test_rolling_average():
    """
    Rates: [0.90, 0.91, 0.92]
    Expected avg: 0.913
    """
    ...
```

Run all tests: `pytest test_metrics.py -v`

---

## Part 4: How to Use This System

### Quick Start (5 minutes)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate mock data (or pull from real API)
python test_pipeline.py

# 3. Start the backend
python app.py
# Output: Running on http://127.0.0.1:5000

# 4. Open the dashboard
# Open dashboard.html in your browser

# 5. (Optional) Trigger another pull
# In another terminal:
python pipeline.py
```

### Real-World Use (with scheduler)

```bash
# Terminal 1: Backend API
python app.py

# Terminal 2: Scheduler (pulls every 5 minutes)
python scheduler.py

# Terminal 3: View dashboard
# Open dashboard.html in browser
```

### Testing

```bash
# Run all unit tests
pytest test_metrics.py -v

# Test the full pipeline
python test_pipeline.py

# Query the database directly
sqlite3 exchange_rates.db "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT 10;"
```

---

## Part 5: Design Decisions & Tradeoffs

### Decision 1: SQLite vs. PostgreSQL

**SQLite**:
- ✅ No server setup needed
- ✅ Perfect for small datasets
- ❌ Not suitable for high concurrency
- ❌ Limited to single machine

**Tradeoff**: For this assignment and small deployments, SQLite is perfect. For production with many users, switch to PostgreSQL.

### Decision 2: Manual vs. Automatic Scheduling

**What I built**: Can do manual pulls (`python pipeline.py`) or use a simple scheduler (`python scheduler.py`).

**Why not APScheduler?** Adds a dependency, overkill for this use case.

**In production**: Use Airflow, Kubernetes Cron Jobs, or cloud-native schedulers.

### Decision 3: Derived Metrics Window Size

**Window = Last 7 data points** (not 7 days).

**Why?**
- Deterministic (doesn't change based on when you run it)
- Easy to test
- In production, would use 7 calendar days

### Decision 4: Error Handling Strategy

**If pull fails**:
1. Log the error
2. Don't crash the application
3. Dashboard shows last known good data
4. Show a warning to the user

**Alternative (not used)**: Crash and force restart. This is worse for users.

### Decision 5: One HTML File vs. Separate Frontend

**I chose**: Single `dashboard.html` file.

**Why?**
- No build process needed
- No frontend server needed
- Can open directly in browser
- Great for a take-home assignment

**In production**: Would use React/Vue, separate server, proper CI/CD.

---

## Part 6: Common Mistakes & How We Avoided Them

### Mistake 1: Percentage Change Formula

**Wrong**: `(current - previous) / current * 100`
**Right**: `(current - previous) / previous * 100`

**Why**: You want to know what percentage the *previous* value grew by.

Example: 0.90 → 0.93
- Wrong: (0.93 - 0.90) / 0.93 * 100 = 3.23%
- Right: (0.93 - 0.90) / 0.90 * 100 = 3.33%

The right answer shows "the previous rate grew by 3.33%"

**We catch this**: By testing in `test_metrics.py::test_change_calculation_positive`

### Mistake 2: Division by Zero

**Scenario**: Previous rate is 0 (shouldn't happen, but might).

**Solution**:
```python
if previous_rate != 0:
    change_pct = (current - previous) / previous * 100
else:
    change_pct = 0
```

**We catch this**: In `test_metrics.py::test_zero_rate_change_percent`

### Mistake 3: Wrong Index in Rolling Window

**Scenario**: Getting the oldest 7 points instead of newest.

**Solution**: SQL `ORDER BY timestamp DESC LIMIT 7` returns newest first.

```python
history = get_rate_history(...)  # DESC, newest first
current = history[0][1]          # Index 0 is most recent ✓
previous = history[1][1]         # Index 1 is previous ✓
window = [history[i][1] for i in range(7)]  # Last 7 ✓
```

### Mistake 4: Database Locking

**SQLite limitation**: Multiple processes can lock the database.

**Solution**: Enable WAL mode.
```python
conn.execute("PRAGMA journal_mode=WAL")
```

This uses a separate log file, allowing better concurrency.

### Mistake 5: API Failure Crashes App

**Bad code**:
```python
rates = fetch_exchange_rates()  # Crashes if API down
store_snapshot(..., rates)
```

**Good code**:
```python
try:
    rates = fetch_exchange_rates()
    store_snapshot(..., rates)
    return True
except Exception as e:
    print(f"Pull failed: {e}")
    return False
```

The dashboard still shows previous data.

---

## Part 7: What to Study in Each File

### For Understanding Databases:
- Read `db.py` completely
- Pay special attention to `compute_metrics()` - the math is here
- Note the SQL queries: JOINs, ORDER BY, LIMIT

### For Understanding APIs:
- Read `pipeline.py` - how to fetch external data
- Read `app.py` - how to serve data via HTTP
- Understand the difference between client (dashboard) and server (app.py)

### For Understanding Testing:
- Read `test_metrics.py`
- Note: Each test is self-contained (has `setup_test_db` fixture)
- Notice how tests verify edge cases (zero, negative, single point, etc.)

### For Understanding Frontend:
- Read `dashboard.html` - especially the JavaScript
- Note how `fetch()` makes requests to the backend API
- See how Chart.js renders the time series

---

## Part 8: How to Extend This System

### Extension 1: Track Multiple Base Currencies

**Current**: Only USD → other currencies

**Goal**: Also support EUR → USD, GBP → JPY, etc.

**Change**: Modify `pipeline.py` to fetch multiple bases:

```python
bases = ["USD", "EUR", "GBP"]
for base in bases:
    rates = fetch_exchange_rates(base)
    store_snapshot(datetime.now(), base, rates)
```

### Extension 2: Add Alerts

**Goal**: Flag if rate moved > 5% since last pull

**Implementation**:

```python
def check_alert_condition(base, currency, threshold=0.05):
    metrics = compute_metrics(base, currency)
    pct_change = abs(metrics["change_percent"])
    
    if pct_change > threshold * 100:
        return f"Alert: {currency} moved {pct_change:.2f}%"
    return None
```

Render on dashboard with a red banner.

### Extension 3: Add Data Export

**Goal**: Download rates as CSV

**Implementation**:

```python
# In app.py
@app.route("/export")
def export():
    history = get_history()
    csv = "timestamp,currency,rate\n"
    for snap in history:
        for curr, rate in snap["rates"].items():
            csv += f"{snap['timestamp']},{curr},{rate}\n"
    
    return csv, 200, {"Content-Type": "text/csv"}
```

### Extension 4: Compare Multiple Currencies

**Goal**: Chart EUR vs. GBP vs. JPY on same graph

**Implementation**: Modify dashboard to allow multi-select, pass to Chart.js with multiple datasets.

---

## Part 9: Interview Talking Points

When discussing this with your interviewer:

**1. Data Modeling**
- "I separated snapshots (immutable historical data) from metrics (computed values)"
- "Database schema supports time-series queries efficiently with indexes"

**2. Error Handling**
- "If the API fails, the system stays running and shows last known good data"
- "Logs errors for monitoring but doesn't crash"

**3. Testing**
- "16 automated tests verify metric calculations are correct"
- "Tests cover edge cases: single data point, division by zero, large changes"

**4. Architecture**
- "Clean separation of concerns: pipeline pulls, database stores, API serves, UI visualizes"
- "Each layer can be tested and modified independently"

**5. Tradeoffs**
- "Used SQLite for simplicity, would use PostgreSQL at scale"
- "Manual scheduler for demo, would use Airflow for production"
- "Single HTML file for simplicity, would use React at scale"

---

## Part 10: Running the Tests

```bash
# Install test dependencies
pip install pytest

# Run all tests with verbose output
pytest test_metrics.py -v

# Run a specific test
pytest test_metrics.py::TestMetricsBasics::test_change_calculation_positive -v

# Run tests and show coverage
pytest test_metrics.py --cov=db

# Run and stop on first failure
pytest test_metrics.py -x
```

**Expected output**: All 16 tests pass ✓

---

## Summary

This system demonstrates:
- ✅ **Data pipelines**: Fetch → Store → Compute → Serve
- ✅ **Database design**: Snapshots, indexes, time-series queries
- ✅ **Error handling**: Graceful degradation, no crashes
- ✅ **Testing**: Unit tests for critical logic
- ✅ **APIs**: REST endpoints serving JSON
- ✅ **Frontend**: Real-time visualization with charts
- ✅ **Code organization**: Clear separation of concerns

**Key lesson**: Good software is built in layers, each with clear responsibilities. This makes it easier to build, test, debug, and extend.

Good luck with your interview! 🚀
