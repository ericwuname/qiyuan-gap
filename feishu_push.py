import os, re, io, urllib.request, json
def _load_dotenv():
    ef = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(ef):
        for line in open(ef, "r", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
_load_dotenv()

def push(title, content):
    br = os.path.dirname(os.path.abspath(__file__))
    import yaml
    cfg = yaml.safe_load(io.open(os.path.join(br, "config.yaml"), "r", encoding="utf-8"))
    webhook = cfg["report"]["feishu_webhook"]
    webhook = re.sub(r'\$\{([^}]+)\}', lambda m: os.environ.get(m.group(1), m.group(0)), webhook)
    msg = {"msg_type": "interactive", "card": {"header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"}, "elements": [{"tag": "markdown", "content": content[:3000]}]}}
    data = json.dumps(msg).encode("utf-8")
    req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read().decode("utf-8"))
    return {"ok": result.get("code") == 0, "msg": result.get("msg", "")}