# -*- coding: utf-8 -*-
"""Nightly report generator for Qiyuan Brain."""
import io, os, sys, sqlite3, json, time, smtplib, uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
def _resolve_env(value):
    """Resolve ${ENV_VAR} placeholders in config values."""
    import re
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        env_val = os.environ.get(env_key, "")
        if env_val:
            return env_val
    return value
from email.mime.multipart import MIMEMultipart
try: import urllib.request
except ImportError: urllib = None
_brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _brain_dir)

def load_config():
    try:
        import yaml
        with io.open(os.path.join(_brain_dir, "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def collect_data(config):
    data = {"timestamp": datetime.now().isoformat(), "errors": []}
    probe_cfg = config.get("probe", {})
    db_path = probe_cfg.get("database", {}).get("path", os.path.join(_brain_dir, "probe", "probe.db"))
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        sql = "SELECT COUNT(*) as cnt, AVG(error_rate_1h) as avg_err FROM probe_self_state WHERE timestamp >= date(\"now\", \"-1 days\")"
        row = conn.execute(sql).fetchone()
        if row:
            data["request_count"] = row["cnt"] or 0
            data["error_rate_avg"] = round(row["avg_err"], 4) if row["avg_err"] else 0
        sql2 = "SELECT AVG(agency_ratio) as avg_a FROM probe_agency WHERE timestamp >= date(\"now\", \"-1 days\")"
        ar = conn.execute(sql2).fetchone()
        data["agency_avg"] = round(ar["avg_a"], 4) if ar and ar["avg_a"] else 0
        sql3 = "SELECT AVG(cpu_load) as cpu, AVG(memory_usage) as mem FROM probe_self_state WHERE timestamp >= date(\"now\", \"-1 days\")"
        sr = conn.execute(sql3).fetchone()
        if sr:
            data["cpu_avg"] = round(sr["cpu"]*100, 1) if sr["cpu"] else 0
            data["memory_avg"] = round(sr["mem"]*100, 1) if sr["mem"] else 0
        conn.close()
    except Exception as e:
        data["errors"].append("probe.db: " + str(e))
    try:
        wm_db = os.path.join(_brain_dir, "probe", "world_model.db")
        if os.path.exists(wm_db):
            wm_conn = sqlite3.connect(wm_db)
            wm_conn.row_factory = sqlite3.Row
            sql4 = "SELECT AVG(surprise_score) as avg_s FROM world_model_surprise WHERE timestamp >= date(\"now\", \"-1 days\")"
            sr2 = wm_conn.execute(sql4).fetchone()
            data["surprise_avg"] = round(sr2["avg_s"], 4) if sr2 and sr2["avg_s"] else 0
            wm_conn.close()
    except Exception:
        data["surprise_avg"] = 0
    try:
        rules_dir = os.path.join(_brain_dir, "rules")
        data["rule_count"] = sum(1 for f in os.listdir(rules_dir) if f.endswith(".yaml"))
        proposals_dir = os.path.join(_brain_dir, "proposals")
        if os.path.exists(proposals_dir):
            data["proposal_count"] = sum(1 for f in os.listdir(proposals_dir) if f.endswith(".yaml"))
        else:
            data["proposal_count"] = 0
    except Exception:
        data["rule_count"] = 0
        data["proposal_count"] = 0
    return data

def generate_report(data):
    today = datetime.now().strftime("%Y-%m-%d")
    l = []
    l.append("# Qiyuan Brain Nightly Report " + today)
    l.append("")
    l.append("## Core Metrics")
    l.append("- Requests: " + str(data.get("request_count", 0)))
    l.append("- Error rate avg: {:.2f}%".format(data.get("error_rate_avg", 0)*100))
    l.append("- Surprise avg: {:.4f}".format(data.get("surprise_avg", 0)))
    l.append("- Agency avg: {:.4f}".format(data.get("agency_avg", 0)))
    l.append("- CPU: {:.1f}%  Memory: {:.1f}%".format(data.get("cpu_avg",0), data.get("memory_avg",0)))
    l.append("")
    l.append("## Rules")
    l.append("- Rule count: " + str(data.get("rule_count", 0)))
    l.append("- Pending proposals: " + str(data.get("proposal_count", 0)))
    if data.get("errors"):
        l.append("")
        l.append("## Errors")
        for e in data["errors"]:
            l.append("- " + str(e))
    return chr(10).join(l)

def push_feishu(webhook_url, content, retries=3):
    if not webhook_url: return False, "no webhook"
    payload = json.dumps({"msg_type":"interactive","card":{"header":{"title":{"content":"Qiyuan Brain Nightly","tag":"plain_text"},"template":"blue"},"elements":[{"tag":"markdown","content":content[:3000]}]}}, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, retries+1):
        try:
            req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type":"application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code")==0 or result.get("StatusCode")==0: return True, "OK"
            return False, str(result)
        except Exception as e:
            if attempt < retries: time.sleep(2**attempt)
            else: return False, str(e)
    return False, "unknown"

def push_email(email_cfg, content):
    if not email_cfg or not email_cfg.get("smtp_host"): return False, "no email config"
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "Qiyuan Brain Nightly " + datetime.now().strftime("%Y-%m-%d")
        msg["From"] = email_cfg.get("sender","")
        msg["To"] = ", ".join(email_cfg.get("recipients",[]))
        msg.attach(MIMEText(content,"plain","utf-8"))
        with smtplib.SMTP(email_cfg["smtp_host"], email_cfg.get("smtp_port",587), timeout=10) as smtp:
            smtp.starttls()
            smtp.login(email_cfg.get("sender",""), email_cfg.get("password",""))
            smtp.send_message(msg)
        return True, "OK"
    except Exception as e: return False, str(e)

def save_local(content):
    d = os.path.join(_brain_dir, "reports", "failed")
    os.makedirs(d, exist_ok=True)
    fn = "report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8] + ".md"
    fp = os.path.join(d, fn)
    with io.open(fp, "w", encoding="utf-8") as f: f.write(content)
    return fp

def main():
    config = load_config()
    data = collect_data(config)
    report = generate_report(data)
    cfg = config.get("report",{})
    webhook = _resolve_env(cfg.get("feishu_webhook",""))
    email_raw = cfg.get("email",{}); email = {k: _resolve_env(v) for k, v in email_raw.items()} if email_raw else {}
    ok, msg = push_feishu(webhook, report)
    if ok: print("[OK] Feishu sent"); return True
    print("[WARN] Feishu: " + msg)
    ok, msg = push_email(email, report)
    if ok: print("[OK] Email sent"); return True
    print("[WARN] Email: " + msg)
    fp = save_local(report)
    print("[WARN] Saved: " + fp)
    return False

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
