# -*- coding: utf-8 -*-
"""AB Card check - standalone, zero heavy imports"""
import io, os, json, sys

def _get_ab_dir():
    brain_dir = os.path.dirname(os.path.abspath(__file__))
    kb_dir = os.path.join(brain_dir, "..", "05_组织知识库", "防Agent_BUG知识库", "AB-Cards")
    return os.path.normpath(kb_dir)

def search(keyword):
    ab_dir = _get_ab_dir()
    if not os.path.isdir(ab_dir):
        return {"ok": False, "error": "AB-Cards directory not found: " + ab_dir, "results": []}
    results = []
    for fname in sorted(os.listdir(ab_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(ab_dir, fname)
        with io.open(fpath, "r", encoding="utf-8") as f:
            text = f.read()
        if keyword.lower() in text.lower():
            title = fname.replace(".md", "")
            for line in text.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            sev, cat = "", ""
            for line in text.split("\n"):
                if "**严重度**" in line:
                    if "S+" in line: sev = "S+"
                    elif "P1" in line: sev = "P1"
                    elif "P2" in line: sev = "P2"
                    elif "P0" in line: sev = "P0"
                if "**分类**" in line:
                    idx = line.find("**分类**")
                    after = line[idx+6:].strip()
                    if after.startswith(":"): after = after[1:].strip()
                    cat = after.split("**")[0].strip()
            results.append({"id": fname.replace(".md", ""), "title": title, "severity": sev, "category": cat})
    return {"ok": True, "count": len(results), "results": results}

def check():
    """Verify all AB Cards have required fields."""
    ab_dir = _get_ab_dir()
    if not os.path.isdir(ab_dir):
        return {"ok": False, "error": "AB-Cards directory not found: " + ab_dir}
    cards = [f for f in os.listdir(ab_dir) if f.endswith(".md")]
    errors = []
    # Match actual card format: # AB-XXX, **symptom**, **root_cause**, **prevention**, **严重度**, **状态**
    required_keywords = ["# AB-", "**symptom**", "**root_cause**", "**prevention**", "**严重度**", "**状态**"]
    for card in sorted(cards):
        fpath = os.path.join(ab_dir, card)
        with io.open(fpath, "r", encoding="utf-8") as f:
            text = f.read()
        missing = [kw for kw in required_keywords if kw not in text]
        if missing:
            errors.append({"card": card, "missing_fields": missing})
    return {
        "ok": len(errors) == 0,
        "total_cards": len(cards),
        "errors": errors,
        "card_list": [c.replace(".md", "") for c in sorted(cards)]
    }

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "search":
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        result = search(keyword)
    else:
        result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
