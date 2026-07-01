# -*- coding: utf-8 -*-
"""启元智能 · 外部大脑 CLI 入口 (Phase 4)"""

import argparse, json, io, os, sys, yaml

# Ensure brain/ is on path for imports


# ── P0-3 输入校验模块 ──────────────────────────────────────────────
import re as _re_v

# Task module (cross-conversation task management)
from task_module import cmd_task_add, cmd_task_list, cmd_task_done, cmd_task_recurring, get_pending_tasks, get_recurring_due_today

# Shell注入危险字符集（管道符、命令分隔符、变量引用等）
_SHELL_DANGER_CHARS = frozenset(";|&`$!")

def validate_input(value, name="参数", allow_empty=False, max_len=1000, allow_shell_chars=False):
    if value is None:
        raise ValueError(f"{name}不能为None")
    if not isinstance(value, str):
        raise ValueError(f"{name}应为字符串类型，实际为{type(value).__name__}")
    if not allow_empty and (not value or value.strip() == ""):
        raise ValueError(f"{name}不能为空")
    if len(value) > max_len:
        raise ValueError(f"{name}过长（{len(value)}字符），最大允许{max_len}字符")

    # 检测null字节和控制字符（保留\t \n \r）
    for i, ch in enumerate(value):
        code = ord(ch)
        if code == 0:
            raise ValueError(f"{name}包含null字节（位置{i}），拒绝处理")
        if code < 0x20 and code not in (9, 10, 13):
            raise ValueError(f"{name}包含不可见控制字符（U+{code:04X}，位置{i}），拒绝处理")

    # Shell注入防护
    if not allow_shell_chars:
        for i, ch in enumerate(value):
            if ch in _SHELL_DANGER_CHARS:
                raise ValueError(f"{name}包含非法字符: {ch}（位置{i}），可能存在注入风险")

    return value


def validate_path_param(value, workspace_root=None):
    value = validate_input(value, "路径参数", max_len=2000)
    # 路径穿越检测
    parts = value.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError("路径越界：路径中包含 .. ，拒绝访问")
    # 绝对路径越界检查
    if os.path.isabs(value) and workspace_root:
        abs_path = os.path.normpath(os.path.realpath(value))
        abs_root = os.path.normpath(os.path.realpath(workspace_root))
        if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
            raise ValueError(f"路径越界：目标路径不在工作区{workspace_root}内")
    return value

# ── END P0-3 输入校验模块 ──────────────────────────────────────────
_brain_dir = os.path.dirname(os.path.abspath(__file__))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)

from rule_engine import RuleEngine

# Phase 2: memory engine (lazy import for graceful fallback)
_MemoryEngine = None
_Workspace = None

def _get_memory():
    global _MemoryEngine
    if _MemoryEngine is None:
        try:
            from memory.memory_engine import MemoryEngine
            _MemoryEngine = MemoryEngine
        except ImportError:
            return None
    return _MemoryEngine

def _get_workspace_cls():
    global _Workspace
    if _Workspace is None:
        try:
            from memory.workspace import Workspace
            _Workspace = Workspace
        except ImportError:
            return None
    return _Workspace

# Phase 3: audit engine (lazy import for graceful fallback)
_AuditEngine = None
_safe_write = None

def _get_audit_engine():
    global _AuditEngine
    if _AuditEngine is None:
        try:
            from audit.audit_engine import AuditEngine
            _AuditEngine = AuditEngine
        except ImportError:
            return None
    return _AuditEngine

def _get_safe_write():
    global _safe_write
    if _safe_write is None:
        try:
            from audit.audit_engine import safe_write as sw
            _safe_write = sw
        except ImportError:
            return None
    return _safe_write

# Phase 4: self-heal engine (lazy import)
_SelfHeal = None

def _get_self_heal():
    global _SelfHeal
    if _SelfHeal is None:
        try:
            from self_heal import SelfHeal
            _SelfHeal = SelfHeal
        except ImportError:
            return None
    return _SelfHeal


# Phase 4: self-heal engine (lazy import)
_SelfHeal = None

def _get_self_heal():
    global _SelfHeal
    if _SelfHeal is None:
        try:
            from self_heal import SelfHeal
            _SelfHeal = SelfHeal
        except ImportError:
            return None
    return _SelfHeal

def load_config(config_path: str) -> dict:
    """Load config.yaml."""
    try:
        with io.open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_engine(include_draft: bool = False) -> RuleEngine:
    """Create RuleEngine from config."""
    config_path = os.path.join(_brain_dir, 'config.yaml')
    config = load_config(config_path)
    rules_dir = config.get('brain', {}).get(
        'rules_dir',
        os.path.join(_brain_dir, 'rules')
    )
    return RuleEngine(rules_dir, config, include_draft=include_draft)


# ── Rule commands ─────────────────────────────────────────

def cmd_rule_check(args):
    try:
        validate_input(args.action, "action", max_len=1000)
    except ValueError as e:
        print(json.dumps({"matched": False, "count": 0, "rules": [], "error": str(e)}, ensure_ascii=True, indent=2))
        return
    include_draft = getattr(args, "include_draft", False)
    engine = get_engine(include_draft=include_draft)
    result = engine.check(args.action)
    try:
        from rule_engine import is_rules_changed
        result['rules_changed'] = is_rules_changed()
    except Exception:
        result['rules_changed'] = False

    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_rule_classify(args):
    try:
        validate_input(args.action, "action", max_len=1000)
    except ValueError as e:
        print(json.dumps({"level": "P2", "reason": str(e), "matched_rules": [], "error": str(e)}, ensure_ascii=True, indent=2))
        return
    engine = get_engine()
    result = engine.classify(args.action)
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_rule_validate(args):
    """Validate all rule YAML files against meta_rules standard."""
    engine = get_engine()
    result = engine.validate_rules()
    print(json.dumps(result, ensure_ascii=True, indent=2))


# ── KB commands ───────────────────────────────────────────

def cmd_kb_search(args):
    try:
        validate_input(args.query, "query", max_len=1000)
    except ValueError as e:
        print(json.dumps({"error": str(e), "results": [], "query": getattr(args, 'query', ''), "total": 0}, ensure_ascii=True, indent=2))
        return
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    mem_cfg = config.get('memory', {})
    kb_root = mem_cfg.get('kb_root',
        os.path.join(os.path.dirname(_brain_dir), '05_组织知识库'))
    persist_dir = mem_cfg.get('persist_dir',
        os.path.join(_brain_dir, 'memory', 'chroma_db'))
    model_name = mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5')
    chunk_size = mem_cfg.get('chunk_size', 1000)
    top_k = mem_cfg.get('top_k', 5)

    MemoryEngine = _get_memory()
    if MemoryEngine is None:
        print(json.dumps({
            "error": "Memory engine not available",
            "results": [], "query": args.query, "total": 0,
        }, ensure_ascii=True, indent=2))
        return

    try:
        engine = MemoryEngine(kb_root, persist_dir, model_name, chunk_size, top_k)
        result = engine.search(args.query, args.top_k if hasattr(args, 'top_k') and args.top_k else top_k)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "results": [], "query": args.query, "total": 0,
        }, ensure_ascii=True, indent=2))


def cmd_kb_rebuild(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    mem_cfg = config.get('memory', {})
    kb_root = mem_cfg.get('kb_root',
        os.path.join(os.path.dirname(_brain_dir), '05_组织知识库'))
    persist_dir = mem_cfg.get('persist_dir',
        os.path.join(_brain_dir, 'memory', 'chroma_db'))
    model_name = mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5')
    chunk_size = mem_cfg.get('chunk_size', 1000)
    top_k = mem_cfg.get('top_k', 5)

    MemoryEngine = _get_memory()
    if MemoryEngine is None:
        print(json.dumps({"error": "Memory engine not available"}, ensure_ascii=True))
        return

    engine = MemoryEngine(kb_root, persist_dir, model_name, chunk_size, top_k)
    engine.rebuild()
    print(json.dumps(engine.status(), ensure_ascii=True, indent=2))


def cmd_kb_status(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    mem_cfg = config.get('memory', {})
    kb_root = mem_cfg.get('kb_root',
        os.path.join(os.path.dirname(_brain_dir), '05_组织知识库'))
    persist_dir = mem_cfg.get('persist_dir',
        os.path.join(_brain_dir, 'memory', 'chroma_db'))
    model_name = mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5')
    chunk_size = mem_cfg.get('chunk_size', 1000)
    top_k = mem_cfg.get('top_k', 5)

    MemoryEngine = _get_memory()
    if MemoryEngine is None:
        print(json.dumps({"error": "Memory engine not available"}, ensure_ascii=True))
        return

    engine = MemoryEngine(kb_root, persist_dir, model_name, chunk_size, top_k)
    print(json.dumps(engine.status(), ensure_ascii=True, indent=2))


# ── Memory commands ───────────────────────────────────────

def cmd_memory_set(args):
    try:
        validate_input(args.key, "key", max_len=256)
        validate_input(args.value, "value", max_len=10000, allow_shell_chars=True)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True, indent=2))
        return
    Workspace = _get_workspace_cls()
    if Workspace is None:
        print(json.dumps({"ok": False, "error": "Workspace not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    ws_cfg = config.get('workspace', {})
    db_path = ws_cfg.get('db_path',
        os.path.join(_brain_dir, 'memory', 'workspace.db'))
    default_ttl = ws_cfg.get('default_ttl', 3600)

    ws = Workspace(db_path)
    ws.set(args.key, args.value, args.ttl if args.ttl else default_ttl)
    print(json.dumps({"ok": True, "key": args.key}, ensure_ascii=True))


def cmd_memory_get(args):
    try:
        validate_input(args.key, "key", max_len=256)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True, indent=2))
        return
    Workspace = _get_workspace_cls()
    if Workspace is None:
        print(json.dumps({"ok": False, "error": "Workspace not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    ws_cfg = config.get('workspace', {})
    db_path = ws_cfg.get('db_path',
        os.path.join(_brain_dir, 'memory', 'workspace.db'))

    ws = Workspace(db_path)
    value = ws.get(args.key)
    if value is None:
        print(json.dumps({"ok": False, "key": args.key, "value": None, "reason": "not found or expired"}, ensure_ascii=True))
    else:
        print(json.dumps({"ok": True, "key": args.key, "value": value}, ensure_ascii=True))


def cmd_memory_list(args):
    Workspace = _get_workspace_cls()
    if Workspace is None:
        print(json.dumps({"ok": False, "error": "Workspace not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    ws_cfg = config.get('workspace', {})
    db_path = ws_cfg.get('db_path',
        os.path.join(_brain_dir, 'memory', 'workspace.db'))

    ws = Workspace(db_path)
    keys = ws.list_keys()
    print(json.dumps({"ok": True, "keys": keys, "count": len(keys)}, ensure_ascii=True))


# ── Audit commands (Phase 3) ──────────────────────────────

def cmd_audit_log(args):
    """brain audit log [--since YYYY-MM-DD] [--action write|read] [--limit N]"""
    AuditEngine = _get_audit_engine()
    if AuditEngine is None:
        print(json.dumps({"error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))

    engine = AuditEngine(db_path)
    logs = engine.query(
        since=getattr(args, 'since', None),
        action=getattr(args, 'action', None),
        limit=getattr(args, 'limit', 100),
    )
    result = {"logs": logs, "count": len(logs)}
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_audit_check(args):
    """brain audit check <target_path>"""
    AuditEngine = _get_audit_engine()
    if AuditEngine is None:
        print(json.dumps({"error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))

    engine = AuditEngine(db_path)
    history = engine.file_history(args.target_path)
    result = {"file": args.target_path, "history": history, "versions": len(history)}
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_audit_stats(args):
    """brain audit stats [--since YYYY-MM-DD]"""
    AuditEngine = _get_audit_engine()
    if AuditEngine is None:
        print(json.dumps({"error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))

    engine = AuditEngine(db_path)
    stats = engine.stats(since=getattr(args, 'since', None))
    print(json.dumps(stats, ensure_ascii=True, indent=2))


# ── Safe-write command (Phase 3) ──────────────────────────

def cmd_safe_write(args):
    """brain safe-write <path> <content> [--operator <name>]"""
    safe_write_fn = _get_safe_write()
    if safe_write_fn is None:
        print(json.dumps({"ok": False, "error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))
    conflict_window = audit_cfg.get('conflict_window_seconds', 30)

    result = safe_write_fn(
        path=args.path,
        content=args.content,
        operator=getattr(args, 'operator', 'codex'),
        db_path=db_path,
        conflict_window=conflict_window,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))



# ── Health (Phase 4 self-heal) ───────────────────────────

def cmd_health_check(args):
    config_path = os.path.join(_brain_dir, "config.yaml")
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({
            "status": "error",
            "detail": "Self-heal engine not available",
        }, ensure_ascii=True, indent=2))
        return
    config = load_config(config_path)
    sh = SelfHeal(config)
    result = sh.health_check()
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_health_repair(args):
    try:
        validate_input(args.component, "component", max_len=128)
    except ValueError as e:
        print(json.dumps({"result": "error", "detail": str(e)}, ensure_ascii=True, indent=2))
        return
    config_path = os.path.join(_brain_dir, "config.yaml")
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({
            "result": "error",
            "detail": "Self-heal engine not available",
        }, ensure_ascii=True, indent=2))
        return
    config = load_config(config_path)
    sh = SelfHeal(config)
    result = sh.auto_repair(args.component)
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_health_degrade(args):
    try:
        level = args.level
        if not isinstance(level, int) or level < 0 or level > 3:
            raise ValueError(f"降级级别不合法：{level}，允许0-3的整数")
    except ValueError as e:
        print(json.dumps({"result": "error", "detail": str(e)}, ensure_ascii=True, indent=2))
        return
    config_path = os.path.join(_brain_dir, "config.yaml")
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({
            "result": "error",
            "detail": "Self-heal engine not available",
        }, ensure_ascii=True, indent=2))
        return
    config = load_config(config_path)
    sh = SelfHeal(config)
    result = sh.degrade(args.level)
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_status(args):
    result = {
        "brain_ok": True,
        "version": "1.0.0",
        "components": {
            "rules": {"ok": True},
            "memory": {"ok": False, "docs": 0},
            "workspace": {"ok": False, "keys": 0},
            "audit": {"ok": False, "total_logs": 0, "db_size_kb": 0},
            "self_heal": {"ok": False, "status": "unknown"},
        },
    }

    # Check rules
    try:
        config_path = os.path.join(_brain_dir, 'config.yaml')
        config = load_config(config_path)
        rules_dir = config.get('brain', {}).get('rules_dir',
            os.path.join(_brain_dir, 'rules'))
        if os.path.isdir(rules_dir):
            yaml_files = [f for f in os.listdir(rules_dir) if f.endswith('.yaml')]
            result['components']['rules'] = {"ok": True, "files": len(yaml_files)}
        else:
            result['components']['rules'] = {"ok": False, "error": "rules_dir not found"}
    except Exception as e:
        result['components']['rules'] = {"ok": False, "error": str(e)}

    # Check memory
    try:
        MemoryEngine = _get_memory()
        if MemoryEngine:
            config = load_config(os.path.join(_brain_dir, 'config.yaml'))
            mem_cfg = config.get('memory', {})
            kb_root = mem_cfg.get('kb_root',
                os.path.join(os.path.dirname(_brain_dir), '05_组织知识库'))
            persist_dir = mem_cfg.get('persist_dir',
                os.path.join(_brain_dir, 'memory', 'chroma_db'))
            engine = MemoryEngine(kb_root, persist_dir,
                                  mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5'),
                                  mem_cfg.get('chunk_size', 1000),
                                  mem_cfg.get('top_k', 5))
            result['components']['memory'] = engine.status()
        else:
            result['components']['memory'] = {"ok": False, "docs": 0}
    except Exception as e:
        result['components']['memory'] = {
            "ok": False, "docs": 0, "error": str(e),
        }

    # Check workspace
    try:
        Workspace = _get_workspace_cls()
        if Workspace:
            config = load_config(os.path.join(_brain_dir, 'config.yaml'))
            ws_cfg = config.get('workspace', {})
            db_path = ws_cfg.get('db_path',
                os.path.join(_brain_dir, 'memory', 'workspace.db'))
            ws = Workspace(db_path)
            result['components']['workspace'] = ws.status()
        else:
            result['components']['workspace'] = {"ok": False, "keys": 0}
    except Exception as e:
        result['components']['workspace'] = {
            "ok": False, "keys": 0, "error": str(e),
        }

    # Check audit (Phase 3)
    try:
        AuditEngine = _get_audit_engine()
        if AuditEngine:
            config = load_config(os.path.join(_brain_dir, 'config.yaml'))
            audit_cfg = config.get('audit', {})
            db_path = audit_cfg.get('db_path',
                os.path.join(_brain_dir, 'audit', 'audit.db'))
            engine = AuditEngine(db_path)
            result['components']['audit'] = engine.status()
        else:
            result['components']['audit'] = {"ok": False, "total_logs": 0, "db_size_kb": 0}
    except Exception as e:
        result['components']['audit'] = {
            "ok": False, "total_logs": 0, "db_size_kb": 0, "error": str(e),
        }

    # Check self_heal (Phase 4)
    try:
        SelfHeal = _get_self_heal()
        if SelfHeal:
            config = load_config(os.path.join(_brain_dir, 'config.yaml'))
            sh = SelfHeal(config)
            health = sh.health_check()
            result['components']['self_heal'] = {
                "ok": health["overall_status"] == "ok",
                "overall_status": health["overall_status"],
                "degrade_level": health["degrade_level"],
                "degrade_name": health["degrade_name"],
                "summary": health["summary"],
            }
        else:
            result['components']['self_heal'] = {"ok": False, "error": "not importable"}
    except Exception as e:
        result['components']['self_heal'] = {"ok": False, "error": str(e)}

    try:
        from rule_engine import is_rules_changed
        result['rules_changed'] = is_rules_changed()
    except Exception:
        result['rules_changed'] = False

    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_rule_validate(args):
    """Validate all rule YAML files against meta_rules standard."""
    engine = get_engine()
    result = engine.validate_rules()
    print(json.dumps(result, ensure_ascii=True, indent=2))


# ── KB commands ───────────────────────────────────────────

def cmd_kb_search(args):
    try:
        validate_input(args.query, "query", max_len=1000)
    except ValueError as e:
        print(json.dumps({"error": str(e), "results": [], "query": getattr(args, 'query', ''), "total": 0}, ensure_ascii=True, indent=2))
        return
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    mem_cfg = config.get('memory', {})
    kb_root = mem_cfg.get('kb_root',
        os.path.join(os.path.dirname(_brain_dir), '05_组织知识库'))
    persist_dir = mem_cfg.get('persist_dir',
        os.path.join(_brain_dir, 'memory', 'chroma_db'))
    model_name = mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5')
    chunk_size = mem_cfg.get('chunk_size', 1000)
    top_k = mem_cfg.get('top_k', 5)

    MemoryEngine = _get_memory()
    if MemoryEngine is None:
        print(json.dumps({
            "error": "Memory engine not available",
            "results": [], "query": args.query, "total": 0,
        }, ensure_ascii=True, indent=2))
        return

    try:
        engine = MemoryEngine(kb_root, persist_dir, model_name, chunk_size, top_k)
        result = engine.search(args.query, args.top_k if hasattr(args, 'top_k') and args.top_k else top_k)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "results": [], "query": args.query, "total": 0,
        }, ensure_ascii=True, indent=2))


def cmd_kb_rebuild(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    mem_cfg = config.get('memory', {})
    kb_root = mem_cfg.get('kb_root',
        os.path.join(os.path.dirname(_brain_dir), '05_组织知识库'))
    persist_dir = mem_cfg.get('persist_dir',
        os.path.join(_brain_dir, 'memory', 'chroma_db'))
    model_name = mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5')
    chunk_size = mem_cfg.get('chunk_size', 1000)
    top_k = mem_cfg.get('top_k', 5)

    MemoryEngine = _get_memory()
    if MemoryEngine is None:
        print(json.dumps({"error": "Memory engine not available"}, ensure_ascii=True))
        return

    engine = MemoryEngine(kb_root, persist_dir, model_name, chunk_size, top_k)
    engine.rebuild()
    print(json.dumps(engine.status(), ensure_ascii=True, indent=2))


def cmd_kb_status(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    mem_cfg = config.get('memory', {})
    kb_root = mem_cfg.get('kb_root',
        os.path.join(os.path.dirname(_brain_dir), '05_组织知识库'))
    persist_dir = mem_cfg.get('persist_dir',
        os.path.join(_brain_dir, 'memory', 'chroma_db'))
    model_name = mem_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5')
    chunk_size = mem_cfg.get('chunk_size', 1000)
    top_k = mem_cfg.get('top_k', 5)

    MemoryEngine = _get_memory()
    if MemoryEngine is None:
        print(json.dumps({"error": "Memory engine not available"}, ensure_ascii=True))
        return

    engine = MemoryEngine(kb_root, persist_dir, model_name, chunk_size, top_k)
    print(json.dumps(engine.status(), ensure_ascii=True, indent=2))


# ── Memory commands ───────────────────────────────────────

def cmd_memory_set(args):
    try:
        validate_input(args.key, "key", max_len=256)
        validate_input(args.value, "value", max_len=10000, allow_shell_chars=True)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True, indent=2))
        return
    Workspace = _get_workspace_cls()
    if Workspace is None:
        print(json.dumps({"ok": False, "error": "Workspace not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    ws_cfg = config.get('workspace', {})
    db_path = ws_cfg.get('db_path',
        os.path.join(_brain_dir, 'memory', 'workspace.db'))
    default_ttl = ws_cfg.get('default_ttl', 3600)

    ws = Workspace(db_path)
    ws.set(args.key, args.value, args.ttl if args.ttl else default_ttl)
    print(json.dumps({"ok": True, "key": args.key}, ensure_ascii=True))


def cmd_memory_get(args):
    try:
        validate_input(args.key, "key", max_len=256)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True, indent=2))
        return
    Workspace = _get_workspace_cls()
    if Workspace is None:
        print(json.dumps({"ok": False, "error": "Workspace not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    ws_cfg = config.get('workspace', {})
    db_path = ws_cfg.get('db_path',
        os.path.join(_brain_dir, 'memory', 'workspace.db'))

    ws = Workspace(db_path)
    value = ws.get(args.key)
    if value is None:
        print(json.dumps({"ok": False, "key": args.key, "value": None, "reason": "not found or expired"}, ensure_ascii=True))
    else:
        print(json.dumps({"ok": True, "key": args.key, "value": value}, ensure_ascii=True))


def cmd_memory_list(args):
    Workspace = _get_workspace_cls()
    if Workspace is None:
        print(json.dumps({"ok": False, "error": "Workspace not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    ws_cfg = config.get('workspace', {})
    db_path = ws_cfg.get('db_path',
        os.path.join(_brain_dir, 'memory', 'workspace.db'))

    ws = Workspace(db_path)
    keys = ws.list_keys()
    print(json.dumps({"ok": True, "keys": keys, "count": len(keys)}, ensure_ascii=True))


# ── Audit commands (Phase 3) ──────────────────────────────

def cmd_audit_log(args):
    """brain audit log [--since YYYY-MM-DD] [--action write|read] [--limit N]"""
    AuditEngine = _get_audit_engine()
    if AuditEngine is None:
        print(json.dumps({"error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))

    engine = AuditEngine(db_path)
    logs = engine.query(
        since=getattr(args, 'since', None),
        action=getattr(args, 'action', None),
        limit=getattr(args, 'limit', 100),
    )
    result = {"logs": logs, "count": len(logs)}
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_audit_check(args):
    """brain audit check <target_path>"""
    AuditEngine = _get_audit_engine()
    if AuditEngine is None:
        print(json.dumps({"error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))

    engine = AuditEngine(db_path)
    history = engine.file_history(args.target_path)
    result = {"file": args.target_path, "history": history, "versions": len(history)}
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_audit_stats(args):
    """brain audit stats [--since YYYY-MM-DD]"""
    AuditEngine = _get_audit_engine()
    if AuditEngine is None:
        print(json.dumps({"error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))

    engine = AuditEngine(db_path)
    stats = engine.stats(since=getattr(args, 'since', None))
    print(json.dumps(stats, ensure_ascii=True, indent=2))


# ── Safe-write command (Phase 3) ──────────────────────────

def cmd_safe_write(args):
    """brain safe-write <path> <content> [--operator <name>]"""
    safe_write_fn = _get_safe_write()
    if safe_write_fn is None:
        print(json.dumps({"ok": False, "error": "Audit engine not available"}, ensure_ascii=True))
        return

    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    audit_cfg = config.get('audit', {})
    db_path = audit_cfg.get('db_path',
        os.path.join(_brain_dir, 'audit', 'audit.db'))
    conflict_window = audit_cfg.get('conflict_window_seconds', 30)

    result = safe_write_fn(
        path=args.path,
        content=args.content,
        operator=getattr(args, 'operator', 'codex'),
        db_path=db_path,
        conflict_window=conflict_window,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_rule_validate(args):
    """Validate all rule YAML files against meta_rules standard."""
    engine = get_engine()
    result = engine.validate_rules()
    print(json.dumps(result, ensure_ascii=True, indent=2))


# ── Health (Phase 4) ──

def cmd_health_check(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({'error': 'SelfHeal not available'}, ensure_ascii=True))
        return
    sh = SelfHeal(config)
    dims = args.dimensions.split(',') if getattr(args, 'dimensions', None) else None
    result = sh.health_check(dimensions=dims)
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_health_repair(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({'error': 'SelfHeal not available'}, ensure_ascii=True))
        return
    sh = SelfHeal(config)
    result = sh.auto_repair(args.component)
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_health_degrade(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({'error': 'SelfHeal not available'}, ensure_ascii=True))
        return
    sh = SelfHeal(config)
    result = sh.degrade(args.level)
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_health_reset(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({'error': 'SelfHeal not available'}, ensure_ascii=True))
        return
    sh = SelfHeal(config)
    result = sh.reset_degrade()
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_health_status(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({'error': 'SelfHeal not available'}, ensure_ascii=True))
        return
    sh = SelfHeal(config)
    result = sh.get_degrade_level()
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_rule_validate(args):
    """Validate all rule YAML files against meta_rules standard."""
    engine = get_engine()
    result = engine.validate_rules()
    print(json.dumps(result, ensure_ascii=True, indent=2))


# ── Chaos (Phase 4) ──

def cmd_regression(args):
    """P0-2: Run regression test suite and report results."""
    import subprocess, sys as _sys
    brain_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(brain_dir)
    print("=" * 60)
    print("  P0-2 regression test suite")
    print("=" * 60)
    result = subprocess.run(
        [_sys.executable, "-m", "unittest", "brain.test_brain", "-v"],
        capture_output=False, timeout=120,
        cwd=root_dir,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    print("=" * 60)
    if result.returncode == 0:
        print("  ALL TESTS PASSED")
    else:
        print("  TESTS FAILED (exit code: {})".format(result.returncode))
    print("=" * 60)
    return result.returncode

def cmd_chaos_test(args):
    config = load_config(os.path.join(_brain_dir, 'config.yaml'))
    SelfHeal = _get_self_heal()
    if SelfHeal is None:
        print(json.dumps({'error': 'SelfHeal not available'}, ensure_ascii=True))
        return
    sh = SelfHeal(config)
    result = sh.chaos_test()
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_rule_validate(args):
    """Validate all rule YAML files against meta_rules standard."""
    engine = get_engine()
    result = engine.validate_rules()
    print(json.dumps(result, ensure_ascii=True, indent=2))


# ── Status ────────────────────────────────────────────────


def cmd_rollback(args):
    fallback_path = os.path.join(_brain_dir, 'fallback.md')
    result = {
        "brain_ok": False,
        "instruction": "大脑不可用。请读取 fallback.md 兜底规则。",
        "fallback_path": fallback_path,
        "fallback_rules": None,
        "return_code": 1,
    }
    if os.path.isfile(fallback_path):
        try:
            with io.open(fallback_path, 'r', encoding='utf-8') as f:
                result["fallback_rules"] = f.read()
        except Exception:
            pass
    print(json.dumps(result, ensure_ascii=True, indent=2))
    sys.exit(1)



# ── Distill (Phase 5) ────────────────────────────────────

def cmd_distill(args):
    """brain distill → 扫描规则YAML,统计triggers权重,生成Top 10蒸馏规则"""
    import datetime
    rules_dir = os.path.join(_brain_dir, 'rules')
    output_path = os.path.join(_brain_dir, 'distilled_agents.md')

    all_rules = []
    for root, dirs, files in os.walk(rules_dir):
        for f in files:
            if f.endswith('.yaml'):
                filepath = os.path.join(root, f)
                try:
                    with io.open(filepath, 'r', encoding='utf-8') as fh:
                        data = yaml.safe_load(fh)
                    if data and 'rules' in data:
                        for rule in data['rules']:
                            triggers = rule.get('triggers', [])
                            all_rules.append({
                                'id': rule.get('id', '?'),
                                'name': rule.get('name', '?'),
                                'weight': len(triggers) if isinstance(triggers, list) else 0,
                                'action': rule.get('action', ''),
                                'level': rule.get('level', '?'),
                            })
                except Exception as e:
                    print(f"skip {filepath}: {e}", file=sys.stderr)

    all_rules.sort(key=lambda r: r['weight'], reverse=True)
    top10 = all_rules[:10]

    if not top10:
        print(json.dumps({"ok": False, "error": "no rules found"}, ensure_ascii=True))
        return

    today = datetime.date.today().isoformat()
    lines = [
        "# 蒸馏规则 · Top 10 高频规则",
        f"> 由 brain distill 自动生成 · {today}",
        "",
    ]
    for i, rule in enumerate(top10, 1):
        action_short = rule['action'][:60] + ('...' if len(rule['action']) > 60 else '')
        lines.append(f"{i}. **{rule['id']}**  {rule['name']}: {action_short}")
        lines.append(f"   触发权重: {rule['weight']} | 级别: {rule['level']}")
        lines.append("")

    md_content = '\n'.join(lines) + '\n'
    try:
        with io.open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        result = {
            "ok": True,
            "output": output_path,
            "total_rules_scanned": len(all_rules),
            "top10": [{"id": r['id'], "name": r['name'], "weight": r['weight']} for r in top10],
        }
    except Exception as e:
        result = {"ok": False, "error": str(e)}

    print(json.dumps(result, ensure_ascii=True, indent=2))



# -- Phase 6: Cost commands --


# -- Digest: knowledge internalization engine --

def cmd_digest(args):
    """brain digest scan|report|ack|stats|json"""
    from digest.digest import scan, pending, ack, report, stats, json_report
    if args.digest_command == "scan":
        since = getattr(args, "since", None)
        results = scan(since=since)
        print(f"scan done: {len(results)} changed")
        for r in results[:20]:
            status_tag = "[NEW]" if r.get("status") == "new" else "[CHG]"
            p = r.get("priority", 0)
            path = r.get("path", "")
            print(f"  P{p} {status_tag} {path}")
            s = r.get("summary", "")
            if s:
                print(f"      {s[:80]}")
        if len(results) > 20:
            print(f"  ... {len(results)} total, use digest report")
    elif args.digest_command == "ack":
        ack()
        print("All pending acknowledged.")
    elif args.digest_command == "report":
        top = getattr(args, "top", None)
        print(report(top=top))
    elif args.digest_command == "stats":
        st = stats()
        fmt = "total: {} pending: {} accepted: {} archived: {}"
        print(fmt.format(st["total"], st["pending"], st["accepted"], st["archived"]))
    elif args.digest_command == "json":
        top = getattr(args, "top", None)
        import json as _json
        print(_json.dumps(json_report(top=top), ensure_ascii=False, indent=2))
    else:
        print(report())

def cmd_cost_report(args):
    """brain cost report"""
    import datetime
    storage_items = {}
    storage_total_kb = 0
    patterns = {
        "audit.db": os.path.join(_brain_dir, "audit", "audit.db"),
        "workspace.db": os.path.join(_brain_dir, "memory", "workspace.db"),
        "fallback_index.pkl": os.path.join(_brain_dir, "memory", "chroma_db", "fallback_index.pkl"),
        "fallback_meta.json": os.path.join(_brain_dir, "memory", "chroma_db", "fallback_meta.json"),
    }
    for name, path in patterns.items():
        if os.path.isfile(path):
            size_kb = round(os.path.getsize(path) / 1024, 1)
            storage_items[name] = size_kb
            storage_total_kb += size_kb
    audit_stats = {"total_ops": 0, "writes": 0, "reads": 0, "conflicts": 0, "db_size_kb": 0}
    first_date = None
    last_date = None
    daily_avg = 0
    days_span = 0
    AuditEngine = _get_audit_engine()
    if AuditEngine:
        try:
            config = load_config(os.path.join(_brain_dir, "config.yaml"))
            audit_cfg = config.get("audit", {})
            db_path = audit_cfg.get("db_path", os.path.join(_brain_dir, "audit", "audit.db"))
            engine = AuditEngine(db_path)
            audit_stats = engine.stats()
            logs = engine.query(limit=10000)
            if logs:
                timestamps = [l.get("timestamp", "") for l in logs if l.get("timestamp")]
                if timestamps:
                    timestamps.sort()
                    first_date = timestamps[0][:10]
                    last_date = timestamps[-1][:10]
                    try:
                        d1 = datetime.datetime.strptime(first_date, "%Y-%m-%d")
                        d2 = datetime.datetime.strptime(last_date, "%Y-%m-%d")
                        days_span = max((d2 - d1).days, 1)
                        daily_avg = round(audit_stats["total_ops"] / days_span, 1)
                    except Exception:
                        pass
        except Exception as e:
            audit_stats["error"] = str(e)
    _NA = chr(39)+chr(78)+chr(47)+chr(65)+chr(39)
    result = {
        "audit": {
            "total_logs": audit_stats["total_ops"],
            "writes": audit_stats["writes"],
            "reads": audit_stats["reads"],
            "conflicts": audit_stats["conflicts"],
            "date_range": f"{first_date or _NA} ~ {last_date or _NA}",
            "days_span": days_span,
            "daily_avg_ops": daily_avg,
        },
        "storage": {
            "items": storage_items,
            "total_kb": round(storage_total_kb, 1),
            "total_mb": round(storage_total_kb / 1024, 2),
        },
    }
    print(json.dumps(result, ensure_ascii=True, indent=2))


def cmd_rule_validate(args):
    """Validate all rule YAML files against meta_rules standard."""
    engine = get_engine()
    result = engine.validate_rules()
    print(json.dumps(result, ensure_ascii=True, indent=2))


# -- Phase 6: Self-evolve commands --

def cmd_evolve_analyze(args):
    """brain evolve analyze"""
    try:
        from self_evolve import SelfEvolve
        engine = SelfEvolve()
        result = engine.analyze()
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except ImportError as e:
        print(json.dumps({"ok": False, "error": f"evolve unavailable: {e}"}, ensure_ascii=True))


def cmd_evolve_suggest(args):
    """brain evolve suggest"""
    try:
        from self_evolve import SelfEvolve
        engine = SelfEvolve()
        result = engine.suggest()
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except ImportError as e:
        print(json.dumps({"ok": False, "error": f"evolve unavailable: {e}"}, ensure_ascii=True))


# ── Main ──────────────────────────────────────────────────

def main():
    # Fix Windows GBK encoding issue — force UTF-8 for emoji/Unicode output
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        prog='brain',
        description='启元智能 · 外部大脑规则引擎 CLI (Phase 4)',
    )
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # brain rule check <action>
    p_rule = subparsers.add_parser('rule', help='规则操作')
    rule_subs = p_rule.add_subparsers(dest='rule_command')

    rc = rule_subs.add_parser('check', help='匹配规则')
    rc.add_argument('action', type=str, help='操作描述')
    rc.add_argument('--include-draft', action='store_true', help='包含draft状态规则')

    rcl = rule_subs.add_parser('classify', help='判定P0/P1/P2级别')
    rcl.add_argument('action', type=str, help='操作描述')

    rv = rule_subs.add_parser('validate', help='校验所有规则元数据')

    # brain kb <subcommand>
    p_kb = subparsers.add_parser('kb', help='知识库检索')
    kb_subs = p_kb.add_subparsers(dest='kb_command')

    kbs = kb_subs.add_parser('search', help='向量检索知识库')
    kbs.add_argument('query', type=str, help='检索内容')
    kbs.add_argument('--top-k', type=int, default=None, help='返回数量 (默认5)')

    kb_subs.add_parser('rebuild', help='重建向量索引')
    kb_subs.add_parser('status', help='索引状态')

    # brain memory <subcommand>
    p_mem = subparsers.add_parser('memory', help='短期记忆工作区')
    mem_subs = p_mem.add_subparsers(dest='mem_command')

    mems = mem_subs.add_parser('set', help='写入键值对')
    mems.add_argument('key', type=str, help='键名')
    mems.add_argument('value', type=str, help='值')
    mems.add_argument('--ttl', type=int, default=None, help='过期秒数 (默认3600)')

    memg = mem_subs.add_parser('get', help='读取键值')
    memg.add_argument('key', type=str, help='键名')

    mem_subs.add_parser('list', help='列出所有有效键')

    # brain audit <subcommand> (Phase 3)
    p_audit = subparsers.add_parser('audit', help='备案审计')
    audit_subs = p_audit.add_subparsers(dest='audit_command')

    al = audit_subs.add_parser('log', help='查询审计日志')
    al.add_argument('--since', type=str, default=None, help='起始日期 (YYYY-MM-DD)')
    al.add_argument('--action', type=str, default=None, choices=['write', 'read'], help='操作类型')
    al.add_argument('--limit', type=int, default=100, help='返回数量 (默认100)')

    ac = audit_subs.add_parser('check', help='查询文件版本历史')
    ac.add_argument('target_path', type=str, help='文件路径')

    ast = audit_subs.add_parser('stats', help='审计统计')
    ast.add_argument('--since', type=str, default=None, help='起始日期 (YYYY-MM-DD)')

    # brain safe-write <path> <content> (Phase 3)
    p_sw = subparsers.add_parser('safe-write', help='安全写入文件')
    p_sw.add_argument('path', type=str, help='目标文件路径')
    p_sw.add_argument('content', type=str, help='写入内容')
    p_sw.add_argument('--operator', type=str, default='codex', help='操作者标识')

    # brain health <subcommand> (Phase 4 self-heal)
    # brain chaos <subcommand> (Phase 4)
    p_chaos = subparsers.add_parser('chaos', help='混沌测试')
    chaos_subs = p_chaos.add_subparsers(dest='chaos_command')
    chaos_subs.add_parser('test', help='故障注入+自愈验证')

    # brain regression (P0-2)
    subparsers.add_parser('regression', help='run regression test suite')

    # brain status
    sp_status = subparsers.add_parser('status', help='大脑状态')
    sp_status.add_argument('--fast', action='store_true', help='快速模式(<2秒)')

    # brain rollback
    subparsers.add_parser('rollback', help='降级兜底')
    # brain distill (Phase 5)
    subparsers.add_parser('distill', help='知识蒸馏: 生成Top 10高频规则')

    # brain digest (knowledge internalization engine)
    p_digest = subparsers.add_parser("digest", help="knowledge internalization engine")
    digest_subs = p_digest.add_subparsers(dest="digest_command")
    p_digest_scan = digest_subs.add_parser("scan", help="scan KB for new/changed docs")
    p_digest_scan.add_argument("--since", help="time range: 7d/24h/1w/2026-06-01", default=None)
    p_digest_report = digest_subs.add_parser("report", help="view pending digest notifications")
    p_digest_report.add_argument("--top", type=int, help="show top N only", default=None)
    digest_subs.add_parser("ack", help="acknowledge all pending")
    digest_subs.add_parser("stats", help="digest statistics")
    p_digest_json = digest_subs.add_parser("json", help="JSON format pending notifications")
    p_digest_json.add_argument("--top", type=int, help="show top N only", default=None)

    # brain cost <subcommand> (Phase 6)
    p_cost = subparsers.add_parser('cost', help='cost report')
    cost_subs = p_cost.add_subparsers(dest='cost_command')
    cost_subs.add_parser('report', help='cost report')

    # brain evolve <subcommand> (Phase 6)
    p_evolve = subparsers.add_parser('evolve', help='self-evolve engine')
    evolve_subs = p_evolve.add_subparsers(dest='evolve_command')
    evolve_subs.add_parser('analyze', help='scan audit logs')
    evolve_subs.add_parser('suggest', help='generate suggested rules')


    p_health = subparsers.add_parser('health', help='自愈系统')
    health_subs = p_health.add_subparsers(dest='health_command')

    health_subs.add_parser('check', help='5维度健康检查')

    hrep = health_subs.add_parser('repair', help='自动修复组件')
    hrep.add_argument('component', type=str, help='组件名: rule_engine, memory, audit, filesystem')

    hdeg = health_subs.add_parser('degrade', help='分级降级')
    hdeg.add_argument('level', type=int, help='降级级别: 0(全功能) 1(记忆降级) 2(规则降级) 3(全降级)')

    # P0-4: Start RuleWatcher background thread for live rule-change monitoring
    try:
        from self_heal import RuleWatcher
        rules_dir = os.path.join(_brain_dir, 'rules')
        _watcher = RuleWatcher(rules_dir)
        _watcher.start()
    except Exception:
        pass

    # Task management (cross-conversation)
    p_task = subparsers.add_parser("task", help="跨对话任务管理")
    task_subs = p_task.add_subparsers(dest="task_command")
    tadd = task_subs.add_parser("add", help="添加任务")
    tadd.add_argument("--title", type=str, required=True, help="任务描述")
    tadd.add_argument("--priority", type=str, default="P2", choices=["P0","P1","P2"], help="优先级")
    tlist = task_subs.add_parser("list", help="列出任务")
    tlist.add_argument("--all", action="store_true", help="显示全部（含已完成）")
    tlist.add_argument("--priority", type=str, choices=["P0","P1","P2"], help="按优先级筛选")
    tdone = task_subs.add_parser("done", help="标记完成")
    tdone.add_argument("task_id", type=str, help="任务ID")
    task_subs.add_parser("recurring", help="查看定期事项")

    args = parser.parse_args()

    if args.command == 'rule':
        if args.rule_command == 'check':
            cmd_rule_check(args)
        elif args.rule_command == 'classify':
            cmd_rule_classify(args)
        elif args.rule_command == 'validate':
            cmd_rule_validate(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == 'kb':
        if args.kb_command == 'search':
            cmd_kb_search(args)
        elif args.kb_command == 'rebuild':
            cmd_kb_rebuild(args)
        elif args.kb_command == 'status':
            cmd_kb_status(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == 'memory':
        if args.mem_command == 'set':
            cmd_memory_set(args)
        elif args.mem_command == 'get':
            cmd_memory_get(args)
        elif args.mem_command == 'list':
            cmd_memory_list(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == 'audit':
        if args.audit_command == 'log':
            cmd_audit_log(args)
        elif args.audit_command == 'check':
            cmd_audit_check(args)
        elif args.audit_command == 'stats':
            cmd_audit_stats(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == "task":
        if args.task_command == "add":
            cmd_task_add(args)
        elif args.task_command == "list":
            cmd_task_list(args)
        elif args.task_command == "done":
            cmd_task_done(args)
        elif args.task_command == "recurring":
            cmd_task_recurring(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == 'safe-write':
        cmd_safe_write(args)
    elif args.command == 'chaos':
        if args.chaos_command == 'test':
            cmd_chaos_test(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == 'regression':
        sys.exit(cmd_regression(args))
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'rollback':
        cmd_rollback(args)
    elif args.command == 'distill':
        cmd_distill(args)
    elif args.command == "digest":
        if args.digest_command in ("scan", "ack", "report", "stats", "json"):
            cmd_digest(args)
        else:
            print("usage: brain digest (scan|report|ack|stats|json)")
    elif args.command == 'cost':
        if args.cost_command == 'report':
            cmd_cost_report(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == 'evolve':
        if args.evolve_command == 'analyze':
            cmd_evolve_analyze(args)
        elif args.evolve_command == 'suggest':
            cmd_evolve_suggest(args)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == 'health':
        if args.health_command == 'check':
            cmd_health_check(args)
        elif args.health_command == 'repair':
            cmd_health_repair(args)
        elif args.health_command == 'degrade':
            cmd_health_degrade(args)
        else:
            parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
