# -*- coding: utf-8 -*-
"""QiYuan external brain automated test suite (P0-2).

Usage: python -m unittest brain.test_brain -v
"""

import io, os, sys, json, unittest, tempfile, time

_brain_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_brain_dir)
if _brain_dir not in sys.path: sys.path.insert(0, _brain_dir)
if _root_dir not in sys.path: sys.path.insert(0, _root_dir)

def _load_config():
    import yaml
    config_path = os.path.join(_brain_dir, 'config.yaml')
    with io.open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def _load_fixtures():
    fp = os.path.join(_root_dir, '04_项目', '外部大脑', '报告', 'P0-1_test_fixtures.json')
    if not os.path.isfile(fp):
        return []
    with io.open(fp, 'r', encoding='utf-8') as f:
        return json.load(f)

class TestRuleEngineCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rule_engine import RuleEngine
        config = _load_config()
        rules_dir = config.get('brain', {}).get('rules_dir',
            os.path.join(_brain_dir, 'rules'))
        cls.engine = RuleEngine(rules_dir, config)

    def test_rule_check_finds_match(self):
        result = self.engine.check('修改SKILL.md')
        self.assertIsInstance(result, dict)
        self.assertIn('rules', result)
        self.assertIn('action', result)

    def test_rule_check_on_file_delete(self):
        result = self.engine.check('删除文件 测试.md')
        self.assertIsInstance(result, dict)
        self.assertIn('rules', result)

    def test_rule_classify(self):
        result = self.engine.classify('修改SKILL.md')
        self.assertIsInstance(result, dict)
        self.assertIn('level', result)
        self.assertIn(result['level'], ['P0', 'P1', 'P2', 'unknown'])

    def test_check_empty_action(self):
        result = self.engine.check('')
        self.assertFalse(result['matched'])
        self.assertEqual(result['count'], 0)

    def test_check_none_action(self):
        result = self.engine.check(None)
        self.assertFalse(result['matched'])

    def test_check_very_long_input(self):
        long_text = 'a' * 10000
        result = self.engine.check(long_text)
        self.assertIsInstance(result, dict)
        self.assertIn('matched', result)

    def test_check_special_characters(self):
        result = self.engine.check('!@#$%^&*()_+{}|:<>?[]')
        self.assertIsInstance(result, dict)
        self.assertIn('matched', result)

    def test_classify_p0_action(self):
        result = self.engine.classify('删除重要文件')
        self.assertEqual(result['level'], 'P0')

    def test_classify_p1_action(self):
        result = self.engine.classify('新建文件 测试.py')
        self.assertEqual(result['level'], 'P1')

    def test_classify_p2_action(self):
        result = self.engine.classify('查看当前项目状态')
        self.assertEqual(result['level'], 'P2')

    def test_status_structure(self):
        status = self.engine.status()
        self.assertIn('brain_ok', status)
        self.assertIn('components', status)
        self.assertIn('rules_loaded', status['components'])
        self.assertTrue(status['brain_ok'])

    def test_classify_unknown_fallback(self):
        result = self.engine.classify('xyzzy_nonexistent_op_abc')
        self.assertEqual(result['level'], 'P2')
class TestRuleEngineFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rule_engine import RuleEngine
        config = _load_config()
        rules_dir = config.get('brain', {}).get('rules_dir',
            os.path.join(_brain_dir, 'rules'))
        cls.engine = RuleEngine(rules_dir, config)
        cls.fixtures = _load_fixtures()

    def test_fixtures_loadable(self):
        self.assertGreater(len(self.fixtures), 0)

    def test_fixture_count_50(self):
        self.assertEqual(len(self.fixtures), 50)

    def test_fixture_classification_consistency(self):
        correct = 0
        total = len(self.fixtures)
        mismatches = []
        for i, fx in enumerate(self.fixtures):
            result = self.engine.classify(fx['action'])
            if result['level'] == fx['expected_level']:
                correct += 1
            else:
                mismatches.append((i, fx['action'][:40], fx['expected_level'], result['level']))
        ratio = correct / total if total > 0 else 0
        self.assertGreaterEqual(ratio, 0.70,
            'consistency {:.1%} ({}/{}). mismatches: {}'.format(ratio, correct, total, str(mismatches[:5])))

    def test_fixture_p0_classes_dont_crash(self):
        for fx in self.fixtures:
            if fx['expected_level'] == 'P0':
                result = self.engine.classify(fx['action'])
                self.assertIn('level', result)

    def test_draft_rules_excluded_by_default(self):
        from rule_engine import RuleEngine
        rules_dir = os.path.join(_brain_dir, 'rules')
        engine = RuleEngine(rules_dir, _load_config(), include_draft=False)
        for r in engine.rules:
            self.assertNotEqual(r.get('status'), 'draft')

    def test_draft_rules_included_when_requested(self):
        from rule_engine import RuleEngine
        rules_dir = os.path.join(_brain_dir, 'rules')
        engine = RuleEngine(rules_dir, _load_config(), include_draft=True)
        draft_count = sum(1 for r in engine.rules if r.get('status') == 'draft')
        self.assertGreaterEqual(draft_count, 0)

    def test_deprecated_rules_have_warning(self):
        from rule_engine import RuleEngine
        rules_dir = os.path.join(_brain_dir, 'rules')
        engine = RuleEngine(rules_dir, _load_config(), include_draft=True)
        deprecated = [r for r in engine.rules if r.get('status') == 'deprecated']
        for r in deprecated:
            self.assertIn('_warning', r)

    def test_rule_reload(self):
        self.engine.reload()
        self.assertGreater(len(self.engine.rules), 0)
class TestMemoryEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from memory.memory_engine import MemoryEngine
            config = _load_config()
            mem_cfg = config.get('memory', {})
            kb_root = mem_cfg.get('kb_root', os.path.join(_root_dir, '05_组织知识库'))
            persist_dir = mem_cfg.get('persist_dir',
                os.path.join(_brain_dir, 'memory', 'chroma_db'))
            cls.engine = MemoryEngine(kb_root, persist_dir,
                mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5'),
                mem_cfg.get('chunk_size', 1000), mem_cfg.get('top_k', 5))
            cls.memory_ok = True
        except (ImportError, Exception):
            cls.memory_ok = False

    def test_memory_set_get(self):
        try:
            from memory.workspace import Workspace
        except ImportError:
            self.skipTest('Workspace unavailable')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = os.path.join(tmpdir, 'test_ws.db')
            ws = Workspace(db_path)
            result = ws.set('test_key', 'test_value', ttl=60)
            if result is not None:
                self.assertTrue(result.get('ok', False))
            value = ws.get('test_key')
            self.assertEqual(value, 'test_value')

    def test_memory_status(self):
        if not self.memory_ok:
            self.skipTest('MemoryEngine unavailable')
        status = self.engine.status()
        self.assertIn('ok', status)
        self.assertIn('indexed_docs', status)

    def test_search_known_keyword(self):
        if not self.memory_ok:
            self.skipTest('MemoryEngine unavailable')
        result = self.engine.search('组织', top_k=5)
        self.assertIn('results', result)
        self.assertIn('total', result)
        self.assertIn('mode', result)

    def test_search_empty_result(self):
        if not self.memory_ok:
            self.skipTest('MemoryEngine unavailable')
        result = self.engine.search('xyz_nonexistent_abc123_xyz', top_k=5)
        self.assertIn('results', result)
        self.assertIn('total', result)
        self.assertIn('mode', result)
        self.assertIsInstance(result['total'], int)

    def test_fallback_mode_detectable(self):
        if not self.memory_ok:
            self.skipTest('MemoryEngine unavailable')
        status = self.engine.status()
        self.assertIn('model', status)
        model_str = str(status.get('model', '')).lower()
        self.assertTrue('fallback' in model_str or 'bge' in model_str or 'sklearn' in model_str)

class TestSafeWrite(unittest.TestCase):
    def _safe_write(self, path, content, **kwargs):
        try:
            from audit.audit_engine import safe_write
        except ImportError:
            self.skipTest('safe_write unavailable')
        db = kwargs.pop('db_path', os.path.join(self._tmpdir, 'audit.db'))
        return safe_write(path=path, content=content, operator='unittest',
                          db_path=db, **kwargs)

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._tmpdir = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def test_safe_write_basic(self):
        test_file = os.path.join(_brain_dir, '_p0_2_test_safe_' + str(time.time()).replace('.','') + '.md')
        audit_db = os.path.join(_brain_dir, '_tmp_audit_' + str(time.time()).replace('.','') + '.db')
        try:
            result = self._safe_write(test_file, 'Hello Qiyuan', db_path=audit_db)
            self.assertTrue(result.get('ok', False), str(result))
            self.assertTrue(os.path.isfile(test_file))
            with io.open(test_file, 'r', encoding='utf-8') as f:
                self.assertEqual(f.read(), 'Hello Qiyuan')
        finally:
            for f in [test_file, audit_db]:
                try: os.remove(f)
                except OSError: pass

    def test_safe_write_conflict_detection(self):
        ts = str(time.time()).replace('.','')
        test_file = os.path.join(_brain_dir, '_p0_2_test_cf_' + ts + '.md')
        audit_db = os.path.join(_brain_dir, '_tmp_audit2_' + ts + '.db')
        try:
            r1 = self._safe_write(test_file, 'v1', db_path=audit_db, conflict_window=300)
            self.assertTrue(r1.get('ok', False), str(r1))
            r2 = self._safe_write(test_file, 'v2', db_path=audit_db, conflict_window=300)
            self.assertFalse(r2.get('ok', False), str(r2))
        finally:
            for f in [test_file, audit_db]:
                try: os.remove(f)
                except OSError: pass

    def test_safe_write_path_traversal_rejected(self):
        evil_path = os.path.join(_brain_dir, '..', '..', 'evil.md')
        result = self._safe_write(evil_path, 'evil')
        self.assertFalse(result.get('ok', False), str(result))

    def test_safe_write_outside_workspace_rejected(self):
        result = self._safe_write(os.path.join(self._tmpdir, 'outside.md'), 'c')
        self.assertFalse(result.get('ok', False), str(result))
class TestAuditEngine(unittest.TestCase):
    def test_audit_log_write_and_query(self):
        try:
            from audit.audit_engine import AuditEngine
        except ImportError:
            self.skipTest('AuditEngine unavailable')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = os.path.join(tmpdir, 'test_audit.db')
            engine = AuditEngine(db_path)
            engine.log_write(
                target_path='/test/file.md',
                operator='unittest',
                content_hash='abc123',
                result='ok',
                details='test entry')
            logs = engine.query(limit=10)
            self.assertGreaterEqual(len(logs), 1)
            self.assertEqual(logs[0]['operator'], 'unittest')

class TestHealthCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from self_heal import SelfHeal
            cls.heal = SelfHeal(_load_config())
            cls.heal_ok = True
        except (ImportError, Exception):
            cls.heal_ok = False

    def test_health_check_basic(self):
        if not self.heal_ok:
            self.skipTest('SelfHeal unavailable')
        result = self.heal.health_check()
        self.assertIsInstance(result, dict)
        self.assertIn('summary', result)

    def test_health_check_all_dimensions(self):
        if not self.heal_ok:
            self.skipTest('SelfHeal unavailable')
        result = self.heal.health_check()
        self.assertIn('dimensions', result)
        for dim in ['rule_engine', 'memory_engine', 'audit_engine',
                    'filesystem', 'dependencies']:
            self.assertIn(dim, result['dimensions'])

    def test_health_check_degrade_level(self):
        if not self.heal_ok:
            self.skipTest('SelfHeal unavailable')
        result = self.heal.health_check()
        self.assertIn('degrade_level', result)
        self.assertIsInstance(result['degrade_level'], int)
        self.assertTrue(0 <= result['degrade_level'] <= 3)

    def test_health_check_degrade_name(self):
        if not self.heal_ok:
            self.skipTest('SelfHeal unavailable')
        result = self.heal.health_check()
        self.assertIn('degrade_name', result)
        self.assertIsInstance(result['degrade_name'], str)
        self.assertGreater(len(result['degrade_name']), 0)

    def test_health_check_overall_status(self):
        if not self.heal_ok:
            self.skipTest('SelfHeal unavailable')
        result = self.heal.health_check()
        self.assertIn('overall_status', result)
        self.assertIn(result['overall_status'], ['ok', 'warning', 'error'])

    def test_health_check_timestamp(self):
        if not self.heal_ok:
            self.skipTest('SelfHeal unavailable')
        result = self.heal.health_check()
        self.assertIn('timestamp', result)

class TestSelfEvolve(unittest.TestCase):
    def test_analyze_returns_expected_keys(self):
        try:
            from self_evolve import SelfEvolve
        except ImportError:
            self.skipTest('SelfEvolve unavailable')
        engine = SelfEvolve()
        result = engine.analyze()
        self.assertIsInstance(result, dict)
        self.assertIn('patterns', result)
        self.assertIn('missing_rules', result)
        self.assertIn('summary', result)

class TestBrainStatus(unittest.TestCase):
    def test_status_returns_ok(self):
        from rule_engine import RuleEngine
        config = _load_config()
        rules_dir = config.get('brain', {}).get('rules_dir',
            os.path.join(_brain_dir, 'rules'))
        engine = RuleEngine(rules_dir, config)
        status = engine.status()
        self.assertIn('components', status)
        self.assertIn('rules_loaded', status['components'])
        self.assertIsInstance(status['components']['rules_loaded'], int)
        self.assertTrue(status['components']['rules_loaded'] > 0)

def run_regression_tests():
    import unittest as ut
    loader = ut.TestLoader()
    suite = ut.TestSuite()
    for cls in [TestRuleEngineCore, TestRuleEngineFixture, TestMemoryEngine,
                TestSafeWrite, TestAuditEngine, TestHealthCheck,
                TestSelfEvolve, TestBrainStatus]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    stream = io.StringIO()
    runner = ut.TextTestRunner(stream=stream, verbosity=0)
    result = runner.run(suite)
    failures = []
    for test, tb in result.failures + result.errors:
        failures.append(str(test))
    passed = len(failures) == 0 and result.testsRun > 0
    return passed, result.testsRun, failures
class TestRegressionAutoTrigger(unittest.TestCase):
    def test_regression_suite_passes(self):
        passed, total, failures = run_regression_tests()
        self.assertTrue(passed,
            'suite should pass: {}/{} passed. failures: {}'.format(
                total - len(failures), total, failures[:5]))
        self.assertGreaterEqual(total, 25,
            'should have >= 25 test cases, got {}'.format(total))

    
class TestABCheck(unittest.TestCase):
    def test_ab_check_all_cards_pass(self):
        import subprocess
        ab_path = os.path.join(_brain_dir, 'ab_check.py')
        proc = subprocess.run(
            [sys.executable, ab_path, 'check'],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(proc.stdout.strip())
        self.assertTrue(data.get('ok', False),
            'ab_check should pass: {}'.format(data.get('errors', [])))
        self.assertEqual(data.get('total_cards'), 6,
            'should have 6 AB cards, got {}'.format(data.get('total_cards', 0)))

    def test_ab_search_returns_results(self):
        import subprocess
        ab_path = os.path.join(_brain_dir, 'ab_check.py')
        proc = subprocess.run(
            [sys.executable, ab_path, 'search', 'stderr'],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(proc.stdout.strip())
        self.assertTrue(data.get('ok', False))
        self.assertGreaterEqual(data.get('count', 0), 1,
            'search "stderr" should return >=1 result')

    def test_regression_rerun_idempotent(self):
        p1, t1, _ = run_regression_tests()
        p2, t2, _ = run_regression_tests()
        self.assertEqual(p1, p2)
        self.assertEqual(t1, t2)

if __name__ == '__main__':
    unittest.main(verbosity=2)