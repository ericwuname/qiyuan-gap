# -*- coding: utf-8 -*-
"""Sprint 3: CEO Morning Report.
Call on new conversation start: python brain/notify_on_startup.py
Presents pending blackboard events since last acknowledgment.
"""
import io, os, sys, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bus.notifier import build_morning_report, Notifier

BRAIN = os.path.dirname(os.path.abspath(__file__))


def notify():
    """Build and display CEO morning report."""
    bus_dir = os.path.join(BRAIN, "bus")
    digest = build_morning_report(bus_dir, push_limit=5)

    if not digest or not digest.get("items"):
        print("No pending notifications.")
        return {"notified": 0, "message": "Nothing new since last check."}

    print()
    print("=" * 50)
    print("  " + digest["title"])
    print("=" * 50)

    for i, item in enumerate(digest["items"], 1):
        src = item.get("source_label", item["source"])
        sev = item.get("severity", "info")
        marker = "WARN" if sev in ("warning", "error") else "INFO"
        print(f"  [{marker}] [{src}] {item["summary"]} ({item["count"]}x)")

    if digest.get("capped"):
        print(f"  ... +{digest["overflow_count"]} more (capped at 5/day)")

    print("=" * 50)
    print(f"  {digest["displayed"]} items displayed | {digest["total_pending"]} total pending")
    print()

    # Auto-acknowledge
    n = Notifier(bus_dir)
    ack = n.mark_acknowledged()

    return {
        "notified": digest["displayed"],
        "total_pending": digest["total_pending"],
        "capped": digest.get("capped", False),
        "acknowledged_at": ack,
    }


if __name__ == "__main__":
    result = notify()
    print(json.dumps(result, ensure_ascii=False, indent=2))