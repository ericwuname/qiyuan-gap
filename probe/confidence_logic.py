# -*- coding: utf-8 -*-
"""Confidence Logic - per-action-type thresholds and behavior mapping (Round 13)."""

DEFAULT_THRESHOLDS = {
    "ask": 0.7, "tune": 0.85, "evolve": 0.9,
    "heal": 0.8, "idle": 0.6
}

def get_threshold(action_type, thresholds=None):
    """Get confidence threshold for a given action type."""
    t = thresholds or DEFAULT_THRESHOLDS
    return t.get(action_type, 0.7)

def classify_confidence(confidence, action_type=None, thresholds=None):
    """Classify confidence level and recommend behavior."""
    threshold = get_threshold(action_type, thresholds) if action_type else 0.9
    if confidence > threshold:
        return {"level": "high", "behavior": "自信执行"}
    elif confidence > 0.5:
        return {"level": "medium", "behavior": "执行但标注中等置信度"}
    else:
        return {"level": "low", "behavior": "我不确定，请求人类确认"}

def is_confident(confidence, action_type="idle", thresholds=None):
    """Check if confidence meets threshold for action."""
    t = thresholds or DEFAULT_THRESHOLDS
    return confidence > t.get(action_type, 0.7)
