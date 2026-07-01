# -*- coding: utf-8 -*-
"""Curiosity Engine - drives exploration from surprise (Round 11).

Converts world_model surprise_score into curiosity_score,
injects into tune/evolve objective functions.
Includes cold-start handling, saturation protection, and exploration bonus.
"""

from collections import deque

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    if HAS_NUMPY:
        a_arr = np.asarray(a, dtype=np.float64)
        b_arr = np.asarray(b, dtype=np.float64)
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
    else:
        dot = sum(ai * bi for ai, bi in zip(a, b))
        norm_a = math.sqrt(sum(ai * ai for ai in a))
        norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


import math


class CuriosityEngine:
    """Converts surprise_score -> curiosity_score, drives exploration."""

    def __init__(self, config=None):
        cfg = config or {}

        # Core parameters
        self.alpha = cfg.get("alpha", 0.1)
        self._original_alpha = self.alpha
        self.ema_alpha = cfg.get("ema_alpha", 0.1)
        self.cold_start_samples = cfg.get("cold_start_samples", 10)

        # Weight factors per action type
        self.weight_factors = cfg.get("weight_factors", {
            "idle": 1.0, "ask": 1.0, "tune": 2.0,
            "evolve": 3.0, "heal": 1.0
        })

        # Exploration bonus
        self.exploration_bonus_window = cfg.get("exploration_bonus_window", 5)

        # Saturation protection
        self.saturation_threshold = cfg.get("saturation_threshold", 0.8)
        self.saturation_hours = cfg.get("saturation_hours", 24)
        self.recovery_threshold = cfg.get("recovery_threshold", 0.3)
        self.recovery_hours = cfg.get("recovery_hours", 1)
        self.saturation_check_interval = cfg.get("saturation_check_interval", 300)  # 5min

        # Internal state
        self.curiosity_ema = 0.0
        self.history_max = 0.0
        self.sample_count = 0
        self.history = deque(maxlen=288)  # ~24h at 5-min intervals
        self.recent_params = deque(maxlen=self.exploration_bonus_window)
        self.saturation_triggered = False
        self.last_saturation_check = 0

    def compute(self, surprise_score, action="idle"):
        """Compute curiosity from surprise_score. Returns dict."""
        weight = self.weight_factors.get(action, 1.0)
        curiosity_raw = surprise_score * weight

        # EMA update
        self.curiosity_ema = (
            self.ema_alpha * curiosity_raw +
            (1.0 - self.ema_alpha) * self.curiosity_ema
        )
        self.history_max = max(self.history_max, self.curiosity_ema)
        self.sample_count += 1

        # Normalize
        if self.sample_count < self.cold_start_samples or self.history_max == 0:
            curiosity_normalized = 0.5
            status = "cold_start"
        else:
            curiosity_normalized = min(1.0, self.curiosity_ema / max(self.history_max, 0.001))
            status = "normal"

        # Track history
        self.history.append(curiosity_normalized)

        return {
            "curiosity_raw": round(curiosity_raw, 6),
            "curiosity_ema": round(self.curiosity_ema, 6),
            "curiosity_normalized": round(curiosity_normalized, 4),
            "surprise_source": round(surprise_score, 6),
            "action": action,
            "status": status,
        }

    def exploration_bonus(self, current_params):
        """Compute exploration bonus: 1 - cosine_similarity(current, recent_mean)."""
        self.recent_params.append(list(current_params))
        if len(self.recent_params) < 2:
            return 0.0
        if HAS_NUMPY:
            recent_mean = np.mean(np.asarray(self.recent_params, dtype=np.float64), axis=0)
        else:
            n = len(self.recent_params)
            dim = len(self.recent_params[0])
            recent_mean = [sum(p[d] for p in self.recent_params) / n for d in range(dim)]
        cos_sim = _cosine_similarity(current_params, recent_mean)
        return round(1.0 - cos_sim, 6)

    def inject_objective(self, original_cost, curiosity_normalized, exploration_bonus_val):
        """Inject curiosity into objective: cost + alpha * curiosity * bonus."""
        return original_cost + self.alpha * curiosity_normalized * exploration_bonus_val

    def check_saturation(self, current_time=None):
        """Check and apply saturation protection.
        
        Returns dict with saturation status and action taken.
        """
        if current_time is None:
            import time
            current_time = time.time()

        # Throttle checks
        if current_time - self.last_saturation_check < self.saturation_check_interval:
            return {"saturated": self.saturation_triggered, "alpha": self.alpha}

        self.last_saturation_check = current_time

        # Check saturation: all recent values > threshold
        needed = int(self.saturation_hours * 3600 / self.saturation_check_interval)
        recent = list(self.history)[-min(needed, len(self.history)):]
        if len(recent) >= needed and all(c > self.saturation_threshold for c in recent):
            if not self.saturation_triggered:
                old_alpha = self.alpha
                self.alpha = max(0.01, self.alpha * 0.5)
                self.saturation_triggered = True
                return {
                    "saturated": True,
                    "alpha": self.alpha,
                    "old_alpha": old_alpha,
                    "message": "Curiosity saturation: alpha reduced from %.4f to %.4f" % (old_alpha, self.alpha)
                }

        # Check recovery
        if self.saturation_triggered:
            recovery_needed = int(self.recovery_hours * 3600 / self.saturation_check_interval)
            recovery_recent = list(self.history)[-min(recovery_needed, len(self.history)):]
            if len(recovery_recent) >= recovery_needed and all(c < self.recovery_threshold for c in recovery_recent):
                old_alpha = self.alpha
                self.alpha = self._original_alpha
                self.saturation_triggered = False
                return {
                    "saturated": False,
                    "alpha": self.alpha,
                    "old_alpha": old_alpha,
                    "message": "Curiosity recovered: alpha restored to %.4f" % self.alpha
                }

        return {"saturated": self.saturation_triggered, "alpha": self.alpha}

    def get_status(self):
        """Return current curiosity status."""
        return {
            "curiosity_raw": round(self.curiosity_ema, 6),
            "curiosity_ema": round(self.curiosity_ema, 6),
            "curiosity_normalized": (
                round(min(1.0, self.curiosity_ema / max(self.history_max, 0.001)), 4)
                if self.sample_count >= self.cold_start_samples and self.history_max > 0
                else 0.5
            ),
            "sample_count": self.sample_count,
            "alpha": self.alpha,
            "saturated": self.saturation_triggered,
            "cold_start": self.sample_count < self.cold_start_samples,
        }


# Singleton convenience
_engine = None


def get_engine(config=None):
    global _engine
    if _engine is None and config is not None:
        _engine = CuriosityEngine(config)
    return _engine
