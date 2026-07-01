# -*- coding: utf-8 -*-
"""启元智能 · 大脑一键恢复脚本
用法: python brain/restore.py <备份路径> [选项]
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime


# ── 备份验证 ─────────────────────────────────────────────────────

REQUIRED_DIRS = ["brain", "brain/rules", "brain/memory", "brain/audit"]
KEY_FILES = [
    "brain/cli.py", "brain/rule_engine.py", "brain/config.yaml",
    "brain/rules/constitution.yaml", "brain/rules/gene_protocols.yaml",
    "brain/rules/immune_system.yaml",
    "brain/memory/memory_engine.py", "brain/audit/audit_engine.py",
    "brain/self_heal.py",
]


def validate_backup(backup_path):
    issues = []
    for d in REQUIRED_DIRS:
        if not os.path.isdir(os.path.join(backup_path, d)):
            issues.append("Missing dir: " + d)
    for f in KEY_FILES:
        if not os.path.isfile(os.path.join(backup_path, f)):
            issues.append("Missing file: " + f)

    rules_dir = os.path.join(backup_path, "brain", "rules")
    yaml_count = 0
    if os.path.isdir(rules_dir):
        for root, dirs, files in os.walk(rules_dir):
            for fn in files:
                if fn.endswith((".yaml", ".yml")):
                    yaml_count += 1
    if yaml_count == 0:
        issues.append("No YAML rule files in backup")

    return issues, yaml_count


def count_rules(brain_dir):
    rules_dir = os.path.join(brain_dir, "rules")
    count = 0
    if os.path.isdir(rules_dir):
        for root, dirs, files in os.walk(rules_dir):
            for fn in files:
                if fn.endswith((".yaml", ".yml")):
                    count += 1
    return count


# ── 验证命令 ─────────────────────────────────────────────────────

def run_brain_command(brain_dir, args, timeout=60):
    cli = os.path.join(brain_dir, "cli.py")
    if not os.path.isfile(cli):
        return False, "cli.py not found at " + cli
    try:
        result = subprocess.run(
            [sys.executable, cli] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=brain_dir,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Timeout after " + str(timeout) + "s"
    except Exception as e:
        return False, str(e)


# ── 恢复主流程 ───────────────────────────────────────────────────

def restore(backup_path, target_path=None, live=False, dry_run=False):
    report = {
        "timestamp": datetime.now().isoformat(),
        "backup_path": os.path.abspath(backup_path),
        "steps": [],
        "success": False,
    }

    # Step 1: 验证备份
    issues, backup_rule_count = validate_backup(backup_path)
    report["steps"].append({
        "step": "validate_backup",
        "ok": len(issues) == 0,
        "issues": issues,
        "backup_rule_count": backup_rule_count,
    })
    if issues:
        return report

    # Step 2: 确定目标
    if live:
        if target_path:
            restore_target = os.path.abspath(target_path)
        else:
            restore_target = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        report["steps"].append({
            "step": "set_target",
            "ok": True,
            "target": restore_target,
            "mode": "live",
        })
    else:
        restore_target = tempfile.mkdtemp(prefix="brain_restore_")
        report["steps"].append({
            "step": "set_target",
            "ok": True,
            "target": restore_target,
            "mode": "isolated",
        })

    report["restore_target"] = restore_target

    if dry_run:
        report["steps"].append({
            "step": "dry_run", "ok": True,
            "note": "dry-run mode, no actual copy",
        })
        report["success"] = True
        return report

    # Step 3: 复制brain目录
    try:
        src_brain = os.path.join(backup_path, "brain")
        dst_brain = os.path.join(restore_target, "brain")
        if os.path.exists(dst_brain):
            shutil.rmtree(dst_brain)
        shutil.copytree(src_brain, dst_brain)
        report["steps"].append({"step": "copy_brain", "ok": True})
    except Exception as e:
        report["steps"].append({"step": "copy_brain", "ok": False, "error": str(e)})
        return report

    # Step 4: brain status
    ok, output = run_brain_command(dst_brain, ["status"])
    report["steps"].append({
        "step": "brain_status", "ok": ok,
        "output": output[:800] if output else "(no output)",
    })

    # Step 5: rule validate
    ok, output = run_brain_command(dst_brain, ["rule", "validate"])
    report["steps"].append({
        "step": "rule_validate", "ok": ok,
        "output": output[:800] if output else "(no output)",
    })

    # Step 6: 核对规则数量
    restored_rule_count = count_rules(dst_brain)
    count_ok = restored_rule_count == backup_rule_count
    report["steps"].append({
        "step": "count_rules",
        "ok": count_ok,
        "backup_count": backup_rule_count,
        "restored_count": restored_rule_count,
    })

    # Step 7: 已知查询验证
    ok, output = run_brain_command(dst_brain, ["kb", "search", "测试"])
    report["steps"].append({
        "step": "kb_search", "ok": ok,
        "output": output[:500] if output else "(no output)",
    })

    # Step 8: health check
    ok, output = run_brain_command(dst_brain, ["health", "check"])
    report["steps"].append({
        "step": "health_check", "ok": ok,
        "output": output[:500] if output else "(no output)",
    })

    # 判定整体成功
    all_ok = all(s.get("ok", False) for s in report["steps"] if s["step"] not in ("dry_run",))
    report["success"] = all_ok
    return report


# ── 输出 ────────────────────────────────────────────────────────

def print_report(report):
    lines = []
    lines.append("=" * 60)
    lines.append("  启元智能 · 大脑恢复报告")
    lines.append("  时间: " + report["timestamp"])
    lines.append("  备份: " + report["backup_path"])
    lines.append("  目标: " + report.get("restore_target", "N/A"))
    lines.append("=" * 60)

    for s in report["steps"]:
        icon = "OK" if s.get("ok") else "!!"
        name = s["step"]
        if s.get("mode"):
            lines.append("  [{0}] {1} ({2})".format(icon, name, s["mode"]))
        elif s.get("count"):
            lines.append("  [{0}] {1}: {2}".format(icon, name, s["count"]))
        elif s.get("target"):
            lines.append("  [{0}] {1}: {2}".format(icon, name, s["target"]))
        elif s.get("backup_rule_count"):
            lines.append("  [{0}] {1}: {2} files".format(icon, name, s["backup_rule_count"]))
        elif s.get("backup_count"):
            lines.append("  [{0}] {1}: backup={2} restored={3}".format(
                icon, name, s["backup_count"], s["restored_count"]))
        elif s.get("error"):
            lines.append("  [{0}] {1}: ERROR {2}".format(icon, name, s["error"]))
        elif s.get("issues"):
            for issue in s["issues"]:
                lines.append("  [{0}] {1}: {2}".format(icon, name, issue))
        elif s.get("note"):
            lines.append("  [{0}] {1}: {2}".format(icon, name, s["note"]))
        else:
            lines.append("  [{0}] {1}: OK".format(icon, name))

    lines.append("=" * 60)
    if report["success"]:
        lines.append("  结果: PASS - 恢复验证全部通过")
    else:
        lines.append("  结果: FAIL - 请检查上述错误")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="启元智能 · 大脑一键恢复 (restore.py)")
    parser.add_argument(
        "backup_path",
        help="备份目录路径，如 _backup/brain_full_20260620_035352/")
    parser.add_argument(
        "--target",
        help="恢复目标目录（默认自动创建隔离测试目录）")
    parser.add_argument(
        "--live", action="store_true",
        help="恢复到当前工作区 brain/ (P0级操作，需CEO确认)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅验证备份完整性，不实际恢复")
    parser.add_argument(
        "--json", action="store_true",
        help="以JSON格式输出报告")
    args = parser.parse_args()

    backup_path = os.path.abspath(args.backup_path)
    if not os.path.isdir(backup_path):
        print("ERROR: 备份路径不存在: " + backup_path)
        sys.exit(1)

    # P0防护: --live 模式下强制二次确认
    if args.live:
        print("=" * 60)
        print("  WARNING: --live 模式将覆盖当前 brain/ 目录")
        print("  备份路径: " + backup_path)
        print("  目标: 当前工作区 brain/")
        print("=" * 60)
        print("  P0级操作。键入 YES 确认恢复，其他任何输入取消。")
        print("=" * 60)
        confirm = input("> ").strip()
        if confirm != "YES":
            print("已取消。")
            sys.exit(0)

    report = restore(
        backup_path,
        target_path=args.target,
        live=args.live,
        dry_run=args.dry_run,
    )

    if args.json:
        output = json.dumps(report, ensure_ascii=False, indent=2)
        print(output)
    else:
        print(print_report(report))

    sys.exit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
