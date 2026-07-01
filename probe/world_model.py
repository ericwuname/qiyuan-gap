# -*- coding: utf-8 -*-
"""World Model - lightweight MLP state transition predictor (Round 10).

Architecture: 13 inputs (8 normalized state + 5 one-hot action) ->
              32 ReLU -> 16 ReLU -> 8 outputs (predicted delta-S).

~1,100 parameters, <0.02ms inference, online SGD with experience replay.
"""

import json, math, os, random, time, uuid
from collections import deque

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from .normalizer import OnlineNormalizer
from .world_model_db import WorldModelDB


class WorldModel:
    """Lightweight MLP predictor with experience replay and online SGD."""

    def __init__(self, config=None, brain_dir=None):
        cfg = config or {}
        if brain_dir is None:
            brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.hidden_layers = cfg.get("hidden_layers", [32, 16])
        self.lr = cfg.get("learning_rate", 0.001)

        replay_cfg = cfg.get("experience_replay", {})
        self.buffer_size = replay_cfg.get("buffer_size", 1000)
        self.batch_size = replay_cfg.get("batch_size", 32)

        surprise_cfg = cfg.get("surprise", {})
        self.surprise_window = surprise_cfg.get("window", 100)

        cold_cfg = cfg.get("cold_start", {})
        self.cold_start_samples = cold_cfg.get("samples", 50)
        self.fallback_method = cold_cfg.get("fallback_method", "sliding_mse")

        model_cfg = cfg.get("model", {})
        self.model_dir = os.path.join(brain_dir, "probe")
        self.version_keep = model_cfg.get("version_keep", 10)
        self.save_interval_steps = model_cfg.get("save_interval_steps", 100)

        self.idle_downsample = cfg.get("idle_downsample", 0.1)

        self.normalizer = OnlineNormalizer(dim=8)
        self.replay_buffer = deque(maxlen=self.buffer_size)
        self.step_count = 0
        self.last_save_time = time.time()
        self.surprise_buffer = deque(maxlen=self.surprise_window)
        self.prev_state = None

        db_path = os.path.join(self.model_dir, "world_model.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = WorldModelDB(db_path)

        self._init_weights()
        self._try_load_weights()

    # ── Weight initialization ────────────────────────────────────────

    def _init_weights(self):
        """Xavier/Glorot uniform initialization."""
        sizes = [13] + self.hidden_layers + [8]
        self.weights = {}
        for k in range(len(sizes) - 1):
            fan_in, fan_out = sizes[k], sizes[k + 1]
            limit = math.sqrt(6.0 / (fan_in + fan_out))
            if HAS_NUMPY:
                self.weights["W%d" % k] = np.random.uniform(
                    -limit, limit, (fan_in, fan_out)).tolist()
                self.weights["b%d" % k] = np.zeros(fan_out).tolist()
            else:
                self.weights["W%d" % k] = [
                    [random.uniform(-limit, limit) for _ in range(fan_out)]
                    for _ in range(fan_in)]
                self.weights["b%d" % k] = [0.0] * fan_out

    # ── Forward pass ──────────────────────────────────────────────────

    def _relu(self, x):
        if HAS_NUMPY:
            return np.maximum(0, np.asarray(x, dtype=np.float64)).tolist()
        return [max(0.0, v) for v in x]

    def _matvec(self, W, x):
        if HAS_NUMPY:
            return (np.asarray(x, dtype=np.float64) @
                    np.asarray(W, dtype=np.float64)).tolist()
        return [sum(x[i] * W[i][j] for i in range(len(x)))
                for j in range(len(W[0]))]

    def _forward(self, x):
        h = x
        for k in range(len(self.hidden_layers) + 1):
            h = self._matvec(self.weights["W%d" % k], h)
            for j in range(len(h)):
                h[j] += self.weights["b%d" % k][j]
            if k < len(self.hidden_layers):
                h = self._relu(h)
        return h

    def predict(self, state_raw, action_onehot):
        """Forward: 13-dim input -> 8-dim delta prediction."""
        state_norm = self.normalizer.normalize(state_raw)
        x = state_norm + action_onehot
        return self._forward(x)

    # ── Online update with experience replay ─────────────────────────

    def update(self, state_before_raw, action_onehot, state_after_raw):
        """One online learning step. Returns (delta_pred, delta_real, surprise)."""
        action_name = self._action_name(action_onehot)

        state_before_norm = self.normalizer.normalize(state_before_raw)
        state_after_norm = self.normalizer.normalize(state_after_raw)

        # Predict
        delta_pred = self.predict(state_before_raw, action_onehot)

        # Actual delta
        delta_real = [state_after_norm[i] - state_before_norm[i]
                      for i in range(8)]

        # Surprise = MSE
        surprise = sum((delta_pred[i] - delta_real[i]) ** 2
                       for i in range(8)) / 8.0
        self.surprise_buffer.append(surprise)

        # Write to DB
        request_id = str(uuid.uuid4())
        self.db.write_prediction(
            request_id, state_before_raw, action_name,
            delta_pred, delta_real, surprise)

        # Add to replay buffer
        self.replay_buffer.append(
            (list(state_before_norm), list(action_onehot), list(delta_real)))

        # SGD update if we have enough samples
        if self.normalizer.ready() and len(self.replay_buffer) >= self.batch_size:
            self._sgd_step()

        self.step_count += 1

        # Aggregate surprise every window
        if self.step_count % self.surprise_window == 0 and self.surprise_buffer:
            buf = list(self.surprise_buffer)
            self.db.write_surprise_aggregate(
                sum(buf) / len(buf), max(buf), min(buf), len(buf))

        # Auto-save weights
        if self.step_count % self.save_interval_steps == 0:
            self.save_weights()

        return delta_pred, delta_real, surprise

    def _action_name(self, onehot):
        names = ["ask", "tune", "evolve", "heal", "idle"]
        for i, v in enumerate(onehot):
            if v == 1.0:
                return names[i] if i < len(names) else "idle"
        return "idle"

    def _sgd_step(self):
        """Mini-batch SGD with experience replay."""
        if len(self.replay_buffer) < self.batch_size:
            return
        batch = random.sample(list(self.replay_buffer), self.batch_size)

        for state_norm, action_oh, delta_real in batch:
            x = list(state_norm) + list(action_oh)
            delta_pred = self._forward(x)

            # MSE gradient: dL/d_pred = 2*(pred - real) / 8
            grad_out = [(delta_pred[i] - delta_real[i]) * 2.0 / 8.0
                        for i in range(8)]

            # Backprop through output layer (no activation)
            W_idx = len(self.hidden_layers)
            h_before = x
            for k in range(W_idx):
                h_before = self._matvec(self.weights["W%d" % k], h_before)
                for j in range(len(h_before)):
                    h_before[j] += self.weights["b%d" % k][j]
                h_before = self._relu(h_before)

            # Update output layer
            lr = self.lr
            W_out = self.weights["W%d" % W_idx]
            b_out = self.weights["b%d" % W_idx]
            for i in range(len(h_before)):
                for j in range(8):
                    W_out[i][j] -= lr * h_before[i] * grad_out[j]
            for j in range(8):
                b_out[j] -= lr * grad_out[j]

    # ── Weights persistence ──────────────────────────────────────────

    def save_weights(self, path=None):
        """Save weights to JSON. Uses timestamp filename, keeps last N versions."""
        if path is None:
            ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            path = os.path.join(
                self.model_dir,
                "world_model_weights_%s.json" % ts)

        data = {
            "weights": {k: v for k, v in self.weights.items()},
            "step_count": self.step_count,
            "normalizer_count": self.normalizer.count,
            "timestamp": ts if path is None else "",
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._cleanup_old_versions()

    def load_weights(self, path):
        """Load weights from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.weights = data["weights"]
        self.step_count = data.get("step_count", 0)

    def _try_load_weights(self):
        """Load latest weight file on startup, if any."""
        versions = self.list_versions()
        if versions:
            latest = versions[0]
            try:
                self.load_weights(latest["path"])
            except Exception:
                pass

    def list_versions(self):
        """List available weight version files sorted by timestamp (newest first)."""
        versions = []
        try:
            for f in os.listdir(self.model_dir):
                if f.startswith("world_model_weights_") and f.endswith(".json"):
                    path = os.path.join(self.model_dir, f)
                    ts = f.replace("world_model_weights_", "").replace(".json", "")
                    versions.append({"filename": f, "path": path, "timestamp": ts})
        except Exception:
            pass
        versions.sort(key=lambda v: v["timestamp"], reverse=True)
        return versions

    def _cleanup_old_versions(self):
        """Keep only the last N version files."""
        versions = self.list_versions()
        for v in versions[self.version_keep:]:
            try:
                os.remove(v["path"])
            except Exception:
                pass

    # ── Status ────────────────────────────────────────────────────────

    def get_status(self):
        """Return status dict."""
        if self.step_count < self.cold_start_samples:
            status = "cold_start"
        elif self.get_surprise_avg() is not None:
            status = "normal"
        else:
            status = "cold_start"

        return {
            "status": status,
            "step_count": self.step_count,
            "surprise_avg": self.get_surprise_avg(),
        }

    def get_surprise_avg(self):
        """Get latest aggregated surprise_avg from DB."""
        result = self.db.get_latest_surprise()
        if result:
            return result[0]
        if self.surprise_buffer:
            buf = list(self.surprise_buffer)
            return sum(buf) / len(buf)
        return None

    def get_surprise_history(self, hours=24):
        """Get surprise history from DB."""
        return self.db.get_surprise_history(hours)

    # ── Data collection ──────────────────────────────────────────────

    def collect_state(self, probe_status, action="idle"):
        """Collect state S_t from probe data and save prev_state."""
        try:
            state = self._extract_state(probe_status)

            if self.prev_state is not None:
                # We have a previous state, can predict and update
                action_oh = self._action_to_onehot(action)
                self.normalizer.update(state)
                self.normalizer.update(self.prev_state)

                if self.normalizer.ready():
                    result = self.update(self.prev_state, action_oh, state)
                else:
                    # Cold start: just buffer
                    result = (None, None, None)

                self.prev_state = state
                return result
            else:
                # First request: just save state as prev_state
                self.prev_state = state
                self.normalizer.update(state)
                return (None, None, None)
        except Exception:
            return (None, None, None)

    def _extract_state(self, probe_status):
        """Extract 8-dim state vector from probe data."""
        ss = probe_status.get("probe_self_state", {}).get("last_value") or {}
        integ = probe_status.get("probe_integration", {}).get("last_value") or {}
        cont = probe_status.get("probe_continuity", {}).get("last_value") or {}

        return [
            ss.get("cpu_load", 0.0),
            ss.get("memory_usage", 0.0),
            ss.get("error_rate_1h", 0.0),
            ss.get("confidence_entropy", 0.5),
            ss.get("param_drift", 0.0),
            float(ss.get("request_volume_1h", 0)),
            integ.get("integration_mean_coupling", 0.5),
            cont.get("continuity_index", 0.5),
        ]

    def _action_to_onehot(self, action):
        mapping = {"ask": 0, "tune": 1, "evolve": 2, "heal": 3, "idle": 4}
        idx = mapping.get(action, 4)
        return [1.0 if i == idx else 0.0 for i in range(5)]