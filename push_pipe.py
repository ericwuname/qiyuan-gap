import os, json
from datetime import datetime

def push_night_brief(brief_text, title=None):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    if not title: title = f"启元夜报 {date_str}"
    results = {"title": title, "channels": {}}
    try:
        from feishu_push import push
        results["channels"]["feishu"] = push(title, brief_text)
    except Exception as e:
        results["channels"]["feishu"] = {"ok": False, "error": str(e)[:100]}
    try:
        from email_push import send
        html = brief_text.replace("\n", "<br>").replace("# ", "<h3>").replace("## ", "<h4>")
        results["channels"]["email"] = send(title, f"<div style=font-family:monospace>{html}</div>")
    except Exception as e:
        results["channels"]["email"] = {"ok": False, "error": str(e)[:100]}
    results["channels"]["local"] = {"ok": True}
    return results