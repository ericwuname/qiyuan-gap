# -*- coding: utf-8 -*-
"""World Model database module (Round 10)."""

import json, sqlite3


class WorldModelDB:
    """Database for world model predictions and surprise aggregation."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS world_model_prediction (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    request_id TEXT,
                    state_before TEXT,
                    action TEXT,
                    delta_predicted TEXT,
                    delta_actual TEXT,
                    surprise REAL
                );

                CREATE TABLE IF NOT EXISTS world_model_surprise (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    surprise_avg REAL,
                    surprise_max REAL,
                    surprise_min REAL,
                    sample_count INTEGER DEFAULT 100
                );
            """)

    def write_prediction(self, request_id, state_before, action,
                         delta_predicted, delta_actual, surprise):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO world_model_prediction "
                    "(request_id, state_before, action, delta_predicted, "
                    "delta_actual, surprise) VALUES (?, ?, ?, ?, ?, ?)",
                    (request_id,
                     json.dumps(state_before),
                     action,
                     json.dumps(delta_predicted),
                     json.dumps(delta_actual),
                     surprise),
                )
                conn.commit()
        except Exception:
            pass

    def write_surprise_aggregate(self, surprise_avg, surprise_max,
                                  surprise_min, sample_count=100):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO world_model_surprise "
                    "(surprise_avg, surprise_max, surprise_min, sample_count) "
                    "VALUES (?, ?, ?, ?)",
                    (surprise_avg, surprise_max, surprise_min, sample_count),
                )
                conn.commit()
        except Exception:
            pass

    def get_latest_surprise(self):
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT surprise_avg, surprise_max, surprise_min "
                    "FROM world_model_surprise ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    return (row["surprise_avg"], row["surprise_max"],
                            row["surprise_min"])
        except Exception:
            pass
        return None

    def get_surprise_history(self, hours=24):
        try:
            cutoff = "datetime('now', '-{} hours')".format(hours)
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT timestamp, surprise_avg FROM world_model_surprise "
                    "WHERE timestamp >= {} ORDER BY timestamp".format(cutoff)
                ).fetchall()
                return [{"timestamp": r["timestamp"],
                         "surprise_avg": r["surprise_avg"]} for r in rows]
        except Exception:
            return []

    def get_prediction_count(self):
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM world_model_prediction"
                ).fetchone()
                return row["cnt"] if row else 0
        except Exception:
            return 0

    def close(self):
        pass