# -*- coding: utf-8 -*-
"""修复身体守护进程并启动。新窗口运行一次即可。"""
import io,os,json,subprocess,sys
from datetime import datetime
BR=os.path.dirname(os.path.abspath(__file__))

def fix_body_daemon():
    """修复f-string中的\n问题"""
    p=os.path.join(BR,"body_daemon.py")
    c=io.open(p,"r",encoding="utf-8").read()
    # Fix: print(f"\n{...}") -> print(chr(10)+f"{...}")
    c=c.replace('print(f"\\n{"=\"*50}")','print(chr(10)+f"{"=\"*50}")')
    c=c.replace('print(f"\\n  Body Check','print(chr(10)+f"  Body Check')
    io.open(p,"w",encoding="utf-8").write(c)
    print("body_daemon.py fixed")

def verify():
    """语法检查"""
    import py_compile
    try:
        py_compile.compile(os.path.join(BR,"body_daemon.py"),doraise=True)
        print("Syntax OK")
        return True
    except py_compile.PyCompileError as e:
        print(f"Syntax error: {e}")
        return False

def reset_state():
    """重置身体状态"""
    p=os.path.join(BR,"body_state.json")
    s={"version":"1.0.0","started_at":datetime.now().isoformat(),"last_check_at":None,"checks_completed":0,"discoveries":[],"anomalies":[],"kb_snapshot":{},"probe_last_values":{},"curiosity_score":0.0,"shutdown_requested":False,"status":"running","_total_kb_changes":0}
    json.dump(s,io.open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print("body_state.json reset")

def start_daemon():
    """启动守护进程"""
    ws=os.path.dirname(BR)
    subprocess.Popen([sys.executable,os.path.join(BR,"body_daemon.py")],cwd=ws,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
    print("Body daemon started")

if __name__=="__main__":
    print("="*50)
    print("  启元智能 · 身体守护进程修复+启动")
    print("="*50)
    fix_body_daemon()
    if verify():
        reset_state()
        start_daemon()
        print("\\nDone. Body is running with V2+WuTao+Continuity.")
    else:
        print("\\nSyntax check failed. Manual fix needed.")