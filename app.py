"""
Flask backend API for serving exchange rate data and metrics.

This provides three main endpoints:
- GET /latest - Get current rates with derived metrics
- GET /history - Get historical time series data
- GET /pull - Manually trigger a data pull (useful for testing)

The dashboard makes requests to these endpoints to display data.

Usage:
    python app.py

Then open dashboard.html in your browser.
"""

from flask import Flask, jsonify, request
from datetime import datetime, timedelta
from db import (
    get_latest_snapshot,
    get_history,
    get_all_bases,
    get_all_currencies_for_base,
    init_db
)
from pipeline import run_pull
import traceback

app = Flask(__name__)

# Enable CORS for development (allow requests from file://)
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response


@app.route("/latest", methods=["GET"])
def latest():
    """
    Get the most recent exchange rate snapshot with derived metrics.
    
    Query parameters (optional):
        - base: Base currency (default "USD")
    
    Response:
        {
            "status": "success",
            "data": {
                "timestamp": "2025-09-22T10:30:00",
                "base": "USD",
                "rates": {"EUR": 0.92, "GBP": 0.81, ...},
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
        }
    
    Or if no data:
        {
            "status": "no_data",
            "message": "No data available yet. Please run a data pull first.",
            "data": null
        }
    """
    try:
        base = request.args.get("base", "USD").upper()
        
        snapshot = get_latest_snapshot(base)
        
        if snapshot is None:
            return jsonify({
                "status": "no_data",
                "message": "No data available yet. Please run a data pull first.",
                "data": None
            }), 200
        
        return jsonify({
            "status": "success",
            "data": snapshot
        }), 200
    
    except Exception as e:
        print(f"Error in /latest: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e),
            "data": None
        }), 500


@app.route("/history", methods=["GET"])
def history():
    """
    Get historical exchange rate snapshots.
    
    Query parameters (optional):
        - base: Base currency (default "USD")
        - currencies: Comma-separated list of currencies to filter by
        - limit: Maximum number of snapshots (default 100)
    
    Example:
        /history?base=USD&currencies=EUR,GBP&limit=30
    
    Response:
        {
            "status": "success",
            "data": [
                {
                    "timestamp": "2025-09-22T10:30:00",
                    "base": "USD",
                    "rates": {"EUR": 0.92, "GBP": 0.81}
                },
                ...
            ],
            "count": 30
        }
    """
    try:
        base = request.args.get("base", "USD").upper()
        
        # Parse optional currency filter
        currencies_param = request.args.get("currencies", "")
        currencies = [c.strip().upper() for c in currencies_param.split(",")] if currencies_param else None
        
        # Parse optional limit
        limit = request.args.get("limit", 100, type=int)
        limit = min(limit, 500)  # Cap at 500 to prevent abuse
        
        snapshots = get_history(base, currencies, limit)
        
        return jsonify({
            "status": "success",
            "data": snapshots,
            "count": len(snapshots)
        }), 200
    
    except Exception as e:
        print(f"Error in /history: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e),
            "data": None
        }), 500


@app.route("/pull", methods=["GET", "POST"])
def pull():
    """
    Manually trigger a data pull from the Frankfurter API.
    
    This is useful for:
    - Testing the pipeline manually
    - Triggering pulls from external systems
    - Debugging API issues
    
    Response on success:
        {
            "status": "success",
            "message": "Data pull completed successfully"
        }
    
    Response on failure:
        {
            "status": "failed",
            "message": "Error details...",
            "note": "The dashboard will show the last known good data"
        }
    """
    try:
        success = run_pull()
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Data pull completed successfully"
            }), 200
        else:
            return jsonify({
                "status": "failed",
                "message": "Data pull encountered an error (see server logs)",
                "note": "The dashboard will show the last known good data"
            }), 200  # Still 200 because it's not a server error
    
    except Exception as e:
        print(f"Error in /pull: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/status", methods=["GET"])
def status():
    """
    Get the overall system status.
    
    Useful for monitoring and debugging.
    
    Response:
        {
            "status": "healthy",
            "bases": ["USD"],
            "currencies": ["EUR", "GBP", "JPY", ...],
            "last_update": "2025-09-22T10:30:00" or null,
            "records_count": 42
        }
    """
    try:
        bases = get_all_bases()
        
        # Get available currencies for first base (or empty if no data)
        currencies = []
        if bases:
            currencies = get_all_currencies_for_base(bases[0])
        
        # Get timestamp of last snapshot
        last_snapshot = get_latest_snapshot(bases[0] if bases else "USD")
        last_update = last_snapshot["timestamp"] if last_snapshot else None
        
        # Count total records (rough estimate)
        try:
            from db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM snapshots")
            count = cursor.fetchone()[0]
            conn.close()
        except:
            count = 0
        
        return jsonify({
            "status": "healthy",
            "bases": bases,
            "currencies": currencies,
            "last_update": last_update,
            "records_count": count
        }), 200
    
    except Exception as e:
        print(f"Error in /status: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


@app.route("/", methods=["GET"])
def root():
    """
    Root endpoint with API documentation.
    """
    return jsonify({
        "app": "Currency Exchange Rate Dashboard",
        "description": "A data pipeline for fetching, storing, and visualizing exchange rates",
        "endpoints": {
            "GET /latest": "Get current rates with derived metrics",
            "GET /history": "Get historical rate snapshots",
            "GET /pull": "Manually trigger a data pull",
            "GET /status": "Get system status and metadata",
            "GET /": "This message"
        },
        "docs": "See dashboard.html for the UI"
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors gracefully."""
    return jsonify({
        "status": "error",
        "message": "Endpoint not found",
        "available_endpoints": {
            "GET /latest": "Get current rates",
            "GET /history": "Get historical data",
            "GET /pull": "Trigger a pull",
            "GET /status": "System status"
        }
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors gracefully."""
    return jsonify({
        "status": "error",
        "message": "Internal server error",
        "note": "Check server logs for details"
    }), 500


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("✓ Database ready")
    print("\n" + "="*60)
    print("Starting Flask server...")
    print("="*60)
    print("\nAPI Documentation:")
    print("  GET http://127.0.0.1:5000/latest  - Current rates")
    print("  GET http://127.0.0.1:5000/history - Historical data")
    print("  GET http://127.0.0.1:5000/pull    - Trigger a pull")
    print("  GET http://127.0.0.1:5000/status  - System status")
    print("\nDashboard:")
    print("  Open dashboard.html in your browser")
    print("\nData Pipeline:")
    print("  python pipeline.py - Pull data manually")
    print("="*60 + "\n")
    
    # Run the Flask development server
    # debug=True means it auto-reloads when you change the code
    app.run(debug=True, port=5000, use_reloader=False)
