# -*- coding: utf-8 -*-
"""WorldModelEnsemble - 5-model ensemble with confidence & diversity (Round 13).

Trains 5 WorldModel instances with different seeds.
Uses prediction variance as confidence metric.
Includes per-action-type thresholds and diversity monitoring.
"""

import math, os, random, time
from collections import deque

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from .world_model import WorldModel


class WorldModelEnsemble:
    """Ensemble of N WorldModels with confidence estimation and diversity monitoring."""

    def __init__(self, config=None, brain_dir=None):
        cfg = config or {}

        if brain_dir is None:
            brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.num_models = cfg.get("num_models", 5)
        self.diversity_threshold = cfg.get("diversity_threshold", 0.01)
        self.confidence_thresholds = cfg.get("confidence_thresholds", {
            "ask": 0.7, "tune": 0.85, "evolve": 0.9,
            "heal": 0.8, "idle": 0.6
        })

        self.brain_dir = brain_dir
        self.models = []
        self.diversity_history = deque(maxlen=100)

        # Create models with different seeds
        for i in range(self.num_models):
            seed = i * 137 + 42
            random.seed(seed)
            if HAS_NUMPY:
                np.random.seed(seed)
            model = WorldModel(config, brain_dir)
            self.models.append(model)

        # Restore random state
        random.seed()
        if HAS_NUMPY:
            np.random.seed()

    def predict(self, state_raw, action_onehot):
        """All models predict, return mean + variance + confidence."""
        preds = []
        for m in self.models:
            try:
                pred = m.predict(state_raw, action_onehot)
                preds.append(pred)
            except Exception:
                preds.append([0.0] * 8)

        if not preds:
            return {"mean": [0.0]*8, "variance": [0.0]*8, "confidence": 0.0}

        dim = len(preds[0])
        n = len(preds)

        # Mean
        if HAS_NUMPY:
            mean = np.mean(np.asarray(preds, dtype=np.float64), axis=0).tolist()
        else:
            mean = [sum(p[i] for p in preds) / n for i in range(dim)]

        # Variance
        if HAS_NUMPY:
            var = np.var(np.asarray(preds, dtype=np.float64), axis=0).tolist()
        else:
            var = [sum((p[i] - mean[i])**2 for p in preds) / n for i in range(dim)]

        max_var = max(var) if var else 0.0
        confidence = max(0.0, min(1.0, 1.0 - max_var))

        return {
            "mean": [round(v, 6) for v in mean],
            "variance": [round(v, 6) for v in var],
            "confidence": round(confidence, 4),
        }

    def is_confident(self, state_raw, action_onehot, action_type="idle"):
        """Check if confident enough for a given action type."""
        threshold = self.confidence_thresholds.get(action_type, 0.7)
        result = self.predict(state_raw, action_onehot)
        return result["confidence"] > threshold, result

    def get_confidence_level(self, confidence):
        """Classify confidence level with behavior recommendation."""
        if confidence > 0.9:
            return {"level": "high", "behavior": "自信执行"}
        elif confidence > 0.5:
            return {"level": "medium", "behavior": "执行但标注中等置信度"}
        else:
            return {"level": "low", "behavior": "我不确定，请求人类确认"}

    def get_weights_flat(self, model_idx=None):
        """Get flattened weights of a model for diversity calculation."""
        if model_idx is not None:
            model = self.models[model_idx]
            flat = []
            for k in range(len(model.hidden_layers) + 1):
                w = model.weights["W%d" % k]
                b = model.weights["b%d" % k]
                for row in w:
                    flat.extend(row)
                flat.extend(b)
            return flat
        return [self.get_weights_flat(i) for i in range(self.num_models)]

    def check_diversity(self):
        """Compute pairwise Euclidean distance between model weights."""
        weights_list = self.get_weights_flat()

        distances = []
        for i in range(len(weights_list)):
            for j in range(i + 1, len(weights_list)):
                wi = weights_list[i]
                wj = weights_list[j]
                if HAS_NUMPY:
                    dist = float(np.linalg.norm(
                        np.asarray(wi) - np.asarray(wj)))
                else:
                    dist = math.sqrt(
                        sum((a - b)**2 for a, b in zip(wi, wj)))
                distances.append(dist)

        if not distances:
            mean_dist = 0.0
        else:
            mean_dist = sum(distances) / len(distances)

        self.diversity_history.append(mean_dist)

        alert = mean_dist < self.diversity_threshold
        return {
            "mean_distance": round(mean_dist, 6),
            "min_distance": round(min(distances), 6) if distances else 0,
            "max_distance": round(max(distances), 6) if distances else 0,
            "threshold": self.diversity_threshold,
            "alert": alert,
            "message": "模型多样性退化，建议重新初始化或增加噪声" if alert else "模型多样性正常",
        }

    def train_all(self, state_before, action_onehot, state_after):
        """Train all models on the same sample."""
        results = []
        for i, m in enumerate(self.models):
            try:
                result = m.update(state_before, action_onehot, state_after)
                results.append({"model": i, "ok": True, "result": result})
            except Exception as e:
                results.append({"model": i, "ok": False, "error": str(e)})
        return results

    def get_status(self):
        """Return ensemble status summary."""
        steps = [m.step_count for m in self.models]
        diversity = self.check_diversity()

        return {
            "num_models": self.num_models,
            "model_steps": steps,
            "total_steps": sum(steps),
            "avg_steps": sum(steps) / len(steps) if steps else 0,
            "diversity": diversity,
            "confidence_thresholds": self.confidence_thresholds,
        }


# Singleton
_ensemble = None


def get_ensemble(config=None, brain_dir=None):
    global _ensemble
    if _ensemble is None:
        _ensemble = WorldModelEnsemble(config, brain_dir)
    return _ensemble
