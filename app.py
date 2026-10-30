"""TradeCourt - Streamlit Community Cloud entry point.
On a fresh container there is no replay state, so the app starts the replay
agent in a background thread (one per container) and then renders the same
dashboard used locally. SIMULATED / paper trading only throughout."""
import os, threading, time

BASE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(BASE, ".replay_started")

def _bootstrap():
    try:
        from run_replay import run_replay
        # delay keeps the agent "live" for several minutes so judges can use the
        # kill switch and scenario buttons while the replay is still running
        run_replay(days=120, delay=2.0, cash=1_000_000.0)
    except Exception as e:  # surfaced in Cloud logs; dashboard stays up
        print(f"[bootstrap] replay thread ended with error: {e}", flush=True)

if not os.path.exists(LOCK):
    try:
        open(LOCK, "w").write(str(time.time()))
        threading.Thread(target=_bootstrap, daemon=True).start()
        print("[bootstrap] replay agent started in background thread", flush=True)
    except Exception as e:
        print(f"[bootstrap] could not start replay thread: {e}", flush=True)

import dashboard  # noqa: F401,E402  (renders the UI; set_page_config lives there)
