# -*- coding: utf-8 -*-
"""Sprint 4: StyleAdapter - CEO DNA read-only style adaptation for output formatting."""
import io, os, sys, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DNA_DIR = os.path.join(WORKSPACE, "02_基础信息", "CEO偏好DNA")

# Hard constraint: StyleAdapter READS DNA, NEVER WRITES
# Any DNA modification must go through CEO confirmation


class StyleAdapter:
    """Adapt output style to CEO preferences. Reads DNA, never modifies."""

    def __init__(self, dna_dir=None):
        self.dna_dir = dna_dir or DNA_DIR
        self._dna_cache = {}
        self._loaded = False

    def load_dna(self):
        """Load CEO DNA files into memory. Read-only."""
        if self._loaded:
            return self._dna_cache

        if not os.path.isdir(self.dna_dir):
            self._loaded = True
            return {"_note": "DNA directory not found"}

        for fname in os.listdir(self.dna_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(self.dna_dir, fname)
                try:
                    with io.open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    role = fname.replace("_DNA_v1.0.md", "").replace("CEO偏好DNA", "")
                    self._dna_cache[role] = {
                        "file": fpath,
                        "content": content,
                        "mtime": os.path.getmtime(fpath)
                    }
                except Exception:
                    pass

        self._loaded = True
        return self._dna_cache

    def get_tone_preferences(self):
        """Extract CEO tone/style preferences from DNA."""
        dna = self.load_dna()
        prefs = {
            "directness": "high",       # CEO prefers direct, no fluff
            "formality": "medium",      # Professional but not cold
            "detail_level": "structured",  # Bullet points, tables, clear sections
            "emotion": "restrained",    # Facts first, emotion when earned
            "length": "concise"         # Short, actionable
        }

        for role, data in dna.items():
            content = data.get("content", "")
            if "直接" in content or "不绕" in content:
                prefs["directness"] = "very_high"
            if "完整" in content or "全面" in content:
                prefs["detail_level"] = "comprehensive"

        return prefs

    def format_notification(self, digest_items, tone=None):
        """Format notification items in CEO-preferred style.
        
        Args:
            digest_items: list of notification items from Notifier
            tone: optional tone override dict
        
        Returns: formatted string
        """
        if tone is None:
            tone = self.get_tone_preferences()

        lines = []
        lines.append("=" * 50)
        lines.append("  QiYuan Status Update")
        lines.append("=" * 50)
        lines.append("")

        for i, item in enumerate(digest_items, 1):
            src = item.get("source_label", item.get("source", "unknown"))
            summary = item.get("summary", "")
            count = item.get("count", 1)
            severity = item.get("severity", "info")

            icon = "[!]" if severity in ("warning", "error") else "[*]"
            lines.append("{} {} | {} | {}x".format(icon, src, summary, count))

            # Add semantic context if available
            semantic = item.get("_semantic", {})
            if semantic and semantic.get("concepts"):
                concepts_str = ", ".join(semantic["concepts"][:3])
                lines.append("    concepts: {}".format(concepts_str))

        lines.append("")
        lines.append("-" * 50)

        if tone.get("directness") in ("high", "very_high"):
            lines.append("  Bottom line: {} items pending review.".format(len(digest_items)))
        else:
            lines.append("  Summary: {} new observations since last check.".format(len(digest_items)))

        lines.append("=" * 50)

        return chr(10).join(lines)

    def format_morning_brief(self, digest):
        """Format full morning brief from digest dict."""
        if not digest or not digest.get("items"):
            return "Nothing new since last check."

        return self.format_notification(digest["items"])

    def verify_dna_integrity(self):
        """Safety check: verify DNA files haven't been modified by this module.
        Returns True if DNA is intact (read-only constraint verified)."""
        dna = self.load_dna()
        for role, data in dna.items():
            fpath = data.get("file")
            if fpath and os.path.isfile(fpath):
                current_mtime = os.path.getmtime(fpath)
                cached_mtime = data.get("mtime")
                if cached_mtime and current_mtime != cached_mtime:
                    return {
                        "ok": False,
                        "warning": "DNA file {} was modified EXTERNALLY (not by StyleAdapter)".format(fpath),
                        "role": role
                    }
        return {"ok": True, "message": "DNA integrity verified"}
