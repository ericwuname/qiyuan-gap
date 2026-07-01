# -*- coding: utf-8 -*-
"""Sprint 3: CEO Morning Report Notifier.
Reads blackboard events, builds digest with 5/day push limit.
"""
import io, os, sys, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bus.blackboard import Blackboard

SEVERITY_ORDER = {"warning": 0, "error": 0, "info": 1, "debug": 2}

SOURCE_LABELS = {
    "probe": "意识探针",
    "body_daemon": "身体守护进程",
    "self_evolve": "自进化引擎",
    "curiosity": "好奇心引擎",
    "router": "路由",
}

SOURCE_SUMMARIES = {
    "probe": "探针检测到系统状态变化",
    "body_daemon": "守护进程状态更新",
    "self_evolve": "生成了新的建议规则",
    "curiosity": "好奇心引擎有新发现",
}


class Notifier:
    """Build CEO morning digest from blackboard events. 5/day push limit."""

    def __init__(self, bus_dir, push_limit=5):
        self.bus_dir = bus_dir
        self.push_limit = push_limit
        self.bb = Blackboard(bus_dir, push_limit)
        self._kb = None  # Lazy init KnowledgeBus
        self._style = None  # Lazy init StyleAdapter

    def build_digest(self, since_timestamp=None):
        """Build CEO morning digest.
        Returns None if no pending events, digest dict otherwise.
        """
        events = self.bb.read_events(since_timestamp=since_timestamp, limit=200)
        if not events:
            return None

        # Filter out internal noise
        skip_types = {"startup", "init", "check_complete", "scan_complete", "cycle_complete"}
        visible = [e for e in events if e.get("type") not in skip_types]
        if not visible:
            return None

        # Group by source+type
        grouped = {}
        for e in visible:
            key = e["source"] + "/" + e["type"]
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(e)

        # Build items
        items = []
        for key, evts in grouped.items():
            latest = evts[-1]
            source = latest["source"]
            items.append({
                "source": source,
                "source_label": SOURCE_LABELS.get(source, source),
                "type": latest["type"],
                "summary": self._summarize(source, evts, latest),
                "count": len(evts),
                "severity": latest.get("severity", "info"),
                "last_timestamp": latest["timestamp"],
                "event_ids": [e["event_id"] for e in evts[-3:]],
            })

        # Sort by severity then recency
        items.sort(key=lambda x: (
            SEVERITY_ORDER.get(x["severity"], 99),
            x["last_timestamp"]
        ))

        capped = len(items) > self.push_limit
        overflow = len(items) - self.push_limit if capped else 0
        items = items[:self.push_limit]

        # Enrich with semantic context
        self._enrich_items(items)

        return {
            "title": "你不在的时候，我观察到了这些：",
            "items": items,
            "total_pending": len(visible),
            "displayed": len(items),
            "capped": capped,
            "overflow_count": overflow,
            "generated_at": datetime.now().isoformat(),
            "since": since_timestamp or "beginning",
        }

    def _summarize(self, source, events, latest):
        """Build human-readable summary from events."""
        payload = latest.get("payload", {})

        if source == "self_evolve":
            count = payload.get("count", 0)
            if count > 0:
                return "生成了 {} 条建议规则（在 _suggested/ 待审）".format(count)
            return "自进化引擎完成了分析"

        if source == "probe":
            triggers = payload.get("triggers", [])
            if triggers:
                names = ", ".join(t.get("probe", "") for t in triggers[:2])
                return "探针检测到变化：{}".format(names)
            return "探针完成扫描"

        if source == "body_daemon":
            check_num = payload.get("check_num", "?")
            return "守护进程完成第 {} 次检查".format(check_num)

        if source == "curiosity":
            cv2 = payload.get("cv2", 0)
            return "好奇心指数: {:.2f}".format(cv2)

        return SOURCE_SUMMARIES.get(source, "{} 有 {} 条更新".format(source, len(events)))

    def mark_acknowledged(self):
        """Mark current timestamp as acknowledged, so next check starts fresh."""
        ack_file = os.path.join(self.bus_dir, "last_ack.json")
        ack = {"last_ack_at": datetime.now().isoformat()}
        os.makedirs(self.bus_dir, exist_ok=True)
        with io.open(ack_file, "w", encoding="utf-8") as f:
            json.dump(ack, f, ensure_ascii=False, indent=2)
        return ack["last_ack_at"]

    def _enrich_items(self, items):
        """Enrich digest items with semantic context via KnowledgeBus."""
        try:
            if self._kb is None:
                from bus.knowledge_bus import KnowledgeBus
                brain_dir = os.path.dirname(self.bus_dir)
                self._kb = KnowledgeBus(brain_dir=brain_dir, bus_dir=self.bus_dir)
            for item in items:
                mock_event = {"payload": {"summary": item.get("summary", ""), "type": item.get("type", ""), "source": item.get("source", "")}}
                enriched = self._kb.enrich(mock_event)
                item["_semantic"] = enriched.get("semantic", {})
        except Exception:
            pass

    def format_styled(self, digest):
        """Format digest with CEO style adaptation. Returns formatted string."""
        try:
            if self._style is None:
                from bus.style_adapter import StyleAdapter
                self._style = StyleAdapter()
            return self._style.format_morning_brief(digest)
        except Exception:
            return None

    def get_last_ack(self):
        """Get last acknowledged timestamp."""
        ack_file = os.path.join(self.bus_dir, "last_ack.json")
        if os.path.isfile(ack_file):
            with io.open(ack_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("last_ack_at")
        return None


def build_morning_report(bus_dir=None, push_limit=5):
    """Convenience function: build digest."""
    if bus_dir is None:
        bus_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bus"
        )
    n = Notifier(bus_dir, push_limit)
    last_ack = n.get_last_ack()
    return n.build_digest(since_timestamp=last_ack)
