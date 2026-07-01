# -*- coding: utf-8 -*-
"""启元智能 · 启元智脑 · 自进化引擎 (简化版)

功能:
  analyze(): 扫描审计日志 → 发现高频操作 → 识别缺失规则
  suggest(): 生成建议规则草案 → 输出到 brain/rules/_suggested/
  
不自动应用，仅建议。
"""

import io, os, sys, json
from datetime import datetime, timedelta
from collections import Counter

# Ensure brain/ is on path
_brain_dir = os.path.dirname(os.path.abspath(__file__))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)


class SelfEvolve:
    """自进化引擎：从审计日志中发现模式，生成规则建议。"""

    def __init__(self, brain_dir: str = None):
        self.brain_dir = brain_dir or _brain_dir
        self.audit_db = os.path.join(self.brain_dir, "audit", "audit.db")
        self.rules_dir = os.path.join(self.brain_dir, "rules")
        self.suggested_dir = os.path.join(self.rules_dir, "_suggested")

    def analyze(self) -> dict:
        """扫描审计日志，发现高频操作模式，识别潜在缺失规则。

        Returns:
            {"patterns": [...], "missing_rules": [...], "summary": {...}}
        """
        logs = self._load_audit_logs()
        if not logs:
            return {
                "patterns": [],
                "missing_rules": [],
                "summary": {"total_logs": 0, "message": "无审计日志，无法分析"},
            }

        # 1. 统计文件操作频次
        file_counter = Counter()
        operator_counter = Counter()
        action_counter = Counter()
        hourly_dist = Counter()

        for log in logs:
            target = log.get("target_path", "")
            file_counter[target] += 1
            operator_counter[log.get("operator", "unknown")] += 1
            action_counter[log.get("action", "unknown")] += 1
            try:
                ts = log.get("timestamp", "")
                if ts:
                    hour = ts[11:13] if len(ts) >= 13 else "??"
                    hourly_dist[hour] += 1
            except Exception:
                pass

        # 2. 识别模式
        patterns = []

        # 高频写入文件 (>3次)
        hot_files = [(f, c) for f, c in file_counter.most_common(10) if c >= 3]
        if hot_files:
            patterns.append({
                "type": "hot_files",
                "description": "高频写入文件 (≥3次)",
                "items": [{"file": f, "count": c} for f, c in hot_files],
            })

        # 高频操作时段
        peak_hours = [(h, c) for h, c in hourly_dist.most_common(3) if c >= 3]
        if peak_hours:
            patterns.append({
                "type": "peak_hours",
                "description": "高频操作时段",
                "items": [{"hour": h, "count": c} for h, c in peak_hours],
            })

        # 操作类型分布
        patterns.append({
            "type": "action_distribution",
            "description": "操作类型分布",
            "items": [{"action": a, "count": c} for a, c in action_counter.most_common()],
        })

        # 3. 识别缺失规则
        missing = self._identify_missing_rules(
            logs, file_counter, action_counter, operator_counter
        )

        return {
            "patterns": patterns,
            "missing_rules": missing,
            "summary": {
                "total_logs": len(logs),
                "unique_files": len(file_counter),
                "unique_operators": len(operator_counter),
                "date_range": self._get_date_range(logs),
            },
        }

    def _identify_missing_rules(self, logs, file_counter, action_counter, operator_counter) -> list:
        """基于日志模式，识别可能缺失的规则。"""
        missing = []
        existing_rules = self._load_existing_rules()

        # 检查1: 是否有高频修改的配置文件但无对应SOP
        config_files = [f for f in file_counter if any(
            ext in f.lower() for ext in [".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"]
        )]
        for f in config_files[:5]:
            if file_counter[f] >= 2:
                rule_id = f"EVO-CFG-{hash(f) % 10000:04d}"
                if not any(rule_id in r for r in existing_rules):
                    missing.append({
                        "id": rule_id,
                        "type": "config_hygiene",
                        "title": f"配置文件 {os.path.basename(f)} 变更管控",
                        "description": f"检测到 {os.path.basename(f)} 被修改 {file_counter[f]} 次。建议建立变更审批流程。",
                        "trigger": f"修改 {os.path.basename(f)}",
                        "severity": "P1",
                    })

        # 检查2: 写操作占比高但无审计规则覆盖
        writes = action_counter.get("write", 0)
        total = sum(action_counter.values())
        if total > 0 and writes / total > 0.7:
            if not any("audit" in r.lower() or "审计" in r for r in existing_rules):
                missing.append({
                    "id": "EVO-AUD-0001",
                    "type": "audit_coverage",
                    "title": "写操作占比过高，建议增强审计覆盖",
                    "description": f"写操作占总操作 {writes/total*100:.0f}%，建议检查审计日志完整性。",
                    "trigger": "写操作占比 > 70%",
                    "severity": "P2",
                })

        # 检查3: 有批量操作但无批量操作规范
        batch_candidates = self._detect_batch_operations(logs)
        if batch_candidates and not any("batch" in r.lower() or "批量" in r for r in existing_rules):
            missing.append({
                "id": "EVO-BAT-0001",
                "type": "batch_operations",
                "title": "检测到批量操作模式，建议建立批量操作规范",
                "description": f"在短时间内检测到 {batch_candidates} 个可能的批量操作。建议建立批量操作审批与回滚机制。",
                "trigger": "短时间内多次写入操作",
                "severity": "P1",
            })

        return missing

    def _detect_batch_operations(self, logs) -> int:
        """检测批量操作：1分钟内超过3次写入。"""
        writes = [l for l in logs if l.get("action") == "write"]
        if len(writes) < 3:
            return 0

        batch_count = 0
        writes_sorted = sorted(writes, key=lambda x: x.get("timestamp", ""))
        for i in range(len(writes_sorted) - 2):
            try:
                t1 = datetime.strptime(writes_sorted[i]["timestamp"], "%Y-%m-%d %H:%M:%S")
                t3 = datetime.strptime(writes_sorted[i + 2]["timestamp"], "%Y-%m-%d %H:%M:%S")
                if (t3 - t1).total_seconds() <= 60:
                    batch_count += 1
            except (ValueError, KeyError):
                pass
        return batch_count

    def suggest(self) -> dict:
        """生成建议规则草案，输出到 brain/rules/_suggested/。

        Returns:
            {"suggested": [...], "output_dir": "..."}
        """
        analysis = self.analyze()
        missing = analysis.get("missing_rules", [])

        if not missing:
            return {
                "suggested": [],
                "output_dir": self.suggested_dir,
                "message": "未发现需要建议的规则。",
            }

        os.makedirs(self.suggested_dir, exist_ok=True)
        suggested_files = []

        for rule in missing:
            filename = f"{rule['id']}.yaml"
            filepath = os.path.join(self.suggested_dir, filename)

            yaml_content = self._render_rule_yaml(rule)
            with io.open(filepath, "w", encoding="utf-8") as f:
                f.write(yaml_content)

            suggested_files.append({
                "id": rule["id"],
                "file": filepath,
                "title": rule["title"],
                "severity": rule["severity"],
            })

        return {
            "suggested": suggested_files,
            "output_dir": self.suggested_dir,
            "count": len(suggested_files),
        }

    def mine_reports(self, report_dir: str = None) -> dict:
        """P0-1: KnowledgeMiner - mine reports for rule suggestions."""
        import re, yaml
        from datetime import datetime as dt
        if report_dir is None:
            root = os.path.dirname(self.brain_dir)
            report_dir = os.path.join(root, "04_项目", "外部大脑", "报告")
        if not os.path.isdir(report_dir):
            return {"ok": False, "error": "Report dir not found: " + report_dir}
        reports = []
        for fname in sorted(os.listdir(report_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(report_dir, fname)
                try:
                    with io.open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                    reports.append({"file": fname, "path": fpath, "text": text})
                except Exception:
                    pass
        if not reports:
            return {"ok": False, "error": "No report files found"}
        lessons = []
        lpatterns = [
            (r"(?:教训|经验|学习|反思)[：:]\s*(.+?)(?:\n|$)", "lesson"),
            (r"(?:问题|风险|缺陷|不足)[：:]\s*(.+?)(?:\n|$)", "problem"),
            (r"(?:建议|改进|优化)[：:]\s*(.+?)(?:\n|$)", "suggestion"),
            (r"(?:TODO|待办|待补|遗留)[：:]\s*(.+?)(?:\n|$)", "todo"),
            (r"(?:规则缺失|无规则覆盖|盲区)[：:]\s*(.+?)(?:\n|$)", "rule_gap"),
        ]
        for report in reports:
            for pat, cat in lpatterns:
                for m in re.finditer(pat, report["text"], re.IGNORECASE):
                    line = m.group(1).strip()
                    if 10 <= len(line) <= 500:
                        lessons.append({"category": cat, "content": line, "source_file": report["file"]})
        seen = set()
        unique = []
        for l in lessons:
            k = l["content"][:80]
            if k not in seen:
                seen.add(k)
                unique.append(l)
        existing = self._load_existing_rules()
        existing_ids = set()
        for rt in existing:
            try:
                parsed = yaml.safe_load(rt)
                if isinstance(parsed, list):
                    for r in parsed:
                        if isinstance(r, dict) and "id" in r:
                            existing_ids.add(r["id"])
                elif isinstance(parsed, dict) and "id" in parsed:
                    existing_ids.add(parsed["id"])
            except Exception:
                pass
        suggestions = []
        nid = 1
        while "SUG-{0:03d}".format(nid) in existing_ids:
            nid += 1
        pmap = {"problem": 20, "rule_gap": 18, "todo": 14, "lesson": 12, "suggestion": 10}
        for lesson in unique[:30]:
            sid = "SUG-{0:03d}".format(nid); nid += 1
            priority = pmap.get(lesson["category"], 8)
            rule = {"id": sid, "name": lesson["content"][:60], "priority": priority,
                "triggers": [lesson["category"]], "action": lesson["content"],
                "level": "P2" if priority < 15 else "P1", "owner": "system",
                "severity": "high" if priority >= 18 else ("medium" if priority >= 14 else "low"),
                "status": "draft", "source": "mined from " + lesson["source_file"],
                "category": lesson["category"], "created": dt.now().strftime("%Y-%m-%d")}
            suggestions.append(rule)
        os.makedirs(self.suggested_dir, exist_ok=True)
        drafted = []
        for sug in suggestions[:20]:
            yt_sb = []
            yt_sb.append("# Mined rule suggestion: " + sug["id"] + "\n")
            yt_sb.append("id: " + sug["id"] + "\n")
            yt_sb.append("name: |\n  " + sug["name"] + "\n")
            yt_sb.append("priority: " + str(sug["priority"]) + "\n")
            yt_sb.append("triggers:\n")
            for t in sug["triggers"]:
                yt_sb.append("  - " + t + "\n")
            yt_sb.append("action: |\n  " + sug["action"] + "\n")
            yt_sb.append("level: " + sug["level"] + "\n")
            yt_sb.append("owner: " + sug["owner"] + "\n")
            yt_sb.append("status: " + sug["status"] + "\n")
            yt_sb.append("source: " + sug["source"] + "\n")
            yt_sb.append("severity: " + sug["severity"] + "\n")
            yt_sb.append("category: " + sug["category"] + "\n")
            yt_sb.append("created: " + sug["created"] + "\n")
            yt = "".join(yt_sb)
            sn = sug["id"] + "_" + re.sub(r"[^\w]", "_", sug["name"][:40]) + ".yaml"
            with io.open(os.path.join(self.suggested_dir, sn), "w", encoding="utf-8") as fw:
                fw.write(yt)
            drafted.append({"file": sn, "rule_id": sug["id"]})
        return {"ok": True, "reports_scanned": len(reports), "lessons_extracted": len(unique),
            "suggestions_generated": len(suggestions), "drafted": len(drafted),
            "draft_dir": self.suggested_dir, "files": drafted, "skipped_dupes": skipped_dupes, "sample_lessons": unique[:5]}

    def mine_lessons(self) -> dict:
        """P0-3: Mine bug_tracker + reports into lessons pattern DB."""
        import json
        from datetime import datetime as dt2
        root = os.path.dirname(self.brain_dir)
        db_path = os.path.join(self.brain_dir, "memory", "lessons_patterns.json")
        patterns = []
        if os.path.isfile(db_path):
            try:
                with io.open(db_path, "r", encoding="utf-8") as f:
                    patterns = json.load(f)
            except Exception:
                patterns = []
        bug_patterns = []
        bt = os.path.join(root, "04_项目", "外部大脑", "报告", "bug_tracker.md")
        if os.path.isfile(bt):
            try:
                with io.open(bt, "r", encoding="utf-8") as f:
                    bt_text = f.read()
                import re as re2
                for m in re2.finditer(r"BUG-?\d*[:：]\s*(.+?)(?:\n|$)", bt_text, re2.IGNORECASE):
                    bug_patterns.append({"source": "bug_tracker", "pattern": m.group(1).strip()[:200]})
            except Exception:
                pass
        rep_res = self.mine_reports()
        for rl in rep_res.get("sample_lessons", []):
            if rl.get("category") in ("problem", "lesson"):
                bug_patterns.append({"source": rl.get("source_file", "report"), "pattern": rl["content"][:200]})
        seen_set = set(p["pattern"][:60] for p in patterns)
        new_count = 0
        for bp in bug_patterns:
            key = bp["pattern"][:60]
            if key not in seen_set:
                seen_set.add(key)
                patterns.append({"pattern": bp["pattern"], "source": bp["source"],
                    "added": dt2.now().strftime("%Y-%m-%d"), "status": "active",
                    "category": self._classify_lesson(bp["pattern"])})
                new_count += 1
        with io.open(db_path, "w", encoding="utf-8") as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)
        return {"ok": True, "total_patterns": len(patterns), "new_patterns": new_count, "db_path": db_path}

    def _classify_lesson(self, text: str) -> str:
        """Classify a lesson into failure pattern category."""
        t = text.lower()
        if any(kw in t for kw in ["环境耦合", "硬编码", "路径", "迁移", "agent"]):
            return "environment_coupling"
        if any(kw in t for kw in ["并发", "冲突", "文件锁", "session"]):
            return "concurrency"
        if any(kw in t for kw in ["规则", "编码", "sop", "重复", "id"]):
            return "rule_management"
        if any(kw in t for kw in ["备份", "恢复", "回滚"]):
            return "backup_restore"
        if any(kw in t for kw in ["测试", "验证", "回归"]):
            return "testing"
        if any(kw in t for kw in ["性能", "超时", "慢"]):
            return "performance"
        return "general"

    def distill_cross_session(self, since_days: int = 30) -> dict:
        """Cross-session knowledge distillation.
        Scans audit logs across multiple sessions, identifies high-frequency
        operation patterns not covered by existing rules, and generates
        a distillation report with blind-spot suggestions.

        Returns:
            {"ok": bool, "sessions_analyzed": int, "total_operations": int,
             "blind_spots": [{"pattern": str, "frequency": int, "suggestion": str}],
             "covered_by_rules": int}
        """
        logs = self._load_audit_logs()
        if not logs:
            return {"ok": True, "sessions_analyzed": 0, "total_operations": 0,
                    "blind_spots": [], "covered_by_rules": 0,
                    "message": "No audit logs found"}

        # Aggregate by action type
        from collections import Counter
        action_counts = Counter()
        for entry in logs:
            action = entry.get("action", "unknown")
            action_counts[action] += 1

        # Identify unique sessions
        sessions = set()
        for entry in logs:
            sid = entry.get("session_id", entry.get("operator", "unknown"))
            sessions.add(sid)

        # Compare with existing rules
        existing_rules = self._load_existing_rules()
        blind_spots = []
        covered_by_rules = 0

        for action, freq in action_counts.most_common(30):
            if freq < 2:
                continue
            action_lower = action.lower()
            is_covered = False
            for rule_text in existing_rules:
                # existing_rules contains raw YAML strings, use substring match
                rule_lower = rule_text.lower() if isinstance(rule_text, str) else ""
                # Check if action appears in triggers or action fields
                if action_lower in rule_lower:
                    is_covered = True
                    covered_by_rules += freq
                    break
            if not is_covered:
                blind_spots.append({
                    "pattern": action,
                    "frequency": freq,
                    "suggestion": (
                        "Cross-session high-frequency operation '" + action +
                        "' (" + str(freq) + " times) has no rule coverage. " +
                        "Consider creating a rule with trigger '" + action + "'."
                    ),
                })

        return {
            "ok": True,
            "sessions_analyzed": len(sessions),
            "total_operations": len(logs),
            "blind_spots_count": len(blind_spots),
            "covered_by_rules": covered_by_rules,
            "blind_spots": blind_spots,
        }

def _write_weekly_report(report_path, report, now):
    '''Write the weekly hotspot report as Markdown.'''
    lines = [
        '# Weekly KB Hotspot Report',
        '',
        '- **Period**: ' + report['period'],
        '- **Generated**: ' + now.strftime('%Y-%m-%d %H:%M:%S'),
        '- **Total KB queries**: ' + str(report['total_queries']),
        '',
    ]

    # Top10 queries
    lines.append('## Top 10 Most Frequent Queries')
    lines.append('')
    top10 = report.get('top10_queries', [])
    if top10:
        lines.append('| # | Query | Hits | Match Count | Matched Documents |')
        lines.append('|:--|:------|:-----|:-----------|:------------------|')
        for i, q in enumerate(top10, 1):
            docs_str = ', '.join(q['matched_docs'][:3]) if q['matched_docs'] else 'none'
            lines.append('| ' + str(i) + ' | ' + q['query'] + ' | ' + str(q['count']) +
                ' | ' + str(q['hit_count']) + ' | ' + docs_str + ' |')
    else:
        lines.append('_No KB search queries recorded this week._')
    lines.append('')

    # Top5 zero-hit
    lines.append('## Top 5 Zero-Hit Queries (Missing Docs)')
    lines.append('')
    zh = report.get('top5_zero_hit', [])
    if zh:
        lines.append('| # | Query | Frequency | Signal |')
        lines.append('|:--|:------|:----------|:-------|')
        for i, q in enumerate(zh, 1):
            lines.append('| ' + str(i) + ' | ' + q['query'] + ' | ' + str(q['count']) +
                ' | ' + q['signal'] + ' |')
    else:
        lines.append('_No zero-hit queries recorded._')
    lines.append('')

    # New docs
    lines.append('## New Documents This Week')
    lines.append('')
    nd = report.get('new_docs', [])
    if nd:
        lines.append('| Document | Query Count | First Seen |')
        lines.append('|:---------|:------------|:-----------|')
        for d in nd:
            ts = d.get('first_seen', '')[:10]
            lines.append('| ' + d['document'] + ' | ' + str(d['query_count']) + ' | ' + ts + ' |')
    else:
        lines.append('_No new documents added this week._')
    lines.append('')

    # Stale suggestions
    lines.append('## Stale Document Suggestions')
    lines.append('')
    ss = report.get('stale_suggestions', [])
    if ss:
        for s in ss:
            lines.append('- **' + s['document'] + '**: ' + s['suggestion'])
    else:
        lines.append('_No stale documents detected._')
    lines.append('')

    lines.append('---')
    lines.append('_Generated by self_evolve.weekly_hotspot_report()_')

    with io.open(report_path, 'w', encoding='utf-8') as f:
        f.write(chr(10).join(lines) + chr(10))
