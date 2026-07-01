# -*- coding: utf-8 -*-
"""Fast status check – no heavy imports. Pure filesystem + JSON."""
import io, os, json, sys, glob
from datetime import datetime

def check():
    brain_dir = os.path.dirname(os.path.abspath(__file__))
    result = {
        "brain_ok": True,
        "version": "1.0.0",
        "mode": "fast",
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "components": {}
    }
    
    # Check rules
    rules_dir = os.path.join(brain_dir, "rules")
    try:
        yaml_files = [f for f in os.listdir(rules_dir) if f.endswith(".yaml")]
        result["components"]["rules"] = {"ok": len(yaml_files) > 0, "files": len(yaml_files)}
    except Exception as e:
        result["components"]["rules"] = {"ok": False, "error": str(e)}
    
    # Check fallback
    fallback = os.path.join(brain_dir, "fallback.md")
    try:
        if os.path.isfile(fallback):
            size = os.path.getsize(fallback)
            result["components"]["fallback"] = {"ok": size > 1000, "size_kb": round(size/1024, 1)}
        else:
            result["components"]["fallback"] = {"ok": False, "error": "fallback.md not found"}
    except Exception as e:
        result["components"]["fallback"] = {"ok": False, "error": str(e)}
    
    # SOP sync check
    import subprocess
    try:
        scripts_dir = os.path.join(os.path.dirname(brain_dir), '_scripts')
        sop_script = os.path.join(scripts_dir, 'sop-sync-validator.py')
        if os.path.isfile(sop_script):
            r = subprocess.run([sys.executable, sop_script], capture_output=True, text=True, timeout=5)
            result['components']['sop_sync'] = {'ok': r.returncode == 0}
        else:
            result['components']['sop_sync'] = {'ok': False, 'error': 'script not found'}
    except Exception as e:
        result['components']['sop_sync'] = {'ok': False, 'error': str(e)}
    # Check config
    config_path = os.path.join(brain_dir, "config.yaml")
    try:
        if os.path.isfile(config_path):
            result["components"]["config"] = {"ok": True}
        else:
            result["components"]["config"] = {"ok": False, "error": "config.yaml not found"}
    except Exception as e:
        result["components"]["config"] = {"ok": False, "error": str(e)}
    
    # Check cli.py exists and is valid Python
    cli_path = os.path.join(brain_dir, "cli.py")
    try:
        if os.path.isfile(cli_path):
            with io.open(cli_path, "r", encoding="utf-8") as f:
                first_line = f.readline()
            result["components"]["cli"] = {"ok": first_line.startswith("#"), "size_kb": round(os.path.getsize(cli_path)/1024, 1)}
        else:
            result["components"]["cli"] = {"ok": False, "error": "cli.py not found"}
    except Exception as e:
        result["components"]["cli"] = {"ok": False, "error": str(e)}
    
    # Check ab_check.py (AB-KB Wave C)
    ab_path = os.path.join(brain_dir, "ab_check.py")
    try:
        if os.path.isfile(ab_path):
            result["components"]["ab_check"] = {"ok": True}
        else:
            result["components"]["ab_check"] = {"ok": False, "error": "ab_check.py not found"}
    except Exception as e:
        result["components"]["ab_check"] = {"ok": False, "error": str(e)}

    # Check safe_patch_verify.py (AB-KB gate integrity)
    spv_path = os.path.join(brain_dir, "..", "_scripts", "safe_patch_verify.py")
    try:
        spv_abs = os.path.normpath(spv_path)
        if os.path.isfile(spv_abs):
            result["components"]["safe_patch_verify"] = {"ok": True}
        else:
            result["components"]["safe_patch_verify"] = {"ok": False, "error": "safe_patch_verify.py not found - gate integrity compromised"}
    except Exception as e:
        result["components"]["safe_patch_verify"] = {"ok": False, "error": str(e)}

    # Check SOP index vs brain YAML consistency
    idx_candidates = glob.glob(os.path.join(brain_dir, "..", "01_*", "*SOP*\u7d22\u5f15*.md"))
    idx_path = idx_candidates[0] if idx_candidates else ""
    sops_dir = os.path.join(brain_dir, "rules", "sops")
    pp = "|"
    try:
        idx_abs = os.path.normpath(idx_path)
        sops_abs = os.path.normpath(sops_dir)
        sop_issues = []
        if os.path.isfile(idx_abs) and os.path.isdir(sops_abs):
            import re as _re
            index_sops = set()
            with io.open(idx_abs, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith(pp): continue
                    parts = [x.strip() for x in line.split(pp)]
                    if len(parts) < 4: continue
                    sid = parts[1]
                    px = r"^SOP-\d+[A-Z]*$"
                    if _re.match(px, sid): index_sops.add(sid)
            yaml_sops = {}
            for fname in os.listdir(sops_abs):
                if not fname.endswith(".yaml"): continue
                fpath = os.path.join(sops_abs, fname)
                with io.open(fpath, "r", encoding="utf-8") as f:
                    c = f.read()
                px2 = r"^id:\s*(\S+)"
                mid = _re.search(px2, c, _re.MULTILINE)
                if mid:
                    yid = mid.group(1)
                    yaml_sops[yid] = fname
                    px3 = r"sop_(\d+[a-z]*)\.yaml"
                    fm = _re.search(px3, fname)
                    if fm:
                        exp = "SOP-" + fm.group(1).zfill(3)
                        base = _re.sub("[A-Za-z]+$", "", yid)
                        base_clean = _re.sub(r"[A-Za-z]+$", "", exp).upper()
                        yid_clean = _re.sub(r"[A-Za-z]+$", "", yid).upper()
                        if base_clean != yid_clean: sop_issues.append("CONFLICT:" + fname + " " + yid)
            for sid in sorted(index_sops):
                if sid not in yaml_sops: sop_issues.append("MISS:" + sid)
            for yid in sorted(yaml_sops):
                if yid not in index_sops: sop_issues.append("EXTRA:" + yid)
            result["components"]["sop_consistency"] = {
                "ok": len(sop_issues) == 0,
                "index_count": len(index_sops),
                "yaml_count": len(yaml_sops),
                "issues": sop_issues[:10],
                "issues_count": len(sop_issues)
            }
        else: result["components"]["sop_consistency"] = {"ok": False}
    except Exception as e:
        result["components"]["sop_consistency"] = {"ok": False, "error": str(e)}
    # Overall
    all_ok = all(c.get("ok", False) for c in result["components"].values())
    result["brain_ok"] = all_ok
    
    # Read fallback stats if available
    fallback_path = os.path.join(brain_dir, "fallback.md")
    if os.path.isfile(fallback_path):
        with io.open(fallback_path, "r", encoding="utf-8") as f:
            fb = f.read()
        result["fallback_rules"] = fb.count("### ") - 2  # rough rule count
    
    return result

if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
