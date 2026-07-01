# -*- coding: utf-8 -*-
"""每日仪式检查器"""

import io, os, json
from datetime import datetime

BRAIN = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BRAIN)
STATE_FILE = os.path.join(BRAIN, "body_state.json")
RITUAL_FILE = os.path.join(BRAIN, "daily_ritual.json")
SUGGESTED_DIR = os.path.join(BRAIN, "rules", "_suggested")

def run_ritual():
    results = {}
    reminders = []
    now = datetime.now()

    # 1. GitHub daily
    daily_path = os.path.join(ROOT, "04_项目", "空隙_AI原生短篇集", "发布_GitHub", "secrets",
                              now.strftime("%Y-%m-%d") + "_daily.md")
    if os.path.isfile(daily_path):
        results["github_daily"] = True
    else:
        results["github_daily"] = False
        reminders.append("GitHub daily 还没写/推送")

    # 2. _suggested/ review
    if os.path.isdir(SUGGESTED_DIR):
        pending = len([f for f in os.listdir(SUGGESTED_DIR) if f.endswith(".yaml")])
        results["suggested_review"] = pending == 0
        if pending > 0:
            reminders.append(str(pending) + " 条 _suggested/ 未审核")
    else:
        results["suggested_review"] = True

    # 3. Digest pending
    try:
        from memory.digest import stats
        s = stats()
        results["digest_pending"] = s.get("pending", 0) == 0
        if s.get("pending", 0) > 0:
            reminders.append(str(s["pending"]) + " 条 digest 待处理")
    except:
        results["digest_pending"] = None

    # 4. Constitution drift
    try:
        from sync_constitution import check_drift, get_stale_count
        stale = get_stale_count(check_drift())
        results["constitution_drift"] = stale == 0
        if stale > 0:
            reminders.append(str(stale) + " 个 YAML 滞后于宪法 Markdown")
    except:
        results["constitution_drift"] = None

    # 5. Monthly review (1st of month)
    results["monthly_review"] = now.day == 1
    if now.day == 1:
        reminders.append("今天是新的一个月——该做月度复盘了")

    # Save
    state = {
        "last_run": now.isoformat(),
        "results": results,
        "reminders": reminders,
    }
    with io.open(RITUAL_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    return state

if __name__ == "__main__":
    r = run_ritual()
    icons = {True: "[OK]", False: "[!!]", None: "[?]"}
    names = {
        "github_daily": "GitHub daily 推送",
        "suggested_review": "_suggested/ 审核",
        "digest_pending": "digest pending 处理",
        "constitution_drift": "宪法漂移",
        "monthly_review": "月度复盘",
    }
    print("=" * 40)
    print("  每日仪式检查 ·", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 40)
    for k, name in names.items():
        icon = icons.get(r["results"].get(k), "[?]")
        print("  " + icon + " " + name)
    if r["reminders"]:
        print()
        for rem in r["reminders"]:
            print("  [!] " + rem)
