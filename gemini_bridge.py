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

def ask(prompt, model=None):
    br = os.path.dirname(os.path.abspath(__file__))
    import yaml
    cfg = yaml.safe_load(io.open(os.path.join(br, "config.yaml"), "r", encoding="utf-8"))
    gc = cfg.get("gemini", {})
    api_key = re.sub(r'\$\{([^}]+)\}', lambda m: os.environ.get(m.group(1), m.group(0)), gc.get("api_key", ""))
    m = model or gc.get("model", "gemini-2.5-pro")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read().decode("utf-8"))
    text = result["candidates"][0]["content"]["parts"][0]["text"]
    return {"ok": True, "text": text, "model": m}