# -*- coding: utf-8 -*-
"""Token cost CLI — standalone cost report/summary/by-model commands.
Usage: python cost_cli.py report|summary|by-model [--days N]
"""
import sys, os, json

# Ensure brain/ is on path
_brain_dir = os.path.dirname(os.path.abspath(__file__))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)

from cost.cost_tracker import full_report, summary as cost_summary, by_model

def cmd_report(days=30):
    result = full_report(days)
    # Also include finance estimates
    try:
        from finance.finance_module import FinanceModule
        fm = FinanceModule()
        fin_est = fm.estimate(days)
        result["estimated"] = {
            "total_ops": fin_est.get("total_ops", 0),
            "total_cost_usd": fin_est.get("total_cost_usd", 0),
            "total_cost_cny": fin_est.get("total_cost_cny", 0),
            "source": "audit_log_estimate",
        }
    except Exception:
        result["estimated"] = {"error": "finance module unavailable"}
    print(json.dumps(result, ensure_ascii=False, indent=2))

def cmd_summary():
    s7 = cost_summary(7)
    s30 = cost_summary(30)
    total_tok_7 = s7["input_tokens"] + s7["output_tokens"]
    total_tok_30 = s30["input_tokens"] + s30["output_tokens"]
    print("Token 7d:  %6d calls  |  $%.4f  |  %10s tokens" % (s7["calls"], s7["total_usd"], format(total_tok_7, ",d")))
    print("Token 30d: %6d calls  |  $%.4f  |  %10s tokens" % (s30["calls"], s30["total_usd"], format(total_tok_30, ",d")))
    print("         %8s CNY (est.)" % ("%.2f" % (s30["total_usd"] * 7.25)))

def cmd_by_model(days=30):
    rows = by_model(days)
    if not rows:
        print("(no actual usage records)")
        return
    print("%-25s %7s %12s %12s %10s" % ("Model", "Calls", "Input", "Output", "Cost USD"))
    print("-" * 70)
    for r in rows:
        print("%-25s %7d %12s %12s $%9.4f" % (
            r["model"], r["calls"],
            format(r["input_tokens"], ",d"),
            format(r["output_tokens"], ",d"),
            r["cost_usd"]))
    total = sum(r["cost_usd"] for r in rows)
    print("-" * 70)
    print("%-25s %7s %12s %12s $%9.4f" % ("TOTAL", "", "", "", total))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cost_cli.py report|summary|by-model [--days N]")
        sys.exit(1)

    cmd = sys.argv[1]
    days = 30
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    if cmd == "report":
        cmd_report(days)
    elif cmd == "summary":
        cmd_summary()
    elif cmd == "by-model":
        cmd_by_model(days)
    else:
        print("Unknown command: %s" % cmd)
        print("Usage: python cost_cli.py report|summary|by-model [--days N]")
        sys.exit(1)
