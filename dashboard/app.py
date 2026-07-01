import io, os, sys, sqlite3, json, time
from datetime import datetime, timedelta
from functools import lru_cache

try:
    from flask import Flask, jsonify, render_template, request, send_from_directory
except ImportError:
    Flask = None

_brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _brain_dir)

# ── Sync skills from CDRIVE on startup ──
def _startup_sync():
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from hr.hr_module import HRModule
        h = HRModule()
        r = h.ingest_skills_from_cdrive()
        print(f"[startup] CDRIVE skill sync: {r.get('ingested', 0)} skills ingested")
    except Exception as e:
        print(f"[startup] CDRIVE sync skipped: {e}")

_startup_sync()

# ── Original app creation ──
app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"))


def _get_probe_db():
    try:
        with io.open(os.path.join(_brain_dir, "config.yaml"), "r", encoding="utf-8") as f:
            import yaml
            config = yaml.safe_load(f) or {}
        return config.get("probe", {}).get("database", {}).get("path",
                          os.path.join(_brain_dir, "probe", "probe.db"))
    except Exception:
        return os.path.join(_brain_dir, "probe", "probe.db")


_cache = {"data": None, "ts": 0}


def _collect_metrics():
    global _cache
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < 1.0:
        return _cache["data"]

    db_path = _get_probe_db()
    metrics = {}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT cpu_load, memory_usage, error_rate_1h FROM probe_self_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            metrics["p99_latency_ms"] = round(row["cpu_load"] * 500, 1)
            metrics["error_rate_1h"] = round(row["error_rate_1h"], 4) if row["error_rate_1h"] else 0

        try:
            wm_db = os.path.join(_brain_dir, "probe", "world_model.db")
            wm_conn = sqlite3.connect(wm_db)
            wm_conn.row_factory = sqlite3.Row
            sr = wm_conn.execute(
                "SELECT AVG(surprise_score) as avg_s, MAX(surprise_score) as max_s, MIN(surprise_score) as min_s FROM world_model_surprise WHERE timestamp >= datetime(\"now\", \"-1 hours\")"
            ).fetchone()
            if sr and sr["avg_s"] is not None:
                metrics["surprise_avg"] = round(sr["avg_s"], 4)
                metrics["surprise_max"] = round(sr["max_s"], 4)
                metrics["surprise_min"] = round(sr["min_s"], 4)
            wm_conn.close()
        except Exception:
            metrics["surprise_avg"] = 0.0

        try:
            cur_row = conn.execute(
                "SELECT curiosity FROM probe_curiosity ORDER BY id DESC LIMIT 1"
            ).fetchone()
            metrics["curiosity"] = round(cur_row["curiosity"], 4) if cur_row else 0.5
        except Exception:
            metrics["curiosity"] = 0.5

        try:
            conf_row = conn.execute(
                "SELECT confidence FROM probe_confidence ORDER BY id DESC LIMIT 1"
            ).fetchone()
            metrics["confidence"] = round(conf_row["confidence"], 4) if conf_row else 0.5
        except Exception:
            metrics["confidence"] = 0.5

        try:
            ag_row = conn.execute(
                "SELECT agency_ratio FROM probe_agency ORDER BY id DESC LIMIT 1"
            ).fetchone()
            metrics["agency_ratio"] = round(ag_row["agency_ratio"], 4) if ag_row else 0.0
        except Exception:
            metrics["agency_ratio"] = 0.0

        conn.close()
    except Exception:
        pass

    _cache["data"] = metrics
    _cache["ts"] = now
    return metrics


# ── Routes ──────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/metrics")
def api_metrics():
    return jsonify(_collect_metrics())


@app.route("/api/history")
def api_history():
    limit = request.args.get("limit", 100, type=int)
    try:
        db_path = _get_probe_db()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT timestamp, agency_ratio FROM probe_agency ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        data = [{"t": r["timestamp"], "v": r["agency_ratio"]} for r in reversed(rows)]
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hr")
def api_hr():
    """HR dashboard data."""
    try:
        from hr.hr_module import HRModule
        h = HRModule()
        return jsonify(h.dashboard())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cost")
def api_cost():
    """Cost/value dashboard data — combines actual + estimated."""
    try:
        from finance.finance_module import FinanceModule
        f = FinanceModule()
        est = f.estimate(30)
        result = {
            "ok": True,
            "ops_30d": est.get("total_ops", 0),
            "cost_cny_30d": est.get("total_cost_cny", 0),
            "cost_usd_30d": est.get("total_cost_usd", 0),
            "daily": est.get("daily", [])[-7:],
            "by_proj": f.by_project().get("projects", {}),
            "source": "audit_log_estimate",
        }
        # Also include actual usage if available
        try:
            from cost.cost_tracker import full_report
            actual = full_report(30)
            result["actual"] = {
                "calls_7d": actual["summary_7d"]["calls"],
                "calls_30d": actual["summary_30d"]["calls"],
                "cost_usd_7d": actual["summary_7d"]["total_usd"],
                "cost_usd_30d": actual["total_cost_usd"],
                "cost_cny_30d": actual["total_cost_cny"],
                "daily": actual.get("daily", []),
                "by_model": actual.get("by_model", []),
                "by_project": actual.get("by_project", []),
            }
        except Exception:
            result["actual"] = {"available": False}
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cost/actual")
def api_cost_actual():
    """Actual API usage from cost_tracker (DeepSeek token logs)."""
    try:
        from cost.cost_tracker import full_report
        result = full_report(30)
        result["_note"] = "actual API usage — requires log() calls to be populated"
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


_brain_status_cache = {"raw": None, "ts": 0}

@app.route("/api/brain-status")
def api_brain_status():
    """Quick brain status check (cached 60s)."""
    try:
        now = time.time()
        if _brain_status_cache["raw"] is not None and (now - _brain_status_cache["ts"]) < 60:
            return jsonify({"raw": _brain_status_cache["raw"]})
        import subprocess
        result = subprocess.run(
            ["python", "brain/cli.py", "status"],
            capture_output=True, text=True, timeout=30, 
            cwd=os.path.dirname(_brain_dir)
        )
        raw = result.stdout[:2000] if result.stdout else result.stderr[:2000]
        _brain_status_cache["raw"] = raw
        _brain_status_cache["ts"] = now
        return jsonify({"raw": raw})
    except Exception as e:
        return jsonify({"raw": f"brain status unavailable: {str(e)[:200]}"})



@app.route("/api/hr/detail")
def api_hr_detail():
    """Full employee detail list."""
    try:
        from hr.hr_module import HRModule
        h = HRModule()
        return jsonify(h.employees_full())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/hr/org-chart")
def api_hr_org_chart():
    """Organization chart tree data."""
    try:
        from hr.hr_module import HRModule
        h = HRModule()
        return jsonify(h.org_chart())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/hr/skills")
def api_hr_skills():
    """Skill catalog with descriptions."""
    try:
        from hr.hr_module import HRModule
        h = HRModule()
        return jsonify(h.skills_detail())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/js/pagination.js")
def js_pagination():
    js_path = os.path.join(os.path.dirname(__file__), "templates", "pagination.js")
    with io.open(js_path, "r", encoding="utf-8") as f:
        content = f.read()
    from flask import Response
    return Response(content, mimetype="application/javascript")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Brain Dashboard")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"Dashboard: http://{args.host}:{args.port}")
    if Flask is None:
        print("ERROR: pip install flask")
        sys.exit(1)
    app.run(host=args.host, port=args.port, debug=False)


@app.route("/api/hr/rebuild")
def api_hr_rebuild():
    try:
        from hr.hr_module import HRModule
        h = HRModule()
        return jsonify(h.rebuild_all())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



@app.route("/tasks")
def tasks_page():
    """任务看板页面"""
    return send_from_directory("templates", "tasks.html")

@app.route("/api/tasks")
def api_tasks():
    """任务数据API"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from task_module import get_pending_tasks, get_recurring_due_today
        import json as _json
        with __builtins__.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tasks.json"), "r", encoding="utf-8") as f:
            tasks_data = _json.load(f)
        pending = get_pending_tasks()
        due = get_recurring_due_today()
        
        # Also load recurring for display
        rec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "recurring.json")
        with __builtins__.open(rec_path, "r", encoding="utf-8") as f:
            rec_data = _json.load(f)
        
        # Add label for recurring
        from datetime import datetime as _dt
        now = _dt.now()
        days_map = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
        for t in rec_data.get("tasks", []):
            freq = t.get("frequency", "")
            if freq == "daily":
                t["label"] = now.strftime("%Y-%m-%d")
            elif freq == "weekly":
                t["label"] = t.get("day", "?")
            elif freq == "monthly":
                t["label"] = "day " + str(t.get("day", "?"))
            else:
                t["label"] = "?"
        
        return jsonify({
            "ok": True,
            "pending": pending,
            "recurring": rec_data.get("tasks", []),
            "due_today": due,
            "total_done": tasks_data.get("_meta", {}).get("total_completed", 0)
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    main()