#!/usr/bin/env python3
"""P1-4: 降级路径自动化测试。验证L0-L3降级机制和恢复路径。"""

import unittest, os, sys, json, subprocess

BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BRAIN_DIR)
sys.path.insert(0, BRAIN_DIR)

def _get_brain_output(*args):
    """Run brain CLI and return last JSON object from stdout."""
    proc = subprocess.run(
        [sys.executable, os.path.join(BRAIN_DIR, "cli.py")] + list(args),
        capture_output=True, text=True, timeout=30, cwd=BRAIN_DIR
    )
    # Find last complete JSON object in output
    out = proc.stdout
    json_objects = []
    depth = 0; start = -1
    for i, ch in enumerate(out):
        if ch == '{':
            if depth == 0: start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    json_objects.append(json.loads(out[start:i+1]))
                except: pass
                start = -1
    return json_objects[-1] if json_objects else {}

class DegradePathTests(unittest.TestCase):
    """降级路径三层验证"""

    def test_01_l0_full_function(self):
        """L0全功能：brain status返回brain_ok=true"""
        s = _get_brain_output("status")
        self.assertTrue(s.get("brain_ok", False), f"brain_ok should be true, got: {list(s.keys())}")

    def test_02_l1_memory_fallback(self):
        """L1降级：memory使用fallback模式且功能正常"""
        s = _get_brain_output("status")
        mem = s.get("components", {}).get("memory", {})
        ok = mem.get("ok", False)
        model = mem.get("model", "")
        self.assertTrue(ok or "fallback" in model.lower() or "bge" in model.lower(), 
                       f"Memory fallback should work: ok={ok}, model={model}")

    def test_03_l2_fallback_md(self):
        """L2降级：fallback.md存在且内容有效"""
        fp = os.path.join(BRAIN_DIR, "fallback.md")
        self.assertTrue(os.path.exists(fp), "fallback.md must exist")
        with open(fp, "r", encoding="utf-8") as f:
            c = f.read()
        self.assertGreater(len(c), 100, "fallback.md should be >100 chars")

    def test_04_l3_agents_md_fallback(self):
        """L3降级：AGENTS.md存在且包含治理规则"""
        fp = os.path.join(ROOT_DIR, "AGENTS.md")
        self.assertTrue(os.path.exists(fp), "AGENTS.md must exist")
        with open(fp, "r", encoding="utf-8") as f:
            c = f.read()
        # Check for key governance markers
        markers = ["POL-002", "CEO", "P0", "死规则", "规则一"]
        found = any(m in c for m in markers)
        self.assertTrue(found, "AGENTS.md should contain governance rules")

    def test_05_health_check_dimensions(self):
        """健康检查覆盖5+维度"""
        h = _get_brain_output("health", "check")
        dims = h.get("dimensions", {})
        self.assertGreaterEqual(len(dims), 5, f"Should have >=5 dimensions, got {len(dims)}")

    def test_06_restore_recovery_path(self):
        """恢复路径：restore.py支持--live"""
        rp = os.path.join(BRAIN_DIR, "restore.py")
        self.assertTrue(os.path.exists(rp))
        proc = subprocess.run([sys.executable, rp, "--help"],
            capture_output=True, text=True, timeout=10)
        self.assertIn("--live", proc.stdout)

    def test_07_degrade_state_file(self):
        """降级状态文件存在且格式正确"""
        fp = os.path.join(BRAIN_DIR, "_degrade_state.json")
        self.assertTrue(os.path.exists(fp))
        with open(fp, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertIn("level", state)

    def test_08_restore_dry_run(self):
        """restore.py支持--dry-run"""
        rp = os.path.join(BRAIN_DIR, "restore.py")
        proc = subprocess.run([sys.executable, rp, "--help"],
            capture_output=True, text=True, timeout=10)
        self.assertIn("--dry-run", proc.stdout)

    def test_09_self_heal_degration(self):
        """self_heal.py定义DEGRADE_LEVELS L0-L3"""
        hp = os.path.join(BRAIN_DIR, "self_heal.py")
        self.assertTrue(os.path.exists(hp))
        with open(hp, "r", encoding="utf-8") as f:
            c = f.read()
        self.assertIn("DEGRADE_LEVELS", c)
        for level in ["L0", "L1", "L2", "L3"]:
            self.assertIn(level, c, f"self_heal.py should define {level}")

    def test_10_full_recovery_chain(self):
        """端到端：status->health->restore全链路"""
        s = _get_brain_output("status")
        self.assertTrue(s.get("brain_ok", False))
        h = _get_brain_output("health", "check")
        self.assertIn("overall_status", h)
        rp = os.path.join(BRAIN_DIR, "restore.py")
        self.assertTrue(os.path.exists(rp))

if __name__ == "__main__":
    print("=" * 60)
    print("P1-4 · 降级路径自动化测试")
    print("=" * 60)
    r = unittest.TextTestRunner(verbosity=2)
    result = r.run(unittest.TestLoader().loadTestsFromTestCase(DegradePathTests))
    print("\n" + "=" * 60)
    print(f"Results: {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
    sys.exit(0 if result.wasSuccessful() else 1)