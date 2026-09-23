# Currency Exchange Rate Dashboard

A data pipeline system that pulls currency exchange rates from a public API, stores historical data, computes derived metrics, and displays them on a dashboard.

## What This Project Does

1. **Pulls data** from the Frankfurter API (https://api.frankfurter.app) on a schedule
2. **Stores snapshots** in SQLite with timestamps so we can track history
3. **Computes metrics** like % change, rolling averages, and min/max values
4. **Serves an API** with endpoints for latest data and historical data
5. **Displays a dashboard** showing current rates and charts

## Architecture Overview

```
Frankfurter API (external)
        ↓
   [Pipeline Script]  ← Fetches data, handles errors
        ↓
   [SQLite Database]  ← Stores timestamped snapshots
        ↓
   [Backend API]      ← Computes metrics, serves data
        ↓
   [Dashboard UI]     ← Visualizes everything
```

## Project Structure

```
.
├── README.md                 # This file
├── app.py                    # Flask backend API
├── pipeline.py               # Data pulling & storage logic
├── db.py                     # Database schema & helpers
├── test_metrics.py           # Unit tests for calculations
├── requirements.txt          # Python dependencies
├── dashboard.html            # Frontend (single HTML file)
└── exchange_rates.db         # SQLite database (created on first run)
```

## Setup & Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- **Flask** - web framework for the backend API
- **requests** - for fetching data from the API
- **pytest** - for running tests

### Step 2: Initialize the Database

The database creates automatically on first pull, but you can pre-create it:

```bash
python -c "from db import init_db; init_db()"
```

## How to Run

### Option A: Manual Pull + Dashboard

Perfect for testing:

```bash
# Terminal 1: Run the backend API server
python app.py
# Output: Running on http://127.0.0.1:5000

# Terminal 2: Pull data once
python pipeline.py

# Terminal 3: Open dashboard
# Open dashboard.html in your browser
```

Then manually run `python pipeline.py` whenever you want to simulate a new data pull.

### Option B: Automated Pulls (with scheduler)

For production-like behavior, the pipeline can run on a schedule:

```bash
# Terminal 1: Run the backend API
python app.py

# Terminal 2: Run the scheduler (pulls every 5 minutes)
python scheduler.py
```

Then open `dashboard.html` in your browser.

## API Endpoints

Once the Flask backend is running, you can call:

### GET `/latest`
Returns the most recent data point with derived metrics.

```bash
curl http://127.0.0.1:5000/latest
```

Response:
```json
{
  "timestamp": "2025-09-22T10:30:00",
  "base": "USD",
  "rates": {
    "EUR": 0.92,
    "GBP": 0.81
  },
  "metrics": {
    "EUR": {
      "change_absolute": 0.01,
      "change_percent": 1.1,
      "rolling_avg_7": 0.915,
      "min_7": 0.89,
      "max_7": 0.93
    },
    "GBP": { ... }
  }
}
```

### GET `/history?base=USD&currencies=EUR,GBP&limit=30`
Returns historical data with optional filtering.

```bash
curl "http://127.0.0.1:5000/history?limit=10"
```

Response:
```json
{
  "data": [
    {
      "timestamp": "2025-09-22T10:30:00",
      "base": "USD",
      "rates": {"EUR": 0.92, "GBP": 0.81}
    },
    ...
  ]
}
```

### GET `/pull` (manual trigger)
Manually trigger a data pull from the API.

```bash
curl http://127.0.0.1:5000/pull
```

## Dashboard

Open `dashboard.html` in any web browser. It shows:
- **Current rates** from the most recent data pull
- **Derived metrics** (% change, rolling averages, min/max)
- **Line chart** showing rate history over time
- **Status indicator** showing if the last pull succeeded
- **Currency switcher** to view different pairs

The dashboard auto-refreshes every 10 seconds.

## Design Decisions & Tradeoffs

### 1. Why SQLite?
- **Pro**: No separate database server to manage, perfect for a small project
- **Con**: Not suitable for millions of rows or high concurrency
- **Tradeoff**: Good for learning; would use PostgreSQL in production

### 2. Data Pulling Strategy
- **Manual + Optional Scheduler**: You can run `python pipeline.py` manually to test, or use `scheduler.py` for automated pulls every 5 minutes
- **Tradeoff**: A real cron job would be more resilient, but this is simpler for a take-home project
- **In production**: Would use Airflow, APScheduler, or cloud-native schedulers (AWS Lambda, GCP Cloud Functions)

### 3. Error Handling
- If the API fails, the pipeline logs the error but doesn't crash
- The dashboard shows the last known good data with a warning
- Database integrity is preserved even if pulls fail
- **Why**: Graceful degradation is better than showing broken data

### 4. Derived Metrics
We compute:
- **Change (absolute & %)**: `(current - previous) / previous * 100`
- **Rolling average**: Average of last N data points
- **Min/Max**: Over the last N data points
- **Window size**: Last 7 data points (configurable)
- **Tradeoff**: 7 days is arbitrary but good for demonstration; would be driven by business requirements

### 5. Dashboard Updates
- Dashboard auto-refreshes every 10 seconds (via JavaScript `setInterval`)
- Doesn't use WebSockets (simpler, sufficient for a small dashboard)
- Tradeoff: Not real-time, but good enough for this use case

### 6. Time Window for Metrics
- Uses the last 7 data points (not 7 days of calendar time)
- This makes testing deterministic (doesn't change based on when you run it)
- **In production**: Would likely use calendar-based windows (last 7 days, last 30 days)

## Testing

Run the test suite to verify calculations are correct:

```bash
pytest test_metrics.py -v
```

Tests cover:
- Percentage change calculation
- Rolling average computation
- Min/Max tracking
- Edge cases (first data point, single value, etc.)

**Why test this?** It's easy to get math subtly wrong (off-by-one errors, division issues, etc.), and this gives confidence the dashboard shows correct numbers.

## Assumptions Made

1. **No authentication needed** - APIs chosen are public (they are!)
2. **Single currency base** - Tracks USD → EUR, GBP, JPY, etc.
3. **Consistent API availability** - May fail occasionally, but will recover
4. **Browser-based dashboard** - No mobile app or native clients
5. **Small dataset** - Assumes <10k rows (SQLite is fine for this)

## What I'd Do With More Time

### High Priority
- [ ] Real scheduler (APScheduler) instead of manual or basic scheduler
- [ ] Database connection pooling for better concurrency
- [ ] More comprehensive error logging and monitoring
- [ ] API rate limit handling (respect Frankfurter's limits)
- [ ] Caching layer to reduce database queries

### Medium Priority
- [ ] Track multiple base currencies (not just USD)
- [ ] Alert thresholds (flag if rate moved >5% since last pull)
- [ ] Data validation (reject obviously bad values)
- [ ] API response time tracking (separate metric)
- [ ] Configuration file instead of hardcoding values

### Polish
- [ ] Better UI/UX for the dashboard (CSS framework, better charts)
- [ ] Export data to CSV
- [ ] Compare across time periods (year-over-year, week-over-week)
- [ ] Performance optimization if using large historical windows

## Troubleshooting

**Dashboard shows "Loading..." forever**
- Make sure Flask backend is running (`python app.py`)
- Check browser console for errors (F12)
- Verify http://127.0.0.1:5000/latest returns data

**Database error: "database is locked"**
- SQLite can have concurrency issues if multiple processes write simultaneously
- Solution: Close other connections, or use `PRAGMA journal_mode=WAL` (included in db.py)

**API pulling but dashboard doesn't update**
- Check that `app.py` and `pipeline.py` are using the same database file
- Verify timestamps in database (run: `sqlite3 exchange_rates.db "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT 1;"`)

**No data yet**
- Run `python pipeline.py` at least once to populate the database
- Wait a few seconds for the API response

## Development Notes

- **Python version**: Tested with 3.8, 3.9, 3.10, 3.11
- **External dependencies**: Only 3 packages (requests, Flask, pytest)
- **Time spent**: ~5 hours (including tests, error handling, documentation)

## Next Steps for Learning

1. **Understand the pipeline** - Read through `pipeline.py` to see data fetching
2. **Explore the database** - Run `sqlite3 exchange_rates.db ".schema"` to see tables
3. **Study the metrics** - Look at `db.py` compute_metrics() to see calculation logic
4. **Check tests** - Read `test_metrics.py` to understand edge cases
5. **Modify and experiment** - Try changing the rolling window, adding new metrics, etc.

Good luck! 🚀
