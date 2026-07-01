import io, os, hashlib, sqlite3, time, json, gzip, glob
from datetime import datetime, timedelta



# ?? P0-3 ???? + ??? ??????????????????????????????????????????
import msvcrt as _msvcrt
import time as _time

# ??????????????
_WORKSPACE_ROOT = os.path.normpath(os.path.realpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
))


def _validate_write_path(path):
    """??????????

    ???????(..)???????????????
    Raises ValueError on failure.
    """
    # ?????
    if not path or not path.strip():
        raise ValueError("??????")

    # ??????: ?????? ".." ??
    normalized = os.path.normpath(path)
    parts = normalized.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError("????????? .. ?????")

    # ????????
    abs_path = os.path.normpath(os.path.realpath(os.path.abspath(path)))
    if not abs_path.startswith(_WORKSPACE_ROOT + os.sep) and abs_path != _WORKSPACE_ROOT:
        raise ValueError(
            "????????? " + abs_path + " ????? " + _WORKSPACE_ROOT + " ?"
        )

    # ???????????
    if os.path.islink(path) or os.path.exists(path):
        real_path = os.path.normpath(os.path.realpath(path))
        if real_path != abs_path:
            if not real_path.startswith(_WORKSPACE_ROOT + os.sep) and real_path != _WORKSPACE_ROOT:
                raise ValueError(
                    "??????????? " + real_path + " ????? " + _WORKSPACE_ROOT + " ?"
                )

    return abs_path


def _acquire_file_lock(fpath, timeout=10.0):
    """????????Windows: msvcrt.LK_NBLCK??
    
    Returns: lock file handle (caller must close), or raises TimeoutError.
    """
    # ???????
    parent = os.path.dirname(fpath)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    locked = False
    deadline = _time.time() + timeout
    fh = open(fpath, "rb+")
    while not locked:
        try:
            _msvcrt.locking(fh.fileno(), _msvcrt.LK_NBLCK, 1)
            locked = True
        except IOError:
            if _time.time() > deadline:
                fh.close()
                raise TimeoutError("???????: " + fpath)
            _time.sleep(0.01)
    return fh


def _release_file_lock(fh):
    """???????????"""
    try:
        _msvcrt.locking(fh.fileno(), _msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    finally:
        try:
            fh.close()
        except Exception:
            pass

# ?? END P0-3 ???? + ??? ??????????????????????????????????????
# ?? P2-1 ???????? ??????????????????????????????????????????
MAX_DB_SIZE_BYTES = 10 * 1024 * 1024   # 10MB ??????
MAX_ROTATION_FILES = 5                  # ????5?????
# ?? END P2-1 ???????????????????????????????????????????????????????


class AuditEngine:
    """???????????????????????????????????

    P2-1 ???????????
    - ????????10MB/??
    - ????5?????
    - ??????? gzip ????
    - rotate() ????????
    - ??????????????????
    """

    MAX_DB_SIZE_BYTES = MAX_DB_SIZE_BYTES
    MAX_ROTATIONS = MAX_ROTATION_FILES

    def __init__(self, db_path: str):
        """?????????"""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        """??????????WAL???????"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA encoding='UTF-8'")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """??audit_logs????????"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    content_hash TEXT DEFAULT '',
                    result TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    version INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_target
                ON audit_logs(target_path)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_logs(timestamp)
            """)
            conn.commit()

            # P2-2: 添加 session_id 字段
            try:
                conn.execute("ALTER TABLE audit_logs ADD COLUMN session_id TEXT DEFAULT ''")
                conn.commit()
            except sqlite3.OperationalError:
                pass
    # ?? P2-1 ?????? ??????????????????????????????????????????


    @staticmethod
    def _get_session_id():
        """P2-2: 获取当前会话ID。优先从 CODEX_SESSION_ID 环境变量读取，否则生成 UUID。"""
        import uuid
        return os.environ.get("CODEX_SESSION_ID", "") or str(uuid.uuid4())

    def _get_db_size(self) -> int:
        """?????????????????????0?"""
        try:
            return os.path.getsize(self.db_path)
        except OSError:
            return 0

    def _wal_checkpoint(self):
        """?? WAL checkpoint?? WAL ??????????? WAL ???"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception:
            pass

    def _cleanup_wal_files(self):
        """?? WAL/SHM ?????"""
        wal_path = self.db_path + "-wal"
        shm_path = self.db_path + "-shm"
        for p in (wal_path, shm_path):
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError:
                pass

    def rotate(self) -> dict:
        """Manual log rotation: copy-truncate strategy (Windows-safe).

        Steps:
        1. WAL checkpoint flush
        2. shutil.copy2 DB to audit_YYYYMMDD_HHMMSS.db
        3. gzip compress the copy
        4. VACUUM + DELETE FROM audit_logs to clear original DB
        5. Remove oldest rotations beyond MAX_ROTATIONS (5)

        Returns:
            {ok, db_size_before, rotated_to, cleaned_count, db_size_after, message}
        """
        import shutil
        db_size_before = self._get_db_size()
        audit_dir = os.path.dirname(self.db_path)

        # 1. WAL checkpoint
        self._wal_checkpoint()
        self._cleanup_wal_files()

        # 2. Copy DB (Windows-safe: no file lock conflict)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_name = f"audit_{timestamp}.db"
        rotated_path = os.path.join(audit_dir, rotated_name)
        gz_path = rotated_path + ".gz"

        if not os.path.isfile(self.db_path) or os.path.getsize(self.db_path) == 0:
            return {
                "ok": True, "db_size_before": 0, "rotated_to": "",
                "cleaned_count": 0, "db_size_after": 0,
                "message": "DB empty or missing, skip rotation",
            }

        try:
            shutil.copy2(self.db_path, rotated_path)
        except OSError as e:
            return {
                "ok": False, "db_size_before": db_size_before, "rotated_to": "",
                "cleaned_count": 0, "db_size_after": 0,
                "message": "Copy failed: " + str(e),
            }

        # 3. gzip compress
        try:
            with open(rotated_path, 'rb') as f_in:
                with gzip.open(gz_path, 'wb', compresslevel=6) as f_out:
                    f_out.write(f_in.read())
            os.remove(rotated_path)
        except Exception:
            gz_path = rotated_path  # keep uncompressed if gzip fails

        # 4. Truncate original DB (VACUUM + DELETE)
        try:
            self._wal_checkpoint()
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM audit_logs")
            conn.commit()
            conn.execute("VACUUM")
            conn.commit()
            conn.close()
        except Exception:
            # If truncate fails, the copy is still safe
            pass

        # 5. Clean old rotations (keep MAX_ROTATIONS=5 newest)
        pattern = os.path.join(audit_dir, "audit_*.db.gz")
        all_rotations = sorted(glob.glob(pattern), reverse=True)
        cleaned_count = 0
        for old_file in all_rotations[self.MAX_ROTATIONS:]:
            try:
                os.remove(old_file)
                cleaned_count += 1
            except OSError:
                pass

        db_size_after = self._get_db_size()

        return {
            "ok": True,
            "db_size_before": db_size_before,
            "rotated_to": os.path.basename(gz_path),
            "cleaned_count": cleaned_count,
            "db_size_after": db_size_after,
            "message": "Rotated: " + os.path.basename(gz_path),
        }

    def _check_auto_rotate(self):
        """?????????????????????

        ??? log_write / log_read ?????
        """
        try:
            if self._get_db_size() >= self.MAX_DB_SIZE_BYTES:
                self.rotate()
        except Exception:
            pass

    # ?? END P2-1 ???????????????????????????????????????????????????

    def log_write(self, target_path: str, operator: str, content_hash: str,
                  result: str, details: str = "", version: int = 0,
                  session_id: str = None):
        """写操作日志（P2-2: 自动记录 session_id）"""
        if session_id is None:
            session_id = self._get_session_id()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO audit_logs
                   (timestamp, action, target_path, operator, content_hash, result, details, version, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, 'write', target_path, operator, content_hash, result, details, version, session_id)
            )
            conn.commit()
        self._check_auto_rotate()

    def log_read(self, target_path: str, operator: str,
                 session_id: str = None):
        """读操作日志（P2-2: 自动记录 session_id）"""
        if session_id is None:
            session_id = self._get_session_id()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO audit_logs
                   (timestamp, action, target_path, operator, content_hash, result, details, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, 'read', target_path, operator, '', 'ok', '', session_id)
            )
            conn.commit()
        self._check_auto_rotate()

    def query(self, since: str = None, action: str = None, limit: int = 100) -> list:
        """???????

        Args:
            since: ???? (YYYY-MM-DD ? YYYY-MM-DD HH:MM:SS)
            action: ?????? (write/read)
            limit: ?????
        """
        sql = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        if since:
            sql += " AND timestamp >= ?"
            params.append(since)
        if action:
            sql += " AND action = ?"
            params.append(action)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def file_history(self, target_path: str) -> list:
        """??????????????????"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT id, timestamp, content_hash, result, version
                   FROM audit_logs
                   WHERE target_path = ? AND action = 'write'
                   ORDER BY id ASC""",
                (target_path,)
            ).fetchall()
            return [dict(r) for r in rows]

    def conflict_check(self, target_path: str, window_seconds: int = 30) -> bool:
        """?????????????????

        ?? window_seconds ?????????? ? ???
        """
        cutoff = (datetime.now() - timedelta(seconds=window_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM audit_logs
                   WHERE target_path = ? AND action = 'write' AND timestamp >= ?""",
                (target_path, cutoff)
            ).fetchone()
            return row['cnt'] > 0

    def stats(self, since: str = None) -> dict:
        """???????/????/????/??????=30????????"""
        params = []
        where_clause = ""
        if since:
            where_clause = " WHERE timestamp >= ?"
            params.append(since)

        with self._get_conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) as cnt FROM audit_logs{where_clause}", params
            ).fetchone()['cnt']

            write_where = f" WHERE action='write'"
            write_params = []
            if since:
                write_where += " AND timestamp >= ?"
                write_params.append(since)
            writes = conn.execute(
                f"SELECT COUNT(*) as cnt FROM audit_logs{write_where}", write_params
            ).fetchone()['cnt']

            read_where = f" WHERE action='read'"
            read_params = []
            if since:
                read_where += " AND timestamp >= ?"
                read_params.append(since)
            reads = conn.execute(
                f"SELECT COUNT(*) as cnt FROM audit_logs{read_where}", read_params
            ).fetchone()['cnt']

        # ????30?????????
        conflicts = 0
        with self._get_conn() as conn:
            cutoff = (datetime.now() - timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                """SELECT target_path, COUNT(*) as cnt FROM audit_logs
                   WHERE action='write' AND timestamp >= ?
                   GROUP BY target_path HAVING cnt > 1""",
                (cutoff,)
            ).fetchall()
            conflicts = sum(r['cnt'] - 1 for r in rows)

        db_size_kb = round(self._get_db_size() / 1024, 1)

        # P2-2: 按 session_id 统计
        session_stats = []
        with self._get_conn() as conn:
            session_sql = "SELECT session_id, COUNT(*) as cnt FROM audit_logs"
            session_params = []
            if since:
                session_sql += " WHERE timestamp >= ?"
                session_params.append(since)
            session_sql += " GROUP BY session_id ORDER BY cnt DESC LIMIT 20"
            session_rows = conn.execute(session_sql, session_params).fetchall()
            session_stats = [{"session_id": r["session_id"] or "(empty)", "ops": r["cnt"]} for r in session_rows]

        return {
            "total_ops": total,
            "writes": writes,
            "reads": reads,
            "conflicts": conflicts,
            "db_size_kb": db_size_kb,
            "sessions": len(session_stats),
            "session_stats": session_stats,
        }

    def status(self) -> dict:
        """?????????? brain status ????"""
        try:
            s = self.stats()
            return {
                "ok": True,
                "total_logs": s["total_ops"],
                "db_size_kb": s["db_size_kb"],
            }
        except Exception as ex:
            return {"ok": False, "error": str(ex)}


# ???????????????????????????????????????????????????????????????
# safe_write ? ??????
# ???????????????????????????????????????????????????????????????

def _compute_hash(text: str) -> str:
    """?????MD5???"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def _next_version_path(path: str, version: int) -> str:
    """?????????file.md ? file_v2.md ? file_v3.md"""
    base, ext = os.path.splitext(path)
    return f"{base}_v{version}{ext}"


def safe_write(path: str, content: str, operator: str = "codex",
               db_path: str = None, conflict_window: int = 30,
               lock_timeout: float = 10.0) -> dict:
    """????????? ? ???? ? ??? ? ?? ? ?????

    P0-3???
    - ????????? .. ???
    - ???????
    - ???????????
    - ??????msvcrt???????

    Args:
        path: ????????
        content: ?????????
        operator: ?????
        db_path: ?????????None???????
        conflict_window: ?????????
        lock_timeout: ????????

    Returns:
        {ok, path, version, hash, message}
    """
    # P0-3 0. ????????????
    try:
        validated_path = _validate_write_path(path)
    except ValueError as e:
        return {
            "ok": False,
            "path": path,
            "version": 0,
            "hash": "",
            "message": str(e),
        }

    if db_path is None:
        brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(brain_dir, 'audit', 'audit.db')

    engine = AuditEngine(db_path)

    # 1. ????
    if engine.conflict_check(path, conflict_window):
        return {
            "ok": False,
            "path": path,
            "version": 0,
            "hash": "",
            "message": "???" + str(conflict_window) + "????????????????",
        }

    # 2. ???? ? ????
    version = 1
    actual_path = validated_path
    if os.path.isfile(validated_path):
        history = engine.file_history(validated_path)
        version = len(history) + 1
        actual_path = _next_version_path(validated_path, version)

    # 3. 写入 + 加锁 (UTF-8 no BOM, P2-1: 使用 FileLock 跨进程文件锁)
    content_hash = _compute_hash(content)
    try:
        os.makedirs(os.path.dirname(actual_path), exist_ok=True)
        from file_lock import FileLock as _FileLock
        lock_path = actual_path + ".lock"
        with _FileLock(lock_path, timeout=lock_timeout):
            with io.open(actual_path, "w", encoding="utf-8") as fh:
                fh.write(content)
    except TimeoutError as e:
        return {
            "ok": False,
            "path": actual_path,
            "version": version,
            "hash": content_hash,
            "message": "lock timeout: " + str(e),
        }
    except Exception as ex:
        return {
            "ok": False,
            "path": actual_path,
            "version": version,
            "hash": content_hash,
            "message": "write failed: " + str(ex),
        }
    # 4. ??????
    engine.log_write(
        target_path=path,
        operator=operator,
        content_hash=content_hash,
        result='ok',
        details="Written to: " + actual_path,
        version=version,
    )

    return {
        "ok": True,
        "path": actual_path,
        "version": version,
        "hash": content_hash,
        "message": "????",
    }
