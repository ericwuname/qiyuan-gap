import io
p = r"D:\0.个人文档\个人文档\启元智能\brain\body_daemon.py"
lines = io.open(p, "r", encoding="utf-8").readlines()
idx = next(i for i, line in enumerate(lines) if "def check_loop(state):" in line)

func_lines = [
    chr(10),
    "# Constitution drift check", chr(10),
    "def run_constitution_check(state):", chr(10),
    "    try:", chr(10),
    "        from sync_constitution import check_drift as cd, get_stale_count as gsc", chr(10),
    "        results = cd()", chr(10),
    "        stale = gsc(results)", chr(10),
    '        state["_const_drift"] = {"stale_count": stale}', chr(10),
    "        if stale > 0:", chr(10),
    '            log_discovery(state, "const_drift", str(stale) + " YAML stale vs Markdown")', chr(10),
    '            return str(stale) + " stale"', chr(10),
    '        return "OK"', chr(10),
    "    except Exception as e:", chr(10),
    '        return "err:" + str(e)[:60]', chr(10),
    chr(10),
    "# Daily ritual", chr(10),
    "def run_daily_ritual(state):", chr(10),
    "    try:", chr(10),
    "        from daily_ritual import run_ritual", chr(10),
    "        ritual = run_ritual()", chr(10),
    '        state["_daily_ritual"] = ritual', chr(10),
    '        reminders = ritual.get("reminders", [])', chr(10),
    "        if reminders:", chr(10),
    '            log_discovery(state, "daily_ritual", str(len(reminders)) + " reminders", {"reminders": reminders})', chr(10),
    '            return str(len(reminders)) + " reminders"', chr(10),
    '        return "OK"', chr(10),
    "    except Exception as e:", chr(10),
    '        return "err:" + str(e)[:60]', chr(10),
    chr(10),
]

for line in reversed(func_lines):
    lines.insert(idx, line)

io.open(p, "w", encoding="utf-8").writelines(lines)
c = io.open(p, "r", encoding="utf-8").read()
print("constitution:", "run_constitution_check" in c)
print("ritual:", "run_daily_ritual" in c)
print("check_loop:", "def check_loop" in c)
