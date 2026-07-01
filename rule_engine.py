# -*- coding: utf-8 -*-
"""启元智能 · 启元智脑规则引擎"""

import io, os, yaml, json, sys, re
from datetime import datetime
from typing import Dict, List, Optional, Any

# Phase 5: logging chain instrumentation
try:
    from logging_chain import log_info, log_error, log_warn
except ImportError:
    log_info = log_error = log_warn = lambda *a, **kw: None



# P0-3 YAML Schema  (P0-3 Input Validation & Security)
import re as _yaml_re

# YAML unsafe tags filter
_YAML_UNSAFE_TAGS = [
    "!!python/object", "!!python/name", "!!python/module",
    "!!python/new", "!!python/apply", "!!python/call",
]

def _validate_yaml_safe(raw_text, filepath=""):
    if not raw_text or not raw_text.strip():
        raise ValueError(": " + filepath)
    for tag in _YAML_UNSAFE_TAGS:
        if tag.lower() in raw_text.lower():
            raise ValueError(": " + filepath + "  " + tag + " ")
    return True

def _validate_rule_schema(rule, source_file=""):
    if not isinstance(rule, dict):
        raise ValueError(": " + source_file + " ")
    if not rule.get("id"):
        raise ValueError("id: " + source_file)
    if not rule.get("name"):
        raise ValueError("name: " + source_file + " id=" + str(rule.get("id", "?")))
    priority = rule.get("priority", 99)
    if not isinstance(priority, (int, float)):
        raise ValueError("priority: " + source_file + " id=" + str(rule.get("id", "?")) + ", priority=" + str(priority) + " ")
    return True

# END P0-3 YAML
class RuleEngine:
    """Core rule engine for Qiyuan Intelligence external brain."""

    # Explicit classification keywords (checked in order: P0 -> P1 -> P2 fallback)
    P0_KEYWORDS = [
        "删除", "删", "改宪法", "修改宪法", "修改规则", "对外发布",
        "发布", "裁撤", "移除>5", "移>5", "Token>50000", "Set-Content",
        "50000", "基因协议",
    ]
    P1_KEYWORDS = [
        "新建文件", "创建文件", "创建", "写文件", "改SKILL", "修改SKILL",
        "改skill", "跨项目", "立项", "写脚本",
    ]
    # P2 keywords: when these match and no P0/P1 keywords match -> P2
    P2_KEYWORDS = [
        "打分", "评估", "报告", "状态更新", "日常", "查询", "搜索",
        "阅读", "查看", "检查", "统计", "汇总", "分析",
        "更新", "整理", "同步", "扫描", "迁移",
    ]

    @staticmethod
    def _fuzzy_match(keyword: str, text: str) -> bool:
        """Non-contiguous substring match: all chars of keyword appear in text in order."""
        ki = 0
        for ch in text:
            if ch == keyword[ki]:
                ki += 1
                if ki == len(keyword):
                    return True
        return False

    def __init__(self, rules_dir: str, config: Optional[Dict] = None, include_draft: bool = False):
        self.rules_dir = rules_dir
        self.config = config or {}
        self.rules: List[Dict] = []
        self.include_draft = include_draft
        self.ab_tests = {}
        self.ab_stats = {}
        self.rule_stats: Dict[str, Dict] = {}  # {rule_id: {call_count, match_count, last_called}}
        self._load_ab_config()
        self._rules_changed = is_rules_changed()
        self._rule_version = get_rule_version()  # P2-3: 当前规则版本号
        self._load_all_rules(include_draft=include_draft)
        if self._rules_changed:
            self._load_all_rules(include_draft=include_draft)


    # ── A/B Testing (P0-3) ──
    def _load_ab_config(self):
        try:
            import yaml as _yaml
            config_path = os.path.join(os.path.dirname(self.rules_dir), "config", "ab_tests.yaml")
            if os.path.isfile(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = _yaml.safe_load(f) or {}
                self.ab_tests = data.get("tests", {})
                self.ab_stats = data.get("stats", {})
        except Exception:
            pass

    def _save_ab_config(self):
        try:
            import yaml as _yaml
            config_dir = os.path.join(os.path.dirname(self.rules_dir), "config")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "ab_tests.yaml")
            with open(config_path, "w", encoding="utf-8") as f:
                _yaml.dump({"tests": self.ab_tests, "stats": self.ab_stats}, f,
                          allow_unicode=True, default_flow_style=False)
        except Exception:
            pass

    def ab_test_start(self, rule_id, ratio=0.1):
        import datetime as _dt
        rule_ids = [r.get("id") for r in self.rules]
        if rule_id not in rule_ids:
            return {"ok": False, "error": "Rule not found: " + rule_id}
        if ratio <= 0 or ratio > 1:
            return {"ok": False, "error": "Ratio must be 0-1"}
        self.ab_tests[rule_id] = {
            "ratio": ratio, "enabled": True,
            "start_time": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.ab_stats[rule_id] = {
            "matches": 0, "executions": 0, "successes": 0,
            "failures": 0, "old_matches": 0, "old_successes": 0,
        }
        self._save_ab_config()
        return {"ok": True, "action": "started", "rule_id": rule_id, "ratio": ratio}

    def ab_test_stop(self, rule_id):
        if rule_id not in self.ab_tests:
            return {"ok": False, "error": "No test for " + rule_id}
        stats = self.ab_stats.get(rule_id, {})
        del self.ab_tests[rule_id]
        self._save_ab_config()
        return {"ok": True, "action": "stopped", "rule_id": rule_id, "final_stats": stats}

    def ab_test_results(self, rule_id=None):
        if rule_id:
            if rule_id not in self.ab_stats:
                return {"ok": False, "error": "No stats for " + rule_id}
            return {"ok": True, "rule_id": rule_id,
                    "config": self.ab_tests.get(rule_id, {}),
                    "stats": self.ab_stats[rule_id]}
        return {"ok": True, "active_tests": list(self.ab_tests.keys()),
                "all_stats": self.ab_stats}


    def _actions_contradict(self, action_a: str, action_b: str) -> bool:
        # Simple contradiction detection: negations + opposites
        negations = ["not", "do not", "don't", "never", "禁止", "不得", "不允许", "不可"]
        opposites_pairs = [
            ("allow", "deny"), ("允许", "禁止"), ("通过", "驳回"),
            ("approve", "reject"), ("enable", "disable"),
            ("保留", "删除"), ("keep", "delete"), ("save", "discard"),
            ("开启", "关闭"), ("open", "close"), ("start", "stop"),
            ("增加", "减少"), ("add", "remove"), ("create", "destroy"),
        ]
        a_lower = action_a.lower()
        b_lower = action_b.lower()
        for neg in negations:
            neg_in_a = neg in a_lower
            neg_in_b = neg in b_lower
            if neg_in_a != neg_in_b:
                # Strip negations and compare
                a_stripped = a_lower
                b_stripped = b_lower
                for n in negations:
                    a_stripped = a_stripped.replace(n, "")
                    b_stripped = b_stripped.replace(n, "")
                a_stripped = " ".join(a_stripped.split())
                b_stripped = " ".join(b_stripped.split())
                if a_stripped and b_stripped and a_stripped == b_stripped:
                    return True
        for w1, w2 in opposites_pairs:
            if w1 in a_lower and w2 in b_lower:
                return True
            if w2 in a_lower and w1 in b_lower:
                return True
        return False

    def detect_conflicts(self, rule_id=None):
        if rule_id:
            target_rule = None
            for r in self.rules:
                if r.get("id") == rule_id:
                    target_rule = r
                    break
            if not target_rule:
                return {"ok": False, "error": "Rule not found: " + rule_id}
            conflicts = self._check_conflicts_for(target_rule)
            return {"ok": True, "rule_id": rule_id, "conflicts": conflicts, "count": len(conflicts)}
        all_conflicts = []
        for r in self.rules:
            all_conflicts.extend(self._check_conflicts_for(r))
        unique = []
        seen = set()
        for c in all_conflicts:
            pair = tuple(sorted([c["rule_a"], c["rule_b"]]))
            if pair not in seen:
                seen.add(pair)
                unique.append(c)
        return {"ok": True, "conflicts": unique, "count": len(unique)}

    def _check_conflicts_for(self, rule):
        triggers_a = set(t.lower() for t in rule.get("triggers", []))
        action_a = rule.get("action", "").lower()
        priority_a = rule.get("priority", 0)
        rule_id_a = rule.get("id", "")
        conflicts = []
        for other in self.rules:
            rule_id_b = other.get("id", "")
            if rule_id_a == rule_id_b:
                continue
            triggers_b = set(t.lower() for t in other.get("triggers", []))
            action_b = other.get("action", "").lower()
            priority_b = other.get("priority", 0)
            overlap = triggers_a & triggers_b
            if not overlap:
                continue
            ctypes = []
            if priority_a != priority_b:
                ctypes.append("priority_mismatch")
            if len(overlap) / max(len(triggers_a), len(triggers_b), 1) >= 0.5:
                ctypes.append("trigger_overlap")
            if action_a and action_b and self._actions_contradict(action_a, action_b):
                ctypes.append("action_contradiction")
            if ctypes:
                conflicts.append({
                    "rule_a": rule_id_a, "rule_b": rule_id_b,
                    "conflict_types": ctypes,
                    "overlapping_triggers": list(overlap)[:10],
                    "severity": "high" if "action_contradiction" in ctypes else ("medium" if "trigger_overlap" in ctypes else "low"),
                })
        return conflicts
    def _ab_should_use_new(self, rule_id):
        import random as _random
        if rule_id not in self.ab_tests:
            return False
        if not self.ab_tests[rule_id].get("enabled", False):
            return False
        return _random.random() < self.ab_tests[rule_id]["ratio"]

    def _ab_record(self, rule_id, used_new, success):
        if rule_id not in self.ab_stats:
            return
        stats = self.ab_stats[rule_id]
        if used_new:
            stats["executions"] = stats.get("executions", 0) + 1
            if success:
                stats["successes"] = stats.get("successes", 0) + 1
            else:
                stats["failures"] = stats.get("failures", 0) + 1
        else:
            stats["old_matches"] = stats.get("old_matches", 0) + 1
            if success:
                stats["old_successes"] = stats.get("old_successes", 0) + 1
        self._save_ab_config()

    def _load_all_rules(self, include_draft=False):
        # Recursively load all YAML rule files from rules_dir.
        # Lifecycle-aware loading per meta_rules.yaml.
        self.rules = []
        if not os.path.isdir(self.rules_dir):
            return

        for root, dirs, files in os.walk(self.rules_dir):
            for fname in sorted(files):
                if fname.endswith(('.yaml', '.yml')):
                    fpath = os.path.join(root, fname)
                    try:
                        with io.open(fpath, 'r', encoding='utf-8') as f:
                            raw_text = f.read()
                        # P0-3:  YAML  (reject unsafe tags)
                        _validate_yaml_safe(raw_text, fname)
                        data = yaml.safe_load(raw_text)
                        if data and 'rules' in data:
                            for rule in data['rules']:
                                rule['_source_file'] = fname
                                self._process_rule(rule, fpath, include_draft)
                        elif data and 'rule' in data:
                            inner = data['rule']
                            inner['_source_file'] = fname
                            self._process_rule(inner, fpath, include_draft)
                        elif data and 'id' in data:
                            data['_source_file'] = fname
                            self._process_rule(data, fpath, include_draft)
                    except yaml.YAMLError as e:
                        print(f"Warning: failed to parse {fpath}: {e}", file=sys.stderr)

        # Sort by priority ascending, then by id
        self.rules.sort(key=lambda r: (r.get('priority', 99), r.get('id', '')))

    def _process_rule(self, rule, fpath, include_draft):
        # Validate and process a single rule per meta_rules.yaml lifecycle.
        rule_id = rule.get('id', '')
        if not rule_id or not str(rule_id).strip():
            print(f"Error: rule in {fpath} missing id field. Rule rejected.", file=sys.stderr)
            return

        status = rule.get('status', 'active')

        if status == 'archived':
            return
        if status == 'draft' and not include_draft:
            return

        if status == 'deprecated':
            rule['_warning'] = f"Rule {rule_id} is deprecated."

        self.rules.append(rule)

    def check(self, action: str, context: Optional[Dict] = None) -> Dict:
        """Match action description against all rules."""
        if not action:
            return {"matched": False, "count": 0, "rules": [], "action": None}

        matched = []
        action_lower = action.lower()
        rules_changed = is_rules_changed()

        # -- S+级: 删除操作路径安全检查 --
        delete_keywords = ['delete', 'remove', 'del ', 'rm ', '清理', '删除', '清空', '整理']
        if any(kw in action_lower for kw in delete_keywords):
            try:
                import importlib.util as _iu
                import os as _os
                _sd_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), '_scripts', 'safe_delete.py')
                _sd_spec = _iu.spec_from_file_location('_sd_mod', _sd_path)
                _sd_mod = _iu.module_from_spec(_sd_spec)
                _sd_spec.loader.exec_module(_sd_mod)
                matched.append({
                    'id': 'INC-S+_AUTO',
                    'name': '自动删除安全检测',
                    'priority': 10,
                    'summary': 'S+级: 删除操作必须通过safe_delete.py检查路径白名单，禁止删除启元智能以外的文件',
                    'level': 'S+',
                    '_source_file': '_scripts/safe_delete.py',
                    'warning': 'S+级事故风险: 删除操作涉及用户数据！必须先调用safe_delete.py检查路径、向CEO报告并获批准后执行'
                })
            except Exception:
                pass


        for rule in self.rules:
            triggers = rule.get('triggers', [])
            if not triggers:
                continue
            for trigger in triggers:
                if trigger.lower() in action_lower:
                    matched.append({
                        "id": rule.get('id', ''),
                        "name": rule.get('name', ''),
                        "priority": rule.get('priority', 99),
                        "summary": rule.get('action', ''),
                        "level": rule.get('level', 'P2'),
                        "_source_file": rule.get('_source_file', ''),
                        "warning": rule.get('_warning', None),
                    })
                    break  # one trigger match is enough

        # Track rule_stats for matched rules
        for m in matched:
            rid = m['id']
            if rid not in self.rule_stats:
                self.rule_stats[rid] = {'call_count': 0, 'match_count': 0, 'last_called': ''}
            self.rule_stats[rid]['call_count'] += 1
            self.rule_stats[rid]['match_count'] += 1
            self.rule_stats[rid]['last_called'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        highest_action = matched[0]['summary'] if matched else None
        rules_changed = is_rules_changed()
        if rules_changed:
            self._load_all_rules()
        return {
            "matched": len(matched) > 0,
            "count": len(matched),
            "rules": matched,
            "action": highest_action,
            "rules_changed": rules_changed,
            "rule_version": get_rule_version(),  # P2-3: 匹配时的规则版本号
        }

    def classify(self, action: str) -> Dict:
        """Determine P0/P1/P2 level.

        Priority order: P0 keywords > P1 keywords > P2 keywords > rule-matching fallback.
        """
        action_lower = action.lower()
        rules_changed = is_rules_changed()

        # Step 1: Check P0 keywords (highest priority)
        for kw in self.P0_KEYWORDS:
            kw_lower = kw.lower()
            if (len(kw) >= 3 and self._fuzzy_match(kw_lower, action_lower)) or kw_lower in action_lower:
                result = self.check(action)
                rules_changed = is_rules_changed()
                return {
                    "level": "P0",
                    "reason": f"Matched P0 keyword: '{kw}'. P0 requires CEO confirmation.",
                    "matched_rules": result['rules'],
                    "rules_changed": rules_changed,
                }

        # Step 2: Check P1 keywords
        for kw in self.P1_KEYWORDS:
            kw_lower = kw.lower()
            if (len(kw) >= 3 and self._fuzzy_match(kw_lower, action_lower)) or kw_lower in action_lower:
                result = self.check(action)
                rules_changed = is_rules_changed()
                return {
                    "level": "P1",
                    "reason": f"Matched P1 keyword: '{kw}'. P1 requires L1 confirmation.",
                    "matched_rules": result['rules'],
                    "rules_changed": rules_changed,
                }

        # Step 3: Check P2 keywords (before rule-matching fallback)
        for kw in self.P2_KEYWORDS:
            kw_lower = kw.lower()
            if (len(kw) >= 3 and self._fuzzy_match(kw_lower, action_lower)) or kw_lower in action_lower:
                # Ensure no P0/P1 keywords are also present
                result = self.check(action)
                rules_changed = is_rules_changed()
                return {
                    "level": "P2",
                    "reason": f"Matched P2 keyword: '{kw}'. Autonomous execution.",
                    "matched_rules": result['rules'],
                    "rules_changed": rules_changed,
                }

        # Step 4: Rule matching fallback
        result = self.check(action)

        if not result['matched']:
            rules_changed = is_rules_changed()
            return {
                "level": "P2",
                "reason": "No matching rules or keywords. Default to P2 (autonomous).",
                "matched_rules": [],
                "rules_changed": rules_changed,
            }

        # Determine highest level from matched rules
        levels = {'P0': 0, 'P1': 1, 'P2': 2}
        highest = 'P2'
        highest_name = 'Default'
        for r in result['rules']:
            lv = r.get('level', 'P2')
            if levels.get(lv, 2) < levels.get(highest, 2):
                highest = lv
                highest_name = r['name']

        rules_changed = is_rules_changed()
        return {
            "level": highest,
            "reason": f"Matched {result['count']} rule(s). Highest: {highest_name} ({highest}).",
            "matched_rules": result['rules'],
            "rules_changed": rules_changed,
        }

    def status(self) -> Dict:
        """Return brain health status (including Phase 2 memory if available)."""
        result = {
            "brain_ok": len(self.rules) > 0,
            "components": {
                "rules_loaded": len(self.rules),
                "rules_dir": self.rules_dir,
                "version": self.config.get('brain', {}).get('version', 'unknown'),
            },
        }

        # Try to add memory engine status
        try:
            from memory.memory_engine import MemoryEngine
            mem_cfg = self.config.get('memory', {})
            kb_root = mem_cfg.get('kb_root', '')
            persist_dir = mem_cfg.get('persist_dir', '')
            if kb_root and persist_dir:
                mem = MemoryEngine(
                    kb_root, persist_dir,
                    mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5'),
                    mem_cfg.get('chunk_size', 1000),
                    mem_cfg.get('top_k', 5),
                )
                result['components']['memory'] = mem.status()
        except Exception:
            result['components']['memory'] = {
                'indexed_docs': 0, 'model': 'unavailable', 'ok': False,
            }

        # Try to add workspace status
        try:
            from memory.workspace import Workspace
            ws_cfg = self.config.get('workspace', {})
            db_path = ws_cfg.get('db_path', '')
            if db_path:
                ws = Workspace(db_path)
                result['components']['workspace'] = ws.status()
        except Exception:
            result['components']['workspace'] = {'ok': False, 'keys': 0}

        return result

    def invalidate_cache(self):
        """Mark rule cache as stale. Called by RuleWatcher on file changes."""
        invalidate_cache()

    def is_rules_changed(self):
        """Check and reset rules_changed flag. Returns True if rules changed since last check."""
        changed = is_rules_changed()
        if changed:
            self._load_all_rules()
        return changed

    def validate_rules(self) -> Dict:
        # Validate all rule YAML files against meta_rules.yaml standard.
        id_pattern = re.compile(r'^[A-Z]+-[0-9]+[A-Z]*$')
        required_fields = ['id', 'name', 'priority', 'triggers', 'action', 'owner', 'status', 'created']
        valid_statuses = {'draft', 'review', 'active', 'deprecated', 'archived', 'suggested'}

        results = []
        if not os.path.isdir(self.rules_dir):
            return {"valid": False, "error": "rules_dir not found",
                    "total_files": 0, "total_rules": 0, "issues_count": 0, "results": []}

        for root, dirs, files in os.walk(self.rules_dir):
            for fname in sorted(files):
                if fname.endswith(('.yaml', '.yml')):
                    fpath = os.path.join(root, fname)
                    file_result = {"file": fname, "path": fpath, "rules": [], "valid": True}
                    try:
                        with io.open(fpath, 'r', encoding='utf-8') as f:
                            raw_text = f.read()
                        # P0-3:  YAML  (reject unsafe tags)
                        _validate_yaml_safe(raw_text, fname)
                        data = yaml.safe_load(raw_text)

                        rule_list = []
                        if data and 'rules' in data:
                            rule_list = data['rules']
                        elif data and 'rule' in data:
                            rule_list = [data['rule']]
                        elif data and 'id' in data:
                            rule_list = [data]

                        for rule in rule_list:
                            rv = self._validate_single_rule(rule, id_pattern, required_fields, valid_statuses)
                            file_result["rules"].append(rv)
                            if not rv["valid"]:
                                file_result["valid"] = False
                    except yaml.YAMLError as e:
                        file_result["valid"] = False
                        file_result["error"] = str(e)

                    results.append(file_result)

        all_valid = all(r["valid"] for r in results)
        total_rules = sum(len(r["rules"]) for r in results)
        issues = sum(1 for r in results for rr in r["rules"] if not rr["valid"])

        return {
            "valid": all_valid,
            "total_files": len(results),
            "total_rules": total_rules,
            "issues_count": issues,
            "results": results,
        }

    def _validate_single_rule(self, rule, id_pattern, required_fields, valid_statuses):
        # Validate a single rule against meta_rules standard.
        issues = []
        rule_id = rule.get('id', '')

        for field in required_fields:
            val = rule.get(field)
            if val is None or (isinstance(val, str) and val.strip() == ''):
                issues.append(f"Missing required field: {field}")

        if rule_id and not id_pattern.match(str(rule_id)):
            issues.append(f"ID '{rule_id}' does not match format ^[A-Z]+-[0-9]+[A-Z]*$")

        status = rule.get('status', '')
        if status and status not in valid_statuses:
            issues.append(f"Unknown status: '{status}'")

        priority = rule.get('priority')
        if priority is not None and not isinstance(priority, (int, float)):
            issues.append(f"priority must be numeric, got {type(priority).__name__}")

        return {
            "id": str(rule_id),
            "name": rule.get('name', ''),
            "valid": len(issues) == 0,
            "issues": issues,
        }


    def get_version_info(self) -> Dict:
        """P2-3: 返回规则引擎版本信息。"""
        import time as _time
        return {
            "rule_version": self._rule_version,
            "rules_count": len(self.rules),
            "last_load": _time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime()) if self.rules else "never",
        }


    # --- P1-2: Rule conflict detection ---



    def reload(self):
        """Reload all rules from disk."""
        self._load_all_rules(include_draft=self.include_draft)
        _reset_rules_changed()
        self._rule_version = get_rule_version()  # P2-3: 重新加载版本号
        bump_rule_version()  # P2-3: 规则变更时递增版本号


# --- Module-level rules_changed state (persists across CLI invocations) ---

_BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
_RULES_STATE_FILE = os.path.join(_BRAIN_DIR, "_rules_state.json")


def invalidate_cache():
    """Mark rule cache as stale (called by RuleWatcher on file changes)."""
    try:
        state = {
            "rules_changed": True,
            "last_change": datetime.now().isoformat(),
        }
        with io.open(_RULES_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # P2-3: 规则变更时递增版本号
    bump_rule_version()

def is_rules_changed():
    """Check and reset the rules_changed flag.
    Returns True if rules changed since last check.
    """
    try:
        if os.path.exists(_RULES_STATE_FILE):
            with io.open(_RULES_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            if state.get("rules_changed", False):
                return True
    except Exception:
        pass
    return False


def _reset_rules_changed():
    """Reset the rules_changed flag to False."""
    try:
        if os.path.exists(_RULES_STATE_FILE):
            with io.open(_RULES_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            state["rules_changed"] = False
            with io.open(_RULES_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# --- P2-3: 规则版本号管理 ---

_VERSION_FILE = os.path.join(_BRAIN_DIR, "rule_version.txt")


def get_rule_version():
    """P2-3: 读取当前全局规则版本号。版本号存储在 brain/rule_version.txt 中。"""
    try:
        if os.path.exists(_VERSION_FILE):
            with io.open(_VERSION_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip())
    except (ValueError, IOError):
        pass
    return 1


def bump_rule_version():
    """P2-3: 规则变更时递增全局版本号。不同会话可持有不同版本，平滑过渡。"""
    v = get_rule_version() + 1
    os.makedirs(_BRAIN_DIR, exist_ok=True)
    with io.open(_VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(str(v))
    return v




def _init_rule_version():
    """P2-3: 初始化版本文件（如果不存在）。"""
    if not os.path.exists(_VERSION_FILE):
        with io.open(_VERSION_FILE, "w", encoding="utf-8") as f:
            f.write("1")


# Ensure version file exists on module load
_init_rule_version()


def auto_repair_rules(rules_dir, dry_run=False):
    import os, io as _io, yaml as _yaml
    from datetime import datetime
    brain_dir = os.path.dirname(os.path.abspath(__file__))
    failed_dir = os.path.join(brain_dir, 'proposals', 'failed_repairs')
    os.makedirs(failed_dir, exist_ok=True)
    eng = RuleEngine(rules_dir)
    rules = list(eng.rules)
    repairs, failures = [], []
    for i, rule in enumerate(rules):
        rid = rule.get('id', 'unknown')
        if not rule.get('name'):
            rule['name'] = 'Auto-repaired ' + rid
            repairs.append({'rule_id': rid, 'fix': 'added name', 'type': 'missing_field'})
        if 'priority' not in rule:
            rule['priority'] = 99
            repairs.append({'rule_id': rid, 'fix': 'added priority=99', 'type': 'missing_field'})
    if repairs and not dry_run:
        for rule in rules:
            src = rule.get('_source_file', '')
            if src and os.path.isfile(src):
                try:
                    with _io.open(src, 'r', encoding='utf-8') as f:
                        data = _yaml.safe_load(f.read())
                    if isinstance(data, dict) and data.get('id') == rule.get('id'):
                        for k in ('name', 'priority', 'triggers'):
                            if k in rule:
                                data[k] = rule[k]
                        with _io.open(src, 'w', encoding='utf-8') as f:
                            _yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
                except Exception as e:
                    failures.append({'rule_id': rule.get('id'), 'attempted': 'save', 'error': str(e)[:100]})
    for fail in failures:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fp = os.path.join(failed_dir, 'failed_' + fail['rule_id'] + '_' + ts + '.md')
        with _io.open(fp, 'w', encoding='utf-8') as f:
            f.write('# repair failed\n\n- rule: ' + fail['rule_id'] + '\n- error: ' + fail['error'] + '\n')
    return {'repaired': len(repairs), 'failed': len(failures), 'repairs': repairs, 'dry_run': dry_run}
