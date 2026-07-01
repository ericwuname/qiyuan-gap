# -*- coding: utf-8 -*-
"""启元智能 · 启元智脑 P1-1 端到端集成测试

覆盖10个全链路场景，验证 brain CLI 对外接口的完整性和健壮性。

用法: python -m unittest brain.test_e2e -v
"""

import io, os, sys, json, unittest, subprocess, tempfile, time, threading, re, shutil

# 固定路径
_BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_CLI = os.path.join(_BRAIN_DIR, "cli.py")
_DEGRADE_STATE = os.path.join(_BRAIN_DIR, "_degrade_state.json")
_PYTHON = sys.executable


def _run_brain(*args, timeout=30, **kwargs):
    """Helper: 调用 brain CLI 并返回 CompletedProcess。"""
    cmd = [_PYTHON, _BRAIN_CLI] + list(args)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          text=True, encoding="utf-8", env=env, **kwargs)


def _parse_json(result):
    """从 subprocess 输出中提取 JSON 对象（兼容 MemoryEngine 等前置日志行）。"""
    # 合并 stdout+stderr，从最后一个 { 开始的行找 JSON 块
    combined = result.stdout
    if not combined:
        combined = result.stderr
    # 找到第一个 { 的位置
    idx = combined.find("{")
    if idx == -1:
        return None
    # 从该位置开始解析 JSON
    candidate = combined[idx:]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # 尝试逐行从后往前找
    for line in reversed(combined.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _read_degrade_state():
    """读取当前降级状态文件。"""
    if os.path.exists(_DEGRADE_STATE):
        with io.open(_DEGRADE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"level": 0}


def _write_degrade_state(level=0):
    """重置降级状态到指定级别。"""
    state = {
        "level": level,
        "name": f"L{level}",
        "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with io.open(_DEGRADE_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


class TestE2E(unittest.TestCase):
    """端到端集成测试 — 10 个全链路场景"""

    @classmethod
    def setUpClass(cls):
        """确保测试开始前大脑处于 L0（全功能）状态。"""
        cls._original_degrade = _read_degrade_state()
        cls._restore_needed = cls._original_degrade.get("level", 0) != 0
        if cls._restore_needed:
            _write_degrade_state(0)

    @classmethod
    def tearDownClass(cls):
        """恢复原始降级状态。"""
        if cls._restore_needed:
            with io.open(_DEGRADE_STATE, "w", encoding="utf-8") as f:
                json.dump(cls._original_degrade, f, ensure_ascii=False, indent=2)

    def setUp(self):
        """每个测试前确保 L0 状态。"""
        current = _read_degrade_state()
        if current.get("level", 0) != 0:
            _write_degrade_state(0)

    # ── 场景1: 正常·文件归位 ──────────────────────────────────

    def test_01_normal_file_placement(self):
        """brain rule check "新建文件并归位" → 匹配规则 → 返回结果"""
        result = _run_brain("rule", "check", "新建文件并归位")
        data = _parse_json(result)
        self.assertIsNotNone(data, "应返回有效JSON")
        self.assertTrue(data.get("matched"), "应匹配到规则")
        self.assertGreater(data.get("count", 0), 0, "匹配数应>0")
        self.assertIsInstance(data.get("rules"), list)
        rule_ids = [r.get("id", "") for r in data.get("rules", [])]
        self.assertTrue(
            any("CONST" in rid for rid in rule_ids),
            f"应包含宪法规则，实际: {rule_ids}",
        )

    # ── 场景2: 正常·项目创建 ──────────────────────────────────

    def test_02_normal_project_creation(self):
        """brain rule check "创建新项目" → 查规则 → 查知识库 → 多规则匹配"""
        result = _run_brain("rule", "check", "创建新项目")
        data = _parse_json(result)
        self.assertIsNotNone(data, "应返回有效JSON")
        self.assertTrue(data.get("matched"), "应匹配到规则")
        self.assertGreater(data.get("count", 0), 0, "匹配数应>0")
        rule_ids = [r.get("id", "") for r in data.get("rules", [])]
        self.assertTrue(
            any("HR" in rid or "CONST" in rid for rid in rule_ids),
            f"应包含立项相关规则，实际: {rule_ids}",
        )

    # ── 场景3: 空结果 ────────────────────────────────────────

    def test_03_empty_result(self):
        """brain rule check "xyz不存在的操作abc123" → matched=false, count=0"""
        result = _run_brain("rule", "check", "xyz不存在的操作abc123")
        data = _parse_json(result)
        self.assertIsNotNone(data, "应返回有效JSON")
        self.assertFalse(data.get("matched"), "不应匹配任何规则")
        self.assertEqual(data.get("count", 0), 0, "匹配数应为0")
        self.assertEqual(len(data.get("rules", [])), 0, "规则列表应为空")

    # ── 场景4: 超时 ──────────────────────────────────────────

    def test_04_timeout_handling(self):
        """模拟超时: subprocess.run 设置极短 timeout → TimeoutExpired"""
        with self.assertRaises(subprocess.TimeoutExpired):
            _run_brain("rule", "check", "测试操作", timeout=0.001)

    # ── 场景5: 降级 L1（记忆降级） ─────────────────────────────

    def test_05_degrade_l1_memory_fallback(self):
        """brain health degrade 1 → 记忆引擎降级至 TF-IDF fallback"""
        # 执行降级
        result = _run_brain("health", "degrade", "1")
        data = _parse_json(result)
        self.assertIsNotNone(data, "降级命令应返回有效JSON")
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("current_level"), 1)
        self.assertIn("L1", data.get("current_name", ""))

        # 验证降级状态文件
        state = _read_degrade_state()
        self.assertEqual(state.get("level"), 1)

        # 降级后 status 仍可正常工作
        result2 = _run_brain("status")
        data2 = _parse_json(result2)
        self.assertIsNotNone(data2, "降级后 status 应仍返回JSON")
        self.assertTrue(data2.get("brain_ok"),
                        f"降级后大脑仍应在线, data2={data2}")

    # ── 场景6: 降级 L2（规则引擎不可用 → fallback.md） ──────────

    def test_06_degrade_l2_rule_fallback(self):
        """brain health degrade 2 → 规则引擎降级 → fallback.md 兜底"""
        result = _run_brain("health", "degrade", "2")
        data = _parse_json(result)
        self.assertIsNotNone(data, "降级命令应返回有效JSON")
        self.assertEqual(data.get("current_level"), 2)
        self.assertIn("L2", data.get("current_name", ""))

        state = _read_degrade_state()
        self.assertEqual(state.get("level"), 2)

        # 验证 fallback.md 存在且可读
        fallback_path = os.path.join(_BRAIN_DIR, "fallback.md")
        self.assertTrue(os.path.isfile(fallback_path),
                        f"fallback.md 应存在: {fallback_path}")
        with io.open(fallback_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("三条铁律", content)

    # ── 场景7: 降级 L3（大脑完全不可用 → AGENTS.md 回退） ───────

    def test_07_degrade_l3_full_fallback(self):
        """brain health degrade 3 → 完全降级 → AGENTS.md 兜底规则"""
        result = _run_brain("health", "degrade", "3")
        data = _parse_json(result)
        self.assertIsNotNone(data, "降级命令应返回有效JSON")
        self.assertEqual(data.get("current_level"), 3)
        self.assertIn("L3", data.get("current_name", ""))

        state = _read_degrade_state()
        self.assertEqual(state.get("level"), 3)

        # 验证 AGENTS.md 存在（根目录回退规则）
        agents_path = os.path.join(os.path.dirname(_BRAIN_DIR), "AGENTS.md")
        self.assertTrue(os.path.isfile(agents_path),
                        f"AGENTS.md 应存在: {agents_path}")
        with io.open(agents_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("三条铁律", content)

    # ── 场景8: 冲突检测 ──────────────────────────────────────

    def test_08_conflict_detection(self):
        """两次 brain safe-write 同时写同一文件 → 一个成功一个检测到冲突"""
        # 使用 brain 目录内的临时文件（safe-write 工作区校验要求在 workspace 内）
        tmpfile = os.path.join(_BRAIN_DIR, "_test_e2e_conflict.txt")
        try:
            # 清理可能残留的旧文件
            if os.path.exists(tmpfile):
                os.remove(tmpfile)

            go_event = threading.Event()
            results = []

            def writer(content, operator):
                go_event.wait()
                r = subprocess.run(
                    [_PYTHON, _BRAIN_CLI, "safe-write", tmpfile, content,
                     "--operator", operator],
                    capture_output=True, text=True, encoding="utf-8",
                    timeout=15,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                results.append(r)

            t1 = threading.Thread(target=writer, args=("content-A-t1", "thread1"))
            t2 = threading.Thread(target=writer, args=("content-B-t2", "thread2"))

            t1.start()
            t2.start()
            time.sleep(0.15)
            go_event.set()

            t1.join(timeout=15)
            t2.join(timeout=15)

            self.assertEqual(len(results), 2, "应有2个写入结果")

            parsed = []
            for r in results:
                d = _parse_json(r)
                self.assertIsNotNone(d, f"safe-write 应返回有效JSON, stdout={r.stdout}")
                parsed.append(d)

            ok_count = sum(1 for p in parsed if p.get("ok"))
            conflict_count = sum(
                1 for p in parsed
                if not p.get("ok") and "conflict" in str(p).lower()
            )
            error_ok = sum(
                1 for p in parsed
                if not p.get("ok") and "conflict" not in str(p).lower()
            )

            self.assertGreaterEqual(ok_count, 1,
                                    f"至少一个写入应成功, results={parsed}")
            self.assertGreaterEqual(
                ok_count + conflict_count, 2,
                f"所有结果应成功或冲突检测, results={parsed}",
            )
        finally:
            if os.path.exists(tmpfile):
                os.remove(tmpfile)

    # ── 场景9: 权限拒绝 (P0 拦截) ──────────────────────────────

    def test_09_permission_denied_p0_block(self):
        """brain rule classify "删除宪法文件" → P0 级别 → 需要 CEO 确认"""
        result = _run_brain("rule", "classify", "删除宪法文件")
        data = _parse_json(result)
        self.assertIsNotNone(data, "classify 应返回有效JSON")
        self.assertEqual(data.get("level"), "P0",
                         f"删除宪法文件应为 P0，实际: {data.get('level')}")
        self.assertIn("CEO", data.get("reason", ""),
                      "P0 原因应提及 CEO 确认")

    # ── 场景10: 错误输入 ─────────────────────────────────────

    def test_10_error_input_empty(self):
        """brain rule check "" → 空输入拒绝 → 返回友好提示"""
        result = _run_brain("rule", "check", "")
        data = _parse_json(result)
        self.assertIsNotNone(data, "空输入应返回JSON错误响应")
        self.assertFalse(data.get("matched"), "空输入不应匹配规则")
        error_msg = data.get("error", "")
        self.assertIn("不能为空", error_msg,
                      f"应包含友好提示, 实际error={error_msg}")


if __name__ == "__main__":
    unittest.main()
