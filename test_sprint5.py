# -*- coding: utf-8 -*-
"""Sprint 5 E2E Test: External Gateway + Identity Declaration."""
import io, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BRAIN = os.path.dirname(os.path.abspath(__file__))
BUS_DIR = os.path.join(BRAIN, "bus")

def test_AC1_identity_declares():
    """AC1: IdentityDeclaration generates valid declaration."""
    from bus.identity_declaration import IdentityDeclaration
    
    id_decl = IdentityDeclaration()
    decl = id_decl.declare("model_router", "api_call", "abc123")
    
    assert decl["identity"]["identity"] == "Qiyuan"
    assert "declaration_id" in decl
    assert decl["declaration_id"].startswith("qy-")
    assert decl["declared_by"] == "Qiyuan/model_router"
    assert decl["payload_hash"] == "abc123"
    print("  AC1 PASS: identity declared as", decl["declared_by"])
    return True

def test_AC2_identity_verifies():
    """AC2: IdentityDeclaration.verify() validates correctly."""
    from bus.identity_declaration import IdentityDeclaration
    
    id_decl = IdentityDeclaration()
    decl = id_decl.declare("test", "test", "hash")
    
    result = id_decl.verify(decl)
    assert result["ok"], "Valid declaration should pass: " + str(result)
    
    # Fake should fail
    fake = {"identity": {"identity": "Imposter"}}
    result2 = id_decl.verify(fake)
    assert not result2["ok"], "Fake identity should fail"
    print("  AC2 PASS: valid passes, fake rejected")
    return True

def test_AC3_gateway_permission_check():
    """AC3: ExternalGateway checks permissions correctly."""
    from bus.external_gateway import ExternalGateway
    
    gw = ExternalGateway(brain_dir=r"D:/0.个人文档/个人文档/启元智能")
    
    # model_router can api_call
    perm = gw.check_permission("model_router", "api_call")
    assert perm["ok"], "model_router should be allowed api_call"
    assert perm["requires_ceo"], "api_call requires CEO confirm"
    
    # body_daemon cannot send
    perm2 = gw.check_permission("body_daemon", "send")
    assert not perm2["ok"], "body_daemon should NOT be allowed send"
    print("  AC2->AC3 PASS: permission matrix enforced")
    return True

def test_AC4_gateway_blocks_without_ceo():
    """AC4: ExternalGateway blocks CEO-gated actions without confirmation."""
    from bus.external_gateway import ExternalGateway
    
    gw = ExternalGateway(brain_dir=r"D:/0.个人文档/个人文档/启元智能")
    
    result = gw.send("model_router", "api_call", {"test": True}, ceo_confirmed=False)
    assert not result["ok"], "Should block without CEO confirmation"
    assert result.get("requires_ceo"), "Should indicate CEO confirmation needed"
    print("  AC4 PASS: blocked without CEO confirmation")
    return True

def test_AC5_gateway_allows_with_ceo():
    """AC5: ExternalGateway allows with CEO confirmation."""
    from bus.external_gateway import ExternalGateway
    
    gw = ExternalGateway(brain_dir=r"D:/0.个人文档/个人文档/启元智能")
    
    result = gw.send("model_router", "api_call", {"test": "hello"}, ceo_confirmed=True)
    assert result["ok"], "Should allow with CEO confirmation: " + str(result)
    assert "declaration" in result
    assert result["declaration"]["identity"]["identity"] == "Qiyuan"
    assert "event_id" in result
    print("  AC5 PASS: allowed with CEO confirmation, declaration attached")
    return True

def test_AC6_external_audit_trail():
    """AC6: External gateway creates audit trail."""
    from bus.external_gateway import ExternalGateway
    
    gw = ExternalGateway(brain_dir=r"D:/0.个人文档/个人文档/启元智能")
    
    # Send with CEO confirmation
    gw.send("model_router", "api_call", {"audit_test": True}, ceo_confirmed=True)
    
    # Check audit log
    logs = gw.get_audit_log(limit=10)
    assert len(logs) > 0, "Should have audit entries"
    
    last = logs[-1]
    assert last["status"] == "sent"
    assert last["module"] == "model_router"
    print("  AC6 PASS: audit trail recorded,", len(logs), "entries")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("  Sprint 5 E2E Test Suite")
    print("=" * 50)
    
    tests = [
        ("AC1 Identity Declares", test_AC1_identity_declares),
        ("AC2 Identity Verifies", test_AC2_identity_verifies),
        ("AC3 Permission Check", test_AC3_gateway_permission_check),
        ("AC4 Blocks Without CEO", test_AC4_gateway_blocks_without_ceo),
        ("AC5 Allows With CEO", test_AC5_gateway_allows_with_ceo),
        ("AC6 External Audit Trail", test_AC6_external_audit_trail),
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