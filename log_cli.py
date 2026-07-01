# -*- coding: utf-8 -*-
"""启元智能 · 日志监控数据链 · CLI 入口

用法:
    python brain/log_cli.py tail [N]      — 查看最近N条日志
    python brain/log_cli.py errors        — 查看所有ERROR级别日志
    python brain/log_cli.py stats         — 各模块日志统计
    python brain/log_cli.py chain <id>    — 追踪一次完整调用链路
    python brain/log_cli.py dates         — 列出所有日志日期
"""

import argparse, io, json, os, sys

_brain_dir = os.path.dirname(os.path.abspath(__file__))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)

from logging_chain import (
    tail, errors, stats, trace, list_dates,
    log_info, log_error, log_warn, generate_request_id
)


def cmd_tail(args):
    n = args.n if args.n else 20
    entries = tail(n)
    print(json.dumps({"logs": entries, "count": len(entries)},
                     ensure_ascii=False, indent=2))


def cmd_errors(args):
    since = getattr(args, "since", None)
    errs = errors(since)
    print(json.dumps({"errors": errs, "count": len(errs),
                      "since": since or "today"},
                     ensure_ascii=False, indent=2))


def cmd_stats(args):
    since = getattr(args, "since", None)
    result = stats(since)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_chain(args):
    since = getattr(args, "since", None)
    chain = trace(args.request_id, since)
    print(json.dumps({"request_id": args.request_id, "chain": chain,
                      "count": len(chain), "since": since or "today"},
                     ensure_ascii=False, indent=2))


def cmd_dates(args):
    dates = list_dates()
    print(json.dumps({"dates": dates, "count": len(dates)},
                     ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="启元智能 · 日志监控数据链 CLI",
        prog="brain log"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    p_tail = subparsers.add_parser("tail", help="查看最近N条日志")
    p_tail.add_argument("n", type=int, nargs="?", default=20,
                        help="条数 (默认20)")

    p_err = subparsers.add_parser("errors", help="查看所有ERROR级别日志")
    p_err.add_argument("--since", type=str, default=None,
                       help="日期 (YYYY-MM-DD)")

    p_stats = subparsers.add_parser("stats", help="各模块日志统计")
    p_stats.add_argument("--since", type=str, default=None,
                         help="日期 (YYYY-MM-DD)")

    p_chain = subparsers.add_parser("chain", help="追踪一次完整调用链路")
    p_chain.add_argument("request_id", type=str,
                         help="请求ID (8位UUID前缀)")
    p_chain.add_argument("--since", type=str, default=None,
                         help="日期 (YYYY-MM-DD)")

    subparsers.add_parser("dates", help="列出所有日志日期")

    args = parser.parse_args()

    if args.command == "tail":
        cmd_tail(args)
    elif args.command == "errors":
        cmd_errors(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "chain":
        cmd_chain(args)
    elif args.command == "dates":
        cmd_dates(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
