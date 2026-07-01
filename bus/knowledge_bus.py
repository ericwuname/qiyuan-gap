# -*- coding: utf-8 -*-
"""Sprint 4: KnowledgeBus - Semantic bridge between blackboard events and FAISS knowledge store."""
import io, os, sys, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bus.blackboard import Blackboard


class KnowledgeBus:
    """Enriches blackboard events with semantic context from FAISS + memory."""

    def __init__(self, brain_dir=None, bus_dir=None):
        if brain_dir is None:
            brain_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.brain_dir = brain_dir
        self.bus_dir = bus_dir or os.path.join(brain_dir, "bus")
        self.bb = Blackboard(self.bus_dir)

    def enrich(self, event, top_k=3):
        """Enrich a single event with semantic context.
        Returns: {event: ..., semantic: {related_docs: [...], concepts: [...], gaps: [...]}}
        Falls back gracefully if FAISS unavailable.
        """
        enrichment = {
            "related_docs": [],
            "concepts": [],
            "gaps": [],
            "method": "none"
        }

        payload = event.get("payload", {})
        query_text = self._extract_query(payload)

        if not query_text:
            enrichment["method"] = "no_query"
            return {"event": event, "semantic": enrichment}

        # Try FAISS semantic search
        try:
            from memory.faiss_store import FAISSStore
            persist_dir = os.path.join(self.brain_dir, "memory", "chroma_db")
            store = FAISSStore(persist_dir)

            if store._index is not None and store._index.ntotal > 0:
                results = store.search(query_text, k=top_k)
                enrichment["related_docs"] = results[:top_k] if results else []
                enrichment["method"] = "faiss"
        except Exception:
            pass

        # Extract key concepts
        enrichment["concepts"] = self._extract_concepts(query_text)

        # Check for knowledge gaps
        if not enrichment["related_docs"]:
            enrichment["gaps"].append({
                "query": query_text[:100],
                "note": "No relevant documents found in knowledge base"
            })
            enrichment["method"] = "gap_detected" if enrichment["method"] == "none" else enrichment["method"]

        return {"event": event, "semantic": enrichment}

    def enrich_batch(self, events, top_k=3):
        """Enrich multiple events. Returns list of enriched events."""
        return [self.enrich(e, top_k) for e in events]

    def _extract_query(self, payload):
        """Extract meaningful search query from event payload."""
        if isinstance(payload, str):
            return payload[:200]
        if isinstance(payload, dict):
            parts = []
            for key in ("summary", "message", "msg", "title", "name", "description"):
                if key in payload:
                    parts.append(str(payload[key]))
            if "triggers" in payload:
                for t in payload["triggers"]:
                    if isinstance(t, dict) and "probe" in t:
                        parts.append("probe " + t["probe"])
            if "results" in payload:
                parts.append(str(payload["results"])[:100])
            return " ".join(parts)[:200] if parts else ""
        return ""

    def _extract_concepts(self, text):
        """Extract key concepts from text (simple keyword extraction)."""
        keywords = ["探针", "自我", "进化", "规则", "建议", "异常",
                    "知识库", "记忆", "连续性", "好奇心", "整合度",
                    "probe", "evolve", "rule", "anomaly", "curiosity", "memory"]
        found = []
        text_lower = text.lower()
        for kw in keywords:
            if kw.lower() in text_lower:
                found.append(kw)
        return found[:5]

    def get_knowledge_gaps_report(self):
        """Scan all events for knowledge gaps. Returns gap report."""
        events = self.bb.read_events(limit=200)
        enriched = self.enrich_batch(events)
        gaps = [e for e in enriched if e["semantic"]["gaps"]]
        return {
            "total_events": len(events),
            "events_with_gaps": len(gaps),
            "gaps": [e["semantic"]["gaps"] for e in gaps[:10]],
            "generated_at": datetime.now().isoformat()
        }
