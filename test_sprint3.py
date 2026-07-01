# -*- coding: utf-8 -*-
"""Sprint 3 E2E Test: notification pipeline."""
import io, os, sys, json, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BRAIN = os.path.dirname(os.path.abspath(__file__))
BUS_DIR = os.path.join(BRAIN, "bus")

def setup_mock_events():
    """Write mock blackboard events for testing."""
    from bus.blackboard import Blackboard
    
    bb = Blackboard(BUS_DIR, push_limit=5)
    
    ack_file = os.path.join(BUS_DIR, "last_ack.json")
    if os.path.isfile(ack_file):
        os.remove(ack_file)
    
    bb.write_event("probe", "anomaly_detected", {
        "triggered": True,
        "triggers": [{"probe": "agency", "delta": 0.6}]
    }, severity="warning")
    
    bb.write_event("self_evolve", "suggested", {
        "count": 3
    }, severity="info")
    
    bb.write_event("curiosity", "discovery", {
        "cv2": 0.75, "open_qs": 2
    }, severity="info")
    
    bb.write_event("body_daemon", "startup", {"version": "V1.9"}, severity="info")
    
    return bb

def test_AC1_notifier_builds_digest():
    setup_mock_events()
    from bus.notifier import build_morning_report
    
    digest = build_morning_report(BUS_DIR, push_limit=5)
    assert digest is not None, "Should build digest"
    assert len(digest["items"]) > 0, "Should have notification items"
    assert len(digest["items"]) <= 5, "Should respect 5/day limit"
    assert digest["title"], "Should have title"
    print("  AC1 PASS:", digest["displayed"], "items")
    return True

def test_AC2_notify_startup_displays():
    setup_mock_events()
    from notify_on_startup import notify
    
    result = notify()
    assert result["notified"] > 0
    print("  AC2 PASS:", result["notified"], "items notified")
    return True

def test_AC3_ack_prevents_duplicate():
    setup_mock_events()
    from bus.notifier import Notifier
    
    n = Notifier(BUS_DIR)
    digest1 = n.build_digest()
    assert digest1 and len(digest1["items"]) > 0
    
    n.mark_acknowledged()
    
    from bus.notifier import build_morning_report
    digest2 = build_morning_report(BUS_DIR, push_limit=5)
    assert digest2 is None, "Should be None after ack"
    print("  AC3 PASS: Ack prevents duplicate notifications")
    return True

def test_AC4_push_limit_caps():
    setup_mock_events()
    from bus.blackboard import Blackboard
    from bus.notifier import build_morning_report
    
    bb = Blackboard(BUS_DIR, push_limit=5)
    for i in range(8):
        bb.write_event("s" + str(i), "e" + str(i), {"msg": "t" + str(i)}, severity="info")
    
    digest = build_morning_report(BUS_DIR, push_limit=5)
    assert digest["capped"], "Should be capped"
    assert digest["displayed"] == 5
    print("  AC4 PASS: Capped at 5,", digest["overflow_count"], "overflow")
    return True

def test_AC5_source_traceability():
    setup_mock_events()
    from bus.notifier import build_morning_report
    
    digest = build_morning_report(BUS_DIR, push_limit=5)
    for item in digest["items"]:
        assert "source" in item
        assert "event_ids" in item
        assert len(item["event_ids"]) > 0
    print("  AC5 PASS: All", len(digest["items"]), "items have traceable source")
    return True

def test_AC6_body_daemon_v19():
    daemon_path = os.path.join(BRAIN, "body_daemon.py")
    with io.open(daemon_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "V1.9" in content, "Version not V1.9"
    assert "Daily push limit" in content, "Missing push limit check"
    assert "_daily_push_count" in content, "Missing push counter"
    assert "_daily_push_date" in content, "Missing push date"
    print("  AC6 PASS: body_daemon.py V1.9 integrity verified")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("  Sprint 3 E2E Test Suite")
    print("=" * 50)
    
    tests = [
        ("AC1 Notifier Builds Digest", test_AC1_notifier_builds_digest),
        ("AC2 Notify Startup Displays", test_AC2_notify_startup_displays),
        ("AC3 Ack Prevents Duplicate", test_AC3_ack_prevents_duplicate),
        ("AC4 Push Limit Caps at 5", test_AC4_push_limit_caps),
        ("AC5 Source Traceability", test_AC5_source_traceability),
        ("AC6 Body Daemon V1.9", test_AC6_body_daemon_v19),
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    for name, test_fn in tests:
        try:
            print()
            print("--- " + name + " ---")
            test_fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((name, str(e)))
            print("  FAIL: " + str(e))
        except Exception as e:
            failed += 1
            errors.append((name, "ERROR: " + str(e)))
            print("  ERROR: " + str(e))
    
    print()
    print("=" * 50)
    print("  RESULTS: " + str(passed) + "/" + str(passed+failed) + " passed")
    if errors:
        for name, err in errors:
            print("    - " + name + ": " + err)
    print("=" * 50)
    sys.exit(0 if failed == 0 else 1)
