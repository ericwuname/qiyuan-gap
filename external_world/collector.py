# -*- coding: utf-8 -*-
"""External data collector."""
import io, os, sys, sqlite3
from datetime import datetime, timedelta
_brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _brain_dir)

class ExternalCollector:
    def __init__(self, db_path):
        self.db_path = db_path

    def snapshot(self):
        now = datetime.now()
        state = {
            "time_of_day": now.hour / 23.0,
            "day_of_week": now.weekday() / 6.0,
            "is_holiday": 0,
            "request_volume_1h": 0.0,
            "top_keyword_1": "",
            "top_keyword_2": "",
            "external_api_latency": 0.0,
            "user_active_sessions": 0
        }
        try:
            probe_db = os.path.join(_brain_dir, "probe", "probe.db")
            if os.path.exists(probe_db):
                cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
                conn = sqlite3.connect(probe_db)
                conn.row_factory = sqlite3.Row
                q = "SELECT COUNT(1) as cnt FROM probe_self_state WHERE timestamp >= ?"
                row = conn.execute(q, (cutoff,)).fetchone()
                if row:
                    state["request_volume_1h"] = float(row["cnt"])
                conn.close()
        except Exception:
            pass
        return state
