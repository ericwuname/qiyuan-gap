# -*- coding: utf-8 -*-
"""Self-narrative generator for Qiyuan Brain."""
import io, os, sys, sqlite3, json
from datetime import datetime, timedelta
_brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _brain_dir)

DEFAULT_TEMPLATE_ZH = """【{date} 启元智脑日志】

今天我一共处理了 {request_count} 次查询。

我的惊讶度平均值是 {surprise_avg}，自主决策度是 {agency_avg}。

CPU占用约 {cpu_avg}%，内存占用约 {memory_avg}%。

目前有 {rule_count} 条运作规则，{proposal_count} 条待审批建议。

整体状态：{health_summary}"""

DEFAULT_TEMPLATE_EN = """【{date} Qiyuan Brain Log】

Today I handled {request_count} queries.

My surprise average was {surprise_avg}, agency ratio {agency_avg}.

CPU ~{cpu_avg}%, Memory ~{memory_avg}%.

I have {rule_count} rules and {proposal_count} pending proposals.

Overall status: {health_summary}"""

def collect_narrative_data():
    data = {"date": datetime.now().strftime("%Y-%m-%d")}
    db_path = os.path.join(_brain_dir, "probe", "probe.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        sql = "SELECT AVG(cpu_load) as cpu, AVG(memory_usage) as mem FROM probe_self_state WHERE timestamp >= date(\"now\", \"-1 days\")"
        sr = conn.execute(sql).fetchone()
        if sr:
            data["cpu_avg"] = round(sr["cpu"]*100, 1) if sr["cpu"] else 0
            data["memory_avg"] = round(sr["mem"]*100, 1) if sr["mem"] else 0
        ar = conn.execute("SELECT AVG(agency_ratio) as aa FROM probe_agency WHERE timestamp >= date(\"now\", \"-1 days\")").fetchone()
        data["agency_avg"] = round(ar["aa"], 4) if ar and ar["aa"] else 0
        conn.close()
    except Exception:
        data["cpu_avg"] = 0; data["memory_avg"] = 0; data["agency_avg"] = 0
    try:
        wm_db = os.path.join(_brain_dir, "probe", "world_model.db")
        if os.path.exists(wm_db):
            wm_conn = sqlite3.connect(wm_db); wm_conn.row_factory = sqlite3.Row
            sr2 = wm_conn.execute("SELECT AVG(surprise_score) as avg_s FROM world_model_surprise WHERE timestamp >= date(\"now\", \"-1 days\")").fetchone()
            data["surprise_avg"] = round(sr2["avg_s"],4) if sr2 and sr2["avg_s"] else 0
            wm_conn.close()
    except Exception:
        data["surprise_avg"] = 0
    try:
        rules_dir = os.path.join(_brain_dir, "rules")
        data["rule_count"] = sum(1 for f in os.listdir(rules_dir) if f.endswith(".yaml"))
        proposals_dir = os.path.join(_brain_dir, "proposals")
        data["proposal_count"] = sum(1 for f in os.listdir(proposals_dir) if f.endswith(".yaml")) if os.path.exists(proposals_dir) else 0
    except Exception:
        data["rule_count"] = 0; data["proposal_count"] = 0
    data["request_count"] = data.get("rule_count", 0)
    data["health_summary"] = "运行平稳" if data.get("surprise_avg",0) < 0.3 else "正在学习调整中"
    return data

def generate_narrative(lang="zh"):
    data = collect_narrative_data()
    template = DEFAULT_TEMPLATE_ZH if lang == "zh" else DEFAULT_TEMPLATE_EN
    return template.format(**data)

def save_narrative(narrative, date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    d = os.path.join(_brain_dir, "reports", "narratives")
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, f"narrative_{date_str}.md")
    with io.open(fp, "w", encoding="utf-8") as f: f.write(narrative)
    return fp

def main(date_str=None, lang="zh"):
    narrative = generate_narrative(lang)
    fp = save_narrative(narrative, date_str)
    print(narrative)
    print(f"Saved: {fp}")
    return fp

if __name__ == "__main__": main()
