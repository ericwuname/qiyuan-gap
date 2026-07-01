# -*- coding: utf-8 -*-
"""External World Model - predicts external environment trends."""
import io, os, sys, json, sqlite3, random, time
from datetime import datetime, timedelta
try: import numpy as np; HAS_NUMPY = True
except ImportError: HAS_NUMPY = False; np = None
_brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _brain_dir)

class ExternalWorldModel:
    """MLP model predicting external state (8-dim).
    Architecture: 8 -> 128 -> 64 -> 32 -> 8 (mirrors WorldModel)
    """
    def __init__(self, db_path, config=None):
        self.db_path = db_path
        self.config = config or {}
        self._init_db()
        self._cold_start_complete = False
        self._samples_collected = 0
        self._start_time = time.time()
        self._buffer = []
        self._weights = self._random_weights()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS external_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime("now")),
                    request_volume_1h REAL,
                    top_keyword_1 TEXT,
                    top_keyword_2 TEXT,
                    external_api_latency REAL,
                    time_of_day REAL,
                    day_of_week REAL,
                    is_holiday INTEGER DEFAULT 0,
                    user_active_sessions INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS external_world_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime("now")),
                    status TEXT,
                    samples_collected INTEGER DEFAULT 0,
                    cold_start_complete INTEGER DEFAULT 0
                );
            """)
            conn.commit()

    def _random_weights(self):
        if HAS_NUMPY:
            rng = np.random.RandomState(42)
            return {
                "w1": rng.randn(8, 128).tolist(),
                "w2": rng.randn(128, 64).tolist(),
                "w3": rng.randn(64, 32).tolist(),
                "w4": rng.randn(32, 8).tolist()
            }
        return {}

    def _mlp_forward(self, x):
        if not HAS_NUMPY or not self._weights.get("w1"):
            return [0.0] * 8
        h = np.tanh(np.dot(x, self._weights["w1"]))
        h = np.tanh(np.dot(h, self._weights["w2"]))
        h = np.tanh(np.dot(h, self._weights["w3"]))
        return np.dot(h, self._weights["w4"]).tolist()

    def collect(self, state):
        with self._get_conn() as conn:
            conn.execute("INSERT INTO external_predictions (request_volume_1h,top_keyword_1,top_keyword_2,external_api_latency,time_of_day,day_of_week,is_holiday,user_active_sessions) VALUES (?,?,?,?,?,?,?,?)", [state.get(k,0) for k in ["request_volume_1h","top_keyword_1","top_keyword_2","external_api_latency","time_of_day","day_of_week","is_holiday","user_active_sessions"]])
            conn.commit()
        self._samples_collected += 1
        if self._samples_collected >= 24 and not self._cold_start_complete:
            self._cold_start_complete = True
            self._train_initial()

    def _train_initial(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM external_predictions ORDER BY id DESC LIMIT 168").fetchall()
        if len(rows) < 10: return
        self._samples_collected = len(rows)

    def predict(self, current_state=None):
        if not self._cold_start_complete:
            remaining = 24 - self._samples_collected
            return {"status": "cold_start", "hours_remaining": max(0, remaining), "prediction": None}
        if current_state is None:
            with self._get_conn() as conn:
                row = conn.execute("SELECT * FROM external_predictions ORDER BY id DESC LIMIT 1").fetchone()
            if not row: return {"prediction": None}
            current_state = [row[k] for k in ["request_volume_1h","top_keyword_1","top_keyword_2","external_api_latency","time_of_day","day_of_week","is_holiday","user_active_sessions"]]
        pred = self._mlp_forward(current_state)
        return {"status": "active", "prediction": {"request_volume_1h": pred[0], "next_hour_volume": pred[0]}}

    def status(self):
        remaining = max(0, 24 - self._samples_collected) if not self._cold_start_complete else 0
        return {"cold_start_complete": self._cold_start_complete, "samples_collected": self._samples_collected, "hours_remaining": remaining}
