# -*- coding: utf-8 -*-
"""Knowledge Digest Engine - 知识内化引擎 (兼容层)

委托给 brain/memory/digest.py 的 DigestEngine 执行。
保留此文件以兼容现有 CLI 导入路径。
"""
import os, sys

# 确保 brain/ 在 sys.path 中
_BRAIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

from memory.digest import (
    scan, pending, ack, report, stats, json_report, DigestEngine
)

__all__ = ["scan", "pending", "ack", "report", "stats", "json_report", "DigestEngine"]

if __name__ == "__main__":
    import sys
    from memory.digest import DigestEngine
    engine = DigestEngine()
    args = sys.argv[1:]

    if "scan" in args:
        since = None
        for a in args:
            if a.startswith("--since="):
                since = a.split("=", 1)[1]
        results = engine.scan(since=since)
        print(f"扫描完成: {len(results)} 篇变更")
        for r in sorted(results, key=lambda x: -x["priority"])[:20]:
            print(f"  P{r['priority']} [{r['status']}] {r['title']}")
    elif "report" in args:
        top = None
        for a in args:
            if a.startswith("--top="):
                top = int(a.split("=", 1)[1])
        print(engine.report(top=top))
    elif "ack" in args:
        engine.ack()
        print("已确认全部待处理通知。")
    elif "stats" in args:
        s = engine.stats()
        print(f"总计: {s['total']} · 待处理: {s['pending']} · 已确认: {s['accepted']} · 已归档: {s['archived']}")
    else:
        print(engine.report())
