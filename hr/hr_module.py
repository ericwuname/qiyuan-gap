# -*- coding: utf-8 -*-
# HR module v2.0 - reads skill source from CDRIVE (~/.agents/skills/)
# D: drive is backup only. Dedup + CDRIVE sync included.

import os, io, json, sqlite3, re, yaml
from datetime import datetime

C_SKILLS_ROOT = os.path.expanduser(r"~\.agents\skills")

SKILL_OWNER_OVERRIDES = {
    "chushi": "\u4eba\u529b\u603b\u76d1",
    "wangwen-dashi": "chief-narrative-designer",
    "chongzhen": "strategy-advisor",
    "hongmeng": "strategy-advisor",
    "r0/qidian-male-expert": "chief-narrative-designer",
}

OWNER_KEYWORDS = [
    ("hr-director", ["hr-", "communication-expert", "emotional-counselor",
     "dna-archivist", "conversation-banker", "contribution-analyst",
     "doc-gatekeeper", "retrospective-coach", "knowledge-architect",
     "sop-manager", "notion-", "ancient-ritual-expert", "piano-coach",
     "requirement-miner", "brainstorm-workshop"]),
    ("cfo-director", ["cfo-", "financial-", "legal-advisor"]),
    ("brand-designer", ["brand-designer", "brand-communication-expert"]),
    ("design-director", ["design-", "color-", "motion-designer",
     "visual-director", "font-designer", "interaction-designer",
     "interface-designer", "ux-architect", "figma", "mobile-adapter",
     "css-detail-polisher", "accessibility-specialist"]),
    ("devops-engineer", ["devops-engineer", "cloudflare-deploy",
     "netlify-deploy", "render-deploy", "vercel-deploy", "security-auditor"]),
    ("test-automation-engineer", ["test-automation-engineer"]),
    ("qa-reviewer", ["qa-reviewer", "qa-inspector", "proactive-defender",
     "js-error-checker"]),
    ("data-engineer", ["data-engineer", "jupyter-notebook"]),
    ("scrum-master", ["scrum-master"]),
    ("technical-writer", ["technical-writer", "pdf", "screenshot",
     "speech", "transcribe"]),
    ("chief-narrative-designer", ["chief-narrative-designer", "script-",
     "wangwen-", "literary-", "female-", "narratology-", "rhetoric-",
     "stylistics-", "text-", "linguistics-", "naming-", "world-building-",
     "genre-", "rhythm-", "hardcore-"]),
    ("strategy-advisor", ["strategy-advisor", "decision-", "define-goal",
     "org-management-expert", "market-strategy-expert",
     "quantitative-analyst", "trader-coach", "xiangyu-simulator"]),
    ("software-architect", ["software-architect", "software-dev-dept",
     "python-developer", "frontend-engineer-react"]),
    ("project-chief", ["project-chief", "chatgpt-apps"]),
    ("project-manager", ["project-manager", "execution-director"]),
    ("product-manager", ["product-manager"]),
    ("painting-master", ["painting-master"]),
]

TIER_MAP = {
    "\u6218\u7565\u987e\u95ee": "T1", "\u9879\u76ee\u603b\u76d1": "T1",
    "\u4ea7\u54c1\u7ecf\u7406": "T1", "\u4eba\u529b\u603b\u76d1": "T1",
    "\u8d22\u52a1\u603b\u76d1": "T1", "\u519b\u5e08": "T1",
    "\u9879\u76ee\u603b\u7ba1": "T2", "\u67b6\u6784\u5e08": "T2",
    "\u8bbe\u8ba1\u603b\u76d1": "T2", "\u6267\u884c\u603b\u76d1": "T2",
    "\u8d28\u91cf\u8bc4\u5ba1": "T2",
    "Scrum Master": "T3", "\u6d4b\u8bd5\u81ea\u52a8\u5316": "T3",
    "DevOps": "T3", "\u6570\u636e\u5de5\u7a0b\u5e08": "T3",
    "\u5b89\u5168\u5ba1\u8ba1": "T3", "\u6280\u672f\u6587\u6863": "T3",
    "\u8d28\u68c0\u5458": "T4", "JS\u9519\u8bef\u68c0\u67e5": "T4",
    "\u9700\u6c42\u6316\u6398\u5e08": "Shared", "\u5934\u8111\u98ce\u66b4": "Shared",
    "\u9e3f\u8499\u4e4b\u521d": "Shared",
}

DEPT_MAP = {
    "\u6218\u7565\u987e\u95ee": "T1-\u6218\u7565\u51b3\u7b56",
    "\u9879\u76ee\u603b\u76d1": "T1-\u9879\u76ee\u6307\u6325",
    "\u4ea7\u54c1\u7ecf\u7406": "T1-\u4ea7\u54c1\u7ba1\u7406",
    "\u4eba\u529b\u603b\u76d1": "T1-\u4eba\u529b\u8d44\u6e90",
    "\u8d22\u52a1\u603b\u76d1": "T1-\u8d22\u52a1\u6cd5\u52a1",
    "\u519b\u5e08": "T1-\u72ec\u7acb\u5ba1\u8ba1",
    "\u9879\u76ee\u603b\u7ba1": "T2-\u9879\u76ee\u7ba1\u7406",
    "\u67b6\u6784\u5e08": "T2-\u6280\u672f\u67b6\u6784",
    "\u8bbe\u8ba1\u603b\u76d1": "T2-\u8bbe\u8ba1",
    "\u6267\u884c\u603b\u76d1": "T2-\u6267\u884c\u7ba1\u7406",
    "\u8d28\u91cf\u8bc4\u5ba1": "T2-\u8d28\u91cf\u4fdd\u969c",
    "Scrum Master": "T3-\u654f\u6377\u534f\u4f5c",
    "\u6d4b\u8bd5\u81ea\u52a8\u5316": "T3-\u8d28\u91cf\u5de5\u7a0b",
    "DevOps": "T3-\u8fd0\u7ef4\u5de5\u7a0b",
    "\u6570\u636e\u5de5\u7a0b\u5e08": "T3-\u6570\u636e\u5de5\u7a0b",
    "\u5b89\u5168\u5ba1\u8ba1": "T3-\u5b89\u5168\u5de5\u7a0b",
    "\u6280\u672f\u6587\u6863": "T3-\u6280\u672f\u5199\u4f5c",
    "\u8d28\u68c0\u5458": "T4-\u8d28\u91cf\u6267\u884c",
    "JS\u9519\u8bef\u68c0\u67e5": "T4-\u8d28\u91cf\u6267\u884c",
    "\u9700\u6c42\u6316\u6398\u5e08": "Shared-\u9700\u6c42\u5de5\u7a0b",
    "\u5934\u8111\u98ce\u66b4": "Shared-\u521b\u65b0",
    "\u9e3f\u8499\u4e4b\u521d": "Shared-\u521b\u65b0",
}


class HRModule:
    def __init__(self, brain_dir=None):
        if brain_dir is None:
            brain_dir = os.path.dirname(os.path.abspath(__file__))
        if "hr" in os.path.basename(brain_dir):
            brain_dir = os.path.dirname(brain_dir)
        self.hr_dir = os.path.join(brain_dir, "hr")
        os.makedirs(self.hr_dir, exist_ok=True)
        self.db_path = os.path.join(self.hr_dir, "hr.db")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT,
                tier TEXT,
                capability_score REAL DEFAULT 0,
                status TEXT DEFAULT "active",
                skills TEXT DEFAULT "",
                department TEXT DEFAULT "",
                first_seen TEXT,
                last_assessment TEXT,
                notes TEXT DEFAULT "",
                created_at TEXT DEFAULT (datetime("now","localtime"))
            );
            CREATE TABLE IF NOT EXISTS skill_versions (
                skill_name TEXT PRIMARY KEY,
                version TEXT,
                owner TEXT,
                owner_role TEXT,
                call_permission TEXT DEFAULT "all",
                last_updated TEXT,
                status TEXT DEFAULT "active",
                category TEXT DEFAULT "",
                description TEXT DEFAULT "",
                display_name TEXT DEFAULT ""
            );
            CREATE TABLE IF NOT EXISTS recruitments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position TEXT NOT NULL,
                department TEXT DEFAULT "",
                status TEXT DEFAULT "open",
                urgency TEXT DEFAULT "normal",
                created_at TEXT DEFAULT (datetime("now","localtime")),
                filled_at TEXT,
                notes TEXT DEFAULT ""
            );
            CREATE TABLE IF NOT EXISTS capability_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gap_area TEXT NOT NULL,
                severity TEXT DEFAULT "medium",
                related_role TEXT,
                status TEXT DEFAULT "open",
                created_at TEXT DEFAULT (datetime("now","localtime")),
                resolved_at TEXT,
                notes TEXT DEFAULT ""
            );
        """)
        try:
            conn.execute("ALTER TABLE skill_versions ADD COLUMN display_name TEXT DEFAULT ''")
        except:
            pass
        conn.commit()
        conn.close()    # --- Employee Ingest from D: drive ---
    def ingest(self, hr_root=None):
        if hr_root is None:
            hr_root = os.path.join(
                os.path.dirname(os.path.dirname(self.hr_dir)), "06_人力资源")
        results = {"ok": True, "employees": 0, "deduped": 0, "db_path": self.db_path}
        conn = sqlite3.connect(self.db_path)
        kb_path = os.path.join(hr_root, "组织能力看板.md")
        seen_roles = set()
        if os.path.isfile(kb_path):
            try:
                with io.open(kb_path, "r", encoding="utf-8") as f:
                    text = f.read()
                for m in re.finditer(
                    r"\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*([\d.]+)\s*\|\s*([^|]+)\s*\|",
                    text
                ):
                    eid = "EMP-" + m.group(1).zfill(3)
                    role = m.group(2).strip()
                    score = float(m.group(3))
                    if role in seen_roles:
                        results["deduped"] += 1
                        continue
                    seen_roles.add(role)
                    tier = TIER_MAP.get(role, "Unknown")
                    dept = DEPT_MAP.get(role, f"{tier}-通用")
                    conn.execute(
                        "INSERT OR REPLACE INTO employees "
                        "(id, name, role, tier, capability_score, department, "
                        "last_assessment, status) VALUES (?,?,?,?,?,?,?,?)",
                        (eid, role, role, tier, score, dept,
                         datetime.now().strftime("%Y-%m-%d"), "active")
                    )
                    results["employees"] += 1
            except Exception as e:
                results["error"] = str(e)[:200]
        conn.commit()
        conn.close()
        return results

    # --- Skill Ingest from CDRIVE ---
    def ingest_skills_from_cdrive(self):
        results = {"ok": True, "total_found": 0, "ingested": 0, "errors": 0}
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        for skill_rel, skill_md_path in self._walk_skills(C_SKILLS_ROOT):
            results["total_found"] += 1
            try:
                with io.open(skill_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                name = skill_rel.split("/")[-1]
                desc = ""
                display_name = ""
                if content.startswith("---"):
                    try:
                        end = content.index("---", 3)
                        fm = yaml.safe_load(content[3:end])
                        name = fm.get("name", name) if fm else name
                        desc = (fm.get("description", "") or "") if fm else ""
                        meta = fm.get("metadata", {}) if fm else {}
                        display_name = meta.get("display-name", "") if meta else ""
                        if not desc and meta and meta.get("short-description"):
                            desc = meta["short-description"]
                    except Exception:
                        pass
                category = self._skill_category(skill_rel)
                owner = self._skill_owner(skill_rel, name, category)
                mtime = os.path.getmtime(skill_md_path)
                last_updated = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                if desc and len(desc) > 200:
                    desc = desc[:200] + "..."
                conn.execute(
                    "INSERT OR REPLACE INTO skill_versions "
                    "(skill_name, version, owner, description, display_name, "
                    "category, last_updated, status, call_permission) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (skill_rel, "1.0", owner, desc, display_name,
                     category, last_updated, "active", "public")
                )
                results["ingested"] += 1
            except Exception as e:
                results["errors"] += 1
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO skill_versions "
                        "(skill_name, version, status, description) VALUES (?,?,?,?)",
                        (skill_rel, "1.0", "active", f"ERROR: {str(e)[:100]}")
                    )
                except Exception:
                    pass
        conn.commit()
        conn.close()
        return results

    def _walk_skills(self, base):
        pairs = []
        try:
            for entry in sorted(os.listdir(base)):
                ep = os.path.join(base, entry)
                if not os.path.isdir(ep) or entry.startswith("."):
                    continue
                sm = os.path.join(ep, "SKILL.md")
                if os.path.isfile(sm):
                    pairs.append((entry, sm))
                for sub in sorted(os.listdir(ep)):
                    sp = os.path.join(ep, sub)
                    if not os.path.isdir(sp) or sub.startswith("."):
                        continue
                    ssm = os.path.join(sp, "SKILL.md")
                    if os.path.isfile(ssm):
                        pairs.append((entry + "/" + sub, ssm))
        except Exception:
            pass
        return pairs

    def _skill_category(self, skill_rel):
        if "公司核心/Tier1_高层" in skill_rel:
            return "T1"
        if "公司核心/Tier2_中层" in skill_rel:
            return "T2"
        if "公司核心/Tier3_基层" in skill_rel:
            return "T3"
        if "公司核心/Tier4_执行" in skill_rel:
            return "T4"
        if "公司核心/共享资源" in skill_rel:
            return "Shared"
        return "Unknown"

    def _skill_owner(self, skill_rel, name, category):
        if name in SKILL_OWNER_OVERRIDES:
            return SKILL_OWNER_OVERRIDES[name]
        if skill_rel in SKILL_OWNER_OVERRIDES:
            return SKILL_OWNER_OVERRIDES[skill_rel]
        cat_defaults = {
            "T1": "strategy-advisor", "T2": "project-manager",
            "T3": "devops-engineer", "T4": "qa-inspector",
            "Shared": "hr-director",
        }
        for owner_name, keywords in OWNER_KEYWORDS:
            for kw in keywords:
                if kw.endswith("-"):
                    if name.startswith(kw):
                        return owner_name
                elif name == kw:
                    return owner_name
        return cat_defaults.get(category, "hr-director")

    def employee(self, name=None):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        if name:
            rows = conn.execute(
                "SELECT * FROM employees WHERE name LIKE ? OR id = ?",
                ("%" + name + "%", name)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM employees ORDER BY capability_score DESC LIMIT 30"
            ).fetchall()
        conn.close()
        return {"ok": True, "count": len(rows), "employees": [dict(r) for r in rows]}

    def gaps(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM capability_gaps WHERE status = ? ORDER BY created_at DESC",
            ("open",)
        ).fetchall()
        conn.close()
        return {"ok": True, "count": len(rows), "gaps": [dict(r) for r in rows]}

    def dashboard(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        te = conn.execute(
            "SELECT COUNT(*) as c FROM employees WHERE status = ?", ("active",)
        ).fetchone()["c"]
        ts = conn.execute(
            "SELECT COUNT(*) as c FROM skill_versions WHERE status = ?", ("active",)
        ).fetchone()["c"]
        og = conn.execute(
            "SELECT COUNT(*) as c FROM capability_gaps WHERE status = ?", ("open",)
        ).fetchone()["c"]
        ore = conn.execute(
            "SELECT COUNT(*) as c FROM recruitments WHERE status = ?", ("open",)
        ).fetchone()["c"]
        top = conn.execute(
            "SELECT name, role, capability_score FROM employees "
            "ORDER BY capability_score DESC LIMIT 5"
        ).fetchall()
        conn.close()
        return {
            "ok": True, "total_employees": te, "total_skills": ts,
            "open_gaps": og, "open_recruitments": ore,
            "top_employees": [dict(r) for r in top]
        }

    def recruit_add(self, position, department="", urgency="normal", notes=""):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO recruitments (position, department, urgency, notes) "
            "VALUES (?,?,?,?)",
            (position, department, urgency, notes)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "action": "recruit_add", "position": position}

    def employees_full(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT * FROM employees
               ORDER BY CASE tier
                 WHEN "T1" THEN 1 WHEN "T2" THEN 2 WHEN "T3" THEN 3
                 WHEN "T4" THEN 4 WHEN "Shared" THEN 5 ELSE 6 END,
               capability_score DESC"""
        ).fetchall()
        conn.close()
        return {"ok": True, "count": len(rows), "employees": [dict(r) for r in rows]}

    def org_chart(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        tiers = {
            "T1": {"name": "T1 战略决策层", "tier": "T1", "children": []},
            "T2": {"name": "T2 任务转化层", "tier": "T2", "children": []},
            "T3": {"name": "T3 执行支撑层", "tier": "T3", "children": []},
            "T4": {"name": "T4 质量保障层", "tier": "T4", "children": []},
            "Shared": {"name": "共享资源", "tier": "Shared", "children": []},
        }
        rows = conn.execute(
            """SELECT name, role, tier, department, capability_score
               FROM employees WHERE status="active"
               ORDER BY tier, capability_score DESC"""
        ).fetchall()
        conn.close()
        for r in rows:
            t = r["tier"] or "Shared"
            if t in tiers:
                tiers[t]["children"].append({
                    "name": r["name"],
                    "role": r["role"],
                    "department": r["department"] or "",
                    "score": r["capability_score"] or 0,
                    "tier": t,
                })
        tree = {
            "name": "CEO 吴涛",
            "role": "CEO",
            "tier": "CEO",
            "children": [
                {"name": "军师", "role": "CVO 独立审计", "tier": "CVO",
                 "score": 8.0, "department": "独立审计"},
                tiers["T1"], tiers["T2"], tiers["T3"], tiers["T4"],
                tiers["Shared"]
            ]
        }
        return {"ok": True, "org_chart": tree}

    def skills_detail(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM skill_versions WHERE status='active' "
            "ORDER BY category, skill_name"
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                "skill_name": r["skill_name"],
                "display_name": r["display_name"] or "",
                "owner": r["owner"] or "",
                "category": r["category"] or "",
                "status": r["status"],
                "description": r["description"] or "",
                "version": r["version"] or "",
                "last_updated": r["last_updated"] or "",
            })
        return {"ok": True, "count": len(result), "skills": result}

    def rebuild_all(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM employees")
        conn.execute("DELETE FROM skill_versions")
        conn.commit()
        conn.close()
        emp_result = self.ingest()
        skill_result = self.ingest_skills_from_cdrive()
        return {"ok": True, "employees": emp_result, "skills": skill_result}

    def dedup_employees(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, role, capability_score FROM employees "
            "ORDER BY role, capability_score DESC"
        ).fetchall()
        seen = {}
        to_delete = []
        for r in rows:
            if r["role"] in seen:
                to_delete.append(r["id"])
            else:
                seen[r["role"]] = r["id"]
        for eid in to_delete:
            conn.execute("DELETE FROM employees WHERE id = ?", (eid,))
        conn.commit()
        conn.close()
        return {"ok": True, "deleted": len(to_delete), "ids": to_delete}