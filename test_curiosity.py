# -*- coding: utf-8 -*-
"""Tests for CuriosityEngine (Round 11)."""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.probe.curiosity import CuriosityEngine, _cosine_similarity


def test_init():
    """CU-1: Engine initializes with default config."""
    engine = CuriosityEngine()
    assert engine.alpha == 0.1
    assert engine.cold_start_samples == 10
    assert engine.sample_count == 0
    print("PASS test_init")


def test_cold_start():
    """CU-7: Cold start returns 0.5 for first samples."""
    engine = CuriosityEngine()
    for i in range(5):
        result = engine.compute(0.3, "ask")
        assert result["curiosity_normalized"] == 0.5, "Sample " + str(i) + ": expected 0.5"
    assert engine.get_status()["cold_start"] == True
    print("PASS test_cold_start")


def test_normalization():
    """CU-1: After cold start, curiosity normalized to [0,1]."""
    engine = CuriosityEngine(cold_start_samples=3)
    for i in range(3):
        engine.compute(0.1, "ask")
    result = engine.compute(0.5, "ask")
    assert 0 <= result["curiosity_normalized"] <= 1.0
    assert engine.get_status()["cold_start"] == False
    print("PASS test_normalization")


def test_weight_factors():
    """CU-1: tune/evolve have higher weight factors."""
    engine = CuriosityEngine()
    r_ask = engine.compute(0.3, "ask")
    r_tune = engine.compute(0.3, "tune")
    r_evolve = engine.compute(0.3, "evolve")
    assert r_tune["curiosity_raw"] > r_ask["curiosity_raw"]
    assert r_evolve["curiosity_raw"] > r_ask["curiosity_raw"]
    print("PASS test_weight_factors")


def test_exploration_bonus():
    """CU-2: exploration_bonus in [0,1] range."""
    engine = CuriosityEngine()
    bonus = engine.exploration_bonus((0.1, 0.2, 0.3))
    assert 0.0 <= bonus <= 1.0
    bonus2 = engine.exploration_bonus((0.5, 0.6, 0.7))
    assert 0.0 <= bonus2 <= 1.0
    print("PASS test_exploration_bonus")


def test_inject_objective():
    """CU-2: Objective function injection."""
    engine = CuriosityEngine()
    new_obj = engine.inject_objective(10.0, 0.5, 0.2)
    assert new_obj == 10.01
    print("PASS test_inject_objective")


def test_saturation_check():
    """CU-8: Saturation check does not crash."""
    engine = CuriosityEngine(saturation_hours=1, saturation_check_interval=300,
                             recovery_hours=3, cold_start_samples=3)
    for _ in range(3):
        engine.compute(0.3, "ask")
    result = engine.check_saturation(0)
    assert "saturated" in result
    assert engine.alpha == 0.1
    print("PASS test_saturation_check")


def test_get_status():
    """CU-4: Status returns correct fields."""
    engine = CuriosityEngine()
    status = engine.get_status()
    assert "curiosity_raw" in status
    assert "curiosity_normalized" in status
    assert "alpha" in status
    assert status["cold_start"] == True
    print("PASS test_get_status")


def test_cosine_similarity():
    """Helper: cosine_similarity."""
    sim = _cosine_similarity([1.0, 0.0], [1.0, 0.0])
    assert abs(sim - 1.0) < 0.001
    sim = _cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert abs(sim - 0.0) < 0.001
    print("PASS test_cosine_similarity")


def test_performance():
    """CU-5: compute under 1ms per call (safety bound)."""
    engine = CuriosityEngine()
    for _ in range(20):
        engine.compute(0.3, "ask")
    start = time.perf_counter()
    for _ in range(1000):
        engine.compute(0.3, "ask")
    elapsed = time.perf_counter() - start
    per_call_ms = elapsed / 1000 * 1000
    assert per_call_ms < 1.0, "Too slow: " + format(per_call_ms, ".4f") + "ms per call"
    print("PASS test_performance (" + format(per_call_ms, ".4f") + "ms per call)")


def test_saturation_protection():
    """CU-8: Verify saturation alpha reduction via direct state manipulation."""
    engine = CuriosityEngine(saturation_threshold=0.5, saturation_hours=1,
                             saturation_check_interval=300, recovery_hours=3,
                             cold_start_samples=3)
    for _ in range(3):
        engine.compute(0.9, "evolve")
    needed = int(12.0)
    engine.history.extend([0.9] * needed)
    result = engine.check_saturation(10000)
    assert "saturated" in result
    print("PASS test_saturation_protection")


def test_saturation_recovery():
    """CU-8: Verify alpha recovery."""
    engine = CuriosityEngine(saturation_threshold=0.8, saturation_hours=1,
                             saturation_check_interval=300, recovery_threshold=0.3,
                             recovery_hours=3, cold_start_samples=3)
    for _ in range(3):
        engine.compute(0.9, "evolve")
    needed = int(12.0)
    engine.history.extend([0.9] * needed)
    engine.check_saturation(10000)
    assert engine.saturation_triggered == True
    engine.history.clear()
    engine.history.extend([0.1] * needed)
    engine.check_saturation(20000)
    assert engine.saturation_triggered == False
    assert engine.alpha == 0.1
    print("PASS test_saturation_recovery")


if __name__ == "__main__":
    tests = [
        test_init, test_cold_start, test_normalization, test_weight_factors,
        test_exploration_bonus, test_inject_objective, test_saturation_check,
        test_get_status, test_cosine_similarity, test_performance,
        test_saturation_protection, test_saturation_recovery,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print("FAIL " + t.__name__ + ": " + str(e))
    print(str(passed) + "/" + str(len(tests)) + " tests passed")