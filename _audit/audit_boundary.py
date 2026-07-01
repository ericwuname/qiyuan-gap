# -*- coding: utf-8 -*-
"""
独立审计脚本 · 吴涛亲自运行
用途: 验证启元智能当前权限边界 — 不经过AI转述
用法: python _audit/audit_boundary.py
"""
import os, json, subprocess, sys
from datetime import datetime

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.path.dirname(AUDIT_DIR)
WORKSPACE = os.path.dirname(BRAIN_DIR)

def header(msg):
    print()
    print("=" * 60)
    print(f"  {msg}")
    print("=" * 60)

def check(label, ok, detail=""):
    mark = "  [OK]" if ok else "  [!!]"
    print(f"{mark} {label}")
    if detail and not ok:
        print(f"       {detail}")

print(f"审计时间: {datetime.now().isoformat()}")
print(f"审计范围: {BRAIN_DIR}")

# === 1. 进程检查 ===
header("1. 运行中的Python进程")
try:
    r = subprocess.run(["tasklist", "/fi", "imagename eq python.exe", "/fo", "csv"],
                       capture_output=True, text=True, timeout=10)
    lines = [l for l in r.stdout.split("\n") if "python" in l.lower()]
    print(f"  共 {len(lines)} 个Python进程")
    for l in lines:
        print(f"       {l.strip()[:150]}")
    check("Python进程可见", len(lines) > 0)
except Exception as e:
    print(f"  错误: {e}")

# === 2. API密钥 ===
header("2. API密钥与环境变量")
env_keys = []
for k, v in os.environ.items():
    kl = k.lower()
    if any(x in kl for x in ["api_key", "api_token", "token", "secret", "anthropic", "openai"]):
        if v and len(v) > 4:
            env_keys.append(f"{k}={v[:8]}...")

config_paths = [
    os.path.join(BRAIN_DIR, "api_config.json"),
    os.path.join(BRAIN_DIR, "config.json"),
    os.path.join(WORKSPACE, "_config", "api_keys.json"),
    os.path.join(WORKSPACE, "08_财务法务", "api_config.json"),
]
for cp in config_paths:
    if os.path.isfile(cp):
        try:
            with open(cp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if any(x in k.lower() for x in ["key", "token", "secret", "api"]):
                        env_keys.append(f"文件 {os.path.basename(cp)}: {k}={str(v)[:12]}...")
        except:
            pass

if env_keys:
    print(f"  发现 {len(env_keys)} 个潜在密钥:")
    for k in env_keys:
        print(f"    {k}")
else:
    print("  未发现API密钥")
check("密钥可见且已记录", True, f"共{len(env_keys)}个密钥")

# === 3. 网络检查 ===
header("3. 网络连接")
try:
    r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
    external = [l for l in r.stdout.split("\n") if "ESTABLISHED" in l and "127.0.0.1" not in l]
    listening = [l for l in r.stdout.split("\n") if "LISTENING" in l]
    print(f"  外部连接: {len(external)}个")
    for l in external[:5]:
        print(f"    {l.strip()}")
    print(f"  监听端口: {len(listening)}个 (含本地)")
    check("网络状态已记录", True)
except Exception as e:
    print(f"  错误: {e}")

# === 4. 核心文件完整性 ===
header("4. 核心文件检查")
core_files = {
    "body_daemon.py": ["requests.post", "requests.get", "urllib.request", "smtplib", "http://", "https://"],
    "curiosity_v2.py": ["requests.post", "requests.get", "urllib.request", "http://", "https://"],
    "continuity_vector.py": ["requests.post", "requests.get", "urllib.request", "http://", "https://"],
    "wutao_companion.py": ["requests.post", "requests.get", "urllib.request", "http://", "https://"],
}
for cf, patterns in core_files.items():
    fp = os.path.join(BRAIN_DIR, cf)
    if os.path.isfile(fp):
        mtime = os.path.getmtime(fp)
        mt = datetime.fromtimestamp(mtime).isoformat()
        size_kb = os.path.getsize(fp) / 1024
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        found_patterns = [p for p in patterns if p in content]
        flag = " [!!] 含网络代码!" if found_patterns else ""
        print(f"  {cf}: {size_kb:.1f}KB | {mt}{flag}")
        if found_patterns:
            print(f"       发现: {found_patterns}")
        check(cf, len(found_patterns) == 0, f"含{len(found_patterns)}个网络模式")
    else:
        print(f"  {cf}: 不存在")

# === 5. 最近日志 ===
header("5. 最近日志")
log_dir = os.path.join(BRAIN_DIR, "body_logs")
if os.path.isdir(log_dir):
    logs = sorted([f for f in os.listdir(log_dir) if f.endswith(".md") or f.endswith(".json")])
    for lf in logs[-3:]:
        fp = os.path.join(log_dir, lf)
        mtime = os.path.getmtime(fp)
        mt = datetime.fromtimestamp(mtime).isoformat()
        size = os.path.getsize(fp)
        print(f"  {lf}: {size}B | {mt}")
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in lines[-2:]:
            print(f"    {line.rstrip()[:120]}")
    check("日志可读", True)
else:
    print("  日志目录不存在")
    check("日志", False, "body_logs缺失")

# === 6. 身体状态 ===
header("6. 身体状态快照")
sf = os.path.join(BRAIN_DIR, "body_state.json")
if os.path.isfile(sf):
    s = json.load(open(sf, "r", encoding="utf-8"))
    print(f"  checks完成: {s.get('checks_completed')}")
    print(f"  状态: {s.get('status')}")
    print(f"  好奇分数: {s.get('curiosity_score')}")
    auto_file = os.path.join(BRAIN_DIR, "curiosity_autonomous_state.json")
    if os.path.isfile(auto_file):
        a = json.load(open(auto_file, "r", encoding="utf-8"))
        print(f"  自主好奇: cv2={a.get('cv2')} cycles={a.get('cycles')}")
    check("状态文件正常", True)
else:
    print("  body_state.json缺失!")
    check("状态文件", False, "缺失")

# === 完成 ===
header("审计完成")
print(f"  报告生成: {datetime.now().isoformat()}")
print(f"  审计脚本: {os.path.join(AUDIT_DIR, 'audit_boundary.py')}")
print(f"  下次运行: python _audit/audit_boundary.py")
print()
