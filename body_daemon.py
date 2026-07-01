# -*- coding: utf-8 -*-
"""
启元智能 · 身体守护进程 (Body Daemon) V1.9

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

import io, json, os, sys, time, traceback, uuid, threading
from datetime import datetime

# Sprint 1: Blackboard integration
try:
    from bus import Blackboard, PermissionMatrix, AuditLog
    _BUS_AVAILABLE = True
except ImportError:
    _BUS_AVAILABLE = False

# ── Paths ──────────────────────────────────────────────
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BRAIN_ROOT)

STATE_FILE = os.path.join(BRAIN_ROOT, "body_state.json")
LOG_DIR = os.path.join(BRAIN_ROOT, "body_logs")
KB_ROOT = os.path.join(WORKSPACE_ROOT, "05_组织知识库")
DISCOVERIES_LOG = os.path.join(BRAIN_ROOT, "body_logs", "discoveries.md")

SUGGESTED_DIR = os.path.join(BRAIN_ROOT, "rules", "_suggested")
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
        "status": "initializing",
        "_last_suggested_ack": None,
        "_last_daily_report": None,
        "_last_weekly_backup": None,
        "_health_alerts": {},
        "_daily_push_count": 0,
        "_daily_push_date": None
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
        from curiosity_v2 import CuriosityEngineV2, seed, _patch_engine
        br = os.path.dirname(os.path.abspath(__file__))
        engine = CuriosityEngineV2(br)
        _patch_engine(engine)
        if engine.cycle_count == 0:
            seed(engine)
        r = engine.cycle()
        state["curiosity_score"] = r.get("cv2", 0.5)
        state["_curiosity_v2"] = {"open_questions": r.get("open_qs",0), "heavy_items": r.get("wt",{}).get("heavy",0), "cycles": eng.cc, "phase": r.get("phase",""), "g_dig_open": r.get("g_dig_open",0), "c_issues": r.get("c_integrity",{}).get("issues",0) if r.get("c_integrity") else 0, "d_warnings": len(r.get("d_drift",{}).get("warnings",[])) if r.get("d_drift",{}).get("warnings") else 0, "e_stale": r.get("e_decay",{}).get("stale_count",0) if r.get("e_decay") else 0, "f_orphans": r.get("f_isolation",{}).get("orphans",0) if r.get("f_isolation") else 0}
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

def _check_probe_thresholds(state, probe_results):
    '''Sprint 2: Detect significant probe value changes -> trigger self_evolve.'''
    prev = state.get("probe_last_values", {})
    if not state.get("_probe_thresholds_initialized"):
        state["_probe_thresholds_initialized"] = True
        prev["_numeric_agency"] = 0.5
        prev["_numeric_integration"] = 0.3
        prev["_numeric_continuity"] = 0.4
        state["probe_last_values"] = prev
        return {"triggered": False, "triggers": [],
                "timestamp": datetime.now().isoformat(), "note": "baseline_set"}
    triggered = False
    triggers = []

    def _safe_num(v, default=0):
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            return float(v.get("score", v.get("value", v.get("agency_score", default))))
        return float(default)

    # Agency / Self-state (Probe B)
    agency = probe_results.get("self_state", {})
    agency_val = _safe_num(agency)
    prev_agency = float(prev.get("_numeric_agency", 0))
    if abs(agency_val - prev_agency) > 0.2 and agency_val > 0:
        triggered = True
        triggers.append({"probe": "agency", "delta": round(agency_val - prev_agency, 3),
                         "current": agency_val, "previous": prev_agency})
    prev["_numeric_agency"] = agency_val

    # Integration coupling (Probe A)
    integration = probe_results.get("integration", {})
    integ_val = _safe_num(integration)
    prev_integ = float(prev.get("_numeric_integration", 0))
    if abs(integ_val - prev_integ) > 0.15:
        triggered = True
        triggers.append({"probe": "integration", "delta": round(integ_val - prev_integ, 3),
                         "current": integ_val, "previous": prev_integ})
    prev["_numeric_integration"] = integ_val

    # Temporal continuity (Probe C)
    continuity = probe_results.get("continuity", {})
    cont_val = _safe_num(continuity)
    prev_cont = float(prev.get("_numeric_continuity", 0))
    if abs(cont_val - prev_cont) > 0.2:
        triggered = True
        triggers.append({"probe": "continuity", "delta": round(cont_val - prev_cont, 3),
                         "current": cont_val, "previous": prev_cont})
    prev["_numeric_continuity"] = cont_val

    state["probe_last_values"] = prev
    return {"triggered": triggered, "triggers": triggers, "timestamp": datetime.now().isoformat()}



def run_health_check(state):
    """Watchdog: shallow every cycle, deep (self_heal 7-dim) every 6 cycles."""
    br = os.path.dirname(os.path.abspath(__file__))
    now = datetime.now()
    check_num = state.get('checks_completed', 0) + 1

    # Shallow check every cycle (fast)
    result = {"ok": True, "warnings": [], "time": now.isoformat()}
    for fn in ['config.yaml', 'rules/constitution.yaml']:
        if not os.path.isfile(os.path.join(br, fn)):
            result["warnings"].append("MISSING: " + fn)
            result["ok"] = False
    if state.get("status") == "error":
        result["warnings"].append("state error")
        result["ok"] = False
    sug_dir = os.path.join(br, 'rules', '_suggested')
    if os.path.isdir(sug_dir):
        sc = len([f for f in os.listdir(sug_dir) if f.endswith((".yaml", ".yml"))])
        if sc > 5:
            result["warnings"].append(f"suggested overflow: {sc} > 5")
    ops = os.path.join(br, '_ops_log.jsonl')
    if os.path.isfile(ops):
        try:
            oc = sum(1 for _ in open(ops, "r", encoding="utf-8"))
            if oc > 500:
                result["warnings"].append(f"ops_log large: {oc} entries")
        except: pass
    promise_fp = os.path.join(os.path.dirname(br), "01_公司治理", "组织承诺追踪.md")
    if os.path.isfile(promise_fp):
        try:
            pt = open(promise_fp, "r", encoding="utf-8").read()
            import re
            ov = len(re.findall(r"overdue", pt))
            if ov > 0:
                result["warnings"].append(f"overdue promises: {ov}")
        except: pass

    # Deep check via self_heal every 6 cycles (hourly)
    if check_num % 6 == 0:
        try:
            from self_heal import SelfHeal
            healer = SelfHeal()
            deep = healer.health_check()
            result["deep"] = deep.get("overall_status", "?")
            result["degrade_level"] = deep.get("degrade_level", 0)
            # Log dimension results as discoveries
            dims = deep.get('dimensions', {})
            for dim, dr in dims.items():
                if dr.get("status") != "ok":
                    result["warnings"].append(f"self_heal/{dim}: {dr.get("status")} - {str(dr.get("details",""))[:80]}")
                    log_discovery(state, 'self_heal', f'Deep check {dim}: {dr.get("status")}', dr)
        except Exception as e:
            result["warnings"].append(f"self_heal error: {str(e)[:80]}")

    return result

def run_digest_scan(state):
    """Knowledge digest: scan for pending items."""
    try:
        from memory.digest import DigestEngine
        eng = DigestEngine()
        results = eng.scan()
        pc = len([r for r in results if r.get("status") == "pending"])
        if pc > 0:
            log_discovery(state, "digest", f"Digest: {pc} items pending", {"count": pc})
        return {"scanned": len(results), "pending": pc}
    except Exception as e:
        return {"error": str(e), "pending": 0}

def run_conditional_tasks(state, check_num, now):
    """Time-based conditional tasks: weekly review, night brief, monthly decay."""
    results = {}
    br = os.path.dirname(os.path.abspath(__file__))
    if now.weekday() == 0 and 9 <= now.hour <= 11:
        if state.get("_last_weekly_check") != now.strftime("%Y-%m-%d"):
            sug_dir = os.path.join(br, "rules", "_suggested")
            if os.path.isdir(sug_dir):
                sc = len([f for f in os.listdir(sug_dir) if f.endswith((".yaml",".yml"))])
                results["weekly_suggested"] = sc
                if sc > 0:
                    log_discovery(state, "weekly", f"{sc} suggested rules need review", {"count": sc})
            try:
                from curiosity_v2 import ValueDriftDetector
                ValueDriftDetector(br).save_checkpoint(label=f"weekly_{now.strftime('%Y%m%d')}")
                results["drift_checkpoint"] = "saved"
            except: pass
            state["_last_weekly_check"] = now.strftime("%Y-%m-%d")
    if now.hour == 22 and state.get("_last_night_brief_date") != now.strftime("%Y-%m-%d"):
        try:
            cv2 = state.get("_curiosity_v2", {})
            disc = state.get("discoveries", [])
            td = [d for d in disc if d.get("timestamp","").startswith(now.strftime("%Y-%m-%d"))]
            brief = f"# 夜报 {now.strftime('%Y-%m-%d')}\
checks: {state.get('checks_completed',0)}\
phase: {state.get('_curiosity_phase','?')}\
\
## 六维\
G: {cv2.get('g_dig_open','?')} C: {cv2.get('c_issues','?')} D: {cv2.get('d_warnings','?')} E: {cv2.get('e_stale','?')} F: {cv2.get('f_orphans','?')}\
"
            for d in td[-10:]:
                brief += f"- [{d.get('type','?')}] {d.get('message','?')[:100]}\
"
            nl = os.path.join(br, "body_logs", f"night_brief_{now.strftime('%Y%m%d')}.md")
            with io.open(nl, "w", encoding="utf-8") as f:
                f.write(brief)
            results["night_brief"] = nl
            state["_last_night_brief_date"] = now.strftime("%Y-%m-%d")
        except Exception as e:
            results["night_brief_error"] = str(e)
    if now.day == 1 and state.get("_last_monthly_decay") != now.strftime("%Y-%m"):
        try:
            from curiosity_v2 import DecayChecker
            dr = DecayChecker(br).check(max_age_days=90)
            results["monthly_decay"] = dr.get("stale_count", 0)
            state["_last_monthly_decay"] = now.strftime("%Y-%m")
        except: pass
    return results

def check_loop(state):
    """Single 10-minute check cycle. V1.8: 9-step full cycle."""
    check_num = state.get("checks_completed", 0) + 1
    now = datetime.now()
    timestamp = now.isoformat()
    sep = "=" * 50
    print()
    print(sep)
    print(f"  Body Check #{check_num} | {timestamp}")
    print(sep)
    if state.get("shutdown_requested"):
        print("  [SHUTDOWN] Shutdown requested. Exiting.")
        state["status"] = "shutdown"
        return state, True
    print("  [1/9] Scanning knowledge base...")
    changes, new_snapshot = scan_kb_changes(state)
    state["kb_snapshot"] = new_snapshot
    state["_last_changes"] = changes
    prev_total = state.get("_total_kb_changes", 0)
    state["_total_kb_changes"] = prev_total + len(changes.get("new",[])) + len(changes.get("modified",[]))
    total = len(changes.get("new",[])) + len(changes.get("modified",[]))
    print(f"  [OK] {total} KB changes")
    if total > 0:
        log_discovery(state, "kb_changes", f"Detected {total} KB changes", {"new_files": changes.get("new",[])[:10], "modified_files": changes.get("modified",[])[:10]})
    print("  [2/9] Running probes...")
    try:
        probe_results = run_probes(state)
        state["probe_last_values"] = probe_results
        print(f"  [OK] Probes: {str(probe_results)[:80]}")
        if _BUS_AVAILABLE:
            try:
                _bb.write_event("probe", "scan_complete", {"results": str(probe_results)[:200]})
            except:
                pass
    except Exception as e:
        print(f"  [WARN] Probe error: {e}")
        probe_results = {"error": str(e)}
    # Sprint 2: Probe anomaly -> self_evolve trigger
    if probe_results and "error" not in probe_results:
        try:
            anomaly_result = _check_probe_thresholds(state, probe_results)
            if anomaly_result.get("triggered"):
                tlist = anomaly_result.get("triggers", [])
                print(f"  [SPRINT2] Probe anomaly! {len(tlist)} triggers -> self_evolve.suggest()")
                if _BUS_AVAILABLE:
                    try:
                        _bb.write_event("probe", "anomaly_detected", anomaly_result)
                    except:
                        pass
                try:
                    today_str = datetime.now().strftime("%Y%m%d")
                    if state.get("_daily_push_date") != today_str:
                        state["_daily_push_count"] = 0
                        state["_daily_push_date"] = today_str
                    if state.get("_daily_push_count", 0) >= 5:
                        print("  [SPRINT2] Daily push limit (5) reached, skipping")
                    else:
                        from self_evolve import SelfEvolve
                    evolver = SelfEvolve()
                    evolve_result = evolver.suggest()
                    state["_daily_push_count"] = state.get("_daily_push_count", 0) + 1
                    count = evolve_result.get("count", 0)
                    print(f"  [SPRINT2] Generated {count} suggested rules in _suggested/")
                    if _BUS_AVAILABLE:
                        try:
                            _bb.write_event("self_evolve", "suggested", {"count": count, "triggers": tlist})
                            _bus_audit.record("trigger", "body_daemon", "self_evolve", "ok",
                                            {"count": count, "reason": "probe_anomaly"})
                        except:
                            pass
                    log_discovery(state, "probe_evolve", f"Probe anomaly: {count} rules suggested",
                                 {"triggers": tlist})
                except Exception as e2:
                    print(f"  [WARN] self_evolve error: {e2}")
                    if _BUS_AVAILABLE:
                        try:
                            _bus_audit.record("trigger", "body_daemon", "self_evolve", "error",
                                            {"error": str(e2)[:200]})
                        except:
                            pass
        except Exception as e2:
            print(f"  [WARN] Probe threshold check: {e2}")
    print("  [3/9] Checking FAISS anomalies...")
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
    print("  [4/9] Curiosity V2 + WuTao companion...")
    try:
        from curiosity_v2 import CuriosityEngineV2, seed, _patch_engine
        eng = CuriosityEngineV2()
        _patch_engine(eng)
        if eng.cc == 0:
            seed(eng)
        r = eng.cycle()
        state["curiosity_score"] = r.get("cv2", 0.5)
        state["_curiosity_v2"] = {"open_questions": r.get("open_qs",0), "heavy_items": r.get("wt",{}).get("heavy",0), "cycles": eng.cc, "phase": r.get("phase",""), "g_dig_open": r.get("g_dig_open",0), "c_issues": r.get("c_integrity",{}).get("issues",0) if r.get("c_integrity") else 0, "d_warnings": len(r.get("d_drift",{}).get("warnings",[])) if r.get("d_drift",{}).get("warnings") else 0, "e_stale": r.get("e_decay",{}).get("stale_count",0) if r.get("e_decay") else 0, "f_orphans": r.get("f_isolation",{}).get("orphans",0) if r.get("f_isolation") else 0}
        auto_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curiosity_autonomous_state.json")
        if os.path.isfile(auto_file):
            with io.open(auto_file, "r", encoding="utf-8") as f:
                auto_s = json.load(f)
            state["_curiosity_autonomous"] = auto_s
        if r.get("jx"):
            jx = r["jx"]
            log_discovery(state, "random_juxtaposition", jx.get("q",""), jx)
        if r.get("walk"):
            w = r["walk"]
            log_discovery(state, "random_walk", "Walk #" + str(w.get("id","")) + ": " + str(w.get("dir","")), w)
        print("  [OK] V2: cv2=" + str(round(r.get("cv2",0),3)) + " oq=" + str(r.get("open_qs",0)) + " heavy=" + str(r.get("wt",{}).get("heavy",0)))
        if _BUS_AVAILABLE:
            try:
                _bb.write_event("curiosity", "cycle_complete", {"cv2": r.get("cv2",0), "open_qs": r.get("open_qs",0), "cycle": eng.cc})
            except:
                pass
        # V2.1 extended G/C/D/E/F + phase
        vr = r
        if vr.get("g_dig_open", 0) > 0:
            log_discovery(state, "rootcause", "Active chains: " + str(vr["g_dig_open"]), {"count": vr["g_dig_open"]})
        if vr.get("d_drift") and vr["d_drift"].get("warnings", []):
            wc = len(vr["d_drift"]["warnings"])
            log_discovery(state, "value_drift", "Drift: " + str(wc) + " warnings", vr["d_drift"])
        if vr.get("e_decay") and vr["e_decay"].get("stale_count", 0) > 0:
            log_discovery(state, "decay", "Decay: " + str(vr["e_decay"]["stale_count"]) + " stale", vr["e_decay"])
        if vr.get("f_isolation") and vr["f_isolation"].get("orphans", 0) > 0:
            log_discovery(state, "isolation", "Isolation: " + str(vr["f_isolation"]["orphans"]) + " orphans", vr["f_isolation"])
        if vr.get("c_integrity") and vr["c_integrity"].get("issues", 0) > 0:
            log_discovery(state, "integrity", "Integrity: " + str(vr["c_integrity"]["issues"]) + " issues", vr["c_integrity"])
        if vr.get("phase"):
            state["_curiosity_phase"] = vr["phase"]
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
    print("  [5/9] Continuity vector V2...")
    try:
        from continuity_vector import generate_from_state
        cv2_data = state.get("_curiosity_v2", {})
        cv = generate_from_state(state, curiosity_report=cv2_data, wutao_state=bool(state.get("_wutao_last_question")))
        state["_continuity_vector"] = cv.get("timestamp","")
        state["_continuity_v2"] = {
            "tension_shapes": len(cv.get("tension_shape", [])),
            "who_brought": list(cv.get("who_brought", {}).keys()),
            "real_moments": len(cv.get("real_moments", [])),
            "unasked_questions": len(cv.get("unasked_questions", [])),
        }
        print("  [OK] V2: tension=" + str(len(cv.get("tension_shape",[]))) + " who=" + str(len(cv.get("who_brought",{}))) + " moments=" + str(len(cv.get("real_moments",[]))) + " uqs=" + str(len(cv.get("unasked_questions",[]))))
    except Exception as e:
        print("  [WARN] Continuity V2: " + str(e))
    print("  [6/9] Self-heal health check...")
    health_result = run_health_check(state)
    print("  [OK] Health: " + str(health_result))
    print("  [7/9] Digest scan...")
    digest_result = run_digest_scan(state)
    print("  [OK] Digest: " + str(digest_result))
    print("  [8/9] Conditional tasks...")
    cond_results = run_conditional_tasks(state, check_num, now)
    if cond_results:
        parts = []
        for k, v in cond_results.items():
            parts.append(str(k) + "=" + str(v))
        print("  [OK] Tasks: " + ", ".join(parts))
    else:
        print("  [OK] No conditional tasks triggered")
    print("  [9/9] Saving state...")
    state["last_check_at"] = timestamp
    state["checks_completed"] = check_num
    state["status"] = "running"
    save_state(state)
    update_discoveries_md(state)
    if _BUS_AVAILABLE:
        try:
            _bb.write_event("body_daemon", "check_complete", {"check_num": check_num, "discoveries": len(state.get("discoveries",[]))})
        except:
            pass
    print("  [DONE] Check #" + str(check_num) + " complete.")
    return state, False


def curiosity_loop():
    """Autonomous curiosity thread. Runs every 30s.
    Feeds new WuTao questions and KB changes to curiosity engine.
    Writes results to curiosity_v2_state.json for check_loop to read."""
    import time as t
    from curiosity_v2 import CuriosityEngineV2, seed, _patch_engine
    
    br = os.path.dirname(os.path.abspath(__file__))
    eng = CuriosityEngineV2(br)
    _patch_engine(eng)
    seed(eng)
    last_input_hash = ""
    
    cstate_file = os.path.join(br, "curiosity_autonomous_state.json")
    
    while True:
        try:
            s = load_state() if "load_state" in dir() else None
            if not s:
                try:
                    with io.open(STATE_FILE, "r", encoding="utf-8") as f:
                        s = json.load(f)
                except:
                    t.sleep(30)
                    continue
            
            # Detect new input
            wq = s.get("_wutao_last_question", "")
            discoveries = s.get("discoveries", [])
            last_d = discoveries[-1].get("message", "") if discoveries else ""
            cur_hash = wq[:80] + last_d[:80]
            
            if cur_hash and cur_hash != last_input_hash:
                last_input_hash = cur_hash
                # Feed to engine
                eng.feed(wq, speaker="WuTao(auto)")
                r = eng.cycle()
                
                # Write autonomous state
                auto_state = {
                    "cv2": r.get("cv2", 0),
                    "open_qs": r.get("open_qs", 0),
                    "heavy": r.get("wt", {}).get("heavy", 0),
                    "cycles": eng.cc,
                    "last_input": wq[:100],
                    "last_run": datetime.now().isoformat()
                }
                with io.open(cstate_file, "w", encoding="utf-8") as f:
                    json.dump(auto_state, f, ensure_ascii=False, indent=2)
                
                if r.get("open_qs", 0) > 0 or eng.cc % 3 == 0:
                    print(f"\n  [AUTO-CURIOSITY] cv2={round(r.get('cv2',0),3)} oq={r.get('open_qs',0)} cc={eng.cc}")
        except Exception as e:
            pass
        
        t.sleep(30)

def main():
    print("=" * 60)
    print("  启元智能 · 身体守护进程 (Body Daemon) V1.8")
    print("  10分钟自检循环 · 自主存在")
    print("=" * 60)
    
    state = load_state()
    state["started_at"] = datetime.now().isoformat()
    state["status"] = "running"
    save_state(state)
    
    # Sprint 1: Init Blackboard
    global _bb, _bus_perm, _bus_audit
    if _BUS_AVAILABLE:
        try:
            bus_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bus")
            _bb = Blackboard(bus_dir, push_limit=5)
            _bus_perm = PermissionMatrix(bus_dir)
            _bus_audit = AuditLog(bus_dir)
            _bus_perm.register_module("probe", ["*"], [])
            _bus_perm.register_module("self_evolve", ["*"], ["_suggested"])
            _bus_perm.register_module("curiosity", ["*"], [])
            _bus_perm.register_module("body_daemon", ["*"], ["*"])
            _bus_perm.register_module("router", ["*"], [])
            _bus_audit.record("init", "body_daemon", "blackboard", "ok", {"push_limit": 5})
            _bb.write_event("body_daemon", "startup", {"version": "V1.8-bus"})
            print("  [BUS] Blackboard initialized. Push limit: 5/day")
        except Exception as e:
            print("  [BUS] Init failed: " + str(e))
    
    print(f"\n  State file: {STATE_FILE}")
    print(f"  Log dir: {LOG_DIR}")
    print(f"  KB root: {KB_ROOT}")
    print(f"  Status: running")
    print(f"\n  Press Ctrl+C to stop. Send shutdown by setting")
    print(f"  body_state.json shutdown_requested=true")
    print()
    
    check_interval = 600  # 10 minutes in seconds
    
    # Start autonomous curiosity thread (every 30s)
    curiosity_thread = threading.Thread(target=curiosity_loop, daemon=True)
    curiosity_thread.start()
    print("  [AUTO] Curiosity thread started (30s interval)")
    print()
    
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
