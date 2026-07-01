# -*- coding: utf-8 -*-
"""SOP编号分配器 — 防多会话并发冲突，使用跨进程文件锁。"""
import io, os, sys, json

_CTR_FILE = None

def _counter_file():
    global _CTR_FILE
    if _CTR_FILE is None:
        _CTR_FILE = os.path.join(os.path.dirname(__file__), "config", "sop_counter.json")
    return _CTR_FILE

def _read_counter():
    path = _counter_file()
    if not os.path.isfile(path):
        return {"max": 0}
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_counter(data):
    path = _counter_file()
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def next_number(title=""):
    """获取下一个唯一SOP编号，使用跨进程文件锁保证并发安全。"""
    try:
        from file_lock import FileLock
        lock_file = os.path.join(os.path.dirname(__file__), "config", ".sop_counter.lock")
        with FileLock(lock_file, timeout=10.0):
            data = _read_counter()
            data["max"] = data.get("max", 0) + 1
            if title:
                if "history" not in data:
                    data["history"] = []
                data["history"].append({"number": data["max"], "title": title})
                if len(data["history"]) > 50:
                    data["history"] = data["history"][-50:]
            _write_counter(data)
            return data["max"]
    except ImportError:
        pass
    # Fallback: no lock
    data = _read_counter()
    data["max"] = data.get("max", 0) + 1
    _write_counter(data)
    return data["max"]

if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else ""
    num = next_number(title)
    print(f"SOP-{num:03d}")