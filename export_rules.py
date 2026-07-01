# -*- coding: utf-8 -*-
"""Export active rules to fallback.md"""
import io, os, json
from datetime import datetime

def cmd_export_rules(_brain_dir, load_config):
    try:
        from rule_engine import RuleEngine
        config_path = os.path.join(_brain_dir, "config.yaml")
        config = load_config(config_path)
        rules_dir = config.get("brain", {}).get("rules_dir",
            os.path.join(_brain_dir, "rules"))
        engine = RuleEngine(rules_dir, config, include_draft=False)
        engine._load_all_rules(include_draft=False); rules = engine.rules
        
        out = []
        out.append("# 启元智脑 · 规则快照 (fallback)")
        out.append("")
        out.append("> 大脑不可用时自动读取。由 brain export-rules 生成。")
        out.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        out.append(f"> 规则数量: {len(rules)}")
        out.append("")
        out.append("---")
        out.append("")
        out.append("## P0/P1/P2 权限矩阵")
        out.append("")
        out.append("| 级别 | 决策者 | 定义 |")
        out.append("|:--|:--|:--|")
        out.append("| **P0** | CEO确认 | 删文件/改宪法/对外发布/Token超过50000/裁撤Skill |")
        out.append("| **P1** | CSO确认 | 新建文件/改SKILL.md/跨项目数据提取 |")
        out.append("| **P2** | 自主执行 | 打分/评估/报告/状态更新/日常操作（不得问CEO）|")
        out.append("")
        out.append("---")
        out.append("")
        out.append("## S+ 数据保护铁律")
        out.append("")
        out.append("1. 禁止删除/移动/覆盖启元智能之外的用户文件")
        out.append("2. 任何删除须事先向CEO报告并获批准")
        out.append("3. 必须使用完整绝对路径，禁止相对路径和通配符组合")
        out.append("4. 违反 = S+级事故，责任人停用审查")
        out.append("")
        out.append("---")
        out.append("")
        out.append("## 编码铁律")
        out.append("")
        out.append("- 中文文件: UTF-8 无BOM")
        out.append("- 禁止 PowerShell Set-Content 写中文（默认GBK）")
        out.append("- .ps1 脚本: UTF-8 BOM")
        out.append("- 写中文用 Python io.open 或 [IO.File]::WriteAllText")
        out.append("")
        out.append("---")
        out.append("")
        out.append("## 活跃规则")
        out.append("")
        sorted_rules = sorted(rules, key=lambda r: r.get("priority", 99))
        for rule in sorted_rules:
            rid = rule.get("id", "?")
            name = rule.get("name", "?")
            pri = rule.get("priority", "?")
            desc = rule.get("description", "")
            status = rule.get("status", "active")
            if status in ("draft", "archived"):
                continue
            out.append(f"### {rid} - {name} (P{pri})")
            if desc:
                out.append(desc)
            out.append("")
        
        out.append("---")
        out.append("")
        out.append("## 引导")
        out.append("")
        out.append("大脑恢复后请运行: python brain/cli.py status")
        out.append("高级查询: python brain/cli.py ask [你的问题]")
        out.append("")
        out.append("### 新增命令 V1.1")
        out.append("- python brain/cli.py digest scan    扫描知识库变更")
        out.append("- python brain/cli.py digest report  查看待处理内化通知")
        out.append("- python brain/cli.py digest ack     确认全部通知")
        out.append("- python brain/cli.py cost report    Token成本分析")
        out.append("- python brain/status_fast.py        0.3秒纯文件检查")
        out.append("- brain chat                         进入交互模式")
        out.append('- brain ask "你的中文问题"           自然语言查询')
        
        fallback_path = os.path.join(_brain_dir, "fallback.md")
        with io.open(fallback_path, "w", encoding="utf-8") as f:
            f.write(chr(10).join(out))
        
        result = {"ok": True, "exported": len(sorted_rules), "path": fallback_path}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        import traceback as _tb; result = {"ok": False, "code": 4, "message": str(e), "detail": _tb.format_exc()[:300]}; print(json.dumps(result, ensure_ascii=False, indent=2))
