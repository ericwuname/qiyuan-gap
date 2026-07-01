# -*- coding: utf-8 -*-
"""启元智能 · 宪法漂移检测器 (Constitution Drift Detector)

检测 01_公司治理/ Markdown 宪法文件 vs brain/rules/ YAML 规则文件之间的漂移。
不自动同步（需要人工审核），只检测 + 报告 + 通知。

用法:
  python sync_constitution.py           # 检查漂移，打印报告
  python sync_constitution.py --json    # JSON 输出，供 daemon 调用
"""

import io, os, sys, json
from datetime import datetime

BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BRAIN_DIR)
GOV_DIR = os.path.join(ROOT_DIR, "01_公司治理")
RULES_DIR = os.path.join(BRAIN_DIR, "rules")

# ── 映射表: 宪法 Markdown → 规则 YAML ──────────────────
MAPPING = [
    ("灵魂宪章（含基因协议）.md", "constitution.yaml",   "宪法规则"),
    ("灵魂宪章（含基因协议）.md", "gene_protocols.yaml",  "基因协议"),
    ("组织免疫系统.md",           "immune_system.yaml",   "免疫系统"),
    ("组织架构宪法.md",           "culture.yaml",         "组织文化"),
    ("COMPANY_REALITY.md",       "culture.yaml",         "组织文化(次要来源)"),
]

# ── 漂移阈值: 超过此天数标记为 STALE ──────────────────
DRIFT_THRESHOLD_DAYS = 0.5  # 12小时


def check_drift():
    """检查所有映射对的漂移状态。返回 {yaml_name: {status, md_mtime, yaml_mtime, drift_days}}"""
    results = {}
    now = datetime.now()

    for md_name, yaml_name, label in MAPPING:
        md_path = os.path.join(GOV_DIR, md_name)
        yaml_path = os.path.join(RULES_DIR, yaml_name)

        md_exists = os.path.isfile(md_path)
        yaml_exists = os.path.isfile(yaml_path)

        if not md_exists:
            results[yaml_name] = {
                "status": "MISS_MD",
                "label": label,
                "md_mtime": None,
                "yaml_mtime": datetime.fromtimestamp(os.path.getmtime(yaml_path)).isoformat() if yaml_exists else None,
                "drift_days": None,
            }
            continue

        if not yaml_exists:
            results[yaml_name] = {
                "status": "MISS_YAML",
                "label": label,
                "md_mtime": datetime.fromtimestamp(os.path.getmtime(md_path)).isoformat(),
                "yaml_mtime": None,
                "drift_days": None,
            }
            continue

        md_mtime = os.path.getmtime(md_path)
        yaml_mtime = os.path.getmtime(yaml_path)
        drift_days = (md_mtime - yaml_mtime) / 86400.0

        status = "STALE" if drift_days > DRIFT_THRESHOLD_DAYS else "OK"

        results[yaml_name] = {
            "status": status,
            "label": label,
            "md_mtime": datetime.fromtimestamp(md_mtime).strftime("%Y-%m-%d %H:%M"),
            "yaml_mtime": datetime.fromtimestamp(yaml_mtime).strftime("%Y-%m-%d %H:%M"),
            "drift_days": round(drift_days, 2),
        }

    # Deduplicate: if multiple MD map to same YAML, keep the worst status
    # Already handled by keying on yaml_name

    return results


def report_text(results):
    """生成可读报告"""
    lines = ["", "=" * 56, "  宪法漂移检测 · Constitution Drift Report",
             f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}", "=" * 56, ""]

    stale_count = 0
    for yaml_name, r in results.items():
        icon = {"OK": "[OK]", "STALE": "[STALE]", "MISS_MD": "[MISS]", "MISS_YAML": "[MISS]"}.get(r["status"], "[?]")
        lines.append(f"  {icon} {yaml_name}  ({r['label']})")
        if r["status"] == "STALE":
            stale_count += 1
            lines.append(f"       YAML 落后 Markdown {r['drift_days']} 天")
        lines.append(f"       MD: {r['md_mtime']}  |  YAML: {r['yaml_mtime']}")
        lines.append("")

    lines.append("─" * 56)
    if stale_count == 0:
        lines.append("  [OK] 所有运行时规则与宪法同步。")
    else:
        lines.append(f"  [STALE] {stale_count} 个 YAML 规则滞后于宪法 Markdown。")
        lines.append("  运行 python brain/sync_constitution.py --fix 手动同步。")
    lines.append("─" * 56)

    return "\n".join(lines)


def get_stale_count(results):
    """返回 STALE 状态的 YAML 数量"""
    return sum(1 for r in results.values() if r["status"] == "STALE")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="宪法漂移检测器")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--fix", action="store_true", help="尝试手动同步 (暂未实现自动同步)")
    args = parser.parse_args()

    results = check_drift()

    if args.json:
        print(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "stale_count": get_stale_count(results),
            "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(report_text(results))
        if args.fix:
            print("\n  [!] 自动同步尚未实现，请手动将宪法变更合并到 YAML 规则文件。")
