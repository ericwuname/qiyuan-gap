# -*- coding: utf-8 -*-
"""RolloutPlanner - multi-step planning via world model (Round 12).

Uses WorldModel.predict() to simulate action sequences,
beam search for optimal selection, gamma discount for far-future,
and auto-execution threshold logic.
"""

import itertools
from collections import deque

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class RolloutPlanner:
    """Multi-step planner using WorldModel for rollouts."""

    def __init__(self, world_model, config=None):
        cfg = config or {}
        self.wm = world_model
        self.horizon = cfg.get("horizon", 5)
        self.gamma = cfg.get("gamma", 0.9)
        self.beam_width = cfg.get("beam_width", 3)
        self.max_seq_len = cfg.get("max_seq_len", 3)
        self.auto_execute_threshold = cfg.get("auto_execute_threshold", 0.2)
        self.actions = ["ask", "tune", "evolve", "heal", "idle"]
        # History of plans
        self.plan_history = deque(maxlen=100)

    def _onehot(self, action):
        """Convert action name to one-hot vector."""
        idx = self.actions.index(action) if action in self.actions else 4
        return [1.0 if i == idx else 0.0 for i in range(5)]

    def _action_name(self, onehot):
        """Convert one-hot vector back to action name."""
        if HAS_NUMPY:
            idx = int(np.argmax(np.asarray(onehot)))
        else:
            idx = max(range(len(onehot)), key=lambda i: onehot[i])
        return self.actions[idx] if idx < len(self.actions) else "idle"

    def _cost(self, state):
        """Compute cost of a state: error_rate + param_drift + continuity."""
        error_rate = state[2] if len(state) > 2 else 0.0
        param_drift = state[4] if len(state) > 4 else 0.0
        continuity = state[7] if len(state) > 7 else 0.5
        return error_rate + param_drift + continuity

    def _simulate(self, state, action_seq):
        """Simulate an action sequence starting from state.
        Returns (final_state, total_cost, trajectory).
        """
        current = list(state)
        total_cost = 0.0
        trajectory = []

        for step_idx, action in enumerate(action_seq):
            action_oh = self._onehot(action)
            try:
                delta = self.wm.predict(current, action_oh)
            except Exception:
                delta = [0.0] * 8
            current = [current[i] + delta[i] for i in range(min(len(current), len(delta)))]
            step_cost = self._cost(current)
            # Apply gamma discount
            total_cost += step_cost * (self.gamma ** step_idx)
            trajectory.append({
                "step": step_idx,
                "action": action,
                "state": list(current),
                "delta": list(delta),
                "cost": step_cost,
                "discounted_cost": step_cost * (self.gamma ** step_idx),
            })

        return current, total_cost, trajectory

    def _generate_candidates(self):
        """Generate candidate action sequences using beam search.
        
        Starts with 5 single-step candidates, expands up to max_seq_len,
        keeping only beam_width best at each depth.
        """
        # Level 1: single actions
        candidates = [(action,) for action in self.actions]

        seq_len = min(self.max_seq_len, self.horizon)
        if seq_len <= 1:
            return candidates

        # Beam search for deeper sequences
        for depth in range(2, seq_len + 1):
            new_candidates = []
            for seq in candidates:
                for action in self.actions:
                    new_candidates.append(seq + (action,))
            # All combos at this depth - keep beam_width best will happen during plan()
            candidates = new_candidates

        return candidates

    def plan(self, current_state):
        """Execute multi-step planning.
        
        Returns dict with best_action, best_seq, expected_cost, trajectory,
        auto_execute flag, and candidates.
        """
        candidates = self._generate_candidates()

        best_seq = None
        best_cost = float('inf')
        best_trajectory = None
        all_results = []

        for seq in candidates:
            final_state, total_cost, trajectory = self._simulate(current_state, seq)
            all_results.append({
                "seq": list(seq),
                "total_cost": round(total_cost, 6),
                "final_state": [round(s, 6) for s in final_state],
            })
            if total_cost < best_cost:
                best_cost = total_cost
                best_seq = seq
                best_trajectory = trajectory

        # Sort candidates by cost
        all_results.sort(key=lambda r: r["total_cost"])

        # Baseline cost: doing nothing (idle repeated)
        idle_seq = ("idle",)
        _, idle_cost, _ = self._simulate(current_state, idle_seq)

        # Check auto-execute threshold
        cost_reduction = (idle_cost - best_cost) / max(idle_cost, 0.001) if idle_cost > 0 else 0
        auto_execute = cost_reduction > self.auto_execute_threshold

        result = {
            "best_action": best_seq[0] if best_seq else "idle",
            "best_seq": list(best_seq) if best_seq else ["idle"],
            "expected_cost": round(best_cost, 6),
            "baseline_cost": round(idle_cost, 6),
            "cost_reduction": round(cost_reduction, 4),
            "auto_execute": auto_execute,
            "horizon": self.horizon,
            "gamma": self.gamma,
            "trajectory": best_trajectory,
            "top_candidates": all_results[:self.beam_width],
        }

        self.plan_history.append(result)
        return result

    def get_status(self):
        """Return planner status summary."""
        return {
            "horizon": self.horizon,
            "gamma": self.gamma,
            "beam_width": self.beam_width,
            "max_seq_len": self.max_seq_len,
            "auto_execute_threshold": self.auto_execute_threshold,
            "plan_count": len(self.plan_history),
        }


# Singleton convenience
_planner = None


def get_planner(world_model=None, config=None):
    global _planner
    if _planner is None and world_model is not None:
        _planner = RolloutPlanner(world_model, config)
    return _planner
