# -*- coding: utf-8 -*-
"""每周规则建议审核脚本"""
import io, os, sys
from datetime import datetime

BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
SUGGESTED_DIR = os.path.join(BRAIN_DIR, "rules", "_suggested")
REPORT_DIR = os.path.join(BRAIN_DIR, "reports", "weekly")

def scan():
    if not os.path.exists(SUGGESTED_DIR):
        return []
    files = sorted([f for f in os.listdir(SUGGESTED_DIR) if f.endswith(".yaml")])
    results = []
    for fn in files:
        fp = os.path.join(SUGGESTED_DIR, fn)
        try:
            with io.open(fp, "r", encoding="utf-8") as f:
                content = f.read()
            stat = os.stat(fp)
            results.append({
                "file": fn,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "preview": content[:200]
            })
        except Exception as e:
            results.append({"file": fn, "error": str(e)})
    return results

def generate_report(results):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# 规则建议周审报告")
    lines.append("")
    lines.append(f"> 生成: {now} | 待审核: {len(results)} 条")
    lines.append("")
    lines.append("| # | 文件名 | 大小 | 修改时间 | 操作 |")
    lines.append("|:--|:--|:--|:--|:--|")
    for i, r in enumerate(results, 1):
        fn = r.get("file", "?").replace(".yaml", "")[:60]
        size = r.get("size", 0)
        size_str = f"{size/1024:.1f}KB" if size else "?"
        mtime = r.get("mtime", "?")
        lines.append(f"| {i} | {fn} | {size_str} | {mtime} | 待审核 |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 审核操作")
    lines.append("")
    lines.append("- 采纳: python brain/cli.py rule approve ID")
    lines.append("- 驳回: python brain/cli.py rule reject ID")
    lines.append("- 暂缓: 不操作，保留在 _suggested/")
    return "\n".join(lines)

def save_report(text):
    os.makedirs(REPORT_DIR, exist_ok=True)
    fn = f"suggested_review_{datetime.now().strftime('%Y%m%d')}.md"
    fp = os.path.join(REPORT_DIR, fn)
    with io.open(fp, "w", encoding="utf-8") as f:
        f.write(text)
    return fp

if __name__ == "__main__":
    print("=" * 50)
    print("  规则建议周审")
    print("=" * 50)
    results = scan()
    print(f"\n  待审核: {len(results)} 条\n")
    for r in results:
        status = "ERR" if "error" in r else " "
        print(f"  [{status}] {r.get('file', '?')[:55]}")
    report = generate_report(results)
    fp = save_report(report)
    print(f"\n  报告已保存: {os.path.relpath(fp, BRAIN_DIR)}")
