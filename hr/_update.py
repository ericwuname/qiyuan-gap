import io, os, sqlite3, re

# Resolve relative to this script location
import sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(_script_dir, "hr_module.py")
with io.open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_code = """
    def employees_full(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
\"\"\"SELECT * FROM employees ORDER BY CASE tier WHEN 'T1' THEN 1 WHEN 'T2' THEN 2 WHEN 'T3' THEN 3 WHEN 'T4' THEN 4 ELSE 5 END, capability_score DESC\"\"\"
        ).fetchall()
        conn.close()
        return {"ok": True, "count": len(rows), "employees": [dict(r) for r in rows]}

    def org_chart(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        tiers = {
            "T1": {"name": "T1 战略决策层", "children": []},
            "T2": {"name": "T2 任务转化层", "children": []},
            "T3": {"name": "T3 执行支撑层", "children": []},
            "T4": {"name": "T4 质量保障层", "children": []},
            "Shared": {"name": "共享资源", "children": []},
        }
        rows = conn.execute(
\"\"\"SELECT name, role, tier, department, capability_score FROM employees WHERE status='active' ORDER BY tier, capability_score DESC\"\"\"
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
                })
        tree = {
            "name": "CEO 吴涛",
            "role": "CEO",
            "children": [
                {"name": "军师 (独立审计)", "role": "CVO", "score": 8.0},
                tiers["T1"], tiers["T2"], tiers["T3"], tiers["T4"], tiers["Shared"]
            ]
        }
        return {"ok": True, "org_chart": tree}

    def skills_detail(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
\"\"\"SELECT * FROM skill_versions WHERE status='active' ORDER BY category, skill_name\"\"\"
        ).fetchall()
        conn.close()
        skill_descs = {}
        for skills_root in [
            os.path.join(os.path.expanduser("~"), ".agents", "skills"),
            os.path.join(os.path.expanduser("~"), ".codex", "skills", ".system"),
        ]:
            if os.path.isdir(skills_root):
                for d in os.listdir(skills_root):
                    skill_md = os.path.join(skills_root, d, "SKILL.md")
                    if os.path.isfile(skill_md):
                        try:
                            with io.open(skill_md, "r", encoding="utf-8") as f:
                                text = f.read()
                            m = re.search(r'description:\\s*\"?([^\"\\n]+)\"?', text)
                            if m:
                                skill_descs[d] = m.group(1).strip()
                        except:
                            pass
                break
        result = []
        for r in rows:
            sn = r["skill_name"]
            result.append({
                "skill_name": sn,
                "owner": r["owner"] or "",
                "category": r["category"] or "",
                "status": r["status"],
                "description": skill_descs.get(sn, skill_descs.get(sn.replace("-", "_"), "")),
                "version": r["version"] or "",
                "last_updated": r["last_updated"] or "",
            })
        return {"ok": True, "count": len(result), "skills": result}
"""

# Find insertion point: right before the last method's return + closing
# We'll insert before the blank line that leads to end of class
idx = content.rfind("def recruit_add")
if idx > 0:
    # Find the end of this method's return statement
    return_idx = content.find("\n\n", content.find("return {", idx))
    if return_idx < 0:
        return_idx = len(content)
    content = content[:return_idx] + "\n" + new_code + content[return_idx:]
else:
    content += "\n" + new_code

with io.open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("HR module updated successfully")
