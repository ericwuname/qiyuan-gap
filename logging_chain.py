# -*- coding: utf-8 -*-
"""启元智能 · 日志监控数据链 · Logging Chain

端到端的执行节点追踪、异常埋点、调用链可视化。

模块标识:
  RULES     - 规则引擎
  MEMORY    - 记忆引擎
  WORKSPACE - 工作空间
  AUDIT     - 审计引擎
  SELFHEAL  - 自愈系统
  CLI       - CLI入口
  DASHBOARD - 仪表盘

日志级别:
  INFO  - 正常执行
  WARN  - 异常可恢复
  ERROR - 功能不可用

Write targets:
  - JSONL file: brain/_logs/YYYY-MM-DD.jsonl   (每天一个)
  - SQLite:      brain/audit/audit.db          (结构化记录)
"""

import io, os, sys, json, time, uuid, threading, traceback
from datetime import datetime
from typing import Dict, Optional, Any

_brain_dir = os.path.dirname(os.path.abspath(__file__))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)

_logs_dir = os.path.join(_brain_dir, "_logs")

# ── Module identifiers ──────────────────────────────────────
MODULES = ("RULES", "MEMORY", "WORKSPACE", "AUDIT", "SELFHEAL", "CLI", "DASHBOARD")

# ── Log levels ──────────────────────────────────────────────
LEVELS = ("INFO", "WARN", "ERROR")

# ── Thread-safe write lock ──────────────────────────────────
_write_lock = threading.Lock()


def _ensure_logs_dir():
    """Ensure brain/_logs/ exists."""
    os.makedirs(_logs_dir, exist_ok=True)


def _today_jsonl_path() -> str:
    """Return path to today's JSONL log file."""
    _ensure_logs_dir()
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(_logs_dir, f"{today}.jsonl")


def _jsonl_write(entry: Dict):
    """Append a single JSON line to today's JSONL file (thread-safe)."""
    try:
        with _write_lock:
            _ensure_logs_dir()
            path = _today_jsonl_path()
            line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
            with io.open(path, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        # JSONL write failure should not crash the caller
        pass


def _audit_db_write(module: str, level: str, message: str, request_id: str,
                    extra: Dict = None):
    """Write structured log entry to audit.db (best-effort)."""
    try:
        from audit.audit_engine import AuditEngine
        config_path = os.path.join(_brain_dir, "config.yaml")
        import yaml
        with io.open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        audit_cfg = cfg.get("audit", {})
        db_path = audit_cfg.get(
            "db_path", os.path.join(_brain_dir, "audit", "audit.db"))
        engine = AuditEngine(db_path)

        target = f"log://{module}"
        operator = "logging_chain"
        content_hash = request_id
        result = level.lower()
        detail_parts = [f"[{module}][{level}] {message}"]
        if extra:
            detail_parts.append(json.dumps(extra, ensure_ascii=False, default=str))
        details = " | ".join(detail_parts)

        engine.log_write(
            target_path=target,
            operator=operator,
            content_hash=content_hash,
            result=result,
            details=details,
        )
    except Exception:
        pass


def generate_request_id() -> str:
    """Generate a UUID-based request ID for call chain tracing."""
    return str(uuid.uuid4())[:8]


# ── Public API ──────────────────────────────────────────────

def log(module: str, level: str, message: str, request_id: str = None,
        **extra) -> str:
    """Write a log entry to both JSONL file and audit.db.

    Args:
        module:     One of RULES/MEMORY/WORKSPACE/AUDIT/SELFHEAL/CLI/DASHBOARD
        level:      One of INFO/WARN/ERROR
        message:    Human-readable message
        request_id: Optional UUID for call chain tracing (auto-generated if None)
        **extra:    Additional key-value pairs stored in the log entry

    Returns:
        The request_id used for this entry.

    Raises:
        ValueError if module or level is invalid.
    """
    if module.upper() not in MODULES:
        raise ValueError(
            f"Invalid module: {module}. Must be one of {MODULES}")
    if level.upper() not in LEVELS:
        raise ValueError(
            f"Invalid level: {level}. Must be one of {LEVELS}")

    module = module.upper()
    level = level.upper()

    if request_id is None:
        request_id = generate_request_id()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = {
        "timestamp": timestamp,
        "module": module,
        "level": level,
        "message": message,
        "request_id": request_id,
    }
    if extra:
        entry["extra"] = extra

    # Write to JSONL (primary)
    _jsonl_write(entry)

    # Write to audit.db (secondary, best-effort)
    _audit_db_write(module, level, message, request_id, extra)

    return request_id


def log_error(module: str, message: str, exc_info: bool = False,
              request_id: str = None, **extra) -> str:
    """Convenience: log an ERROR with optional exception traceback."""
    if exc_info:
        tb = traceback.format_exc()
        extra["traceback"] = tb
        if tb and tb != "NoneType: None\n":
            message = f"{message} | {tb.split(chr(10))[-2].strip()}"
    return log(module, "ERROR", message, request_id, **extra)


def log_warn(module: str, message: str, request_id: str = None,
             **extra) -> str:
    """Convenience: log a WARN."""
    return log(module, "WARN", message, request_id, **extra)


def log_info(module: str, message: str, request_id: str = None,
             **extra) -> str:
    """Convenience: log an INFO."""
    return log(module, "INFO", message, request_id, **extra)


# ── Query API ───────────────────────────────────────────────

def _read_jsonl_lines(path: str) -> list:
    """Read and parse all JSONL lines from a file."""
    entries = []
    if not os.path.isfile(path):
        return entries
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return entries


def tail(n: int = 20) -> list:
    """Return the last N log entries from today's JSONL."""
    path = _today_jsonl_path()
    entries = _read_jsonl_lines(path)
    return entries[-n:] if n > 0 else entries


def errors(since: str = None) -> list:
    """Return all ERROR-level entries.

    Args:
        since: Optional date filter in YYYY-MM-DD format.
               If omitted, scans today's file only.
    """
    if since:
        path = os.path.join(_logs_dir, f"{since}.jsonl")
        entries = _read_jsonl_lines(path)
    else:
        path = _today_jsonl_path()
        entries = _read_jsonl_lines(path)
    return [e for e in entries if e.get("level") == "ERROR"]


def stats(since: str = None) -> Dict:
    """Return aggregated log statistics.

    Args:
        since: Optional date filter in YYYY-MM-DD format.
               If omitted, scans today's file only.

    Returns:
        {total, by_level: {INFO: N, WARN: N, ERROR: N},
         by_module: {RULES: N, ...},
         by_hour: {"00": N, ...},
         date: str, file_path: str}
    """
    if since:
        path = os.path.join(_logs_dir, f"{since}.jsonl")
    else:
        path = _today_jsonl_path()

    entries = _read_jsonl_lines(path)

    result = {
        "total": len(entries),
        "by_level": {"INFO": 0, "WARN": 0, "ERROR": 0},
        "by_module": {m: 0 for m in MODULES},
        "by_hour": {},
        "date": since or datetime.now().strftime("%Y-%m-%d"),
        "file_path": path,
    }

    for e in entries:
        level = e.get("level", "UNKNOWN")
        if level in result["by_level"]:
            result["by_level"][level] += 1

        mod = e.get("module", "UNKNOWN")
        if mod in result["by_module"]:
            result["by_module"][mod] += 1

        ts = e.get("timestamp", "")
        if ts and len(ts) >= 13:
            hour = ts[11:13]
            result["by_hour"][hour] = result["by_hour"].get(hour, 0) + 1

    return result


def trace(request_id: str, since: str = None) -> list:
    """Trace a complete call chain by request_id.

    Args:
        request_id: The UUID request_id to trace.
        since: Optional date filter. If omitted, scans today.

    Returns:
        List of log entries with matching request_id, sorted by timestamp.
    """
    if since:
        path = os.path.join(_logs_dir, f"{since}.jsonl")
        entries = _read_jsonl_lines(path)
    else:
        path = _today_jsonl_path()
        entries = _read_jsonl_lines(path)

    chain = [e for e in entries if e.get("request_id") == request_id]
    chain.sort(key=lambda e: e.get("timestamp", ""))
    return chain


def list_dates() -> list:
    """List all available JSONL log files (dates)."""
    _ensure_logs_dir()
    dates = []
    try:
        for f in sorted(os.listdir(_logs_dir)):
            if f.endswith(".jsonl"):
                dates.append(f.replace(".jsonl", ""))
    except Exception:
        pass
    return dates
