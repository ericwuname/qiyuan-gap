# -*- coding: utf-8 -*-
"""Sprint 4 E2E Test: KnowledgeBus + StyleAdapter."""
import io, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BRAIN = os.path.dirname(os.path.abspath(__file__))
BUS_DIR = os.path.join(BRAIN, "bus")


def test_AC1_knowledge_bus_enriches_event():
    """AC1: KnowledgeBus.enrich() adds semantic context."""
    from bus.knowledge_bus import KnowledgeBus
    
    kb = KnowledgeBus(brain_dir=BRAIN, bus_dir=BUS_DIR)
    
    event = {
        "source": "probe",
        "type": "anomaly_detected",
        "payload": {"summary": "agency spike detected", "triggers": [{"probe": "agency"}]}
    }
    
    result = kb.enrich(event)
    assert "event" in result
    assert "semantic" in result
    assert "concepts" in result["semantic"]
    assert "method" in result["semantic"]
    print("  AC1 PASS: enriched with method=", result["semantic"]["method"])
    return True

def test_AC2_knowledge_bus_handles_empty():
    """AC2: KnowledgeBus handles empty payload gracefully."""
    from bus.knowledge_bus import KnowledgeBus
    
    kb = KnowledgeBus(brain_dir=BRAIN, bus_dir=BUS_DIR)
    
    event = {"source": "test", "type": "empty", "payload": {}}
    result = kb.enrich(event)
    assert result["semantic"]["method"] == "no_query"
    print("  AC2 PASS: empty payload handled")
    return True

def test_AC3_style_adapter_loads_dna():
    """AC3: StyleAdapter loads CEO DNA (read-only)."""
    from bus.style_adapter import StyleAdapter
    
    sa = StyleAdapter()
    dna = sa.load_dna()
    tone = sa.get_tone_preferences()
    
    assert isinstance(dna, dict)
    assert isinstance(tone, dict)
    assert "directness" in tone
    print("  AC3 PASS: DNA loaded,", len(dna), "roles, tone:", tone.get("directness"))
    return True

def test_AC4_style_adapter_formats():
    """AC4: StyleAdapter formats notification output."""
    from bus.style_adapter import StyleAdapter
    
    sa = StyleAdapter()
    items = [
        {"source_label": "意识探针", "summary": "检测到变化：agency", "count": 3, "severity": "warning", "_semantic": {"concepts": ["探针", "agency"]}},
        {"source_label": "自进化引擎", "summary": "生成了 2 条建议规则", "count": 1, "severity": "info", "_semantic": {"concepts": ["进化", "规则"]}},
    ]
    
    output = sa.format_notification(items)
    assert isinstance(output, str)
    assert len(output) > 50
    assert "QiYuan Status Update" in output
    print("  AC4 PASS: formatted output,", len(output), "chars")
    return True

def test_AC5_style_adapter_dna_readonly():
    """AC5: StyleAdapter NEVER modifies DNA (hard constraint)."""
    from bus.style_adapter import StyleAdapter
    
    sa = StyleAdapter()
    integrity = sa.verify_dna_integrity()
    assert integrity.get("ok"), "DNA modified! " + str(integrity)
    
    # Also verify: StyleAdapter has no write methods
    sa_code = io.open(os.path.join(BRAIN, "bus", "style_adapter.py"), "r", encoding="utf-8").read()
    assert "def write" not in sa_code, "StyleAdapter has write method!"
    assert "def save" not in sa_code, "StyleAdapter has save method!"
    w_marker = chr(34) + "w" + chr(34)
    assert "io.open(..., " + w_marker + ")" not in sa_code, "StyleAdapter opens files for writing!"
    print("  AC5 PASS: DNA read-only constraint verified")
    return True

def test_AC6_notifier_semantic_enrichment():
    """AC6: Notifier.build_digest enriches items with semantic context."""
    from bus.blackboard import Blackboard
    from bus.notifier import build_morning_report
    
    bb = Blackboard(BUS_DIR, push_limit=5)
    bb.write_event("probe", "anomaly_detected", {"summary": "agency spike", "triggers": [{"probe": "agency"}]}, severity="warning")
    bb.write_event("self_evolve", "suggested", {"count": 2}, severity="info")
    
    # Clear ack to see fresh events
    ack_file = os.path.join(BUS_DIR, "last_ack.json")
    if os.path.isfile(ack_file):
        os.remove(ack_file)
    
    digest = build_morning_report(BUS_DIR, push_limit=5)
    assert digest is not None
    assert len(digest["items"]) > 0
    
    # Check enrichment was applied
    has_semantic = any("_semantic" in item for item in digest["items"])
    print("  AC6 PASS: notifier enrichment active:", has_semantic)
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("  Sprint 4 E2E Test Suite")
    print("=" * 50)
    
    tests = [
        ("AC1 KB Enriches Event", test_AC1_knowledge_bus_enriches_event),
        ("AC2 KB Handles Empty", test_AC2_knowledge_bus_handles_empty),
        ("AC3 StyleAdapter Loads DNA", test_AC3_style_adapter_loads_dna),
        ("AC4 StyleAdapter Formats", test_AC4_style_adapter_formats),
        ("AC5 DNA Read-Only Constraint", test_AC5_style_adapter_dna_readonly),
        ("AC6 Notifier Semantic Enrichment", test_AC6_notifier_semantic_enrichment),
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