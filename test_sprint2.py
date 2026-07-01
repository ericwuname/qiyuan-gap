# -*- coding: utf-8 -*-
"""Sprint 2 E2E Test: probe anomaly -> self_evolve -> suggested rules."""
import io, os, sys, json, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BRAIN = os.path.dirname(os.path.abspath(__file__))
SUGGESTED_DIR = os.path.join(BRAIN, "rules", "_suggested")

def test_AC1_threshold_detection():
    """AC1: _check_probe_thresholds detects agency spike > 0.2."""
    from body_daemon import _check_probe_thresholds

    state = {"probe_last_values": {}}

    # Mock normal probe results
    probe_results = {
        "self_state": {"score": 0.5, "agency_score": 0.5},
        "integration": {"coupling": 0.3},
        "continuity": {"score": 0.4}
    }

    result = _check_probe_thresholds(state, probe_results)
    assert not result["triggered"], "First run should not trigger (no previous values)"

    # Simulate agency spike
    state["probe_last_values"]["_numeric_agency"] = 0.3
    probe_results2 = {
        "self_state": {"score": 0.9, "agency_score": 0.9},
        "integration": {"coupling": 0.3},
        "continuity": {"score": 0.4}
    }

    result2 = _check_probe_thresholds(state, probe_results2)
    assert result2["triggered"], "Agency spike 0.3->0.9 should trigger!"
    assert any(t["probe"] == "agency" for t in result2["triggers"]), "Should have agency trigger"
    print("  AC1 PASS: Threshold detection works")
    return True

def test_AC2_suggest_never_auto_applies():
    """AC2: self_evolve.suggest() writes to _suggested/ NOT rules/."""
    from self_evolve import SelfEvolve

    evolver = SelfEvolve()
    result = evolver.suggest()

    output_dir = result.get("output_dir", "")
    assert "_suggested" in output_dir or output_dir == "", f"Output dir must be _suggested/ or empty, got: {output_dir}"

    if os.path.isdir(SUGGESTED_DIR):
        for fname in os.listdir(SUGGESTED_DIR):
            if fname.endswith(".yaml"):
                fpath = os.path.join(SUGGESTED_DIR, fname)
                with io.open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                # Safety: no active status in suggested files
                assert "status: active" not in content, f"{fname} has active status - SAFETY VIOLATION!"
                assert ("suggested" in content.lower() or "draft" in content.lower()), \
                    f"{fname}: missing suggested/draft status"

    print(f"  AC2 PASS: {result.get('count', 0)} suggestions, all in _suggested/")
    return True

def test_AC3_blackboard_event_integration():
    """AC3: Blackboard can receive probe anomaly events."""
    from bus import Blackboard, PermissionMatrix, AuditLog

    bus_dir = os.path.join(BRAIN, "bus")
    bb = Blackboard(bus_dir, push_limit=5)
    pm = PermissionMatrix(bus_dir)
    audit = AuditLog(bus_dir)

    pm.register_module("probe", ["*"], [])
    pm.register_module("self_evolve", ["*"], ["_suggested"])
    pm.register_module("body_daemon", ["*"], ["*"])

    event_result = bb.write_event("probe", "anomaly_detected", {
        "triggered": True,
        "triggers": [{"probe": "agency", "delta": 0.6, "current": 0.9, "previous": 0.3}],
        "timestamp": "2026-07-01T00:00:00"
    })

    assert isinstance(event_result, str) and event_result.startswith("evt-"), f"Write event failed: {event_result}"

    events = bb.read_events(limit=100)
    probe_events = [e for e in events if e.get("source") == "probe"]
    assert len(probe_events) > 0, f"Should have at least 1 probe event, got {len(probe_events)}"

    audit.record("trigger", "body_daemon", "self_evolve", "ok", {"count": 3, "reason": "probe_anomaly"})
    print("  AC3 PASS: Blackboard event + audit log works")
    return True

def test_AC4_suggest_file_structure():
    """AC4: Suggested YAML files have correct structure."""
    if not os.path.isdir(SUGGESTED_DIR):
        print("  AC4 SKIP: No _suggested/ directory")
        return True

    files = [f for f in os.listdir(SUGGESTED_DIR) if f.endswith(".yaml")]
    if not files:
        print("  AC4 SKIP: No YAML files in _suggested/")
        return True

    for fname in files[:3]:
        fpath = os.path.join(SUGGESTED_DIR, fname)
        with io.open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        active1 = chr(34) + "status" + chr(34) + ": " + chr(34) + "active" + chr(34)
        assert active1 not in content, f"{fname}: status is active!"
        assert ("suggested" in content.lower() or "draft" in content.lower()), \
            f"{fname}: missing suggested/draft status indicator"

    print(f"  AC4 PASS: {min(3, len(files))} files verified, all safe")
    return True

def test_AC5_suggest_does_not_modify_rules_dir():
    """AC5: self_evolve.suggest() does NOT touch rules/ directory."""
    from self_evolve import SelfEvolve

    rules_dir = os.path.join(BRAIN, "rules")
    if not os.path.isdir(rules_dir):
        print("  AC5 SKIP: No rules/ directory")
        return True

    before = {}
    for root, dirs, files in os.walk(rules_dir):
        for f in files:
            fpath = os.path.join(root, f)
            before[fpath] = os.path.getmtime(fpath)

    evolver = SelfEvolve()
    evolver.suggest()

    after = {}
    for root, dirs, files in os.walk(rules_dir):
        for f in files:
            fpath = os.path.join(root, f)
            after[fpath] = os.path.getmtime(fpath)

    for fpath, mtime in after.items():
        if "_suggested" in fpath:
            continue
        if fpath in before:
            assert before[fpath] == mtime, \
                f"SAFETY VIOLATION: {fpath} was modified by suggest()!"

    print("  AC5 PASS: No rules/ files modified outside _suggested/")
    return True

def test_AC6_body_daemon_v18_integrity():
    """AC6: body_daemon.py is V1.8 with all Sprint 2 components."""
    daemon_path = os.path.join(BRAIN, "body_daemon.py")
    with io.open(daemon_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "V1.8" in content, "Version not bumped to V1.8"
    assert "_check_probe_thresholds" in content, "Missing threshold detection"
    assert "SPRINT2" in content, "Missing Sprint 2 block"
    assert "evolver.suggest()" in content, "Missing self_evolve trigger"
    assert "anomaly_detected" in content, "Missing blackboard event"

    print("  AC6 PASS: body_daemon.py V1.8 integrity verified")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("  Sprint 2 E2E Test Suite")
    print("=" * 50)

    results = []
    tests = [
        ("AC1 Threshold Detection", test_AC1_threshold_detection),
        ("AC2 Suggest Never Auto-Applies", test_AC2_suggest_never_auto_applies),
        ("AC3 Blackboard Event", test_AC3_blackboard_event_integration),
        ("AC4 Suggested File Structure", test_AC4_suggest_file_structure),
        ("AC5 No Rules/ Modification", test_AC5_suggest_does_not_modify_rules_dir),
        ("AC6 Body Daemon V1.8 Integrity", test_AC6_body_daemon_v18_integrity),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        try:
            print(f"\n--- {name} ---")
            test_fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  FAIL: {e}")
        except Exception as e:
            failed += 1
            errors.append((name, f"ERROR: {e}"))
            print(f"  ERROR: {e}")

    print("\n" + "=" * 50)
    print(f"  RESULTS: {passed}/{passed+failed} passed")
    if errors:
        print("  Failures:")
        for name, err in errors:
            print(f"    - {name}: {err}")
    print("=" * 50)
    sys.exit(0 if failed == 0 else 1)