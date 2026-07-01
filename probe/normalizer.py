# -*- coding: utf-8 -*-
"""Online normalization module for 8-dim state vectors.

Normalization rules (per spec):
  Dims 0-3: cpu_load, memory_usage, error_rate_1h, confidence_entropy
              already ~[0,1], pass-through
  Dims 4-5: param_drift, request_volume_1h -> min-max normalize to [0,1]
  Dims 6-7: integration_mean_coupling, continuity_index -> z-score normalize
  Cold start (count < 50): identity (no normalization).

Updates statistics every update_interval samples.
"""

import io, math

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None


class OnlineNormalizer:
    """Online normalization for 8-dimensional state vectors."""
    
    def __init__(self, dim=8, update_interval=100):
        self.dim = dim
        self.update_interval = update_interval
        self.count = 0
        self.min_vals = [float("inf")] * dim
        self.max_vals = [float("-inf")] * dim
        self.sum_vals = [0.0] * dim
        self.sum_sq_vals = [0.0] * dim
        self._cached_mean = [0.0] * dim
        self._cached_std = [1.0] * dim
        self._stats_stale = True
    
    def update(self, state_vector):
        """Feed a new state vector to update rolling statistics."""
        self.count += 1
        for i in range(self.dim):
            v = state_vector[i]
            if v < self.min_vals[i]:
                self.min_vals[i] = v
            if v > self.max_vals[i]:
                self.max_vals[i] = v
            self.sum_vals[i] += v
            self.sum_sq_vals[i] += v * v
        if self.count % self.update_interval == 0:
            self._stats_stale = True
    
    def _refresh_stats(self):
        """Recompute cached mean/std from running sums."""
        if not self._stats_stale:
            return
        n = float(self.count)
        for i in range(self.dim):
            self._cached_mean[i] = self.sum_vals[i] / n
            var = (self.sum_sq_vals[i] / n) - (self._cached_mean[i] ** 2)
            self._cached_std[i] = math.sqrt(max(var, 1e-8))
        self._stats_stale = False
    
    def normalize(self, state_vector):
        """Normalize an 8-dim state vector.
        Dims 0-3: pass-through. Dims 4-5: min-max. Dims 6-7: z-score.
        Cold start -> identity.
        """
        if self.count < 50:
            return list(state_vector)
        self._refresh_stats()
        out = [0.0] * self.dim
        for i in range(self.dim):
            v = state_vector[i]
            if i < 4:
                out[i] = max(0.0, min(1.0, v))
            elif i < 6:
                rng = self.max_vals[i] - self.min_vals[i]
                out[i] = (v - self.min_vals[i]) / rng if rng > 1e-8 else 0.5
            else:
                out[i] = (v - self._cached_mean[i]) / self._cached_std[i]
        return out
    
    def inverse(self, norm_vector):
        """Reverse normalization. Returns raw 8-dim list."""
        if self.count < 50:
            return list(norm_vector)
        self._refresh_stats()
        out = [0.0] * self.dim
        for i in range(self.dim):
            v = norm_vector[i]
            if i < 4:
                out[i] = v
            elif i < 6:
                rng = self.max_vals[i] - self.min_vals[i]
                out[i] = v * rng + self.min_vals[i] if rng > 1e-8 else v
            else:
                out[i] = v * self._cached_std[i] + self._cached_mean[i]
        return out
    
    def ready(self):
        """Return True if enough samples collected (count >= 50)."""
        return self.count >= 50
