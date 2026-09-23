"""
Optional scheduler for automated data pulls.

This runs data pulls on a schedule without using external libraries like APScheduler.
Perfect for simple use cases like this assignment.

Usage:
    python scheduler.py

    # Then in another terminal:
    python app.py

    # Open dashboard.html in your browser

Why no APScheduler?
- We want minimal dependencies
- For this use case, simple threading is sufficient
- APScheduler would be overkill for a take-home project
- In production, would use proper orchestration (Airflow, etc.)

How it works:
1. Creates a background thread that runs every N seconds
2. Thread calls pipeline.run_pull()
3. Never blocks the main thread
4. Graceful shutdown with Ctrl+C
"""

import time
import threading
from datetime import datetime
from pipeline import run_pull

# How often to pull data (in seconds)
PULL_INTERVAL = 300  # 5 minutes

# Control the scheduler
scheduler_running = False
scheduler_thread = None


def pull_worker():
    """
    Background worker thread that pulls data on a schedule.
    
    This function runs in a separate thread and never returns.
    It periodically calls run_pull() with the specified interval.
    """
    global scheduler_running
    
    print(f"[Scheduler] Started. Will pull data every {PULL_INTERVAL} seconds ({PULL_INTERVAL/60:.1f} minutes)")
    
    while scheduler_running:
        try:
            print(f"\n[Scheduler] {datetime.now().isoformat()} - Running scheduled pull...")
            run_pull()
            
            # Sleep until the next pull, but check every second if we should stop
            for _ in range(PULL_INTERVAL):
                if not scheduler_running:
                    break
                time.sleep(1)
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Scheduler] Error in pull cycle: {e}")
            # Wait a bit before retrying
            time.sleep(10)


def start_scheduler():
    """
    Start the background scheduler thread.
    
    Safe to call multiple times (only starts if not already running).
    """
    global scheduler_running, scheduler_thread
    
    if scheduler_running:
        print("[Scheduler] Already running!")
        return
    
    scheduler_running = True
    scheduler_thread = threading.Thread(target=pull_worker, daemon=False)
    scheduler_thread.start()
    
    print("[Scheduler] Background scheduler started")


def stop_scheduler():
    """
    Stop the background scheduler thread.
    
    Gracefully shuts down the scheduler.
    """
    global scheduler_running, scheduler_thread
    
    if not scheduler_running:
        return
    
    print("\n[Scheduler] Stopping...")
    scheduler_running = False
    
    if scheduler_thread:
        scheduler_thread.join(timeout=5)
        print("[Scheduler] Stopped")


if __name__ == "__main__":
    print("="*60)
    print("Currency Exchange Rate Data Scheduler")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Pull interval: {PULL_INTERVAL} seconds ({PULL_INTERVAL/60:.1f} minutes)")
    print(f"  API: Frankfurter")
    print(f"\nUsage:")
    print(f"  1. Run this script: python scheduler.py")
    print(f"  2. In another terminal: python app.py")
    print(f"  3. Open dashboard.html in your browser")
    print(f"\nPress Ctrl+C to stop\n")
    print("="*60 + "\n")
    
    try:
        # Start the scheduler
        start_scheduler()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n")
        stop_scheduler()
        print("Goodbye!")
