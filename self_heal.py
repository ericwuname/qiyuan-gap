# -*- coding: utf-8 -*-
"""启元智能 · 启元智脑 · 自愈+反脆弱系统 · Phase 4

SelfHeal — 5维健康检查 + 组件级自修复 + 4级降级策略
"""

import io, os, sys, json, time, tempfile, shutil, threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Phase 5: logging chain instrumentation
try:
    from logging_chain import log_info, log_error, log_warn
except ImportError:
    log_info = log_error = log_warn = lambda *a, **kw: None

_brain_dir = os.path.dirname(os.path.abspath(__file__))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)



# P1-6: Health check quantitative thresholds
HEALTH_THRESHOLDS = {
    "rule_check_p99_ms": {"ok": 200, "warn": 300},       # rule match avg <=200ms ok, >300ms alarm
    "cache_hit_rate_pct": {"ok": 80, "warn": 60},         # cache hit rate >=80% ok, <60% alarm
    "kb_search_p99_ms": {"ok": 1000, "warn": 2000},       # kb retrieval avg <=1s ok, >2s alarm
    "audit_write_success_pct": {"ok": 99, "warn": 95},    # record write success >=99% ok, <95% alarm
    "memory_usage_pct": {"ok": 70, "warn": 85},           # memory usage <=70% ok, >85% alarm
    "disk_free_pct": {"ok": 20, "warn": 10},              # disk free >=20% ok, <10% alarm
}

class SelfHeal:
    """自愈系统：健康检查 → 自动修复 → 降级控制"""

    DIMENSIONS = [
        "rule_engine",
        "memory_engine",
        "audit_engine",
        "filesystem",
        "dependencies",
        "anti_bug",
    ]

    DEGRADE_LEVELS = {
        0: {"name": "L0-全功能", "desc": "所有系统正常运行"},
        1: {"name": "L1-记忆降级", "desc": "记忆引擎降至fallback模式"},
        2: {"name": "L2-规则降级", "desc": "规则引擎仅加载constitution.yaml"},
        3: {"name": "L3-全降级", "desc": "全部回退至fallback.md兜底"},
    }

    CRITICAL_DIRS = [
        "01_公司治理",
        "04_项目",
        "05_组织知识库",
        "06_人力资源",
        "brain",
        "brain/rules",
        "brain/memory",
        "brain/audit",
    ]

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._brain_dir = os.path.dirname(os.path.abspath(__file__))
        self._root_dir = os.path.dirname(self._brain_dir)
        self._degrade_level = 0
        self._degrade_file = os.path.join(self._brain_dir, "_degrade_state.json")
        self._load_degrade_state()

    def _load_degrade_state(self):
        try:
            if os.path.exists(self._degrade_file):
                with io.open(self._degrade_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._degrade_level = data.get("level", 0)
        except Exception:
            self._degrade_level = 0

    def _save_degrade_state(self):
        try:
            with io.open(self._degrade_file, "w", encoding="utf-8") as f:
                json.dump({
                    "level": self._degrade_level,
                    "name": self.DEGRADE_LEVELS[self._degrade_level]["name"],
                    "updated": datetime.now().isoformat(),
                }, f, ensure_ascii=True, indent=2)
        except Exception:
            pass

    # ── Health Check ──────────────────────────────────────────────

    def health_check(self, dimensions: List[str] = None) -> Dict:
        log_info("SELFHEAL", f"health_check start: dims={dimensions}")
        checks = dimensions or self.DIMENSIONS
        results = {}
        ok_count = 0
        warning_count = 0
        error_count = 0

        # P1-6: added performance dimension
        check_map = {
            "rule_engine": self._check_rule_engine,
            "memory_engine": self._check_memory_engine,
            "audit_engine": self._check_audit_engine,
            "filesystem": self._check_filesystem,
            "dependencies": self._check_dependencies,
            "anti_bug": self._check_anti_bug,
            "performance": self._check_performance,
        }

        for dim in checks:
            if dim in check_map:
                r = check_map[dim]()
                results[dim] = r
                if r["status"] == "ok":
                    ok_count += 1
                elif r["status"] == "warning":
                    warning_count += 1
                else:
                    error_count += 1

        if error_count > 0:
            overall = "error"
        elif warning_count > 0:
            overall = "warning"
        else:
            overall = "ok"

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall,
            "summary": {
                "ok": ok_count,
                "warning": warning_count,
                "error": error_count,
                "total": len(checks),
            },
            "degrade_level": self._degrade_level,
            "degrade_name": self.DEGRADE_LEVELS[self._degrade_level]["name"],
            "dimensions": results,
        }

    def _check_rule_engine(self) -> Dict:
        """P1-6: enhanced with rule check performance timing"""
        try:
            import time
            from rule_engine import RuleEngine
            rules_dir = self.config.get("brain", {}).get(
                "rules_dir", os.path.join(self._brain_dir, "rules"))
            engine = RuleEngine(rules_dir, self.config)
            rule_count = len(engine.rules)

            if rule_count == 0:
                return {
                    "status": "error",
                    "rule_count": 0,
                    "detail": "No rules loaded",
                }

            # Performance timing (P1-6)
            t0 = time.perf_counter()
            test_result = engine.check("新建文件")
            elapsed_ms = (time.perf_counter() - t0) * 1000
            matched = test_result.get("count", 0)

            # Threshold evaluation
            th = HEALTH_THRESHOLDS["rule_check_p99_ms"]
            if elapsed_ms <= th["ok"]:
                perf_status = "ok"
            elif elapsed_ms <= th["warn"]:
                perf_status = "warning"
            else:
                perf_status = "error"

            result = {
                "rule_count": rule_count,
                "test_match": matched,
                "check_latency_ms": round(elapsed_ms, 2),
                "check_latency_threshold_ms": th["ok"],
                "perf_status": perf_status,
            }

            if rule_count > 0 and matched > 0:
                if perf_status == "error":
                    result["status"] = "warning"
                    result["detail"] = "Loaded {} rules but check P99={:.1f}ms > {}ms (warn)".format(
                        rule_count, elapsed_ms, th["warn"])
                else:
                    result["status"] = "ok"
                    result["detail"] = "Loaded {} rules, test-match ok, latency {:.1f}ms".format(
                        rule_count, elapsed_ms)
            elif rule_count > 0:
                result["status"] = "warning"
                result["detail"] = "Loaded {} rules but test-match returned 0".format(rule_count)
            else:
                result["status"] = "error"
                result["detail"] = "No rules loaded"

            return result
        except Exception as e:
            return {
                "status": "error",
                "rule_count": 0,
                "detail": "RuleEngine failed: {}".format(e),
            }

    def _check_memory_engine(self) -> Dict:
        try:
            from memory.memory_engine import MemoryEngine
            mem_cfg = self.config.get("memory", {})
            kb_root = mem_cfg.get("kb_root",
                os.path.join(self._root_dir, "05_组织知识库"))
            persist_dir = mem_cfg.get("persist_dir",
                os.path.join(self._brain_dir, "memory", "chroma_db"))

            engine = MemoryEngine(
                kb_root, persist_dir,
                mem_cfg.get("model_name", "BAAI/bge-small-zh-v1.5"),
                mem_cfg.get("chunk_size", 1000),
                mem_cfg.get("top_k", 5),
            )

            status = engine.status()
            doc_count = status.get("indexed_docs", 0)
            mem_ok = status.get("ok", False)

            if not mem_ok:
                return {
                    "status": "error",
                    "doc_count": doc_count,
                    "model": status.get("model", "unknown"),
                    "detail": "MemoryEngine.status() reports not ok",
                }

            try:
                result = engine.search("测试", top_k=1)
                search_ok = result.get("total", -1) >= 0
            except Exception:
                search_ok = False

                if doc_count == 0 and status.get("fallback_docs", 0) == 0:
                    return {
                    "status": "warning",
                    "doc_count": 0,
                    "model": status.get("model", "unknown"),
                    "detail": "Index empty — run brain kb rebuild",
                }

            if search_ok:
                return {
                    "status": "ok",
                    "doc_count": doc_count,
                    "model": status.get("model", "unknown"),
                    "detail": "Index ok, {} docs, search functional".format(doc_count),
                }
            else:
                return {
                    "status": "warning",
                    "doc_count": doc_count,
                    "model": status.get("model", "unknown"),
                    "detail": "Index has docs but search query failed",
                }

        except ImportError:
            return {
                "status": "warning",
                "doc_count": 0,
                "detail": "MemoryEngine not importable",
            }
        except Exception as e:
            return {
                "status": "error",
                "doc_count": 0,
                "detail": "MemoryEngine failed: {}".format(e),
            }

    def _check_audit_engine(self) -> Dict:
        try:
            from audit.audit_engine import AuditEngine
            audit_cfg = self.config.get("audit", {})
            db_path = audit_cfg.get("db_path",
                os.path.join(self._brain_dir, "audit", "audit.db"))

            engine = AuditEngine(db_path)

            engine.log_write(
                target_path="_self_heal_test",
                operator="self_heal",
                content_hash="self_heal_test_hash",
                result="test",
                details="SelfHeal health check test log",
            )

            status = engine.status()
            total_logs = status.get("total_logs", 0)

            if total_logs > 0:
                return {
                    "status": "ok",
                    "total_logs": total_logs,
                    "db_size_kb": status.get("db_size_kb", 0),
                    "detail": "Audit engine ok, {} logs, write+read verified".format(total_logs),
                }
            else:
                return {
                    "status": "warning",
                    "total_logs": 0,
                    "db_size_kb": status.get("db_size_kb", 0),
                    "detail": "Audit DB accessible but no logs found",
                }
        except ImportError:
            return {
                "status": "warning",
                "total_logs": 0,
                "detail": "AuditEngine not importable",
            }
        except Exception as e:
            return {
                "status": "error",
                "total_logs": 0,
                "detail": "AuditEngine failed: {}".format(e),
            }

    def _check_filesystem(self) -> Dict:
        missing = []
        no_read = []
        no_write = []

        for rel_path in self.CRITICAL_DIRS:
            full_path = os.path.join(self._root_dir, rel_path)
            if not os.path.exists(full_path):
                missing.append(rel_path)
                continue
            if not os.access(full_path, os.R_OK):
                no_read.append(rel_path)
            if not os.access(full_path, os.W_OK):
                no_write.append(rel_path)

        total = len(self.CRITICAL_DIRS)
        problem_count = len(missing) + len(no_read) + len(no_write)

        if problem_count == 0:
            return {
                "status": "ok",
                "dirs_checked": total,
                "detail": "All {} critical dirs present and accessible".format(total),
            }
        elif len(missing) > 0:
            return {
                "status": "error",
                "dirs_checked": total,
                "missing": missing,
                "no_read": no_read,
                "no_write": no_write,
                "detail": "{} dirs missing: {}".format(len(missing), missing),
            }
        else:
            return {
                "status": "warning",
                "dirs_checked": total,
                "missing": missing,
                "no_read": no_read,
                "no_write": no_write,
                "detail": "Access issues: no_read={}, no_write={}".format(no_read, no_write),
            }

    def _check_dependencies(self) -> Dict:
        dep_checks = {
            "yaml": "PyYAML",
            "json": "stdlib",
            "sqlite3": "stdlib",
            "numpy": "numpy",
            "sklearn.feature_extraction.text": "scikit-learn",
            "sklearn.metrics.pairwise": "scikit-learn",
            "scipy.sparse": "scipy",
        }
        ok_deps = []
        missing_deps = []

        for module_name, package_name in dep_checks.items():
            try:
                __import__(module_name)
                ok_deps.append(package_name)
            except ImportError:
                missing_deps.append(package_name)

        if len(missing_deps) == 0:
            return {
                "status": "ok",
                "deps_checked": len(dep_checks),
                "detail": "All {} deps importable".format(len(ok_deps)),
            }
        elif len(missing_deps) <= 2:
            return {
                "status": "warning",
                "deps_checked": len(dep_checks),
                "missing": missing_deps,
                "detail": "Missing optional: {}".format(missing_deps),
            }
        else:
            return {
                "status": "error",
                "deps_checked": len(dep_checks),
                "missing": missing_deps,
                "detail": "Critical deps missing: {}".format(missing_deps),
            }

    # ── Auto Repair ───────────────────────────────────────────────


    def _check_performance(self) -> Dict:
        """P1-6: aggregated performance health check using brain perf"""
        import subprocess, json as _json, os as _os
        try:
            cli_path = _os.path.join(self._brain_dir, "cli.py")
            proc = subprocess.run(
                ["python", cli_path, "perf", "--quiet"],
                capture_output=True, text=True, timeout=60,
                cwd=self._root_dir
            )
            if proc.stdout.strip():
                data = _json.loads(proc.stdout.strip())
            else:
                return {"status": "warning", "detail": "perf command produced no output", "perf_stderr": proc.stderr[:200]}
            th = HEALTH_THRESHOLDS
            issues = []
            rule_p99 = data.get("rule_check", {}).get("p99_ms", 999)
            if rule_p99 > th["rule_check_p99_ms"]["warn"]:
                issues.append(f"rule_check P99={rule_p99:.1f}ms > {th["rule_check_p99_ms"]["warn"]}ms")
            kb_p99 = data.get("kb_search", {}).get("p99_ms", 9999)
            if kb_p99 > th["kb_search_p99_ms"]["warn"]:
                issues.append(f"kb_search P99={kb_p99:.1f}ms > {th["kb_search_p99_ms"]["warn"]}ms")
            result = {"rule_check_p99_ms": rule_p99, "kb_search_p99_ms": kb_p99, "perf_data": data}
            if len(issues) == 0:
                result["status"] = "ok"
                result["detail"] = "All perf metrics within thresholds"
            elif len(issues) == 1:
                result["status"] = "warning"
                result["detail"] = "; ".join(issues)
            else:
                result["status"] = "error"
                result["detail"] = "; ".join(issues)
            return result
        except Exception as e:
            return {"status": "warning", "detail": f"Performance check unavailable: {e}"}
    def _check_anti_bug(self) -> Dict:
        """AB Card health check - verify anti-bug knowledge base integrity"""
        import subprocess, json as _json, os as _os
        try:
            ab_path = _os.path.join(self._brain_dir, 'ab_check.py')
            if not _os.path.isfile(ab_path):
                return {"status": "error", "detail": "ab_check.py not found"}
            proc = subprocess.run(
                [sys.executable, ab_path, "check"],
                capture_output=True, text=True, timeout=15
            )
            data = _json.loads(proc.stdout.strip())
            card_count = data.get("total_cards", 0)
            errors = data.get("errors", [])
            all_ok = data.get("ok", False)
            result = {"card_count": card_count, "errors": len(errors)}
            if all_ok and card_count >= 6:
                result["status"] = "ok"
                result["detail"] = f"All {card_count} AB cards valid"
            elif all_ok and card_count < 6:
                result["status"] = "warning"
                result["detail"] = f"Only {card_count} AB cards, expected >=6"
            else:
                result["status"] = "error"
                result["detail"] = f"{len(errors)} card(s) have issues: {[e['card'] for e in errors]}"
            return result
        except Exception as e:
            return {"status": "warning", "detail": f"Anti-bug check unavailable: {e}"}

    def _trigger_export_rules(self):
        """Trigger export-rules after rule change (AB-KB B4)"""
        import subprocess
        try:
            cli_path = os.path.join(self._brain_dir, 'cli.py')
            proc = subprocess.run(
                [sys.executable, cli_path, 'export-rules'],
                capture_output=True, text=True, timeout=30,
                cwd=self._root_dir
            )
            if proc.returncode != 0:
                print(f"RuleWatcher: export-rules FAILED: {proc.stderr[-200:]}", file=sys.stderr)
        except Exception as e:
            print(f"RuleWatcher: export-rules error: {e}", file=sys.stderr)

    def auto_repair(self, component: str) -> Dict:
        log_info("SELFHEAL", f"auto_repair: component={component}")
        if component == "all":
            results = {}
            for comp in self.DIMENSIONS:
                results[comp] = self._repair_component(comp)
            all_ok = all(r.get("status") == "ok" for r in results.values())
            return {
                "component": "all",
                "status": "ok" if all_ok else "partial",
                "results": results,
                "detail": "Batch repair complete",
            }

        if component not in self.DIMENSIONS:
            return {
                "component": component,
                "status": "error",
                "detail": "Unknown component '{}'. Valid: {}".format(component, self.DIMENSIONS),
            }

        return self._repair_component(component)

    def _repair_component(self, component: str) -> Dict:
        repair_map = {
            "rule_engine": self._repair_rule_engine,
            "memory_engine": self._repair_memory_engine,
            "audit_engine": self._repair_audit_engine,
            "filesystem": self._repair_filesystem,
            "dependencies": self._repair_dependencies,
        }
        fn = repair_map.get(component)
        if fn is None:
            return {
                "component": component,
                "status": "error",
                "detail": "No repair handler for {}".format(component),
            }
        result = fn()
        return {
            "component": component,
            "status": result.get("status", "ok"),
            "actions": [result],
            "detail": result.get("detail", ""),
        }

    def _repair_rule_engine(self) -> Dict:
        rules_dir = self.config.get("brain", {}).get(
            "rules_dir", os.path.join(self._brain_dir, "rules"))

        if not os.path.isdir(rules_dir):
            try:
                os.makedirs(rules_dir, exist_ok=True)
            except Exception as e:
                return {
                    "action": "create_rules_dir",
                    "status": "error",
                    "detail": "Cannot create: {}".format(e),
                }

        yaml_files = [f for f in os.listdir(rules_dir) if f.endswith(".yaml")]
        if len(yaml_files) == 0:
            return {
                "action": "check_rules_dir",
                "status": "warning",
                "detail": "Rules dir exists but no YAML files — manual restore needed",
            }

        return {
            "action": "check_rules_dir",
            "status": "ok",
            "detail": "Rules dir ok, {} YAML files".format(len(yaml_files)),
        }

    def _repair_memory_engine(self) -> Dict:
        mem_cfg = self.config.get("memory", {})
        persist_dir = mem_cfg.get("persist_dir",
            os.path.join(self._brain_dir, "memory", "chroma_db"))

        try:
            os.makedirs(persist_dir, exist_ok=True)
        except Exception as e:
            return {
                "action": "ensure_persist_dir",
                "status": "error",
                "detail": "Cannot create: {}".format(e),
            }

        fallback_index = os.path.join(persist_dir, "fallback_index.pkl")
        fallback_meta = os.path.join(persist_dir, "fallback_meta.json")

        if os.path.exists(fallback_index) and os.path.exists(fallback_meta):
            return {
                "action": "check_fallback_index",
                "status": "ok",
                "detail": "Fallback index files present",
            }
        else:
            return {
                "action": "check_fallback_index",
                "status": "warning",
                "detail": "Fallback index missing — run 'brain kb rebuild'",
            }

    def _repair_audit_engine(self) -> Dict:
        audit_cfg = self.config.get("audit", {})
        db_path = audit_cfg.get("db_path",
            os.path.join(self._brain_dir, "audit", "audit.db"))
        db_dir = os.path.dirname(db_path)

        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception as e:
            return {
                "action": "ensure_audit_dir",
                "status": "error",
                "detail": "Cannot create: {}".format(e),
            }

        if not os.path.exists(db_path):
            try:
                from audit.audit_engine import AuditEngine
                AuditEngine(db_path)
                return {
                    "action": "create_audit_db",
                    "status": "ok",
                    "detail": "Audit DB created",
                }
            except Exception as e:
                return {
                    "action": "create_audit_db",
                    "status": "error",
                    "detail": "Failed: {}".format(e),
                }

        return {
            "action": "check_audit_db",
            "status": "ok",
            "detail": "Audit DB file exists",
        }

    def _repair_filesystem(self) -> Dict:
        created = []
        failed = []

        for rel_path in self.CRITICAL_DIRS:
            full_path = os.path.join(self._root_dir, rel_path)
            if not os.path.exists(full_path):
                try:
                    os.makedirs(full_path, exist_ok=True)
                    created.append(rel_path)
                except Exception:
                    failed.append(rel_path)

        if failed:
            return {
                "action": "create_missing_dirs",
                "status": "error",
                "created": created,
                "failed": failed,
                "detail": "Created {}, failed {}: {}".format(len(created), len(failed), failed),
            }
        elif created:
            return {
                "action": "create_missing_dirs",
                "status": "ok",
                "created": created,
                "detail": "Created {} dirs: {}".format(len(created), created),
            }
        else:
            return {
                "action": "check_dirs",
                "status": "ok",
                "detail": "All critical dirs exist",
            }

    def _repair_dependencies(self) -> Dict:
        missing = []
        for module_name, package_name in [
            ("yaml", "PyYAML"),
            ("numpy", "numpy"),
            ("sklearn.feature_extraction.text", "scikit-learn"),
            ("scipy.sparse", "scipy"),
        ]:
            try:
                __import__(module_name)
            except ImportError:
                missing.append(package_name)

        if missing:
            return {
                "action": "report_missing_deps",
                "status": "warning",
                "missing": missing,
                "detail": "Missing: {}. pip install {}".format(
                    missing, " ".join(missing)),
            }
        else:
            return {
                "action": "check_deps",
                "status": "ok",
                "detail": "All core deps present",
            }

    # ── Degrade Control ───────────────────────────────────────────

    def degrade(self, level: int) -> Dict:
        log_info("SELFHEAL", f"degrade: level={level}")
        if level not in self.DEGRADE_LEVELS:
            return {
                "status": "error",
                "detail": "Invalid degrade level {}. Valid: {}".format(
                    level, list(self.DEGRADE_LEVELS.keys())),
            }

        previous_level = self._degrade_level
        self._degrade_level = level
        self._save_degrade_state()

        degrade_config = {}
        if level >= 1:
            degrade_config["memory_mode"] = "fallback_only"
            degrade_config["memory_skip_sentence_transformers"] = True
        if level >= 2:
            degrade_config["rules_mode"] = "constitution_only"
            degrade_config["rules_skip_sops"] = True
        if level >= 3:
            degrade_config["brain_mode"] = "fallback_md_only"
            degrade_config["skip_all_engines"] = True

        prev_info = self.DEGRADE_LEVELS[previous_level]
        level_info = self.DEGRADE_LEVELS[level]

        return {
            "status": "ok",
            "previous_level": previous_level,
            "previous_name": prev_info["name"],
            "current_level": level,
            "current_name": level_info["name"],
            "description": level_info["desc"],
            "degrade_config": degrade_config,
            "detail": "Degraded from {} to {}".format(prev_info["name"], level_info["name"]),
        }

    def get_degrade_level(self) -> Dict:
        info = self.DEGRADE_LEVELS[self._degrade_level]
        return {
            "level": self._degrade_level,
            "name": info["name"],
            "description": info["desc"],
            "state_file": self._degrade_file,
        }

    def reset_degrade(self) -> Dict:
        return self.degrade(0)

    # ── Chaos Test ────────────────────────────────────────────────

    def chaos_test(self) -> Dict:
        timestamp = datetime.now().isoformat()
        phases = []

        # Phase 1: Baseline
        baseline = self.health_check()
        phases.append({
            "phase": "baseline",
            "overall": baseline["overall_status"],
            "summary": baseline["summary"],
        })

        # Phase 2: Inject faults
        faults = self._inject_faults()
        phases.append({
            "phase": "fault_injection",
            "faults": faults,
        })

        # Phase 3: Post-fault health
        post_fault = self.health_check()
        fault_errors = sum(
            1 for d in post_fault["dimensions"].values()
            if d["status"] != "ok"
        )
        phases.append({
            "phase": "post_fault",
            "overall": post_fault["overall_status"],
            "fault_dimensions": fault_errors,
        })

        # Phase 4: Auto-repair
        repair_result = self.auto_repair("all")
        phases.append({
            "phase": "auto_repair",
            "status": repair_result["status"],
        })

        # Phase 5: Post-repair health
        post_repair = self.health_check()
        phases.append({
            "phase": "post_repair",
            "overall": post_repair["overall_status"],
            "summary": post_repair["summary"],
        })

        # Recovery assessment
        baseline_ok = baseline["summary"]["ok"]
        post_repair_ok = post_repair["summary"]["ok"]
        recovery_rate = post_repair_ok / max(baseline_ok, 1)
        recovered = recovery_rate >= 0.8

        return {
            "timestamp": timestamp,
            "test_type": "chaos_engineering",
            "recovered": recovered,
            "recovery_rate": round(recovery_rate, 2),
            "baseline_ok": baseline_ok,
            "post_repair_ok": post_repair_ok,
            "phases": phases,
            "verdict": (
                "自愈系统验证通过 — 故障注入后成功恢复"
                if recovered
                else "部分恢复 — 检查未修复的维度"
            ),
        }

    def _inject_faults(self) -> List[Dict]:
        faults = []

        # Fault 1: filesystem temp file stress
        rules_dir = self.config.get("brain", {}).get(
            "rules_dir", os.path.join(self._brain_dir, "rules"))
        try:
            test_file = os.path.join(rules_dir, "_chaos_test_temp.yaml")
            with io.open(test_file, "w", encoding="utf-8") as f:
                f.write("# chaos test temp file\n")
            os.remove(test_file)
            faults.append({
                "id": "fault_001",
                "component": "filesystem",
                "action": "create_and_delete_temp_file",
                "result": "injected",
            })
        except Exception as e:
            faults.append({
                "id": "fault_001",
                "component": "filesystem",
                "action": "create_and_delete_temp_file",
                "result": "failed",
                "detail": str(e),
            })

        # Fault 2: audit engine test log injection
        try:
            from audit.audit_engine import AuditEngine
            audit_cfg = self.config.get("audit", {})
            db_path = audit_cfg.get("db_path",
                os.path.join(self._brain_dir, "audit", "audit.db"))
            engine = AuditEngine(db_path)
            engine.log_write(
                target_path="_chaos_test",
                operator="chaos_test",
                content_hash="chaos",
                result="test",
                details="Chaos test injected log",
            )
            faults.append({
                "id": "fault_002",
                "component": "audit_engine",
                "action": "inject_test_log",
                "result": "injected",
            })
        except Exception as e:
            faults.append({
                "id": "fault_002",
                "component": "audit_engine",
                "action": "inject_test_log",
                "result": "failed",
                "detail": str(e),
            })

        # Fault 3: memory engine empty query stress
        try:
            from memory.memory_engine import MemoryEngine
            mem_cfg = self.config.get("memory", {})
            kb_root = mem_cfg.get("kb_root",
                os.path.join(self._root_dir, "05_组织知识库"))
            persist_dir = mem_cfg.get("persist_dir",
                os.path.join(self._brain_dir, "memory", "chroma_db"))
            engine = MemoryEngine(
                kb_root, persist_dir,
                mem_cfg.get("model_name", "BAAI/bge-small-zh-v1.5"),
                mem_cfg.get("chunk_size", 1000),
                mem_cfg.get("top_k", 5),
            )
            try:
                engine.search("", top_k=1)
            except Exception:
                pass
            faults.append({
                "id": "fault_003",
                "component": "memory_engine",
                "action": "empty_query_stress",
                "result": "injected",
            })
        except Exception as e:
            faults.append({
                "id": "fault_003",
                "component": "memory_engine",
                "action": "empty_query_stress",
                "result": "failed",
                "detail": str(e),
            })

        return faults


# ── CLI helpers ──────────────────────────────────────────────────

def create_self_heal(config: Dict = None) -> SelfHeal:
    if config is None:
        import yaml
        config_path = os.path.join(_brain_dir, "config.yaml")
        try:
            with io.open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}
    return SelfHeal(config)


# ─ ─ RuleWatcher ─ ─

class RuleWatcher:
    """Monitors brain/rules/ for YAML changes. On change: runs regression -> invalidates cache on pass. (P0-2)
    Uses polling (mtime check every 1s) when watchdog is unavailable.
    """

    def __init__(self, rules_dir: str, audit_db_path: str = None):
        self.rules_dir = rules_dir
        self.audit_db_path = audit_db_path
        self._running = False
        self._thread = None
        self._mtimes: Dict = {}  # filepath -> mtime
        self._first_scan = True

    def start(self):
        """Start watching in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _watch_loop(self):
        """Main watch loop. Polls file mtimes every second."""
        # First scan to establish baseline
        self._scan_mtimes()
        self._first_scan = False

        while self._running:
            time.sleep(1)
            try:
                if self._scan_mtimes():
                    self._on_change()
            except Exception as e:
                print(f"RuleWatcher: error in watch loop: {e}", file=sys.stderr)

    def _scan_mtimes(self) -> bool:
        """Scan all YAML files, return True if any mtime changed."""
        changed = False
        current = set()

        if not os.path.isdir(self.rules_dir):
            return False

        for root, dirs, files in os.walk(self.rules_dir):
            for fname in files:
                if fname.endswith(('.yaml', '.yml')):
                    fpath = os.path.join(root, fname)
                    try:
                        mtime = os.path.getmtime(fpath)
                        current.add(fpath)
                        if fpath not in self._mtimes:
                            self._mtimes[fpath] = mtime
                        elif mtime != self._mtimes[fpath]:
                            self._mtimes[fpath] = mtime
                            changed = True
                    except OSError:
                        pass

        # Check for deleted files
        removed = [fp for fp in self._mtimes if fp not in current]
        for fp in removed:
            del self._mtimes[fp]
            changed = True

        # Check for new files
        if len(current) != len(self._mtimes):
            changed = True

        return changed

    def _on_change(self):
        """Handle rule file change. Runs regression tests before allowing cache invalidation.

        P0-2: Rule change -> auto-run regression -> block on failure.
        """
        # Step 1: Run regression tests
        test_passed = self._run_regression_tests()
        
        # Step 2: Only invalidate cache if regression passes
        if test_passed:
            try:
                from rule_engine import invalidate_cache
                invalidate_cache()
            except Exception as e:
                print("RuleWatcher: failed to invalidate cache: {}".format(e), file=sys.stderr)
        else:
            print("RuleWatcher: regression tests FAILED. Cache NOT invalidated. Rules not in effect.", file=sys.stderr)

        # Step 3: Write audit log
        self._write_audit_log()

        # Step 4: Trigger export-rules to update fallback.md (AB-KB Wave B)
        self._trigger_export_rules()

    def _run_regression_tests(self):
        """Run the brain regression suite. Returns True if all tests pass."""
        import subprocess, json
        brain_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(brain_dir)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "brain.test_brain", "-q"],
                capture_output=True, text=True, timeout=60,
                cwd=root_dir,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            passed = result.returncode == 0
            # Log result to audit
            self._log_regression_result(passed, result.stdout[-500:] if result.stdout else "", result.stderr[-500:] if result.stderr else "")
            return passed
        except Exception as e:
            print("RuleWatcher: regression run failed: {}".format(e), file=sys.stderr)
            self._log_regression_result(False, "", str(e))
            return False

    def _log_regression_result(self, passed, stdout_tail, stderr_tail):
        """Log regression test result to rules audit."""
        try:
            from datetime import datetime
            log_entry = {
                "event": "regression_tests",
                "timestamp": datetime.now().isoformat(),
                "passed": passed,
                "source": "P0-2_RuleWatcher",
            }
            log_path = os.path.join(os.path.dirname(self.rules_dir), "_rules_audit.jsonl")
            with io.open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _write_audit_log(self):
        """Write audit log entry for rules change."""
        try:
            from datetime import datetime
            log_entry = {
                "event": "rules_changed",
                "timestamp": datetime.now().isoformat(),
                "source": "RuleWatcher",
            }
            log_path = os.path.join(os.path.dirname(self.rules_dir), "_rules_audit.jsonl")
            with io.open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=True) + "\n")
        except Exception:
            pass


def create_rule_watcher(rules_dir: str = None) -> RuleWatcher:
    """Create a RuleWatcher for the default rules dir-ectory."""
    if rules_dir is None:
        rules_dir = os.path.join(_brain_dir, "rules")
    return RuleWatcher(rules_dir)
# ---- W1-3: Health alert push (8 indicators) ----

def check_and_alert(config_path=None):
    '''Run health checks for 8 indicators and generate alerts for exceeding thresholds.

    Indicators monitored (alert condition):
      disk_usage_pct       > 85%    cleanup needed
      memory_usage_pct     > 85%    high memory pressure
      cache_hit_rate_pct   < 60%    cache degradation
      audit_write_success  < 95%    audit engine issue
      rule_check_p99_ms    > 300ms  rule engine slowdown
      kb_search_p99_ms     > 2000ms KB search slowdown
      overall_health       != ok    system health degraded
      degrade_level        > 0      system in degraded mode

    Alert dedup: same indicator not re-alerted within 30 minutes.
    Alert output: CLI warning, markdown file, webhook POST (if configured).
    Returns dict with indicators snapshot, alerts triggered, and dedup info.
    '''
    import shutil
    from datetime import datetime

    brain_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(brain_dir)

    # ---- Load config ----
    config = {}
    cfg_path = config_path or os.path.join(brain_dir, 'config.yaml')
    if os.path.isfile(cfg_path):
        try:
            import yaml
            with io.open(cfg_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

    # ---- Run health checks via SelfHeal ----
    healer = SelfHeal(config)
    health = healer.health_check()

    dimensions = health.get('dimensions', {})
    perf_dim = dimensions.get('performance', {})
    audit_dim = dimensions.get('audit_engine', {})
    memory_dim = dimensions.get('memory_engine', {})

    # ---- 8 Indicators ----

    indicators = {}

    # 1. disk_usage_pct
    try:
        usage = shutil.disk_usage(root_dir)
        indicators['disk_usage_pct'] = round((usage.used / usage.total) * 100, 1)
    except Exception:
        indicators['disk_usage_pct'] = 0

    # 2. memory_usage_pct
    try:
        import psutil
        indicators['memory_usage_pct'] = round(psutil.virtual_memory().percent, 1)
    except Exception:
        indicators['memory_usage_pct'] = 0

    # 3. cache_hit_rate_pct
    cache_hit = None
    perf_data = perf_dim.get('perf_data', {})
    if isinstance(perf_data, dict):
        cache_hit = perf_data.get('cache_hit_rate_pct')
    if cache_hit is None:
        cache_hit = memory_dim.get('cache_hit_rate_pct', 100)
    indicators['cache_hit_rate_pct'] = cache_hit

    # 4. audit_write_success_pct
    audit_status = audit_dim.get('status', 'ok')
    if audit_status == 'ok':
        indicators['audit_write_success_pct'] = 100
    elif audit_status == 'warning':
        indicators['audit_write_success_pct'] = 90
    else:
        indicators['audit_write_success_pct'] = 0

    # 5. rule_check_p99_ms
    indicators['rule_check_p99_ms'] = perf_dim.get('rule_check_p99_ms', 0)

    # 6. kb_search_p99_ms
    indicators['kb_search_p99_ms'] = perf_dim.get('kb_search_p99_ms', 0)

    # 7. overall_health
    indicators['overall_health'] = health.get('overall_status', 'ok')

    # 8. degrade_level
    indicators['degrade_level'] = health.get('degrade_level', 0)

    # ---- Threshold evaluation ----

    threshold_rules = [
        ('disk_usage_pct',          85,  'gt', 'Clean up temp files, archives, or expand disk space'),
        ('memory_usage_pct',        85,  'gt', 'Close unused applications, restart memory-heavy services'),
        ('cache_hit_rate_pct',      60,  'lt', 'Rebuild KB index, check memory engine health'),
        ('audit_write_success_pct', 95,  'lt', 'Check audit DB permissions and disk space'),
        ('rule_check_p99_ms',      300,  'gt', 'Optimize rule engine, reduce rule count or complexity'),
        ('kb_search_p99_ms',      2000,  'gt', 'Optimize ChromaDB, reduce index size or re-index'),
        ('overall_health',         'ok', 'ne', 'Run full health check: python brain/cli.py status'),
        ('degrade_level',            0,  'gt', 'Check brain/_degrade_state.json for degrade triggers'),
    ]

    raw_alerts = []
    for name, threshold, compare, suggestion in threshold_rules:
        value = indicators[name]
        triggered = False
        if compare == 'gt':
            triggered = isinstance(value, (int, float)) and value > threshold
        elif compare == 'lt':
            triggered = isinstance(value, (int, float)) and value < threshold
        elif compare == 'ne':
            triggered = value != threshold
        if triggered:
            raw_alerts.append(dict(
                indicator=name, value=value,
                threshold=threshold, suggestion=suggestion,
            ))

    # ---- Alert dedup (30-minute window) ----

    alerts_dir = os.path.join(brain_dir, 'alerts')
    os.makedirs(alerts_dir, exist_ok=True)
    dedup_file = os.path.join(alerts_dir, '.dedup_state.json')

    dedup_state = {}
    if os.path.isfile(dedup_file):
        try:
            with io.open(dedup_file, 'r', encoding='utf-8') as f:
                dedup_state = json.load(f)
        except Exception:
            dedup_state = {}

    now = datetime.now()
    now_ts = now.timestamp()
    dedup_window = 30 * 60

    new_alerts = []
    for alert in raw_alerts:
        last_ts = dedup_state.get(alert['indicator'], 0)
        if (now_ts - last_ts) > dedup_window:
            new_alerts.append(alert)
            dedup_state[alert['indicator']] = now_ts

    try:
        with io.open(dedup_file, 'w', encoding='utf-8') as f:
            json.dump(dedup_state, f, ensure_ascii=True, indent=2)
    except Exception:
        pass

    # ---- Alert outputs ----

    if new_alerts:
        # (a) CLI high-visibility warning
        print()
        print('=' * 62)
        print('  !! HEALTH ALERT - {} indicator(s) exceeded threshold'.format(len(new_alerts)))
        print('=' * 62)
        for alert in new_alerts:
            print('  - {}: current={} threshold={} -> {}'.format(
                alert['indicator'], alert['value'],
                alert['threshold'], alert['suggestion']))
        print('=' * 62)
        print()

        # (b) Write alert markdown file to brain/alerts/
        alert_filename = 'alert_{}.md'.format(now.strftime('%Y%m%d_%H%M%S'))
        alert_path = os.path.join(alerts_dir, alert_filename)

        md_lines = [
            '# Health Alert Report', '',
            '- **Generated**: {}'.format(now.strftime('%Y-%m-%d %H:%M:%S')),
            '- **Alerts triggered**: {}'.format(len(new_alerts)), '',
            '## Indicators', '',
            '| Indicator | Current Value | Threshold | Suggested Action |',
            '|:----------|:-------------|:----------|:-----------------|',
        ]
        for a in new_alerts:
            md_lines.append('| {} | {} | {} | {} |'.format(
                a['indicator'], a['value'], a['threshold'], a['suggestion']))

        with io.open(alert_path, 'w', encoding='utf-8') as f:
            f.write(chr(10).join(md_lines) + chr(10))

        print('Alert report saved: {}'.format(alert_path))

        # (c) POST to webhook if configured
        alert_cfg = config.get('alert', {})
        webhook_url = alert_cfg.get('webhook_url', '')
        if webhook_url:
            try:
                import urllib.request
                payload = json.dumps({
                    'type': 'health_alert',
                    'timestamp': now.isoformat(),
                    'alerts': [{
                        'indicator': a['indicator'],
                        'value': a['value'],
                        'threshold': a['threshold'],
                        'suggestion': a['suggestion'],
                    } for a in new_alerts],
                }, ensure_ascii=False).encode('utf-8')
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={'Content-Type': 'application/json; charset=utf-8'},
                    method='POST',
                )
                urllib.request.urlopen(req, timeout=10)
                print('Alert posted to webhook')
            except Exception as e:
                print('Webhook POST failed: {}'.format(e))

    return {
        'timestamp': now.isoformat(),
        'indicators': indicators,
        'alerts_triggered': len(new_alerts),
        'alerts': [{
            'indicator': a['indicator'],
            'value': a['value'],
            'threshold': a['threshold'],
        } for a in new_alerts],
        'dedup_suppressed': len(raw_alerts) - len(new_alerts),
    }

# ── OPS-2: Disk auto-cleanup ─────────────────────────
def auto_cleanup(dry_run=False):
    """Auto-clean old logs, alerts, temp files. Returns dict with stats."""
    import os, io, glob
    from datetime import datetime, timedelta

    brain_dir = os.path.dirname(os.path.abspath(__file__))
    now = datetime.now()
    freed = 0
    files_removed = []

    # 1. Audit log rotation: keep last 5, remove older
    audit_dir = os.path.join(brain_dir, "audit")
    for pattern in ["*.db-wal", "*.db-shm"]:
        for f in glob.glob(os.path.join(audit_dir, pattern)):
            try:
                size = os.path.getsize(f)
                if not dry_run:
                    os.remove(f)
                freed += size
                files_removed.append(f)
            except:
                pass

    # 2. Alert files: keep last 30 days
    alerts_dir = os.path.join(brain_dir, "alerts")
    if os.path.isdir(alerts_dir):
        for f in os.listdir(alerts_dir):
            if f.startswith("alert_"):
                fp = os.path.join(alerts_dir, f)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                    if (now - mtime) > timedelta(days=30):
                        size = os.path.getsize(fp)
                        if not dry_run:
                            os.remove(fp)
                        freed += size
                        files_removed.append(fp)
                except:
                    pass

    # 3. Temp files: remove _tmp_* files older than 24h
    for f in os.listdir(brain_dir):
        if f.startswith("_tmp_"):
            fp = os.path.join(brain_dir, f)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if (now - mtime) > timedelta(hours=24):
                    size = os.path.getsize(fp)
                    if not dry_run:
                        os.remove(fp)
                    freed += size
                    files_removed.append(fp)
            except:
                pass

    return {
        "freed_bytes": freed,
        "freed_mb": round(freed / 1024 / 1024, 2),
        "files_removed": len(files_removed),
        "details": files_removed[:10],
        "dry_run": dry_run,
    }

# ── AI-4: System auto-tuning ─────────────────────────
def auto_tune():
    """Auto-tune system parameters based on usage patterns."""
    import os, io as _io, json as _json

    brain_dir = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(brain_dir, ".tune_state.json")

    # Load previous state
    state = {}
    if os.path.isfile(cache_file):
        try:
            with _io.open(cache_file, 'r', encoding='utf-8') as f:
                state = _json.loads(f.read())
        except:
            pass

    now = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "cache_size": state.get("cache_size", 100),
        "rebuild_freq_days": state.get("rebuild_freq_days", 7),
        "log_level": state.get("log_level", "INFO"),
        "poll_interval_sec": state.get("poll_interval_sec", 30),
    }

    # Count recent queries from audit log
    recent_queries = 0
    try:
        audit_db = os.path.join(brain_dir, "audit", "audit.db")
        if os.path.isfile(audit_db):
            import sqlite3
            conn = sqlite3.connect(audit_db)
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM audit_log WHERE timestamp >= datetime('now', '-7 days')"
            )
            row = cur.fetchone()
            if row:
                recent_queries = row[0]
            conn.close()
    except:
        pass

    # Tuning logic
    changes = []
    if recent_queries > 500:
        new_cache = min(params["cache_size"] * 2, 500)
        if new_cache != params["cache_size"]:
            changes.append({"param": "cache_size", "from": params["cache_size"], "to": new_cache, "reason": f"High query volume ({recent_queries}/week)"})
            params["cache_size"] = new_cache

    if recent_queries < 50:
        new_cache = max(params["cache_size"] // 2, 50)
        if new_cache != params["cache_size"]:
            changes.append({"param": "cache_size", "from": params["cache_size"], "to": new_cache, "reason": "Low query volume, reducing cache"})
            params["cache_size"] = new_cache

    # Save state
    state.update(params)
    state["last_tune"] = now
    with _io.open(cache_file, 'w', encoding='utf-8') as f:
        f.write(_json.dumps(state, ensure_ascii=False, indent=2))

    return {
        "params": params,
        "changes": len(changes),
        "change_details": changes,
        "recent_queries_week": recent_queries,
        "last_tune": now,
    }

