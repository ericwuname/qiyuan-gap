import io, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bus import Blackboard, PermissionMatrix, AuditLog
import tempfile, shutil

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")

tmp = tempfile.mkdtemp()
print("=== test_bus.py: Sprint 1 E2E ===")
print()

# AC1: Blackboard write/read
print("--- AC1: Blackboard write/read ---")
bb = Blackboard(tmp, push_limit=5)
eid = bb.write_event("probe", "anomaly", {"metric": "agency", "value": 0.6})
check("Event ID returned", eid and eid.startswith("evt-"))

events = bb.read_events()
check("Event readable", len(events) == 1 and events[0]["source"] == "probe")

snap = bb.get_snapshot()
check("Snapshot has sources", "probe" in snap["sources"])

health = bb.get_health()
check("Health shows push_limit=5", health["daily_push_limit"] == 5)
check("Health checksum valid", health["checksum_valid"])

# AC2: Permission matrix deny probe writing to rules
print()
print("--- AC2: Permission matrix ---")
pm = PermissionMatrix(tmp)
pm.register_module("probe", ["*"], [])  # read all, write nothing
pm.register_module("self_evolve", ["*"], ["_suggested"])
pm.register_module("router", ["*"], [])

check("probe cannot write rules", not pm.can_write("probe", "rules"))
check("self_evolve can write _suggested", pm.can_write("self_evolve", "_suggested"))
check("self_evolve cannot write rules", not pm.can_write("self_evolve", "rules"))

# AC3: Checksum tamper detection
print()
print("--- AC3: Checksum tamper detection ---")
bb.write_event("test", "heartbeat", {"msg": "tamper_test"})
fp = os.path.join(tmp, "blackboard.json")
with io.open(fp, "r", encoding="utf-8") as f:
    data = json.load(f)
data["events"][-1]["payload"]["tampered"] = True
with io.open(fp, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
try:
    bb.read_events()
    check("Tamper detected (should have raised)", False)
except ValueError as e:
    check("Tamper detected", "checksum" in str(e).lower())

# Fix it back
import hashlib
data.pop("_checksum", None)
data["_checksum"] = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
with io.open(fp, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

# AC5: Audit log
print()
print("--- AC5: Audit log ---")
audit = AuditLog(tmp)
audit.record("write", "probe", "blackboard", "ok", {"event_id": "evt-test"})
audit.record("read", "body_daemon", "blackboard", "ok")
audit.record("write", "self_evolve", "_suggested", "denied", {"reason": "permission"})

entries = audit.query(module="probe")
check("Audit query by module", len(entries) == 1)

entries = audit.query(operation="write")
check("Audit query by operation", len(entries) >= 2)

stats = audit.get_stats()
check("Audit stats total", stats["total_entries"] == 3)

# AC6: Defense line interface (push_limit field present)
print()
print("--- AC6: Defense line interfaces ---")
check("Push limit field exists", hasattr(bb, "daily_push_limit"))
check("Push limit = 5 (configurable)", bb.daily_push_limit == 5)

# Cleanup
shutil.rmtree(tmp, ignore_errors=True)

print()
print(f"=== Results: {passed} passed, {failed} failed ===")
if failed == 0:
    print("  ALL TESTS PASSED")
else:
    print("  SOME TESTS FAILED")
    sys.exit(1)
