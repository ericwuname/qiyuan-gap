import sys, io, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # brain/
from hr.hr_module import HRModule

h = HRModule()
conn = sqlite3.connect(h.db_path)

tier_scores = {
    "\u6218\u7565\u987e\u95ee": ("T1", 7.5), "\u9879\u76ee\u603b\u76d1": ("T1", 7.0), "\u4ea7\u54c1\u7ecf\u7406": ("T1", 6.5),
    "\u4eba\u529b\u603b\u76d1": ("T1", 7.5), "\u8d22\u52a1\u603b\u76d1": ("T1", 6.0), "\u519b\u5e08": ("T1", 8.0),
    "\u9879\u76ee\u603b\u7ba1": ("T2", 7.0), "\u67b6\u6784\u5e08": ("T2", 7.5), "\u8bbe\u8ba1\u603b\u76d1": ("T2", 7.0),
    "\u6267\u884c\u603b\u76d1": ("T2", 6.5), "\u8d28\u91cf\u8bc4\u5ba1": ("T2", 6.0),
    "Scrum Master": ("T3", 5.5), "\u6d4b\u8bd5\u81ea\u52a8\u5316": ("T3", 5.0), "DevOps": ("T3", 5.0),
    "\u6570\u636e\u5de5\u7a0b\u5e08": ("T3", 5.0), "\u5b89\u5168\u5ba1\u8ba1": ("T3", 5.5), "\u6280\u672f\u6587\u6863": ("T3", 5.0),
    "\u8d28\u68c0\u5458": ("T4", 5.0), "JS\u9519\u8bef\u68c0\u67e5": ("T4", 4.5),
    "\u9700\u6c42\u6316\u6398\u5e08": ("Shared", 6.5), "\u5934\u8111\u98ce\u66b4": ("Shared", 7.0), "\u9e3f\u8499\u4e4b\u521d": ("Shared", 7.0),
}

dept_map = {
    "\u6218\u7565\u987e\u95ee": "T1-\u6218\u7565\u51b3\u7b56", "\u9879\u76ee\u603b\u76d1": "T1-\u9879\u76ee\u6307\u6325", "\u4ea7\u54c1\u7ecf\u7406": "T1-\u4ea7\u54c1\u7ba1\u7406",
    "\u4eba\u529b\u603b\u76d1": "T1-\u4eba\u529b\u8d44\u6e90", "\u8d22\u52a1\u603b\u76d1": "T1-\u8d22\u52a1\u6cd5\u52a1", "\u519b\u5e08": "T1-\u72ec\u7acb\u5ba1\u8ba1",
    "\u9879\u76ee\u603b\u7ba1": "T2-\u9879\u76ee\u7ba1\u7406", "\u67b6\u6784\u5e08": "T2-\u6280\u672f\u67b6\u6784", "\u8bbe\u8ba1\u603b\u76d1": "T2-\u8bbe\u8ba1",
    "\u6267\u884c\u603b\u76d1": "T2-\u6267\u884c\u7ba1\u7406", "\u8d28\u91cf\u8bc4\u5ba1": "T2-\u8d28\u91cf\u4fdd\u969c",
    "Scrum Master": "T3-\u654f\u6377\u534f\u4f5c", "\u6d4b\u8bd5\u81ea\u52a8\u5316": "T3-\u8d28\u91cf\u5de5\u7a0b", "DevOps": "T3-\u8fd0\u7ef4\u5de5\u7a0b",
    "\u6570\u636e\u5de5\u7a0b\u5e08": "T3-\u6570\u636e\u5de5\u7a0b", "\u5b89\u5168\u5ba1\u8ba1": "T3-\u5b89\u5168\u5de5\u7a0b", "\u6280\u672f\u6587\u6863": "T3-\u6280\u672f\u5199\u4f5c",
    "\u8d28\u68c0\u5458": "T4-\u8d28\u91cf\u6267\u884c", "JS\u9519\u8bef\u68c0\u67e5": "T4-\u8d28\u91cf\u6267\u884c",
    "\u9700\u6c42\u6316\u6398\u5e08": "Shared-\u9700\u6c42\u5de5\u7a0b", "\u5934\u8111\u98ce\u66b4": "Shared-\u521b\u65b0", "\u9e3f\u8499\u4e4b\u521d": "Shared-\u521b\u65b0",
}

for emp in conn.execute("SELECT id, name FROM employees").fetchall():
    eid, name = emp
    info = tier_scores.get(name, ("", 0))
    dept = dept_map.get(name, "")
    conn.execute("UPDATE employees SET tier=?, department=?, capability_score=? WHERE id=?",
                 (info[0], dept, info[1], eid))
conn.commit()

# Add missing roles
for role, (tier, score) in [("\u519b\u5e08", ("T1", 8.0)), ("\u8d22\u52a1\u603b\u76d1", ("T1", 6.0))]:
    exists = conn.execute("SELECT COUNT(*) FROM employees WHERE name=?", (role,)).fetchone()[0]
    if not exists:
        eid = "EMP-CVO" if role == "\u519b\u5e08" else "EMP-CFO"
        conn.execute(
            "INSERT INTO employees (id, name, role, tier, department, capability_score, status, last_assessment) VALUES (?,?,?,?,?,?,?,?)",
            (eid, role, role, tier, dept_map.get(role, ""), score, "active", "2026-06-21"))

conn.commit()

for row in conn.execute("SELECT id, name, tier, department, capability_score FROM employees ORDER BY CASE tier WHEN 'T1' THEN 1 WHEN 'T2' THEN 2 WHEN 'T3' THEN 3 WHEN 'T4' THEN 4 ELSE 5 END, capability_score DESC").fetchall():
    t = row[2] or "-"
    d = row[3] or "-"
    s = row[4] or 0
    print(f"{row[0]:14s} {row[1]:14s} {t:8s} {d:24s} {s:.1f}")

conn.close()
print("DONE: HR DB enriched")