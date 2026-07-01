# -*- coding: utf-8 -*-
"""Diversity Monitor - tracks ensemble model weight diversity (Round 13)."""

import math
from collections import deque

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class DiversityMonitor:
    """Monitors pairwise weight distance between ensemble models."""

    def __init__(self, threshold=0.01, history_size=100):
        self.threshold = threshold
        self.history = deque(maxlen=history_size)
        self.alert_count = 0

    def compute(self, weights_list):
        """Compute pairwise distances and check for degradation."""
        distances = []
        for i in range(len(weights_list)):
            for j in range(i + 1, len(weights_list)):
                wi = weights_list[i]
                wj = weights_list[j]
                if HAS_NUMPY:
                    dist = float(np.linalg.norm(
                        np.asarray(wi, dtype=np.float64) -
                        np.asarray(wj, dtype=np.float64)))
                else:
                    dist = math.sqrt(
                        sum((a - b)**2 for a, b in zip(wi, wj)))
                distances.append(dist)

        mean_dist = sum(distances) / len(distances) if distances else 0.0
        self.history.append(mean_dist)

        degraded = mean_dist < self.threshold
        if degraded:
            self.alert_count += 1

        return {
            "mean_distance": round(mean_dist, 6),
            "min_distance": round(min(distances), 6) if distances else 0,
            "max_distance": round(max(distances), 6) if distances else 0,
            "threshold": self.threshold,
            "degraded": degraded,
            "alert_count": self.alert_count,
        }

    def get_history(self):
        """Return recent diversity history."""
        return list(self.history)
