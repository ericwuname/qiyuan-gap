# -*- coding: utf-8 -*-
"""Body status checker - called by new conversation instances.
Usage: python brain/body_status.py
Returns: summary of what the body has been thinking since last conversation.
"""
import io, json, os, sys
from datetime import datetime

BRAIN_ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BRAIN_ROOT, "body_state.json")
LOG_DIR = os.path.join(BRAIN_ROOT, "body_logs")
DISCOVERIES_FILE = os.path.join(LOG_DIR, "discoveries.md")

def main():
    if not os.path.isfile(STATE_FILE):
        print('{"status":"no_body","msg":"Body daemon never started."}')
        return
    
    with io.open(STATE_FILE, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    status = state.get("status", "unknown")
    checks = state.get("checks_completed", 0)
    last_check = state.get("last_check_at", "never")
    discoveries = state.get("discoveries", [])
    
    print(f"body_status: {status} | checks: {checks} | last: {last_check}")
    print(f"discoveries: {len(discoveries)} total, {len([d for d in discoveries if d.get('type') not in ('kb_changes',)])} non-trivial")
    
    if discoveries:
        recent = discoveries[-5:]
        print("\n--- Recent discoveries ---")
        for d in recent:
            print(f"  [{d['timestamp']}] {d['type']}: {d['message']}")
    
    if state.get("anomalies"):
        print("\n--- Anomalies ---")
        for a in state["anomalies"]:
            print(f"  - {a}")
    
    print(f"\ncuriosity_score: {state.get('curiosity_score', 0.0):.3f}")
    
    # If there are discoveries log, show path
    if os.path.isfile(DISCOVERIES_FILE):
        print(f"\nFull discoveries: {DISCOVERIES_FILE}")
    
    # Return JSON for programmatic use
    summary = {
        "status": status,
        "checks_completed": checks,
        "last_check_at": last_check,
        "discovery_count": len(discoveries),
        "recent_discoveries": discoveries[-5:] if discoveries else [],
        "curiosity_score": state.get("curiosity_score", 0.0),
        "anomalies": state.get("anomalies", [])
    }
    
    # Also write as JSON for easy parsing
    summary_path = os.path.join(BRAIN_ROOT, "body_summary.json")
    with io.open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    return summary

if __name__ == "__main__":
    main()
