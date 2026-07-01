import os, re, io, smtplib
from email.mime.text import MIMEText
from email.header import Header
def _load_dotenv():
    ef = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(ef):
        for line in open(ef, "r", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
_load_dotenv()

def send(subject, body_html):
    br = os.path.dirname(os.path.abspath(__file__))
    import yaml
    cfg = yaml.safe_load(io.open(os.path.join(br, "config.yaml"), "r", encoding="utf-8"))
    ec = cfg["report"]["email"]
    def x(v): return re.sub(r'\$\{([^}]+)\}', lambda m: os.environ.get(m.group(1), m.group(0)), v) if isinstance(v, str) else v
    sender = x(ec["sender"])
    password = x(ec["password"])
    recipients = [x(r) for r in ec["recipients"]]
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    server = smtplib.SMTP_SSL(x(ec.get("smtp_host", "smtp.qq.com")), 465, timeout=15)
    server.login(sender, password)
    server.sendmail(sender, recipients, msg.as_string())
    server.quit()
    return {"ok": True, "recipients": len(recipients)}