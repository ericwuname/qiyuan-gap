# -*- coding: utf-8 -*-
"""启元智能 · 规则优化建议引擎

分析 rule_engine 的规则列表和调用统计，输出四种优化建议：
  - low_efficiency:  匹配失败率 > 50%
  - high_overlap:    两规则 triggers 交集 > 60% → 建议合并
  - priority_mismatch: 高频使用但低 priority → 建议提升
  - unused:          call_count = 0 超 90 天 → 建议归档

用法:
    from rule_optimizer import RuleOptimizer
    opt = RuleOptimizer()
    result = opt.analyze(rules, stats)
    result = opt.analyze_file("path/to/stats.json", rules)          # 从JSON文件读取stats
    result = opt.analyze_file("path/to/stats.json")                  # stats文件自带rules
"""

import io, os, json, math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


class RuleOptimizer:
    """规则优化建议引擎。"""

    # ── 阈值配置 ──
    LOW_EFFICIENCY_THRESHOLD = 0.50       # 匹配率 < 50% 触发
    HIGH_OVERLAP_THRESHOLD = 0.60         # trigger 交集比例 > 60% 触发
    UNUSED_DAYS = 90                      # 90 天未使用触发
    PRIORITY_HIGH_USAGE_PCT = 0.25        # 前 25% 为"高频"
    PRIORITY_LOW_THRESHOLD = 50           # priority > 50 视为"低优先级"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    # ── 公共入口 ──

    def analyze(
        self,
        rules: List[Dict],
        stats: Dict,
        *,
        now: Optional[datetime] = None,
    ) -> Dict:
        """主入口：分析规则列表 + 统计，返回优化建议。

        Args:
            rules: 规则字典列表，每个规则至少含 id, name, priority, triggers, level, status。
            stats: 规则统计，支持两种格式：
                   - 汇总格式: {"rules": [{id, call_count, match_count, last_used, ...}, ...]}
                   - 扁平映射: {"CONST-001": {"call_count": ..., "match_count": ...}, ...}
            now: 可选，当前时间（用于 unused 计算）。

        Returns:
            {"ok": True/False, "suggestions": [{rule_id, issue_type, severity, suggestion, impact}, ...]}
        """
        if now is None:
            now = datetime.now()

        # 规范化 stats → per-rule 映射
        stats_map = self._normalize_stats(stats)

        if not rules and not stats_map:
            return {"ok": True, "suggestions": []}

        suggestions: List[Dict] = []

        # 1. 低效率检测
        suggestions.extend(self._detect_low_efficiency(rules, stats_map))

        # 2. trigger 高重叠检测
        suggestions.extend(self._detect_high_overlap(rules))

        # 3. 优先级错配检测
        suggestions.extend(self._detect_priority_mismatch(rules, stats_map))

        # 4. 未使用检测
        suggestions.extend(self._detect_unused(rules, stats_map, now))

        # 按 severity 排序: high → medium → low
        sev_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: sev_order.get(s.get("severity", "low"), 99))

        return {"ok": True, "suggestions": suggestions}

    def analyze_file(
        self,
        stats_path: str,
        rules: Optional[List[Dict]] = None,
        *,
        now: Optional[datetime] = None,
    ) -> Dict:
        """从 JSON stats 文件读取数据并分析。

        Args:
            stats_path: stats JSON 文件路径（格式同 brain rule stats 输出）。
            rules: 可选。未提供时尝试从 stats 的 "rules" 字段中提取基本信息。
        """
        if not os.path.isfile(stats_path):
            return {"ok": False, "suggestions": [], "error": f"文件不存在: {stats_path}"}

        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return {"ok": False, "suggestions": [], "error": f"读取失败: {e}"}

        if rules is None:
            # 从 stats 的 rules 列表构建最小规则列表
            raw_rules = stats.get("rules", [])
            rules = [
                {
                    "id": r.get("id", ""),
                    "name": r.get("name", ""),
                    "priority": r.get("priority", 99),
                    "triggers": r.get("triggers", []),
                    "level": r.get("level", "P2"),
                    "status": r.get("status", "active"),
                }
                for r in raw_rules
            ]

        return self.analyze(rules, stats, now=now)

    # ── stats 规范化 ──

    def _normalize_stats(self, stats: Dict) -> Dict[str, Dict]:
        """将 stats 统一为 {rule_id: {call_count, match_count, last_used, ...}} 格式。"""
        result: Dict[str, Dict] = {}

        # 格式 A: {"rules": [{id, call_count, ...}]}  (brain rule stats 输出)
        if "rules" in stats and isinstance(stats["rules"], list):
            for entry in stats["rules"]:
                rid = entry.get("id", "")
                if rid:
                    result[rid] = {
                        "call_count": entry.get("call_count", 0),
                        "match_count": entry.get("match_count", 0),
                        "last_used": self._parse_last_used(entry.get("last_used", "never")),
                        "level": entry.get("level", ""),
                        "name": entry.get("name", ""),
                    }
            return result

        # 格式 B: {"CONST-001": {"call_count": N, "match_count": N}, ...}  (扁平映射)
        for key, val in stats.items():
            if isinstance(val, dict) and "call_count" in val:
                result[key] = {
                    "call_count": val.get("call_count", 0),
                    "match_count": val.get("match_count", 0),
                    "last_used": self._parse_last_used(val.get("last_used", 0)),
                    "level": val.get("level", ""),
                    "name": val.get("name", ""),
                }

        return result

    @staticmethod
    def _parse_last_used(value) -> Optional[datetime]:
        """解析 last_used 字段，支持 str/datetime/timestamp。"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            if value <= 0:
                return None
            return datetime.fromtimestamp(value)
        if isinstance(value, str):
            if value.lower() == "never":
                return None
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return None

    # ── 检测器 ──

    def _detect_low_efficiency(self, rules: List[Dict], stats_map: Dict[str, Dict]) -> List[Dict]:
        """检测匹配失败率 > 50% 的规则。"""
        suggestions = []
        for rule in rules:
            rid = rule.get("id", "")
            st = stats_map.get(rid, {})
            call_count = st.get("call_count", 0)
            match_count = st.get("match_count", 0)

            if call_count < 5:
                continue  # 样本太小，不触发

            match_rate = match_count / call_count if call_count > 0 else 1.0
            miss_rate = 1.0 - match_rate

            if miss_rate <= self.LOW_EFFICIENCY_THRESHOLD:
                continue

            severity = "high" if miss_rate > 0.70 else "medium"
            suggestions.append({
                "rule_id": rid,
                "rule_name": rule.get("name", ""),
                "issue_type": "low_efficiency",
                "severity": severity,
                "suggestion": (
                    f"匹配率仅 {match_rate:.0%}（{match_count}/{call_count}），"
                    f"建议收紧 triggers 关键词或降低规则 scope"
                ),
                "impact": f"减少无效匹配 {call_count - match_count} 次",
                "data": {
                    "call_count": call_count,
                    "match_count": match_count,
                    "miss_rate": round(miss_rate, 3),
                },
            })
        return suggestions

    def _detect_high_overlap(self, rules: List[Dict]) -> List[Dict]:
        """检测 triggers 交集 > 60% 的规则对，建议合并。"""
        suggestions = []
        n = len(rules)
        seen_pairs = set()

        for i in range(n):
            a = rules[i]
            rid_a = a.get("id", "")
            trig_a = set(t.lower() for t in a.get("triggers", []))
            if not trig_a:
                continue

            for j in range(i + 1, n):
                b = rules[j]
                rid_b = b.get("id", "")
                pair_key = (rid_a, rid_b) if rid_a < rid_b else (rid_b, rid_a)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                trig_b = set(t.lower() for t in b.get("triggers", []))
                if not trig_b:
                    continue

                max_len = max(len(trig_a), len(trig_b), 1)
                overlap = trig_a & trig_b
                overlap_ratio = len(overlap) / max_len

                if overlap_ratio < self.HIGH_OVERLAP_THRESHOLD:
                    continue

                severity = "high" if overlap_ratio > 0.80 else "medium"
                common_triggers = sorted(overlap)[:8]
                suggestions.append({
                    "rule_id": rid_a,
                    "related_rule_id": rid_b,
                    "rule_name": a.get("name", ""),
                    "related_rule_name": b.get("name", ""),
                    "issue_type": "high_overlap",
                    "severity": severity,
                    "suggestion": (
                        f"与 {rid_b}（{b.get('name', '')}）triggers "
                        f"重叠 {overlap_ratio:.0%}，建议评估是否可合并为一条规则"
                    ),
                    "impact": f"合并后可减少 {(len(trig_a) + len(trig_b) - len(overlap))} 个 trigger 维护项",
                    "data": {
                        "overlap_ratio": round(overlap_ratio, 3),
                        "common_triggers": common_triggers,
                    },
                })
        return suggestions

    def _detect_priority_mismatch(self, rules: List[Dict], stats_map: Dict[str, Dict]) -> List[Dict]:
        """检测高频使用但 priority 偏低的规则（priority 值越大 → 优先级越低）。"""
        suggestions = []
        active_rules = []
        for rule in rules:
            rid = rule.get("id", "")
            st = stats_map.get(rid, {})
            cc = st.get("call_count", 0)
            if cc > 0:
                active_rules.append((rule, cc))

        if len(active_rules) < 4:
            return suggestions

        # 按 call_count 从高到低排序
        active_rules.sort(key=lambda x: x[1], reverse=True)

        # 前 25% 为"高频"
        threshold_idx = max(1, int(len(active_rules) * self.PRIORITY_HIGH_USAGE_PCT))
        high_usage = active_rules[:threshold_idx]
        high_usage_ids = {r[0].get("id") for r in high_usage}

        # 计算中位数 priority
        all_priorities = [r[0].get("priority", 99) for r in active_rules]
        median_priority = sorted(all_priorities)[len(all_priorities) // 2]

        for rule, cc in high_usage:
            rid = rule.get("id", "")
            priority = rule.get("priority", 99)
            if priority > max(self.PRIORITY_LOW_THRESHOLD, median_priority):
                suggestions.append({
                    "rule_id": rid,
                    "rule_name": rule.get("name", ""),
                    "issue_type": "priority_mismatch",
                    "severity": "medium",
                    "suggestion": (
                        f"调用频率高（{cc} 次, 前 {threshold_idx}/{len(active_rules)}），"
                        f"但 priority={priority}（偏低），"
                        f"建议提升至 ≤{max(self.PRIORITY_LOW_THRESHOLD, median_priority)}"
                    ),
                    "impact": "高频规则优先响应，减少关键场景遗漏",
                    "data": {
                        "call_count": cc,
                        "current_priority": priority,
                        "suggested_priority": max(self.PRIORITY_LOW_THRESHOLD, median_priority),
                        "rank": f"{high_usage.index((rule, cc)) + 1}/{len(active_rules)}",
                    },
                })
        return suggestions

    def _detect_unused(self, rules: List[Dict], stats_map: Dict[str, Dict], now: datetime) -> List[Dict]:
        """检测 call_count = 0 且超过 90 天未使用的规则。"""
        suggestions = []
        cutoff = now - timedelta(days=self.UNUSED_DAYS)

        for rule in rules:
            rid = rule.get("id", "")
            status = rule.get("status", "active")
            if status in ("archived", "deprecated", "draft"):
                continue

            st = stats_map.get(rid, {})
            call_count = st.get("call_count", 0)
            last_used = st.get("last_used", None)

            is_stale = False
            if call_count == 0 and last_used is None:
                is_stale = True  # 从未使用
            elif call_count == 0 and last_used is not None and last_used < cutoff:
                is_stale = True  # 超 90 天未使用
            elif call_count > 0 and last_used is not None and last_used < cutoff:
                # 有调用但很久以前，提示但不强制
                suggestions.append({
                    "rule_id": rid,
                    "rule_name": rule.get("name", ""),
                    "issue_type": "unused",
                    "severity": "low",
                    "suggestion": (
                        f"最后使用于 {last_used.strftime('%Y-%m-%d')}（超 {self.UNUSED_DAYS} 天），"
                        f"累计 {call_count} 次调用，建议评估是否降级或归档"
                    ),
                    "impact": "减少规则引擎扫描开销",
                    "data": {
                        "call_count": call_count,
                        "last_used": last_used.strftime("%Y-%m-%d") if last_used else "never",
                        "days_since": (now - last_used).days if last_used else None,
                    },
                })
                continue

            if is_stale:
                last_used_str = last_used.strftime("%Y-%m-%d") if last_used else "从未使用"
                suggestions.append({
                    "rule_id": rid,
                    "rule_name": rule.get("name", ""),
                    "issue_type": "unused",
                    "severity": "low",
                    "suggestion": (
                        f"call_count=0，{last_used_str}，超 {self.UNUSED_DAYS} 天未活动，"
                        f"建议归档至 _archived/"
                    ),
                    "impact": "减少扫描项，降低引擎开销",
                    "data": {
                        "call_count": call_count,
                        "last_used": last_used_str,
                        "days_since": None if last_used is None else (now - last_used).days,
                    },
                })
        return suggestions


# ── 独立运行入口 ──
if __name__ == "__main__":
    import sys

    # 示例：从文件读取
    if len(sys.argv) > 1:
        path = sys.argv[1]
        opt = RuleOptimizer()
        result = opt.analyze_file(path)
    else:
        # 裸跑：空输入验证
        opt = RuleOptimizer()
        result = opt.analyze([], {})

    print(json.dumps(result, ensure_ascii=False, indent=2))
