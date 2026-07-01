# -*- coding: utf-8 -*-
import http.server, json, os
from datetime import datetime
BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
HOST, PORT = "127.0.0.1", 8080

def get_state():
    sf = os.path.join(BRAIN_DIR, "body_state.json")
    st = json.load(open(sf,"r",encoding="utf-8")) if os.path.isfile(sf) else {}
    cv2 = st.get("_curiosity_v2",{})
    sd = os.path.join(BRAIN_DIR,"rules","_suggested")
    sg = len([f for f in os.listdir(sd) if f.endswith((".yaml",".yml"))]) if os.path.isdir(sd) else 0
    return {"brain_ok":True,"version":"V2.1","checks":st.get("checks_completed",0),
        "phase":cv2.get("phase","?"),"suggested":sg,
        "G":cv2.get("g_dig_open",0),"C":cv2.get("c_issues",0),
        "D":cv2.get("d_warnings",0),"E":cv2.get("e_stale",0),"F":cv2.get("f_orphans",0),
        "updated":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        if s.path in ["/","/index.html"]:
            state = get_state()
            rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in state.items() if not isinstance(v,dict))
            for k,v in state.items():
                if isinstance(v,list): rows += f"<tr><td>{k}</td><td>{len(v)} items</td></tr>"
            html = f"""<!DOCTYPE html><html lang=zh-CN><head><meta charset=UTF-8><meta http-equiv=refresh content=30><title>启元仪表盘</title><style>body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:24px}}h1{{font-size:24px}}table{{border-collapse:collapse}}td{{padding:8px 12px;border-bottom:1px solid #334155}}td:first-child{{color:#94a3b8}}.ok{{color:#22c55e}}</style></head><body><h1>启元智能 仪表盘 V2.1</h1><p style=color:#94a3b8>更新:{state["updated"]} | 30s自动刷新 | <a href=/api/state style=color:#38bdf8>JSON API</a></p><table>{rows}</table></body></html>"""
            s.send_response(200); s.send_header("Content-Type","text/html; charset=utf-8"); s.end_headers()
            s.wfile.write(html.encode("utf-8"))
        elif s.path == "/api/state":
            s.send_response(200); s.send_header("Content-Type","application/json; charset=utf-8"); s.send_header("Access-Control-Allow-Origin","*"); s.end_headers()
            s.wfile.write(json.dumps(get_state(),ensure_ascii=False).encode("utf-8"))
        else: s.send_response(404); s.end_headers()
    def log_message(s,f,*a): pass

def main():
    srv = http.server.HTTPServer((HOST,PORT),H)
    print(f"\n启元仪表盘\n  http://{HOST}:{PORT}\n  API: http://{HOST}:{PORT}/api/state\n  Ctrl+C to stop\n")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nShutdown.")

if __name__ == "__main__": main()