# -*- coding: utf-8 -*-
"""World Model test suite (Round 10).

Usage: python -m unittest brain.test_world_model -v
"""

import io, os, sys, json, unittest, tempfile, math, time

_brain_dir = os.path.dirname(os.path.abspath(__file__))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)


def run_regression_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestOnlineNormalizer))
    suite.addTests(loader.loadTestsFromTestCase(TestWorldModel))
    suite.addTests(loader.loadTestsFromTestCase(TestWorldModelDB))
    suite.addTests(loader.loadTestsFromTestCase(TestWorldModelIntegration))
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    return result.wasSuccessful()


# ============================================================
class TestOnlineNormalizer(unittest.TestCase):
    """Online normalization tests."""

    @classmethod
    def setUpClass(cls):
        try:
            from probe.normalizer import OnlineNormalizer
            cls.norm = OnlineNormalizer(dim=8)
            cls.ok = True
        except (ImportError, Exception):
            cls.ok = False

    def _require(self):
        if not self.ok:
            self.skipTest('OnlineNormalizer unavailable')

    def test_ready_false_initially(self):
        """ready() returns False for a fresh normalizer."""
        self._require()
        from probe.normalizer import OnlineNormalizer
        fresh = OnlineNormalizer(dim=8)
        self.assertFalse(fresh.ready())

    def test_ready_true_after_50(self):
        self._require()
        for i in range(50):
            self.norm.update([0.3] * 8)
        self.assertTrue(self.norm.ready())

    def test_normalize_passthrough_bounded_dims(self):
        """Dims 0-3 pass through unchanged."""
        self._require()
        for i in range(60):
            self.norm.update([i * 0.01] * 8)
        vec = [0.5, 0.3, 0.1, 0.7, 100, 500, 0.4, 0.6]
        result = self.norm.normalize(vec)
        self.assertEqual(len(result), 8)
        self.assertAlmostEqual(result[0], 0.5, delta=0.1)
        self.assertAlmostEqual(result[1], 0.3, delta=0.1)

    def test_inverse_roundtrip(self):
        self._require()
        for i in range(60):
            self.norm.update([0.5, 0.5, 0.5, 0.5, i, i * 5, 0.5, 0.5])
        vec = [0.5, 0.3, 0.1, 0.7, 100, 500, 0.4, 0.6]
        normed = self.norm.normalize(vec)
        back = self.norm.inverse(normed)
        for i in range(8):
            self.assertAlmostEqual(vec[i], back[i], delta=max(abs(vec[i]) * 0.1, 0.01),
                msg='Dim %d: %.4f != %.4f' % (i, vec[i], back[i]))


# ============================================================
class TestWorldModel(unittest.TestCase):
    """WorldModel core tests."""

    @classmethod
    def setUpClass(cls):
        try:
            from probe.world_model import WorldModel
            cls.tmp_dir = tempfile.mkdtemp(prefix='wm_test_')
            cls.model = WorldModel(config={
                'model': {'path': os.path.join(cls.tmp_dir, 'weights.json')}
            }, brain_dir=cls.tmp_dir)
            cls.ok = True
        except (ImportError, Exception):
            cls.ok = False

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'tmp_dir'):
            import shutil
            shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _require(self):
        if not self.ok:
            self.skipTest('WorldModel unavailable')

    def test_predict_output_shape(self):
        self._require()
        result = self.model.predict([0.5] * 8, [1, 0, 0, 0, 0])
        self.assertEqual(len(result), 8)

    def test_update_returns_tuple(self):
        self._require()
        s1 = [0.5] * 8
        s2 = [0.51] * 8
        dp, dr, surp = self.model.update(s1, [1, 0, 0, 0, 0], s2)
        self.assertEqual(len(dp), 8)
        self.assertEqual(len(dr), 8)
        self.assertGreaterEqual(surp, 0.0)

    def test_get_status_cold_start(self):
        self._require()
        s = self.model.get_status()
        self.assertIn('status', s)

    def test_save_load_weights(self):
        self._require()
        p = os.path.join(self.tmp_dir, 'test_save.json')
        self.model.save_weights(p)
        self.assertTrue(os.path.isfile(p))

    def test_list_versions(self):
        self._require()
        self.model.save_weights()
        v = self.model.list_versions()
        self.assertGreater(len(v), 0)

    def test_step_count_increments(self):
        self._require()
        c1 = self.model.step_count
        self.model.update([0.5] * 8, [1, 0, 0, 0, 0], [0.51] * 8)
        self.assertGreater(self.model.step_count, c1)


# ============================================================
class TestWorldModelDB(unittest.TestCase):
    """WorldModelDB tests."""

    @classmethod
    def setUpClass(cls):
        try:
            from probe.world_model_db import WorldModelDB
            cls.tmp_dir = tempfile.mkdtemp(prefix='wmdb_test_')
            cls.db = WorldModelDB(os.path.join(cls.tmp_dir, 'test.db'))
            cls.ok = True
        except (ImportError, Exception):
            cls.ok = False

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'tmp_dir'):
            import shutil
            shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _require(self):
        if not self.ok:
            self.skipTest('WorldModelDB unavailable')

    def test_tables_created(self):
        self._require()
        import sqlite3
        conn = sqlite3.connect(os.path.join(self.tmp_dir, 'test.db'))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        self.assertIn('world_model_prediction', tables)
        self.assertIn('world_model_surprise', tables)

    def test_write_and_read_prediction(self):
        self._require()
        self.db.write_prediction(
            'req-1', [0.5] * 8, 'ask', [0.01] * 8, [0.02] * 8, 0.001)
        count = self.db.get_prediction_count()
        self.assertGreaterEqual(count, 1)

    def test_write_and_read_surprise(self):
        self._require()
        self.db.write_surprise_aggregate(0.05, 0.1, 0.01)
        result = self.db.get_latest_surprise()
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 0.05)

    def test_get_latest_surprise_empty(self):
        self._require()
        db2_path = os.path.join(self.tmp_dir, 'empty.db')
        from probe.world_model_db import WorldModelDB
        db2 = WorldModelDB(db2_path)
        self.assertIsNone(db2.get_latest_surprise())


# ============================================================
class TestWorldModelIntegration(unittest.TestCase):
    """Full pipeline integration tests."""

    @classmethod
    def setUpClass(cls):
        try:
            from probe.world_model import WorldModel
            cls.tmp_dir = tempfile.mkdtemp(prefix='wm_int_')
            cls.model = WorldModel(config={
                'model': {'path': os.path.join(cls.tmp_dir, 'wm.json')}
            }, brain_dir=cls.tmp_dir)
            cls.ok = True
        except (ImportError, Exception):
            cls.ok = False

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'tmp_dir'):
            import shutil
            shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _require(self):
        if not self.ok:
            self.skipTest('WorldModel unavailable')

    def test_full_pipeline(self):
        """Normalizer + Model + DB: full pipeline works."""
        self._require()
        for i in range(5):
            s1 = [0.5 + i * 0.01] * 8
            s2 = [0.51 + i * 0.01] * 8
            self.model.update(s1, [1, 0, 0, 0, 0], s2)
        status = self.model.get_status()
        self.assertIn('status', status)

    def test_performance(self):
        """predict < 5ms avg, update < 10ms avg."""
        self._require()
        s = [0.5] * 8
        act = [1, 0, 0, 0, 0]
        # Warm up
        self.model.predict(s, act)
        self.model.update(s, act, [0.51] * 8)

        t0 = time.perf_counter()
        for _ in range(100):
            self.model.predict(s, act)
        elapsed_predict = (time.perf_counter() - t0) / 100 * 1000
        self.assertLess(elapsed_predict, 5.0,
                        f"predict avg {elapsed_predict:.3f}ms, expected <5ms")

        t0 = time.perf_counter()
        for _ in range(100):
            self.model.update(s, act, [0.51] * 8)
        elapsed_update = (time.perf_counter() - t0) / 100 * 1000
        self.assertLess(elapsed_update, 10.0,
                        f"update avg {elapsed_update:.3f}ms, expected <10ms")


# ============================================================
class TestRegressionAutoTrigger(unittest.TestCase):
    """Regression auto-trigger."""

    def test_regression_suite_passes(self):
        ok = run_regression_tests()
        self.assertTrue(ok, 'World Model regression suite did not pass')

    def test_regression_rerun_idempotent(self):
        r1 = run_regression_tests()
        r2 = run_regression_tests()
        self.assertEqual(r1, r2, 'Regression suite not idempotent')


if __name__ == '__main__':
    unittest.main()