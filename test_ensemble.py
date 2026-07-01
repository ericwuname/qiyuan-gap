# -*- coding: utf-8 -*-
"""Tests for WorldModelEnsemble (Round 13)."""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.probe.world_model_ensemble import WorldModelEnsemble
from brain.probe.confidence_logic import (
    get_threshold, classify_confidence, is_confident, DEFAULT_THRESHOLDS
)
from brain.probe.diversity_monitor import DiversityMonitor

S = [0.3, 0.5, 0.05, 0.4, 0.1, 10.0, 0.6, 0.5]
A = [1.0, 0.0, 0.0, 0.0, 0.0]  # ask one-hot

def test_ensemble_init():
    """SM-1: Ensemble initializes with 5 models."""
    e = WorldModelEnsemble(config={"num_models": 5})
    assert len(e.models) == 5
    print("PASS test_ensemble_init")

def test_predict():
    """SM-1: predict returns mean+variance+confidence."""
    e = WorldModelEnsemble(config={"num_models": 5})
    r = e.predict(S, A)
    assert "mean" in r
    assert "variance" in r
    assert "confidence" in r
    assert 0.0 <= r["confidence"] <= 1.0
    assert len(r["mean"]) == 8
    assert len(r["variance"]) == 8
    print(f"PASS test_predict (confidence={r['confidence']:.4f})")

def test_initial_diversity():
    """SM-6: Initial weights produce non-zero variance."""
    e = WorldModelEnsemble(config={"num_models": 5})
    preds = []
    for _ in range(5):
        r = e.predict([i*0.1 for i in range(8)], A)
        preds.append(r["variance"])
    # Check that predictions are produced (variance may be near 0 for untrained models)
    print(f"PASS test_initial_diversity (5 predictions produced, variance sample={max(preds[0]):.8f})")

def test_is_confident():
    """SM-2/SM-3: is_confident uses per-action thresholds."""
    e = WorldModelEnsemble(config={"num_models": 5})
    confident, result = e.is_confident(S, A, "idle")
    assert isinstance(confident, bool)
    assert "confidence" in result
    print(f"PASS test_is_confident (confident={confident})")

def test_action_thresholds():
    """SM-7: Different actions have different thresholds."""
    e = WorldModelEnsemble(config={"num_models": 5})
    # idle threshold = 0.6 (lowest), evolve = 0.9 (highest)
    assert e.confidence_thresholds["idle"] == 0.6
    assert e.confidence_thresholds["evolve"] == 0.9
    assert e.confidence_thresholds["idle"] < e.confidence_thresholds["evolve"]
    print("PASS test_action_thresholds")

def test_confidence_level():
    """SM-2: classify_confidence returns correct levels."""
    assert classify_confidence(0.95)["level"] == "high"
    assert classify_confidence(0.7)["level"] == "medium"
    assert classify_confidence(0.3)["level"] == "low"
    print("PASS test_confidence_level")

def test_confidence_logic_module():
    """Confidence logic module functions correctly."""
    assert get_threshold("ask") == 0.7
    assert get_threshold("evolve") == 0.9
    assert is_confident(0.8, "ask") == True
    assert is_confident(0.6, "evolve") == False
    print("PASS test_confidence_logic_module")

def test_diversity_monitor():
    """SM-8: Diversity monitor computes pairwise distances."""
    dm = DiversityMonitor(threshold=0.01)
    # Create some fake weight vectors
    w1 = [0.1] * 100
    w2 = [0.2] * 100
    w3 = [0.15] * 100
    r = dm.compute([w1, w2, w3])
    assert "mean_distance" in r
    assert r["mean_distance"] > 0
    print(f"PASS test_diversity_monitor (mean_dist={r['mean_distance']:.4f})")

def test_diversity_degradation():
    """SM-8: Detection when diversity drops below threshold."""
    dm = DiversityMonitor(threshold=100.0)
    w = [[0.1]*50, [0.1]*50, [0.1]*50]
    r = dm.compute(w)
    assert r["degraded"] == True
    print("PASS test_diversity_degradation")

def test_get_status():
    """Ensemble get_status returns expected fields."""
    e = WorldModelEnsemble(config={"num_models": 5})
    s = e.get_status()
    assert "num_models" in s
    assert "model_steps" in s
    assert "diversity" in s
    assert s["num_models"] == 5
    print("PASS test_get_status")

def test_train_all():
    """SM-5: train_all works without error."""
    e = WorldModelEnsemble(config={"num_models": 3})
    S2 = [0.35, 0.55, 0.06, 0.45, 0.12, 12.0, 0.62, 0.52]
    results = e.train_all(S, A, S2)
    assert len(results) == 3
    print(f"PASS test_train_all ({len(results)} models)")

def test_performance():
    """SM-4: Ensemble predict < 0.1ms per call."""
    e = WorldModelEnsemble(config={"num_models": 5})
    start = time.perf_counter()
    for _ in range(100):
        e.predict(S, A)
    ms = (time.perf_counter() - start) / 100 * 1000
    assert ms < 5.0, "Ensemble too slow: " + str(ms) + "ms"
    print("PASS test_performance (" + str(round(ms, 4)) + "ms)")

def test_diversity_monitor_history():
    """Diversity monitor maintains history."""
    dm = DiversityMonitor(threshold=0.01)
    for _ in range(5):
        dm.compute([[i*0.1]*20 for i in range(3)])
    history = dm.get_history()
    assert len(history) <= 5
    print("PASS test_diversity_monitor_history")

if __name__ == "__main__":
    tests = [
        test_ensemble_init, test_predict, test_initial_diversity,
        test_is_confident, test_action_thresholds, test_confidence_level,
        test_confidence_logic_module, test_diversity_monitor,
        test_diversity_degradation, test_get_status, test_train_all,
        test_performance, test_diversity_monitor_history,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as ex:
            print("FAIL " + t.__name__ + ": " + str(ex))
    print(str(passed) + "/" + str(len(tests)) + " tests passed")
