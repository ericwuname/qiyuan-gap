# -*- coding: utf-8 -*-
"""Token cost tracker for DeepSeek API — actual usage tracking, daily aggregation, by-model/by-project breakdown."""
import sqlite3, os, json
from datetime import datetime, timedelta
from collections import defaultdict

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cost.db")

# Pricing per 1M tokens (USD)
PRICE = {
    "deepseek-chat":     {"in": 0.14, "out": 0.28},
    "deepseek-reasoner": {"in": 0.55, "out": 2.19},
}
DEFAULT_MODEL = "deepseek-chat"
CNY_RATE = 7.25  # USD → CNY

def _db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS usage_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now','localtime')),
        model TEXT, input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0.0,
        source TEXT, project TEXT, notes TEXT
    )""")
    conn.commit()
    return conn

# ── Core: log a single API call ──────────────────────────

def log(model, inp_tok, out_tok, source="brain", project="", notes=""):
    p = PRICE.get(model, PRICE[DEFAULT_MODEL])
    cost = round((inp_tok * p["in"] + out_tok * p["out"]) / 1000000, 6)
    c = _db()
    c.execute(
        "INSERT INTO usage_log(model,input_tokens,output_tokens,cost_usd,source,project,notes) VALUES(?,?,?,?,?,?,?)",
        (model, inp_tok, out_tok, cost, source, project, notes))
    c.commit(); c.close()
    return cost

# ── Quick summary (N days) ───────────────────────────────

def summary(days=7):
    c = _db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    r = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(cost_usd),0) FROM usage_log WHERE date(timestamp) >= ?",
        (since,)).fetchone()
    c.close()
    return dict(calls=r[0], input_tokens=r[1], output_tokens=r[2], total_usd=round(r[3], 6))

# ── Daily breakdown ──────────────────────────────────────

def daily_summary(days=30):
    c = _db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = c.execute(
        "SELECT date(timestamp) as d, COUNT(*) as calls, COALESCE(SUM(input_tokens),0) as inp, COALESCE(SUM(output_tokens),0) as outp, COALESCE(SUM(cost_usd),0) as cost FROM usage_log WHERE date(timestamp) >= ? GROUP BY d ORDER BY d ASC",
        (since,)).fetchall()
    c.close()
    return [dict(date=r[0], calls=r[1], input_tokens=r[2], output_tokens=r[3], cost_usd=round(r[4], 6)) for r in rows]

# ── By model breakdown ───────────────────────────────────

def by_model(days=30):
    c = _db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = c.execute(
        "SELECT model, COUNT(*) as calls, COALESCE(SUM(input_tokens),0) as inp, COALESCE(SUM(output_tokens),0) as outp, COALESCE(SUM(cost_usd),0) as cost FROM usage_log WHERE date(timestamp) >= ? GROUP BY model ORDER BY cost DESC",
        (since,)).fetchall()
    c.close()
    return [dict(model=r[0], calls=r[1], input_tokens=r[2], output_tokens=r[3], cost_usd=round(r[4], 6)) for r in rows]

# ── By project breakdown ─────────────────────────────────

def by_project(days=30):
    c = _db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = c.execute(
        "SELECT COALESCE(NULLIF(project,''), 'general') as proj, COUNT(*) as calls, COALESCE(SUM(input_tokens),0) as inp, COALESCE(SUM(output_tokens),0) as outp, COALESCE(SUM(cost_usd),0) as cost FROM usage_log WHERE date(timestamp) >= ? GROUP BY proj ORDER BY cost DESC",
        (since,)).fetchall()
    c.close()
    return [dict(project=r[0], calls=r[1], input_tokens=r[2], output_tokens=r[3], cost_usd=round(r[4], 6)) for r in rows]

# ── By source breakdown ──────────────────────────────────

def by_source(days=30):
    c = _db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = c.execute(
        "SELECT source, COUNT(*) as calls, COALESCE(SUM(input_tokens),0) as inp, COALESCE(SUM(output_tokens),0) as outp, COALESCE(SUM(cost_usd),0) as cost FROM usage_log WHERE date(timestamp) >= ? GROUP BY source ORDER BY cost DESC",
        (since,)).fetchall()
    c.close()
    return [dict(source=r[0], calls=r[1], input_tokens=r[2], output_tokens=r[3], cost_usd=round(r[4], 6)) for r in rows]

# ── Full report (JSON-ready) ─────────────────────────────

def full_report(days=30):
    s7 = summary(7)
    s30 = summary(30)
    daily = daily_summary(days)
    models = by_model(days)
    projects = by_project(days)
    sources = by_source(days)
    total_usd = s30["total_usd"]
    return {
        "ok": True,
        "period_days": days,
        "summary_7d": s7,
        "summary_30d": s30,
        "total_cost_usd": total_usd,
        "total_cost_cny": round(total_usd * CNY_RATE, 2),
        "daily": daily,
        "by_model": models,
        "by_project": projects,
        "by_source": sources,
        "pricing": PRICE,
        "source": "actual_api_usage",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

# ── Legacy report string ─────────────────────────────────

def report():
    s7 = summary(7)
    s30 = summary(30)
    return "Token 7d: %d calls, $%.4f | 30d: %d calls, $%.4f" % (s7["calls"], s7["total_usd"], s30["calls"], s30["total_usd"])

# ── Direct run ───────────────────────────────────────────

if __name__ == "__main__":
    print(json.dumps(full_report(30), ensure_ascii=False, indent=2))
