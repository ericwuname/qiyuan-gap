# -*- coding: utf-8 -*-
"""启元智能 · 知识内化引擎 (DigestEngine)

闭环: 扫描变更 → 提取洞察 → 优先级排序 → 推送通知 → 确认归档
"只输入不内化就是失败"

依赖: FAISS/BGE 语义摘要 (可选), 文件哈希变更检测, SQLite 状态跟踪
"""
import io, os, sys, json, hashlib, re, time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

# ── 路径计算 ──────────────────────────────────────────────────
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))      # brain/memory/
_BRAIN_DIR = os.path.dirname(_MODULE_DIR)                      # brain/
_ROOT_DIR = os.path.dirname(_BRAIN_DIR)                        # 启元智能/
KB_ROOT = os.path.join(_ROOT_DIR, "05_组织知识库")
DB_PATH = os.path.join(_BRAIN_DIR, "digest", "digest.db")

# ── 关键词权重（用于优先级计算）─────────────────────────────
PRIORITY_KEYWORDS = {
    "反模式": 5, "反AI": 5, "禁区": 5, "铁律": 5,
    "事故": 4, "缺陷": 4, "失败": 4, "常见错误": 4,
    "规则": 3, "SOP": 3, "规范": 3, "标准": 3, "POL": 3,
    "模式": 2, "模板": 2, "方法论": 2, "最佳实践": 2,
    "新增": 1, "更新": 1, "迭代": 1,
}

# ── 摘要提取关键词 ──────────────────────────────────────────
SUMMARY_MARKERS = [
    "核心观点", "关键洞察", "一句话总结", "摘要", "概述",
    "核心原则", "核心规则", "铁律", "底线",
]


class DigestEngine:
    """知识内化引擎 —— 扫描、提取、排序、跟踪"""

    def __init__(self, kb_root: str = None, db_path: str = None):
        self.kb_root = kb_root or KB_ROOT
        self.db_path = db_path or DB_PATH
        self._memory_engine = None  # 懒加载

    # ── 数据库 ──────────────────────────────────────────────

    def _db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = __import__("sqlite3").connect(self.db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS digest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            file_mtime REAL,
            last_hash TEXT,
            last_digested TEXT,
            title TEXT,
            summary TEXT,
            extracted_insights TEXT,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            archived_at TEXT
        )""")
        # 迁移: 添加新列 (如果从旧版升级)
        for col, col_type in [
            ("file_mtime", "REAL"), ("priority", "INTEGER DEFAULT 0"),
            ("status", "TEXT DEFAULT 'pending'"), ("archived_at", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE digest_log ADD COLUMN {col} {col_type}")
            except __import__("sqlite3").OperationalError:
                pass
        conn.commit()
        return conn

    # ── 变更检测 ────────────────────────────────────────────

    def scan(self, since: str = None) -> List[Dict]:
        """扫描知识库变更，返回 insight 列表。
        
        Args:
            since: 时间范围，如 "7d", "24h", "1w", "2026-06-01"
        """
        conn = self._db()
        results = []
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M")
        cutoff = self._parse_since(since) if since else None

        for root, dirs, files in os.walk(self.kb_root):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.kb_root)
                mtime = os.path.getmtime(fpath)

                # 时间范围过滤
                if cutoff:
                    mtime_dt = datetime.fromtimestamp(mtime)
                    if mtime_dt < cutoff:
                        continue

                try:
                    with io.open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue

                file_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
                row = conn.execute(
                    "SELECT last_hash, status FROM digest_log WHERE file_path=?",
                    (rel_path,)
                ).fetchone()

                if row is None:
                    # 新文件
                    title, summary, insights, priority = self._extract(content, rel_path)
                    conn.execute(
                        "INSERT INTO digest_log(file_path,file_mtime,last_hash,last_digested,title,summary,extracted_insights,priority,status) VALUES(?,?,?,?,?,?,?,?,?)",
                        (rel_path, mtime, file_hash, now_str, title, summary,
                         json.dumps(insights, ensure_ascii=False), priority, "pending")
                    )
                    results.append({
                        "path": rel_path, "status": "new", "title": title,
                        "summary": summary, "insights": insights, "priority": priority,
                        "mtime": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    })
                elif row[0] != file_hash:
                    # 内容变更
                    old_status = row[1] or "pending"
                    title, summary, insights, priority = self._extract(content, rel_path)
                    conn.execute(
                        "UPDATE digest_log SET file_mtime=?,last_hash=?,last_digested=?,title=?,summary=?,extracted_insights=?,priority=?,status=? WHERE file_path=?",
                        (mtime, file_hash, now_str, title, summary,
                         json.dumps(insights, ensure_ascii=False), priority,
                         "pending" if old_status == "archived" else old_status, rel_path)
                    )
                    results.append({
                        "path": rel_path, "status": "changed", "title": title,
                        "summary": summary, "insights": insights, "priority": priority,
                        "mtime": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    })

        conn.commit()
        conn.close()
        return sorted(results, key=lambda x: (-x["priority"], x["path"]))

    # ── 语义提取 ────────────────────────────────────────────

    def _extract(self, content: str, rel_path: str = "") -> Tuple[str, str, List[str], int]:
        """从 Markdown 内容提取: 标题、摘要、洞察列表、优先级
        
        提取策略:
        1. 标题: 第一个 # 标题
        2. 摘要: SUMMARY_MARKERS 后的段落, 或第一个 >20字的非标题段落
        3. 洞察: 表格规则行, 或 ### 下要点
        4. 优先级: 基于关键词权重
        """
        lines = content.split("\n")
        title = os.path.splitext(os.path.basename(rel_path))[0] if rel_path else ""
        summary = ""
        insights = []
        priority = 0

        # ── 标题 ──
        for line in lines:
            s = line.strip()
            if s.startswith("# ") and not title.startswith("#"):
                title = s[2:].strip()
                break

        # ── 摘要 ──
        # 策略1: 查找摘要标记后的段落
        in_summary_section = False
        for line in lines:
            s = line.strip()
            for marker in SUMMARY_MARKERS:
                if marker in s and (s.startswith("**") or s.startswith("##") or s.startswith("###")):
                    in_summary_section = True
                    break
            if in_summary_section and len(s) > 20 and not s.startswith("#"):
                summary = s[:300]
                break
            if s.startswith("#") and in_summary_section:
                in_summary_section = False

        # 策略2: 回落——取第一段足够长的非标题文本
        if not summary:
            for line in lines:
                s = line.strip()
                if len(s) > 30 and not s.startswith("#") and not s.startswith("|") and not s.startswith("- "):
                    summary = s[:300]
                    break

        # ── 洞察提取 ──
        # 表格规则行 (如 | G22 | 防bug | ...)
        for line in lines:
            s = line.strip()
            if s.startswith("|") and s.count("|") >= 3:
                parts = [p.strip() for p in s.split("|") if p.strip()]
                if len(parts) >= 2:
                    # 过滤表头
                    if parts[0] in ("编号", "规则", "ID", "名称", "基因", "触发"):
                        continue
                    insight = f"[{parts[0]}] {parts[1][:120]}"
                    if insight not in insights:
                        insights.append(insight)

        # 编号列表 (如 G22 / INC-002 / P-001)
        rule_pattern = re.compile(
            r'^[\s]*[-*•]\s*(?:[【\[]?(G\d+|INC-\d+|P-\d+|R\d+|SOP-\d+|CVO-\d+|QA-\d+|STR-\d+|HR-\d+|PM-\d+)[】\]]?[\s:：]+)(.+)',
            re.IGNORECASE
        )
        for line in lines:
            m = rule_pattern.match(line)
            if m:
                rule_id = m.group(1)
                rule_text = m.group(2).strip()[:120]
                insight = f"[{rule_id}] {rule_text}"
                if insight not in insights:
                    insights.append(insight)

        # 限制洞察数量
        insights = insights[:20]

        # ── 优先级计算 ──
        combined = (title + " " + summary + " " + " ".join(insights)).lower()
        for keyword, weight in PRIORITY_KEYWORDS.items():
            if keyword in combined:
                priority += weight
        # 新增文件加分，但权重低于反模式
        if "new" in rel_path.lower() or "新增" in combined:
            priority += 1
        priority = min(priority, 10)

        return title, summary, insights, priority

    # ── 待处理报告 ──────────────────────────────────────────

    @staticmethod
    def _safe_str(s: str) -> str:
        """替换 emoji 为 ASCII 安全字符，兼容 Windows GBK 控制台"""
        replacements = {
            "🧠": "[脑]", "🆕": "[NEW]", "✅": "[OK]",
            "📦": "[AR]", "📄": "[DOC]", "📝": "[..]",
            "💡": "[!]", "━": "-", "─": "-",
            "═": "=", "║": "|", "╔": "+", "╗": "+",
            "╚": "+", "╝": "+", "╠": "+", "╣": "+",
            "╞": "+", "╡": "+", "╦": "+", "╩": "+",
            "╬": "+", "╤": "+", "╧": "+", "╫": "+",
            "╥": "+", "╨": "+", "╪": "+",
        }
        for old, new in replacements.items():
            s = s.replace(old, new)
        return s

    def report(self, top: int = None, status_filter: str = "pending") -> str:
        """生成可读的内化报告
        
        Args:
            top: 限制显示条数
            status_filter: pending/accepted/archived/all
        """
        items = self.get_pending(status_filter)
        if not items:
            return "[OK] 所有知识已内化，无待处理通知。"

        if top:
            items = items[:top]

        lines = ["", "=" * 58,
                 "  [脑] 启元智脑 · 知识内化通知",
                 "=" * 58]

        for i, item in enumerate(items, 1):
            status_icon = {"pending": "[NEW]", "accepted": "[OK]", "archived": "[AR]"}.get(
                item.get("status", "pending"), "[DOC]")
            lines.append(f"  {status_icon} [{item['status']}] P{item['priority']} {item['title'][:42]}")
            if item.get("summary"):
                lines.append(f"     .. {item['summary'][:80]}")
            for insight in item.get("insights", [])[:3]:
                lines.append(f"     !  {insight[:75]}")
            if i < len(items):
                lines.append("  " + "-" * 56)

        lines.append("=" * 58)
        lines.append(f"  共 {len(items)} 条待内化 · brain digest ack 确认全部")
        lines.append("=" * 58)
        return "\n".join(lines)

    def json_report(self, top: int = None, status_filter: str = "pending") -> List[Dict]:
        """返回 JSON 格式报告"""
        items = self.get_pending(status_filter)
        if top:
            items = items[:top]
        return items

    def get_pending(self, status_filter: str = "pending") -> List[Dict]:
        """获取待处理条目，按优先级降序"""
        conn = self._db()
        if status_filter == "all":
            rows = conn.execute(
                "SELECT file_path, title, summary, extracted_insights, priority, status, last_digested FROM digest_log ORDER BY priority DESC, last_digested DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT file_path, title, summary, extracted_insights, priority, status, last_digested FROM digest_log WHERE status=? ORDER BY priority DESC, last_digested DESC",
                (status_filter,)
            ).fetchall()
        conn.close()
        return [{
            "path": r[0], "title": r[1], "summary": r[2],
            "insights": json.loads(r[3]) if r[3] else [],
            "priority": r[4], "status": r[5], "digested_at": r[6],
        } for r in rows]

    # ── 状态管理 ────────────────────────────────────────────

    def ack(self, file_paths: List[str] = None):
        """确认内化: 将状态从 pending → accepted"""
        conn = self._db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if file_paths:
            for fp in file_paths:
                conn.execute(
                    "UPDATE digest_log SET status='accepted', archived_at=? WHERE file_path=?",
                    (now, fp)
                )
        else:
            conn.execute(
                "UPDATE digest_log SET status='accepted', archived_at=? WHERE status='pending'",
                (now,)
            )
        conn.commit()
        conn.close()

    def archive(self, file_paths: List[str] = None):
        """归档: 将状态从 accepted → archived"""
        conn = self._db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if file_paths:
            for fp in file_paths:
                conn.execute(
                    "UPDATE digest_log SET status='archived', archived_at=? WHERE file_path=?",
                    (now, fp)
                )
        else:
            conn.execute(
                "UPDATE digest_log SET status='archived', archived_at=? WHERE status='accepted'",
                (now,)
            )
        conn.commit()
        conn.close()

    # ── 统计 ────────────────────────────────────────────────

    def stats(self) -> Dict:
        """返回内化统计"""
        conn = self._db()
        total = conn.execute("SELECT count(*) FROM digest_log").fetchone()[0]
        pending = conn.execute("SELECT count(*) FROM digest_log WHERE status='pending'").fetchone()[0]
        accepted = conn.execute("SELECT count(*) FROM digest_log WHERE status='accepted'").fetchone()[0]
        archived = conn.execute("SELECT count(*) FROM digest_log WHERE status='archived'").fetchone()[0]
        conn.close()
        return {
            "total": total, "pending": pending,
            "accepted": accepted, "archived": archived,
        }

    # ── 时间解析 ────────────────────────────────────────────

    @staticmethod
    def _parse_since(since: str) -> Optional[datetime]:
        """解析时间范围字符串
        
        支持: "7d", "24h", "1w", "2w", "1m", "2026-06-01"
        """
        now = datetime.now()
        if not since:
            return None

        # 相对时间
        m = re.match(r'^(\d+)\s*([hdwm])$', since.lower())
        if m:
            num = int(m.group(1))
            unit = m.group(2)
            if unit == 'h':
                return now - timedelta(hours=num)
            elif unit == 'd':
                return now - timedelta(days=num)
            elif unit == 'w':
                return now - timedelta(weeks=num)
            elif unit == 'm':
                return now - timedelta(days=num * 30)

        # 绝对日期
        try:
            return datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            pass

        # 中文日期
        try:
            return datetime.strptime(since, "%Y年%m月%d日")
        except ValueError:
            pass

        print(f"[DigestEngine] 无法解析时间范围: {since}，将扫描全部")
        return None


# ── 便捷函数 (兼容旧版 digest.digest 接口) ─────────────────

_engine = None

def _get_engine() -> DigestEngine:
    global _engine
    if _engine is None:
        _engine = DigestEngine()
    return _engine


def scan(since: str = None) -> List[Dict]:
    return _get_engine().scan(since=since)


def pending() -> List[Dict]:
    return _get_engine().get_pending()


def ack(file_paths: List[str] = None):
    _get_engine().ack(file_paths)


def report(top: int = None, status_filter: str = "pending") -> str:
    return _get_engine().report(top=top, status_filter=status_filter)


def stats() -> Dict:
    return _get_engine().stats()


def json_report(top: int = None, status_filter: str = "pending") -> List[Dict]:
    return _get_engine().json_report(top=top, status_filter=status_filter)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    engine = DigestEngine()

    def safe_print(s):
        """GBK-safe print for Windows console"""
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("gbk", errors="replace").decode("gbk", errors="replace"))

    if "scan" in args:
        since = None
        for a in args:
            if a.startswith("--since="):
                since = a.split("=", 1)[1]
        results = engine.scan(since=since)
        safe_print(f"扫描完成: {len(results)} 篇变更")
        for r in sorted(results, key=lambda x: -x["priority"])[:20]:
            safe_print(f"  P{r['priority']} [{r['status']}] {r['title']}")
    elif "report" in args:
        top = None
        for a in args:
            if a.startswith("--top="):
                top = int(a.split("=", 1)[1])
        safe_print(engine.report(top=top))
    elif "ack" in args:
        engine.ack()
        safe_print("已确认全部待处理通知。")
    elif "stats" in args:
        s = engine.stats()
        safe_print(f"总计: {s['total']} · 待处理: {s['pending']} · 已确认: {s['accepted']} · 已归档: {s['archived']}")
    else:
        safe_print(engine.report())
