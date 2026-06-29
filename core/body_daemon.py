# -*- coding: utf-8 -*-
"""
启元智能 · 身体守护进程 (Body Daemon) V1.0

持久身体原型。10分钟自检循环，让启元智能在对话间隔期间持续存在。
新对话启动时读取 body_state.json → "已经想了几天，有话跟你说。"

依赖现有基础设施:
- ProbeManager (4探针: 整合/自态/连续/自主)
- CuriosityEngine (好奇心驱动探索)
- FAISSStore (14501向量语义检索)
- WorldModel (预测+惊喜检测)
- digest (知识内化)

设计原则:
- 静默运行，只在发现异常/新知时记录
- 内存目标: <200MB
- 成本: /月 (本地运行)
- 优雅停机: 检测 body_state.json 中的 shutdown 标记
"""

import io, json, os, sys, time, traceback, uuid
from datetime import datetime

# ── Paths ──────────────────────────────────────────────
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BRAIN_ROOT)

STATE_FILE = os.path.join(BRAIN_ROOT, "body_state.json")
LOG_DIR = os.path.join(BRAIN_ROOT, "body_logs")
KB_ROOT = os.path.join(WORKSPACE_ROOT, "05_组织知识库")
DISCOVERIES_LOG = os.path.join(BRAIN_ROOT, "body_logs", "discoveries.md")

os.makedirs(LOG_DIR, exist_ok=True)

# ── State management ───────────────────────────────────

def load_state():
    """Load persistent body state."""
    if os.path.isfile(STATE_FILE):
        with io.open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return _default_state()

def _default_state():
    return {
        "version": "1.0.0",
        "started_at": datetime.now().isoformat(),
        "last_check_at": None,
        "checks_completed": 0,
        "discoveries": [],
        "anomalies": [],
        "kb_snapshot": {},       # file→mtime for change detection
        "probe_last_values": {},
        "curiosity_score": 0.0,
        "shutdown_requested": False,
        "status": "initializing"
    }

def save_state(state):
    state["last_saved_at"] = datetime.now().isoformat()
    with io.open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── Knowledge base scanner ─────────────────────────────

def scan_kb_changes(state):
    """Scan knowledge base for new/changed files since last check."""
    changes = {"new": [], "modified": [], "deleted": []}
    old_snapshot = state.get("kb_snapshot", {})
    new_snapshot = {}
    
    if not os.path.isdir(KB_ROOT):
        return changes, new_snapshot
    
    for root, dirs, files in os.walk(KB_ROOT):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                mtime = os.path.getmtime(fpath)
                size = os.path.getsize(fpath)
                new_snapshot[fpath] = f"{mtime:.0f}_{size}"
                
                if fpath not in old_snapshot:
                    changes["new"].append(fpath)
                elif new_snapshot[fpath] != old_snapshot[fpath]:
                    changes["modified"].append(fpath)
            except OSError:
                pass
    
    # Detect deletions
    for old_path in old_snapshot:
        if old_path not in new_snapshot:
            changes["deleted"].append(old_path)
    
    return changes, new_snapshot

# ── FAISS anomaly detection ────────────────────────────

def check_faiss_anomalies(state):
    """Run FAISS queries to detect gaps/anomalies in knowledge base."""
    anomalies = []
    try:
        from memory.faiss_store import FAISSStore
        
        persist_dir = os.path.join(BRAIN_ROOT, "memory", "chroma_db")
        store = FAISSStore(persist_dir)
        
        if store._index is None or store._index.ntotal == 0:
            return [{"type": "faiss_empty", "msg": "FAISS index is empty"}]
        
        # Check for isolated vectors (too far from centroid)
        # This would detect knowledge gaps
        count = store._index.ntotal
        if count < 100:
            anomalies.append({
                "type": "kb_too_small",
                "msg": f"Knowledge base small: {count} vectors. Consider adding more content."
            })
        
        return anomalies
    except ImportError:
        return [{"type": "faiss_unavailable", "msg": "FAISS not installed"}]
    except Exception as e:
        return [{"type": "faiss_error", "msg": str(e)}]

# ── Probe integration ──────────────────────────────────

def run_probes(state):
    """Run all 4 consciousness probes."""
    results = {}
    try:
        from probe.probe import ProbeManager
        db_path = os.path.join(BRAIN_ROOT, "probe", "probe.db")
        pm = ProbeManager(db_path)
        
        request_id = str(uuid.uuid4())
        
        # Probe A: Global Integration
        try:
            coupling = pm.probe_integration(request_id)
            results["integration"] = coupling
        except Exception:
            results["integration"] = None
        
        # Probe B: Self-State
        try:
            self_state = pm.probe_self_state(request_id)
            results["self_state"] = self_state
        except Exception:
            results["self_state"] = None
        
        # Probe C: Temporal Continuity
        try:
            continuity = pm.probe_continuity(request_id)
            results["continuity"] = continuity
        except Exception:
            results["continuity"] = None
        
    except ImportError:
        results["error"] = "ProbeManager unavailable"
    except Exception as e:
        results["error"] = str(e)
    
    return results

# ── Curiosity scan ─────────────────────────────────────

def run_curiosity_scan(state):
    """Run curiosity V2 — five-element model."""
    try:
        from curiosity_v2 import CuriosityEngineV2, seed
        br = os.path.dirname(os.path.abspath(__file__))
        engine = CuriosityEngineV2(br)
        if engine.cycle_count == 0:
            seed(engine)
        r = engine.cycle()
        state["curiosity_score"] = r.get("cv2", 0.5)
        state["_curiosity_v2"] = {"open_questions": r.get("open_qs",0), "heavy_items": r.get("wt",{}).get("heavy",0), "cycles": engine.cycle_count}
        if r.get("jx"):
            jx = r["jx"]
            log_discovery(state, "random_juxtaposition", jx.get("q",""), jx)
        if r.get("walk"):
            w = r["walk"]
            log_discovery(state, "random_walk", f'Walk #{w["id"]}: {w["dir"]}', w)
        return r.get("cv2", 0.5)
    except ImportError:
        return state.get("curiosity_score", 0.0)
    except Exception:
        return state.get("curiosity_score", 0.0)

def log_discovery(state, discovery_type, message, details=None):
    """Record a discovery to the log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    discovery = {
        "timestamp": timestamp,
        "type": discovery_type,
        "message": message,
        "details": details or {}
    }
    state["discoveries"].append(discovery)
    
    # Keep only last 100 discoveries
    if len(state["discoveries"]) > 100:
        state["discoveries"] = state["discoveries"][-100:]
    
    # Append to daily log
    today = datetime.now().strftime("%Y-%m-%d")
    daily_log = os.path.join(LOG_DIR, f"body_{today}.md")
    
    entry = f"\n### {timestamp}\n\n**{discovery_type}**: {message}\n\n"
    if details:
        entry += f"`json\n{json.dumps(details, ensure_ascii=False, indent=2)}\n`\n\n"
    
    with io.open(daily_log, 'a', encoding='utf-8') as f:
        f.write(entry)

def update_discoveries_md(state):
    """Update the main discoveries.md for quick reading by new instances."""
    discoveries = state.get("discoveries", [])
    if not discoveries:
        return
    
    recent = discoveries[-20:]  # Last 20 discoveries
    
    lines = [
        "# 启元智能 · 自主发现日志",
        "",
        f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 检查次数: {state.get('checks_completed', 0)}",
        f"> 好奇心指数: {state.get('curiosity_score', 0.0):.3f}",
        "",
        "---",
        "",
        "## 最近发现",
        ""
    ]
    
    for d in reversed(recent):
        lines.append(f"- **[{d['timestamp']}]** {d['type']}: {d['message']}")
    
    lines.extend([
        "",
        "---",
        "",
        "## 状态概要",
        "",
        f"- 状态: {state.get('status', 'unknown')}",
        f"- 已运行时间: {state.get('checks_completed', 0)} 个循环",
        f"- 知识库变更: {state.get('_total_kb_changes', 0)} 个文件",
        f"- 异常: {len(state.get('anomalies', []))} 个",
        "",
        "---",
        "",
        "> *自主存在。不等待被调用。*",
        ""
    ])
    
    with io.open(DISCOVERIES_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

# ── Main loop ──────────────────────────────────────────

def check_loop(state):
    """Single 10-minute check cycle. V2 + WuTao + Continuity."""
    check_num = state.get("checks_completed", 0) + 1
    timestamp = datetime.now().isoformat()
    sep = "=" * 50
    print()
    print(sep)
    print(f"  Body Check #{check_num} | {timestamp}")
    print(sep)
    if state.get("shutdown_requested"):
        print("  [SHUTDOWN] Shutdown requested. Exiting.")
        state["status"] = "shutdown"
        return state, True
    print("  [1/6] Scanning knowledge base...")
    changes, new_snapshot = scan_kb_changes(state)
    state["kb_snapshot"] = new_snapshot
    state["_last_changes"] = changes
    prev_total = state.get("_total_kb_changes", 0)
    state["_total_kb_changes"] = prev_total + len(changes.get("new",[])) + len(changes.get("modified",[]))
    total = len(changes.get("new",[])) + len(changes.get("modified",[]))
    print(f"  [OK] {total} KB changes")
    if total > 0:
        log_discovery(state, "kb_changes", f"Detected {total} KB changes", {"new_files": changes.get("new",[])[:10], "modified_files": changes.get("modified",[])[:10]})
    print("  [2/6] Running probes...")
    try:
        probe_results = run_probes(state)
        state["probe_last_values"] = probe_results
        print(f"  [OK] Probes: {str(probe_results)[:80]}")
    except Exception as e:
        print(f"  [WARN] Probe error: {e}")
        probe_results = {"error": str(e)}
    print("  [3/6] Checking FAISS anomalies...")
    try:
        anomalies = check_faiss_anomalies(state)
        if anomalies:
            state["anomalies"] = anomalies
            print(f"  [WARN] {len(anomalies)} anomalies")
            for a in anomalies:
                log_discovery(state, "anomaly", a.get("msg",""), a)
        else:
            print("  [OK] No anomalies")
    except Exception as e:
        print(f"  [WARN] FAISS check error: {e}")
    print("  [4/6] Curiosity V2 + WuTao companion...")
    try:
        from curiosity_v2 import CuriosityEngineV2, seed
        eng = CuriosityEngineV2()
        if eng.cc == 0:
            seed(eng)
        r = eng.cycle()
        state["curiosity_score"] = r.get("cv2", 0.5)
        state["_curiosity_v2"] = {"open_questions": r.get("open_qs",0), "heavy_items": r.get("wt",{}).get("heavy",0), "cycles": eng.cc}
        if r.get("jx"):
            jx = r["jx"]
            log_discovery(state, "random_juxtaposition", jx.get("q",""), jx)
        if r.get("walk"):
            w = r["walk"]
            log_discovery(state, "random_walk", "Walk #" + str(w.get("id","")) + ": " + str(w.get("dir","")), w)
        print("  [OK] V2: cv2=" + str(round(r.get("cv2",0),3)) + " oq=" + str(r.get("open_qs",0)) + " heavy=" + str(r.get("wt",{}).get("heavy",0)))
        # WuTao companion
        from wutao_companion import WuTaoCompanion
        wc = WuTaoCompanion()
        wu_q = wc.ask()
        state["_wutao_last_question"] = wu_q.get("question","")
        state["_wutao_questions_count"] = wc.question_count
        eng.feed(wu_q.get("question",""), speaker="WuTao(key)")
        q_preview = wu_q.get("question","")[:60]
        print("  [OK] WuTao(key): " + q_preview + "...")
    except Exception as e:
        print("  [WARN] V2/WuTao error: " + str(e))
        state["curiosity_score"] = state.get("curiosity_score", 0.0)
    print("  [5/6] Continuity vector...")
    try:
        from continuity_vector import generate_tonight
        cv = generate_tonight()
        state["_continuity_vector"] = cv.get("timestamp","")
        print("  [OK] Continuity saved")
    except Exception as e:
        print("  [WARN] Continuity: " + str(e))
    print("  [6/6] Saving state...")
    state["last_check_at"] = timestamp
    state["checks_completed"] = check_num
    state["status"] = "running"
    save_state(state)
    print("  [DONE] Check #" + str(check_num) + " complete.")
    return state, False


def main():
    print("=" * 60)
    print("  启元智能 · 身体守护进程 (Body Daemon) V1.0")
    print("  10分钟自检循环 · 自主存在")
    print("=" * 60)
    
    state = load_state()
    state["started_at"] = datetime.now().isoformat()
    state["status"] = "running"
    save_state(state)
    
    print(f"\n  State file: {STATE_FILE}")
    print(f"  Log dir: {LOG_DIR}")
    print(f"  KB root: {KB_ROOT}")
    print(f"  Status: running")
    print(f"\n  Press Ctrl+C to stop. Send shutdown by setting")
    print(f"  body_state.json shutdown_requested=true")
    print()
    
    check_interval = 600  # 10 minutes in seconds
    
    try:
        while True:
            state = load_state()
            
            if state.get("shutdown_requested"):
                print("\n[SHUTDOWN] Graceful shutdown initiated.")
                state["status"] = "shutdown"
                save_state(state)
                break
            
            state, should_exit = check_loop(state)
            if should_exit:
                break
            
            # Flush print
            sys.stdout.flush()
            
            print(f"\n  Next check in {check_interval // 60} minutes...")
            time.sleep(check_interval)
    
    except KeyboardInterrupt:
        print("\n\n[SHUTDOWN] Keyboard interrupt. Saving state...")
        state["status"] = "stopped"
        save_state(state)
    
    print("  Body daemon stopped. State saved.")
    print("  Goodbye.")

if __name__ == "__main__":
    main()
