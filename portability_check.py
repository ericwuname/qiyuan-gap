# -*- coding: utf-8 -*-
"""Portability scanner - detect hardcoded environment-specific values."""
import io, os, re

def scan(brain_dir):
    results = []

    # 1. Scan config.yaml for hardcoded paths
    config_path = os.path.join(brain_dir, "config.yaml")
    if os.path.isfile(config_path):
        with io.open(config_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if re.search(r"[A-Z]:\\", line) and not line.strip().startswith("#"):
                    results.append(("config.yaml", i, "HARDPATH", line.strip()[:80]))

    # 2. Scan ALL Python files (including test_*) for hardcoded paths
    for root_dir, dirs, files in os.walk(brain_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                fp = os.path.join(root_dir, f)
                rel = os.path.relpath(fp, brain_dir)
                with io.open(fp, "r", encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue
                        # Match "D:\..." or 'D:\...' or r"D:\..." patterns
                        if (re.search(r"""["'][A-Z]:[/\\]""", stripped) or
                            re.search(r"""r["'][A-Z]:[/\\]""", stripped)):
                            results.append((rel, i, "HARDPATH", stripped[:80]))

    # 3. Scan AGENTS.md for environment-specific references
    root = os.path.dirname(brain_dir)
    agents_path = os.path.join(root, "AGENTS.md")
    if os.path.isfile(agents_path):
        with io.open(agents_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if "D:" in line and (".py" in line or ".md" in line or ".yaml" in line):
                    results.append(("AGENTS.md", i, "ENVREF", line.strip()[:80]))

    return results

if __name__ == "__main__":
    brain_dir = os.path.dirname(os.path.abspath(__file__))
    results = scan(brain_dir)

    if not results:
        print("OK: No hardcoded environment coupling found.")
    else:
        hardpath = [r for r in results if r[2] == "HARDPATH"]
        envref = [r for r in results if r[2] == "ENVREF"]
        print("Found {} environment coupling issues:".format(len(results)))
        print("  HARDPATH (critical): {}".format(len(hardpath)))
        print("  ENVREF (warning): {}".format(len(envref)))
        print()
        for f, line, cat, detail in results:
            tag = "[CRIT]" if cat == "HARDPATH" else "[WARN]"
            print("  {} {}:{}: {}".format(tag, f, line, detail))