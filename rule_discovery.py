# -*- coding: utf-8 -*-
"""
Rule Discovery Engine (P0-2)
Analyzes audit logs to identify high-frequency operation patterns without rule coverage.
Generates rule proposals in YAML format.

Usage: python rule_discovery.py [--days 30] [--min-freq 3] [--dry-run]
CLI:   brain rule discover [--days 30] [--min-freq 3]
"""
import json, os, re, sys, time
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta

try:
    import yaml
except ImportError:
    yaml = None

_brain_dir = os.path.dirname(os.path.abspath(__file__))
_rules_dir = os.path.join(_brain_dir, "rules")
_proposals_dir = os.path.join(_brain_dir, "proposals")
_audit_db = os.path.join(_brain_dir, "audit", "audit.db")

def _tokenize(text):
    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+", str(text).lower())
    return [t for t in tokens if len(t) >= 1]

def _compute_tfidf(docs):
    import math
    df = Counter()
    for doc in docs:
        df.update(set(doc))
    N = max(len(docs), 1)
    idf = {term: math.log(N / (freq + 1)) + 1 for term, freq in df.items()}
    vectors = []
    for doc in docs:
        tf = Counter(doc)
        vec = {}
        for term, freq in tf.items():
            vec[term] = freq * idf.get(term, 0)
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1
        vec = {k: v / norm for k, v in vec.items()}
        vectors.append(vec)
    return idf, vectors

def _cosine_similarity(v1, v2):
    common = set(v1.keys()) & set(v2.keys())
    return sum(v1[k] * v2[k] for k in common)

def _load_audit_logs(since_days=30):
    import sqlite3
    if not os.path.isfile(_audit_db):
        return []
    since = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(_audit_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT action, target_path, operator, details, result, timestamp "
        "FROM audit_logs WHERE timestamp >= ? ORDER BY timestamp DESC",
        (since,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _extract_operation_patterns(logs):
    patterns = defaultdict(lambda: {"actions": Counter(), "paths": [], "details": [], "timestamps": []})
    for entry in logs:
        action = entry.get("action", "unknown")
        target = entry.get("target_path", "")
        detail = entry.get("details", "")
        ts = entry.get("timestamp", "")
        target_dir = "root"
        if target:
            parts = target.replace("\\", "/").split("/")
            for p in parts:
                if p and p not in ("D:", "0.个人文档", "个人文档", "启元智能"):
                    target_dir = p
                    break
        key = action + ":::" + target_dir
        patterns[key]["actions"][action] += 1
        if target:
            patterns[key]["paths"].append(target)
        if detail:
            patterns[key]["details"].append(detail)
        patterns[key]["timestamps"].append(ts)
    result = []
    for key, data in patterns.items():
        action, target_dir = key.split(":::", 1)
        total = sum(data["actions"].values())
        unique_paths = list(set(data["paths"]))[:5]
        sample_details = list(set(d for d in data["details"] if d))[:3]
        timestamps = sorted(data["timestamps"])
        result.append({
            "pattern_key": key, "action": action, "target_dir": target_dir,
            "count": total, "unique_paths": len(set(data["paths"])),
            "example_paths": unique_paths, "example_details": sample_details,
            "first_seen": timestamps[0] if timestamps else "",
            "last_seen": timestamps[-1] if timestamps else "",
        })
    result.sort(key=lambda x: x["count"], reverse=True)
    return result

def _load_existing_rules():
    rules = []
    if not os.path.isdir(_rules_dir):
        return rules
    for fname in sorted(os.listdir(_rules_dir)):
        if not fname.endswith(".yaml"):
            continue
        fpath = os.path.join(_rules_dir, fname)
        try:
            if yaml:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    rule = data.get("rule", data)
                    if rule.get("status") == "active" or rule.get("status") is None:
                        rules.append(rule)
        except Exception:
            pass
    return rules

def _is_pattern_covered(pattern, rules):
    action = pattern["action"].lower()
    target_dir = pattern["target_dir"].lower()
    examples = " ".join(pattern.get("example_details", [])).lower()
    for rule in rules:
        triggers = [t.lower() for t in rule.get("triggers", [])]
        for trigger in triggers:
            if trigger in action or trigger in target_dir:
                return True
            if len(trigger) >= 3 and (trigger in examples or trigger in pattern["pattern_key"].lower()):
                return True
    return False

def _cluster_patterns(patterns, similarity_threshold=0.3):
    if len(patterns) <= 1:
        return [[p] for p in patterns]
    docs = []
    for p in patterns:
        text = " ".join(p.get("example_details", []) + p.get("example_paths", []))
        docs.append(_tokenize(text))
    _, vectors = _compute_tfidf(docs)
    clusters = []
    assigned = set()
    for i, p in enumerate(patterns):
        if i in assigned:
            continue
        cluster = [p]
        assigned.add(i)
        for j in range(i + 1, len(patterns)):
            if j in assigned:
                continue
            if _cosine_similarity(vectors[i], vectors[j]) >= similarity_threshold:
                cluster.append(patterns[j])
                assigned.add(j)
        clusters.append(cluster)
    return clusters

def _generate_proposal(cluster, confidence, proposal_index=0):
    if not cluster:
        return {}
    total_count = sum(p["count"] for p in cluster)
    actions = Counter()
    target_dirs = []
    all_details = []
    all_paths = []
    for p in cluster:
        actions[p["action"]] += p["count"]
        target_dirs.append(p["target_dir"])
        all_details.extend(p.get("example_details", []))
        all_paths.extend(p.get("example_paths", []))
    top_actions = [a for a, _ in actions.most_common(3)]
    unique_dirs = list(set(target_dirs))[:3]
    unique_details = list(set(d for d in all_details if d))[:5]
    unique_paths = list(set(all_paths))[:5]
    main_action = top_actions[0] if top_actions else "operation"
    main_dir = unique_dirs[0] if unique_dirs else "system"
    proposal_id = "EVO-DISC-" + str(int(time.time()) % 100000).zfill(5)
    level = "P1" if total_count >= 10 else ("P2" if total_count >= 5 else "P3")
    triggers = list(set(top_actions + unique_dirs))[:8]
    rule = {
        "id": proposal_id,
        "name": "Auto-discovered: " + main_dir + " " + main_action + " pattern",
        "level": level, "priority": 5, "owner": "auto-discovery",
        "status": "proposed", "triggers": triggers,
        "action": "Detected " + str(total_count) + " " + main_action + " operations in " + main_dir + " (30d). Recommend defining operational standards.",
        "description": "Auto-discovery: " + str(total_count) + " " + main_action + " ops in " + main_dir + ". Sample paths: " + ", ".join(unique_paths[:3]),
        "examples": unique_details[:3],
    }
    metadata = {
        "_confidence": round(confidence, 2),
        "_discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_source": "rule_discovery.py auto-discovery",
        "_cluster_size": len(cluster),
        "_total_operations": total_count,
        "_pattern_keys": [p["pattern_key"] for p in cluster],
    }
    return {"rule": rule, "_meta": metadata}

def discover(days=30, min_freq=3, dry_run=False):
    if yaml is None:
        return {"ok": False, "error": "PyYAML not installed. Run: pip install pyyaml"}
    os.makedirs(_proposals_dir, exist_ok=True)
    logs = _load_audit_logs(since_days=days)
    if not logs:
        return {"ok": True, "patterns_analyzed": 0, "uncovered_clusters": 0,
                "proposals_generated": 0, "proposals": [],
                "message": "No audit logs in last " + str(days) + " days"}
    patterns = _extract_operation_patterns(logs)
    patterns = [p for p in patterns if p["count"] >= min_freq]
    if not patterns:
        return {"ok": True, "patterns_analyzed": 0, "uncovered_clusters": 0,
                "proposals_generated": 0, "proposals": [],
                "message": "No patterns with freq >= " + str(min_freq)}
    rules = _load_existing_rules()
    uncovered = [p for p in patterns if not _is_pattern_covered(p, rules)]
    if not uncovered:
        return {"ok": True, "patterns_analyzed": len(patterns),
                "uncovered_clusters": 0, "proposals_generated": 0,
                "proposals": [], "covered_all": True,
                "message": "All " + str(len(patterns)) + " patterns covered"}
    clusters = _cluster_patterns(uncovered)
    proposals = []
    for idx, cluster in enumerate(clusters):
        if not cluster:
            continue
        total_count = sum(p["count"] for p in cluster)
        confidence = min(0.95, 0.4 + (total_count * 0.05) + (len(cluster) * 0.1))
        proposal = _generate_proposal(cluster, confidence, idx)
        if proposal.get("rule"):
            proposals.append(proposal)
    generated = 0
    if not dry_run and proposals:
        for prop in proposals:
            rule_id = prop["rule"]["id"]
            fpath = os.path.join(_proposals_dir, rule_id + ".yaml")
            if os.path.exists(fpath):
                continue
            header_lines = [
                "# Rule Proposal: " + prop["rule"]["name"],
                "# Auto-discovered: " + prop["_meta"]["_discovered_at"],
                "# Confidence: " + str(prop["_meta"]["_confidence"]),
                "# Total operations detected: " + str(prop["_meta"]["_total_operations"]),
                "# Cluster size: " + str(prop["_meta"]["_cluster_size"]),
                "",
            ]
            yaml_content = yaml.dump(prop, allow_unicode=True, default_flow_style=False,
                                     sort_keys=False, width=120)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(header_lines))
                f.write(yaml_content)
            generated += 1
    return {
        "ok": True, "patterns_analyzed": len(patterns),
        "covered_patterns": len(patterns) - len(uncovered),
        "uncovered_patterns": len(uncovered),
        "uncovered_clusters": len(clusters),
        "proposals_generated": generated, "dry_run": dry_run,
        "proposals": [
            {"id": p["rule"]["id"], "name": p["rule"]["name"],
             "level": p["rule"]["level"], "confidence": p["_meta"]["_confidence"],
             "total_ops": p["_meta"]["_total_operations"],
             "file": p["rule"]["id"] + ".yaml"}
            for p in proposals
        ],
    }

def cmd_rule_discover(args):
    days = getattr(args, "days", 30)
    min_freq = getattr(args, "min_freq", 3)
    dry_run = getattr(args, "dry_run", False)
    result = discover(days=days, min_freq=min_freq, dry_run=dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Rule Discovery Engine")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--min-freq", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    result = discover(days=args.days, min_freq=args.min_freq, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))