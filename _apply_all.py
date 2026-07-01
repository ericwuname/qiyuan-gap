import io, os

P = r"D:\0.个人文档\个人文档\启元智能\brain\body_daemon.py"
C = io.open(P, "r", encoding="utf-8").read()

# === Patch 1: SUGGESTED_DIR ===
C = C.replace(
    "os.makedirs(LOG_DIR, exist_ok=True)",
    'SUGGESTED_DIR = os.path.join(BRAIN_ROOT, "rules", "_suggested")\nos.makedirs(LOG_DIR, exist_ok=True)'
)

# === Patch 2: _default_state new keys ===
C = C.replace(
    '"status": "initializing"',
    '"status": "initializing",\n        "_last_suggested_ack": null,\n        "_last_daily_report": null,\n        "_last_weekly_backup": null,\n        "_health_alerts": {}'
)

# === Patch 3: Insert all new functions before "Main loop" ===
NEW_FUNCS = """
# ---------- Health check ----------
def run_health_check(state):
    try:
        from self_heal import check_and_alert
        result = check_and_alert()
        state["_health_snapshot"] = {"disk_usage_pct": result.get("disk_usage_pct", 0), "memory_usage_pct": result.get("memory_usage_pct", 0), "overall_health": result.get("overall_health", "unknown"), "degrade_level": result.get("degrade_level", 0)}
        alerts = result.get("alerts", [])
        if len(alerts) > 0:
            log_discovery(state, "health_alert", str(len(alerts)) + " health alerts", {"alerts": alerts[:5]})
            return str(len(alerts)) + " alerts"
        return "OK"
    except Exception as e:
        return "err:" + str(e)[:60]

# ---------- Digest scan ----------
def run_digest_scan(state):
    try:
        from memory.digest import scan, pending
        new_items = scan()
        pending_items = pending()
        total_new = len(new_items) + len(pending_items)
        state["_digest_snapshot"] = {"new_scanned": len(new_items), "pending": len(pending_items), "total": total_new}
        if total_new > 0:
            log_discovery(state, "digest", str(total_new) + " new inputs to digest")
            return str(total_new) + " new"
        return "0 new"
    except Exception as e:
        return "err:" + str(e)[:60]

# ---------- Constitution drift ----------
def run_constitution_check(state):
    try:
        from sync_constitution import check_drift as cd, get_stale_count as gsc
        results = cd()
        stale = gsc(results)
        state["_const_drift"] = {"stale_count": stale}
        if stale > 0:
            log_discovery(state, "const_drift", str(stale) + " YAML stale vs Markdown")
            return str(stale) + " stale"
        return "OK"
    except Exception as e:
        return "err:" + str(e)[:60]

# ---------- Daily ritual ----------
def run_daily_ritual(state):
    try:
        from daily_ritual import run_ritual
        ritual = run_ritual()
        state["_daily_ritual"] = ritual
        reminders = ritual.get("reminders", [])
        if reminders:
            log_discovery(state, "daily_ritual", str(len(reminders)) + " reminders", {"reminders": reminders})
            return str(len(reminders)) + " reminders"
        return "OK"
    except Exception as e:
        return "err:" + str(e)[:60]

# ---------- Suggested rules notification ----------
def check_suggested_rules(state):
    try:
        if not os.path.isdir(SUGGESTED_DIR):
            return null
        files = [f for f in os.listdir(SUGGESTED_DIR) if f.endswith(".yaml")]
        if not files:
            return null
        last_ack = state.get("_last_suggested_ack")
        latest_mtime = max(os.path.getmtime(os.path.join(SUGGESTED_DIR, f)) for f in files)
        from datetime import datetime as dt
        latest_mtime_str = dt.fromtimestamp(latest_mtime).isoformat()
        if last_ack is null or latest_mtime_str > last_ack:
            state["_suggested_pending"] = {"count": len(files), "newest": latest_mtime_str}
            return len(files)
        return null
    except:
        return null

# ---------- Conditional tasks ----------
def run_conditional_tasks(state, check_num, now):
    results = {}

    # Daily ritual
    d = run_daily_ritual(state)
    if d != "OK" and d != "0 reminders":
        results["ritual"] = d

    # Constitution drift
    d = run_constitution_check(state)
    if d != "OK":
        results["constitution"] = d

    # _suggested_ notification
    sug_count = check_suggested_rules(state)
    if sug_count:
        log_discovery(state, "suggested_rules", str(sug_count) + " unacknowledged suggestions in _suggested/", {"count": sug_count})
        results["suggested"] = str(sug_count) + " pending"

    # Hourly LTM
    if check_num % 6 == 0:
        try:
            from memory.long_term_memory import LongTermMemory
            ltm = LongTermMemory()
            state["_ltm_snapshot"] = {"records": len(ltm._texts) if hasattr(ltm, "_texts") else 0}
            results["ltm"] = "consolidated"
        except:
            results["ltm"] = "unavailable"

    # Daily (after 22:00)
    today = now.strftime("%Y-%m-%d")
    last_daily = state.get("_last_daily_report", "")
    if today != last_daily and now.hour >= 22:
        state["_last_daily_report"] = today
        try:
            from report.nightly_report import load_config, collect_data, generate_report, save_local
            config = load_config()
            data = collect_data(config)
            report_md = generate_report(data)
            saved_path = save_local(report_md)
            state["_nightly_report"] = {"path": saved_path, "date": today}
            log_discovery(state, "nightly_report", "Daily report generated: " + today)
            results["nightly"] = "generated"
        except:
            results["nightly"] = "unavailable"
        try:
            from finance.finance_module import FinanceModule
            FinanceModule()
            state["_finance_snapshot"] = {"updated": today}
            results["finance"] = "snapshot"
        except:
            results["finance"] = "unavailable"
        try:
            from hr.hr_module import HRModule
            HRModule()
            state["_hr_snapshot"] = {"updated": today}
            results["hr"] = "snapshot"
        except:
            results["hr"] = "unavailable"

    # Weekly backup (Sunday)
    weekday = now.weekday()
    last_weekly = state.get("_last_weekly_backup", "")
    week_id = now.strftime("%YW%W")
    if weekday == 6 and week_id != last_weekly:
        state["_last_weekly_backup"] = week_id
        try:
            from backup_manager import backup
            backup_path, meta = backup(BRAIN_ROOT, label="weekly_auto")
            if backup_path:
                state["_weekly_backup"] = {"path": backup_path, "date": today}
                log_discovery(state, "weekly_backup", "Weekly backup done")
                results["backup"] = "done"
            else:
                results["backup"] = meta.get("skipped", "skipped")
        except:
            results["backup"] = "unavailable"

    return results

"""

# Insert before "# ---------- Main loop"
C = C.replace("# ---------- Main loop", NEW_FUNCS + "\n# ---------- Main loop")

# === Patch 4: Rewrite check_loop ===
OLD = """def check_loop(state):
    \"\"\"Single 10-minute check cycle. V2 + WuTao + Continuity.\"\"\"
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
        # Merge autonomous curiosity state
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
    print("  [5/6] Continuity vector V2...")
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
    print("  [6/6] Saving state...")
    state["last_check_at"] = timestamp
    state["checks_completed"] = check_num
    state["status"] = "running"
    save_state(state)
    print("  [DONE] Check #" + str(check_num) + " complete.")
    return state, False"""

NEW = """def check_loop(state):
    \"\"\"Single 10-minute check cycle. V1.6: 9-step full cycle.\"\"\"
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
    except Exception as e:
        print(f"  [WARN] Probe error: {e}")
        probe_results = {"error": str(e)}
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
        from curiosity_v2 import CuriosityEngineV2, seed
        eng = CuriosityEngineV2()
        if eng.cc == 0:
            seed(eng)
        r = eng.cycle()
        state["curiosity_score"] = r.get("cv2", 0.5)
        state["_curiosity_v2"] = {"open_questions": r.get("open_qs",0), "heavy_items": r.get("wt",{}).get("heavy",0), "cycles": eng.cc}
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
    print("  [DONE] Check #" + str(check_num) + " complete.")
    return state, False"""

C = C.replace(OLD, NEW)

# === Patch 5: Update version ===
C = C.replace("V1.0", "V1.6")

# === Write ===
io.open(P, "w", encoding="utf-8").write(C)

# === Verify ===
V = io.open(P, "r", encoding="utf-8").read()
print("9 steps:", "9/9" in V)
print("health:", "run_health_check" in V)
print("digest:", "run_digest_scan" in V)
print("constitution:", "run_constitution_check" in V)
print("ritual:", "run_daily_ritual" in V)
print("conditional:", "run_conditional_tasks" in V)
print("update_discoveries:", "update_discoveries_md(state)" in V)
print("V1.6:", "V1.6" in V)
