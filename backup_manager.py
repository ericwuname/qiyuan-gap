# -*- coding: utf-8 -*-
"""Brain backup - timestamped snapshot, daily dedup, keep last 3."""
import io, os, shutil, json
from datetime import datetime

MAX_KEEP = 3

def todays_backup_exists(brain_dir):
    root = os.path.dirname(brain_dir)
    backup_dir = os.path.join(root, "_backup")
    if not os.path.isdir(backup_dir):
        return False
    today = datetime.now().strftime("%Y%m%d")
    for d in os.listdir(backup_dir):
        if d.startswith("brain_") and today in d:
            full = os.path.join(backup_dir, d)
            if os.path.isdir(full):
                return True
    return False

def cleanup_old_backups(brain_dir):
    root = os.path.dirname(brain_dir)
    backup_dir = os.path.join(root, "_backup")
    if not os.path.isdir(backup_dir):
        return
    dirs = sorted([d for d in os.listdir(backup_dir)
                   if os.path.isdir(os.path.join(backup_dir, d))
                   and d.startswith("brain_")], reverse=True)
    for old in dirs[MAX_KEEP:]:
        shutil.rmtree(os.path.join(backup_dir, old), ignore_errors=True)

def increment_version(brain_dir):
    import yaml
    config_path = os.path.join(brain_dir, "config.yaml")
    with io.open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    parts = config.get("brain", {}).get("version", "1.0.0").split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    new_ver = ".".join(parts)
    config.setdefault("brain", {})["version"] = new_ver
    with io.open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    return new_ver

def backup(brain_dir, label="", force=False):
    root = os.path.dirname(brain_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Daily dedup: skip if already backed up today (unless force=True)
    if not force and todays_backup_exists(brain_dir):
        return None, {"skipped": "already backed up today", "timestamp": ts}

    new_ver = increment_version(brain_dir)
    name = f"brain_v{new_ver}_{ts}" if not label else f"brain_v{new_ver}_{ts}_{label}"
    backup_path = os.path.join(root, "_backup", name)
    os.makedirs(backup_path, exist_ok=True)

    key_items = [
        "brain/cli.py", "brain/rule_engine.py", "brain/self_heal.py",
        "brain/self_evolve.py", "brain/rule_discovery.py", "brain/rule_optimizer.py",
        "brain/restore.py", "brain/sop_allocator.py", "brain/portability_check.py",
        "brain/file_lock.py", "brain/backup_manager.py",
        "brain/config.yaml",
        "brain/rules/constitution.yaml", "brain/rules/gene_protocols.yaml",
        "brain/rules/immune_system.yaml", "brain/rules/rules.json",
        "brain/memory/memory_engine.py", "brain/memory/long_term_memory.py",
        "brain/memory/workspace.py", "brain/memory/__init__.py",
        "brain/audit/audit_engine.py", "brain/audit/__init__.py",
        "brain/probe/probe.py", "brain/probe/probe_d.py",
        "brain/probe/world_model.py", "brain/probe/world_model_db.py",
        "brain/probe/world_model_ensemble.py", "brain/probe/curiosity.py",
        "brain/probe/rollout_planner.py", "brain/probe/normalizer.py",
        "brain/probe/confidence_logic.py", "brain/probe/diversity_monitor.py",
        "brain/probe/__init__.py",
        "brain/dashboard/app.py",
        "brain/report/nightly_report.py", "brain/report/narrative_generator.py",
        "brain/social/mailbox.py", "brain/social/reputation.py",
        "brain/external_world/model.py", "brain/external_world/collector.py",
        "brain/DEGRADE.md", "brain/RESTORE.md", "brain/fallback.md",
        "brain/config/sop_counter.json",
        "AGENTS.md", "01_公司治理/SOP索引.md",
    ]

    backed, skipped = [], []
    for item in key_items:
        src = os.path.join(root, item)
        dst = os.path.join(backup_path, item)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            backed.append(item)
        else:
            skipped.append(item)

    cleanup_old_backups(brain_dir)

    manifest = {"timestamp": ts, "label": label, "version": new_ver,
                "backed": len(backed), "skipped": len(skipped),
                "files": backed, "missing": skipped}
    with io.open(os.path.join(backup_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return backup_path, manifest

if __name__ == "__main__":
    import sys
    brain_dir = os.path.dirname(os.path.abspath(__file__))
    label = sys.argv[1] if len(sys.argv) > 1 else ""
    force = "--force" in sys.argv
    path, m = backup(brain_dir, label, force)
    if path is None:
        print("SKIPPED: already backed up today (use --force to override)")
    else:
        print(f"Backup created: {path}")
        print(f"  Version: {m['version']}")
        print(f"  Files backed up: {m['backed']}")
        if m["skipped"]:
            print(f"  Files skipped: {m['skipped']}")
