# -*- coding: utf-8 -*-
"""启元智能 · 短期记忆工作区 (SQLite) · P2-2 session管理"""

import io, os, sqlite3, time, uuid
from typing import Optional


class Workspace:
    """Key-value short-term memory backed by SQLite with TTL + session isolation."""

    def __init__(self, db_path: str, session_id: str = None):
        self.db_path = db_path
        self.session_id = session_id or str(uuid.uuid4())
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspace (
                    key TEXT,
                    value TEXT NOT NULL,
                    session_id TEXT NOT NULL DEFAULT 'default',
                    created_at REAL NOT NULL,
                    ttl INTEGER NOT NULL DEFAULT 3600,
                    PRIMARY KEY (key, session_id)
                )
            """)
            # Migration: add session_id column if missing
            try:
                conn.execute("ALTER TABLE workspace ADD COLUMN session_id TEXT NOT NULL DEFAULT 'default'")
            except sqlite3.OperationalError:
                pass  # column already exists
            conn.commit()

    def set(self, key: str, value: str, ttl: int = 3600):
        """Write a key-value pair for current session. ttl in seconds."""
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO workspace (key, value, session_id, created_at, ttl) VALUES (?, ?, ?, ?, ?)",
                (key, value, self.session_id, now, ttl),
            )
            conn.commit()

    def get(self, key: str) -> Optional[str]:
        """Read a key. Cross-session read allowed. Returns None if expired."""
        now = time.time()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value, created_at, ttl FROM workspace WHERE key = ? ORDER BY created_at DESC LIMIT 1",
                (key,),
            ).fetchone()
        if row is None:
            return None
        if row["created_at"] + row["ttl"] < now:
            self.delete(key)
            return None
        return row["value"]

    def list_keys(self) -> list:
        """List all non-expired keys (all sessions)."""
        now = time.time()
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT key, session_id, created_at, ttl FROM workspace"
            ).fetchall()
        valid = []
        expired = []
        for row in rows:
            if row["created_at"] + row["ttl"] < now:
                expired.append((row["key"], row["session_id"]))
            else:
                valid.append(row["key"])
        for key, sid in expired:
            self.delete(key, sid)
        return valid

    def list_my_keys(self) -> list:
        """List keys belonging to current session only."""
        now = time.time()
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT key, created_at, ttl FROM workspace WHERE session_id = ?",
                (self.session_id,)
            ).fetchall()
        valid = []
        for row in rows:
            if row["created_at"] + row["ttl"] >= now:
                valid.append(row["key"])
        return valid

    def delete(self, key: str, session_id: str = None):
        """Delete a key. If session_id specified, only delete that session's entry."""
        with self._get_conn() as conn:
            if session_id:
                conn.execute("DELETE FROM workspace WHERE key = ? AND session_id = ?", (key, session_id))
            else:
                conn.execute("DELETE FROM workspace WHERE key = ?", (key,))
            conn.commit()

    def clear_expired(self):
        """Remove all expired entries across all sessions."""
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("DELETE FROM workspace WHERE created_at + ttl < ?", (now,))
            conn.commit()

    def cleanup_session(self, session_id: str = None):
        """Clean up all entries for a given session (or current if None)."""
        sid = session_id or self.session_id
        with self._get_conn() as conn:
            conn.execute("DELETE FROM workspace WHERE session_id = ?", (sid,))
            conn.commit()

    def status(self) -> dict:
        """Return workspace status with session info."""
        keys = self.list_keys()
        my_keys = self.list_my_keys()
        return {
            "ok": True,
            "keys": len(keys),
            "my_keys": len(my_keys),
            "session_id": self.session_id[:8] + "...",
            "total_sessions": self._count_sessions()
        }

    def _count_sessions(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(DISTINCT session_id) as cnt FROM workspace").fetchone()
            return row["cnt"] if row else 0