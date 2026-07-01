# -*- coding: utf-8 -*-
"""Tests for RolloutPlanner (Round 12)."""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MockWorldModel:
    def predict(self, state, action_onehot):
        idx = max(range(len(action_onehot)), key=lambda i: action_onehot[i])
        effects = [
            [0.0, 0.0, -0.05, 0.0, 0.0, 0.0, 0.02, 0.01],
            [0.0, 0.0, -0.08, 0.0, -0.1, 0.0, 0.03, 0.03],
            [0.0, 0.0, -0.03, 0.0, -0.15, 0.0, 0.05, 0.05],
            [0.0, 0.0, -0.1, 0.0, 0.0, 0.0, 0.01, 0.02],
            [0.0, 0.0, 0.02, 0.0, 0.01, 0.0, -0.01, -0.01],
        ]
        return effects[idx % len(effects)]

from brain.probe.rollout_planner import RolloutPlanner

S = [0.3, 0.5, 0.05, 0.4, 0.1, 10.0, 0.6, 0.5]

def test_init():
    wm = MockWorldModel()
    p = RolloutPlanner(wm)
    assert p.horizon == 5
    assert p.gamma == 0.9
    print("PASS test_init")

def test_single_step():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 1})
    r = p.plan(S)
    assert "best_action" in r
    assert r["best_action"] in ["ask","tune","evolve","heal","idle"]
    print("PASS test_single_step")

def test_multi_step():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 2})
    r = p.plan(S)
    assert len(r["best_seq"]) <= 2
    print("PASS test_multi_step")

def test_gamma():
    wm = MockWorldModel()
    p1 = RolloutPlanner(wm, {"gamma": 1.0, "max_seq_len": 2})
    p2 = RolloutPlanner(wm, {"gamma": 0.5, "max_seq_len": 2})
    r1 = p1.plan(S)
    r2 = p2.plan(S)
    assert r1["expected_cost"] != r2["expected_cost"]
    print("PASS test_gamma")

def test_auto_execute():
    wm = MockWorldModel()
    p1 = RolloutPlanner(wm, {"auto_execute_threshold": 0.99, "max_seq_len": 1})
    p2 = RolloutPlanner(wm, {"auto_execute_threshold": 0.0, "max_seq_len": 1})
    assert p1.plan(S)["auto_execute"] == False
    assert p2.plan(S)["auto_execute"] == True
    print("PASS test_auto_execute")

def test_cost_reduction():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 1})
    r = p.plan(S)
    assert "cost_reduction" in r
    print("PASS test_cost_reduction")

def test_trajectory():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 2})
    r = p.plan(S)
    for step in r["trajectory"]:
        assert "action" in step
    print("PASS test_trajectory")

def test_candidates():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 1})
    r = p.plan(S)
    assert len(r["top_candidates"]) <= 3
    print("PASS test_candidates")

def test_perf():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 1})
    start = time.perf_counter()
    for _ in range(100):
        p.plan(S)
    ms = (time.perf_counter() - start) / 100 * 1000
    assert ms < 5.0, f"Slow: {ms:.4f}ms"
    print(f"PASS test_perf ({ms:.4f}ms)")

def test_status():
    wm = MockWorldModel()
    p = RolloutPlanner(wm)
    s = p.get_status()
    assert "horizon" in s
    print("PASS test_status")

def test_different_states():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 1})
    r1 = p.plan([0.3]*8)
    r2 = p.plan([0.9]*8)
    assert r1["expected_cost"] != r2["expected_cost"]
    print("PASS test_different_states")

def test_sorted():
    wm = MockWorldModel()
    p = RolloutPlanner(wm, {"max_seq_len": 1})
    r = p.plan(S)
    costs = [c["total_cost"] for c in r["top_candidates"]]
    assert costs == sorted(costs)
    print("PASS test_sorted")

if __name__ == "__main__":
    tests = [test_init, test_single_step, test_multi_step, test_gamma,
             test_auto_execute, test_cost_reduction, test_trajectory,
             test_candidates, test_perf, test_status, test_different_states, test_sorted]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
    print("%d/%d tests passed" % (passed, len(tests)))
