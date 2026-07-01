# -*- coding: utf-8 -*-
"""Probe D: Agency Index (自主决策度)

Measures how much of the system output is attributed to internal reasoning
vs direct quotation from knowledge base / rules.

agency_ratio = (output_length - direct_quote_length) / output_length

Integration: called after brain ask / brain act to write into probe_agency table.
"""

import io, os, sqlite3, uuid
from datetime import datetime


class AgencyProbe:
    """Probe D: measures autonomy of system decisions.

    Low agency_ratio (near 0): mostly quoting known rules/docs.
    High agency_ratio (near 1): generating novel reasoning.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        self._ensure_table()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS probe_agency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT DEFAULT (datetime(\"now\")),
                    internal_drive_ratio REAL,
                    external_drive_ratio REAL,
                    agency_ratio REAL
                )
            """)
            conn.commit()

    def record(self, output_text, quoted_sources=None):
        """Record agency for a single request.

        Args:
            output_text: full output string
            quoted_sources: list of (source_name, quoted_text) tuples

        Returns:
            dict with agency_ratio and related metrics
        """
        request_id = str(uuid.uuid4())
        result = {"agency_ratio": 0.0, "internal_drive_ratio": 0.0, "external_drive_ratio": 0.0}

        try:
            output_length = len(output_text) if output_text else 0

            if output_length == 0:
                self._write(request_id, 0.0, 0.0, 0.0)
                return result

            # Calculate total length of direct quotes
            direct_quote_length = 0
            if quoted_sources:
                for _src, quoted_text in quoted_sources:
                    if quoted_text:
                        direct_quote_length += len(quoted_text)

            # Cap at output_length
            direct_quote_length = min(direct_quote_length, output_length)

            # agency_ratio: how much is NOT direct quote
            agency_ratio = (output_length - direct_quote_length) / output_length
            agency_ratio = round(max(0.0, min(1.0, agency_ratio)), 4)

            external_drive_ratio = direct_quote_length / output_length
            internal_drive_ratio = 1.0 - external_drive_ratio

            result = {
                "agency_ratio": agency_ratio,
                "internal_drive_ratio": round(internal_drive_ratio, 4),
                "external_drive_ratio": round(external_drive_ratio, 4)
            }

            self._write(request_id, agency_ratio, internal_drive_ratio, external_drive_ratio)
        except Exception:
            pass  # Probe failure must never crash the system

        return result

    def _write(self, request_id, agency_ratio, internal_drive, external_drive):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO probe_agency (request_id, agency_ratio, internal_drive_ratio, external_drive_ratio) VALUES (?, ?, ?, ?)",
                    (request_id, agency_ratio, internal_drive, external_drive)
                )
                conn.commit()
        except Exception:
            pass

    def latest(self):
        """Return the most recent agency reading."""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM probe_agency ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    return {
                        "agency_ratio": row["agency_ratio"],
                        "internal_drive_ratio": row["internal_drive_ratio"],
                        "external_drive_ratio": row["external_drive_ratio"],
                        "timestamp": row["timestamp"]
                    }
        except Exception:
            pass
        return {"agency_ratio": None, "timestamp": None}

    def stats(self, hours=24):
        """Return agency statistics for the given time window."""
        try:
            with self._get_conn() as conn:
                cutoff = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if hours == 0 else None
                if hours > 0:
                    rows = conn.execute(
                        "SELECT agency_ratio FROM probe_agency WHERE timestamp >= datetime(\"now\", \"-\" || ? || \" hours\")",
                        (str(hours),)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT agency_ratio FROM probe_agency"
                    ).fetchall()

                if not rows:
                    return {"count": 0, "avg": None, "min": None, "max": None}

                vals = [r["agency_ratio"] for r in rows]
                return {
                    "count": len(vals),
                    "avg": round(sum(vals) / len(vals), 4),
                    "min": round(min(vals), 4),
                    "max": round(max(vals), 4)
                }
        except Exception:
            pass
        return {"count": 0, "avg": None, "min": None, "max": None}


# Module-level convenience
_instance = None


def get_probe(db_path=None):
    global _instance
    if _instance is None and db_path:
        _instance = AgencyProbe(db_path)
    return _instance
