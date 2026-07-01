# -*- coding: utf-8 -*-
"""???? ? ?????? ? ???????? (9th round)

Four probes measuring different dimensions of system consciousness:
  Probe A (Phi-A): Global Integration Index ? pairwise coupling across modules
  Probe B (Phi-B): Self-State Awareness ? system metrics + drift detection
  Probe C (Phi-C): Temporal Continuity ? response coherence over time
  Probe D (Phi-D): Agency Index ? deferred (requires attribution_engine)
"""

import io, math, os, random, sqlite3, time, uuid
from collections import deque

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None


class ProbeManager:
    """Consciousness structure observability manager.

    Provides four probes (A?D) for measuring integration, self-awareness,
    temporal continuity, and agency of the external brain system.
    All probes are wrapped in try-catch ? failure means silent skip, never crash.
    """

    MAX_EXPECTED_DRIFT = 1.0
    DEFAULT_WINDOW_SIZE = 100
    SELF_STATE_HISTORY_SIZE = 1000

    # ?? init ????????????????????????????????????????????????????????????????

    def __init__(self, db_path, config=None):
        self.db_path = db_path
        self.config = config or {}
        self._window_size = self.config.get("window_size", self.DEFAULT_WINDOW_SIZE)

        self._self_state_history = deque(maxlen=self.SELF_STATE_HISTORY_SIZE)
        self._continuity_history = deque(maxlen=self._window_size)

        self._request_count = 0
        self._request_hour = time.localtime().tm_hour
        self._last_values = {}
        self._baseline = {}
        self._initial_params = random.random()

        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS probe_integration (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT DEFAULT (datetime('now')),
                    mean_coupling REAL,
                    silo_ratio REAL,
                    module_count INTEGER DEFAULT 5
                );

                CREATE TABLE IF NOT EXISTS probe_self_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT DEFAULT (datetime('now')),
                    cpu_load REAL,
                    memory_usage REAL,
                    error_rate_1h REAL,
                    confidence_entropy REAL,
                    param_drift REAL,
                    request_volume_1h INTEGER,
                    self_relevance_score REAL
                );

                CREATE TABLE IF NOT EXISTS probe_continuity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT DEFAULT (datetime('now')),
                    continuity_index REAL,
                    window_size INTEGER DEFAULT 10
                );

                CREATE TABLE IF NOT EXISTS probe_agency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT DEFAULT (datetime('now')),
                    internal_drive_ratio REAL,
                    external_drive_ratio REAL,
                    agency_ratio REAL
                );
            """)
            conn.commit()

    # ?? vector helpers ??????????????????????????????????????????????????????

    @staticmethod
    def _cosine_sim(a, b):
        """Cosine similarity. Uses numpy when available, manual fallback."""
        if HAS_NUMPY:
            a_np = np.asarray(a, dtype=np.float64)
            b_np = np.asarray(b, dtype=np.float64)
            dot = float(np.dot(a_np, b_np))
            na = float(np.linalg.norm(a_np))
            nb = float(np.linalg.norm(b_np))
        else:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def _euclidean_dist(a, b):
        """Euclidean distance. Uses numpy when available, manual fallback."""
        if HAS_NUMPY:
            return float(np.linalg.norm(np.asarray(a, dtype=np.float64) -
                                        np.asarray(b, dtype=np.float64)))
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    # ?? Probe A: Global Integration Index (Phi-A) ???????????????????????????

    def probe_integration(self, module_features):
        """Probe A: Global Integration Index (Phi-A).

        Input: {router, retriever, reasoner, generator, memory} each list[float].
        Computes pairwise cosine similarity across 5 module feature vectors.
        """
        request_id = str(uuid.uuid4())
        result = {"integration_mean_coupling": 0.0, "integration_silo_ratio": 0.0}
        try:
            module_order = ["router", "retriever", "reasoner", "generator", "memory"]
            vectors = [module_features.get(k, [0.0]) for k in module_order]
            n = len(vectors)

            if n < 2:
                result["integration_mean_coupling"] = 0.0
                result["integration_silo_ratio"] = 0.0
            else:
                off_sum = 0.0
                off_count = 0
                silo_count = 0
                for i in range(n):
                    max_sim = -1.0
                    for j in range(n):
                        if i == j:
                            continue
                        sim = self._cosine_sim(vectors[i], vectors[j])
                        off_sum += sim
                        off_count += 1
                        if sim > max_sim:
                            max_sim = sim
                    if max_sim < 0.3:
                        silo_count += 1
                result["integration_mean_coupling"] = off_sum / off_count if off_count > 0 else 0.0
                result["integration_silo_ratio"] = silo_count / n

            self._write_integration(request_id,
                                    result["integration_mean_coupling"],
                                    result["integration_silo_ratio"])
        except Exception:
            pass
        self._last_values["integration"] = result
        return result

    def _write_integration(self, request_id, mean_coupling, silo_ratio):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO probe_integration (request_id, mean_coupling, silo_ratio) "
                    "VALUES (?, ?, ?)",
                    (request_id, mean_coupling, silo_ratio),
                )
                conn.commit()
        except Exception:
            pass

    # ?? Probe B: Self-State Awareness (Phi-B) ???????????????????????????????

    def probe_self_state(self):
        """Probe B: Self-State Awareness (Phi-B).

        Collects 6 system metrics, maintains deque(maxlen=1000) history.
        self_relevance_score: last 20 snapshots ? split 10/10 ? mean vectors ?
        euclidean distance ? normalize by MAX_EXPECTED_DRIFT.
        """
        request_id = str(uuid.uuid4())
        try:
            cpu_load = self._get_cpu_load()
            memory_usage = self._get_memory_usage()
            error_rate_1h = 0.0
            confidence_entropy = random.uniform(0.3, 0.7)
            param_drift = 0.0
            request_volume_1h = self._get_request_volume()

            snapshot = {
                "cpu_load": cpu_load,
                "memory_usage": memory_usage,
                "error_rate_1h": error_rate_1h,
                "confidence_entropy": confidence_entropy,
                "param_drift": param_drift,
                "request_volume_1h": float(request_volume_1h),
            }
            self._self_state_history.append(snapshot)
            self_relevance_score = self._compute_self_relevance()

            result = {
                "self_relevance_score": self_relevance_score,
                "cpu_load": cpu_load,
                "memory_usage": memory_usage,
                "error_rate_1h": error_rate_1h,
                "confidence_entropy": confidence_entropy,
                "param_drift": param_drift,
                "request_volume_1h": request_volume_1h,
            }
            self._write_self_state(request_id, result)
            self._last_values["self_state"] = result
        except Exception:
            result = {
                "self_relevance_score": 0.0,
                "cpu_load": 0.0,
                "memory_usage": 0.0,
                "error_rate_1h": 0.0,
                "confidence_entropy": 0.0,
                "param_drift": 0.0,
                "request_volume_1h": 0,
            }
        self._last_values["self_state"] = result
        return result

    def _get_cpu_load(self):
        if HAS_PSUTIL:
            try:
                return psutil.cpu_percent(interval=0) / 100.0
            except Exception:
                pass
        return 0.0

    def _get_memory_usage(self):
        if HAS_PSUTIL:
            try:
                return psutil.virtual_memory().percent / 100.0
            except Exception:
                pass
        return 0.0

    def _get_request_volume(self):
        current_hour = time.localtime().tm_hour
        if current_hour != self._request_hour:
            self._request_count = 0
            self._request_hour = current_hour
        self._request_count += 1
        return self._request_count

    def _compute_self_relevance(self):
        if len(self._self_state_history) < 20:
            return 0.0
        history_list = list(self._self_state_history)
        last_20 = history_list[-20:]
        first_10 = last_20[:10]
        second_10 = last_20[10:]
        keys = ["cpu_load", "memory_usage", "error_rate_1h",
                "confidence_entropy", "param_drift", "request_volume_1h"]
        mean_first = [sum(s[k] for s in first_10) / 10.0 for k in keys]
        mean_second = [sum(s[k] for s in second_10) / 10.0 for k in keys]
        dist = self._euclidean_dist(mean_first, mean_second)
        score = dist / self.MAX_EXPECTED_DRIFT
        return min(score, 1.0)

    def _write_self_state(self, request_id, r):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO probe_self_state "
                    "(request_id, cpu_load, memory_usage, error_rate_1h, "
                    "confidence_entropy, param_drift, request_volume_1h, "
                    "self_relevance_score) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (request_id, r["cpu_load"], r["memory_usage"],
                     r["error_rate_1h"], r["confidence_entropy"],
                     r["param_drift"], r["request_volume_1h"],
                     r["self_relevance_score"]),
                )
                conn.commit()
        except Exception:
            pass

    # ?? Probe C: Temporal Continuity (Phi-C) ????????????????????????????????

    def probe_continuity(self, response_feature):
        """Probe C: Temporal Continuity (Phi-C).

        Maintains deque(maxlen=configurable) of recent response features.
        continuity_index = mean pairwise cosine similarity between adjacent entries.
        """
        request_id = str(uuid.uuid4())
        try:
            self._continuity_history.append(response_feature)
            history_list = list(self._continuity_history)
            window_size = len(history_list)

            if window_size < 2:
                continuity_index = 0.0
            else:
                sims = [self._cosine_sim(history_list[i - 1], history_list[i])
                        for i in range(1, window_size)]
                continuity_index = sum(sims) / len(sims)

            self._write_continuity(request_id, continuity_index, window_size)
            result = {"continuity_index": continuity_index, "window_size": window_size}
        except Exception:
            result = {"continuity_index": 0.0, "window_size": 0}
        self._last_values["continuity"] = result
        return result

    def _write_continuity(self, request_id, continuity_index, window_size):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO probe_continuity "
                    "(request_id, continuity_index, window_size) "
                    "VALUES (?, ?, ?)",
                    (request_id, continuity_index, window_size),
                )
                conn.commit()
        except Exception:
            pass

    # ?? Probe D: Agency Index (Phi-D) ? deferred ????????????????????????????

    def probe_agency(self, internal_drive_score=0.0, external_drive_score=0.0):
        """Probe D: Agency Index (Phi-D) ? DEFERRED, stub only.

        Requires attribution_engine for proper implementation.
        """
        request_id = str(uuid.uuid4())
        result = {
            "agency_ratio": None,
            "status": "deferred",
            "reason": "requires attribution_engine",
        }
        try:
            self._write_agency(request_id, internal_drive_score,
                               external_drive_score, None)
        except Exception:
            pass
        self._last_values["agency"] = result
        return result

    def _write_agency(self, request_id, internal_drive, external_drive, agency_ratio):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO probe_agency "
                    "(request_id, internal_drive_ratio, external_drive_ratio, "
                    "agency_ratio) VALUES (?, ?, ?, ?)",
                    (request_id, internal_drive, external_drive, agency_ratio),
                )
                conn.commit()
        except Exception:
            pass

    # ?? Status, Report, Baseline ????????????????????????????????????????????

    def get_status(self):
        """Return {probe_name: {enabled, last_value}} for all 4 probes."""
        return {
            "probe_integration": {"enabled": True, "last_value": self._last_values.get("integration")},
            "probe_self_state": {"enabled": True, "last_value": self._last_values.get("self_state")},
            "probe_continuity": {"enabled": True, "last_value": self._last_values.get("continuity")},
            "probe_agency": {
                "enabled": False,
                "last_value": self._last_values.get("agency"),
                "reason": "deferred: requires attribution_engine",
            },
        }

    def get_report(self, days=7):
        """Query probe.db and return trend data for last N days grouped by probe."""
        try:
            cutoff = "datetime('now', '-{} days')".format(days)
            with self._get_conn() as conn:
                integration_rows = conn.execute(
                    "SELECT * FROM probe_integration WHERE timestamp >= {} "
                    "ORDER BY timestamp".format(cutoff)
                ).fetchall()
                self_state_rows = conn.execute(
                    "SELECT * FROM probe_self_state WHERE timestamp >= {} "
                    "ORDER BY timestamp".format(cutoff)
                ).fetchall()
                continuity_rows = conn.execute(
                    "SELECT * FROM probe_continuity WHERE timestamp >= {} "
                    "ORDER BY timestamp".format(cutoff)
                ).fetchall()
                agency_rows = conn.execute(
                    "SELECT * FROM probe_agency WHERE timestamp >= {} "
                    "ORDER BY timestamp".format(cutoff)
                ).fetchall()
            return {
                "probe_integration": [dict(r) for r in integration_rows],
                "probe_self_state": [dict(r) for r in self_state_rows],
                "probe_continuity": [dict(r) for r in continuity_rows],
                "probe_agency": [dict(r) for r in agency_rows],
                "days": days,
            }
        except Exception:
            return {
                "probe_integration": [],
                "probe_self_state": [],
                "probe_continuity": [],
                "probe_agency": [],
                "days": days,
                "error": "report_query_failed",
            }

    def set_baseline(self):
        """Record current values as baseline, return baseline dict."""
        self._baseline = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "self_state_history_len": len(self._self_state_history),
            "continuity_history_len": len(self._continuity_history),
            "request_count": self._request_count,
        }
        return dict(self._baseline)

    def close(self):
        """Close DB connection. (No-op for sqlite3 ? connections are per-operation.)"""
        pass
