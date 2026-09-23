# Quick Start Guide

## The Absolute Fastest Way to See It Working

### Step 1: Install (2 minutes)

```bash
pip install -r requirements.txt
```

### Step 2: Generate Test Data (1 minute)

```bash
python test_pipeline.py
```

Output:
```
============================================================
TESTING THE COMPLETE PIPELINE
============================================================

1. Initializing database...
   ✓ Database initialized

2. Generating mock data...
Generating 30 mock snapshots...
  Generated 10 snapshots
  Generated 20 snapshots
  Generated 30 snapshots
✓ Mock data generation complete

3. Testing retrieval and metrics...
   Latest snapshot:
   Timestamp: 2026-09-21T17:42:05.134424
   Current rate (EUR): 0.9126
   
   Metrics for EUR:
     Change absolute: -0.003800
     Change percent:  -0.41%
     Rolling avg (7): 0.913300
     Min (7):         0.909100
     Max (7):         0.916400

   Retrieved 10 historical snapshots
   Showing most recent 5:
     1. 2026-09-21T17:42:05.134424: EUR=0.9126
     2. 2026-09-21T16:42:05.133549: EUR=0.9164
     3. 2026-09-21T15:42:05.132549: EUR=0.9132
     4. 2026-09-21T14:42:05.131532: EUR=0.9159
     5. 2026-09-21T13:42:05.130510: EUR=0.9126

4. Verifying all currencies...
   Found 6 currencies: AUD, CAD, CHF, EUR, GBP, JPY

============================================================
✓ PIPELINE TEST SUCCESSFUL
============================================================
```

### Step 3: Run the Backend (1 terminal)

```bash
python app.py
```

You'll see:
```
============================================================
Starting Flask server...
============================================================

API Documentation:
  GET http://127.0.0.1:5000/latest  - Current rates
  GET http://127.0.0.1:5000/history - Historical data
  GET http://127.0.0.1:5000/pull    - Trigger a pull
  GET http://127.0.0.1:5000/status  - System status

Dashboard:
  Open dashboard.html in your browser

Data Pipeline:
  python pipeline.py - Pull data manually

============================================================

 * Running on http://127.0.0.1:5000
```

### Step 4: Open the Dashboard

Open **`dashboard.html`** in your web browser.

You should see:
- 💱 Exchange Rate Dashboard header
- Current rates for each currency pair
- Charts showing historical data
- Metrics like % change, rolling average, min/max
- Controls to switch currencies and manually pull data

That's it! ✅

---

## Testing

### Run Tests

```bash
pytest test_metrics.py -v
```

Expected: 16 tests pass ✓

### Test Individual Components

```bash
# Test just the database
python -c "from db import init_db, get_latest_snapshot; init_db(); print(get_latest_snapshot())"

# Test just the pipeline (generates mock data)
python test_pipeline.py

# Test the API
python app.py &
sleep 2
curl http://127.0.0.1:5000/latest
kill %1
```

---

## Manual Data Pull (Advanced)

If you want to simulate real-time updates:

### Option 1: Manual Pull Every 5 Minutes

```bash
# Terminal 1
python app.py

# Terminal 2 (keep running these commands)
python pipeline.py
# Wait 5 minutes
python pipeline.py
# Wait 5 minutes
python pipeline.py
# ... repeat
```

Each time you run `python pipeline.py`, it fetches new data and stores it.

### Option 2: Automated Scheduler (Background)

```bash
# Terminal 1
python app.py

# Terminal 2
python scheduler.py
```

The scheduler will pull data every 5 minutes automatically.

---

## File Descriptions

| File | Purpose |
|------|---------|
| `db.py` | Database operations (store, retrieve, compute metrics) |
| `pipeline.py` | Fetch data from API, handle errors |
| `app.py` | REST API backend (Flask) |
| `dashboard.html` | Frontend (open in browser) |
| `test_metrics.py` | Unit tests (16 tests for metric calculations) |
| `test_pipeline.py` | Integration test with mock data |
| `scheduler.py` | Optional background scheduler |
| `requirements.txt` | Python dependencies |
| `README.md` | Full documentation |
| `LEARNING_GUIDE.md` | Detailed explanation of everything |
| `QUICKSTART.md` | This file |

---

## Troubleshooting

### "Dashboard shows 'Loading...' forever"
- Make sure `app.py` is running in another terminal
- Check browser console for errors (F12)
- Verify you can access http://127.0.0.1:5000/status

### "No data in database"
- Run `python test_pipeline.py` to generate mock data
- Then open the dashboard

### "Tests fail"
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Delete old database: `rm -f exchange_rates.db`
- Run tests again: `pytest test_metrics.py -v`

### "Address already in use" error
- Another process is using port 5000
- Kill it: `lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill -9`
- Or change the port in `app.py` line ~200

---

## Next Steps

1. **Understand the code** - Read through `db.py`, then `pipeline.py`, then `app.py`
2. **Modify and experiment** - Change the rolling window size, add new currencies, etc.
3. **Extend it** - Add alerts, export to CSV, compare multiple currencies
4. **Deploy it** - Put `app.py` on a server, set up real cron job for pulls

---

## Commands Reference

```bash
# Setup
pip install -r requirements.txt

# Generate test data
python test_pipeline.py

# Run backend
python app.py

# Manually pull data
python pipeline.py

# Run scheduler (auto pulls every 5 min)
python scheduler.py

# Run tests
pytest test_metrics.py -v

# Query database
sqlite3 exchange_rates.db "SELECT * FROM snapshots LIMIT 5;"

# Show database schema
sqlite3 exchange_rates.db ".schema"
```

---

## Time Breakdown

- Setup: 2 minutes
- Run pipeline test: 1 minute
- Start backend: 1 minute
- Open dashboard: 30 seconds
- **Total: ~5 minutes to see it working** ✨

Enjoy! 🚀
