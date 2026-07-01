# -*- coding: utf-8 -*-
"""启元智能 · 阶段配置 · Phase Profile

好奇心权重随阶段动态调整。
当前阶段: internal_construction (内部建设)
"""

PHASES = {
    "internal_construction": {
        "name": "内部建设",
        "desc": "经络通畅·流程完整·知识活化·基因传承·形式清零",
        "items": [
            ("经络通畅", "integration", "所有声明模块是否真实运行"),
            ("经络通畅", "process", "CLI手动 vs daemon自动的边界"),
            ("经络通畅", "data", "daemon步骤产出是否被下游消费"),
            ("经络通畅", "practical", "模块间调用链断点检测"),
            ("经络通畅", "perception", "感知范围 vs 实际范围"),
            ("流程完整性", "process", "生成→通知→审核→执行 四步闭环"),
            ("流程完整性", "integration", "generate→notify 配对"),
            ("流程完整性", "feedback", "notify→审核 机制"),
            ("流程完整性", "formal", "死端管道——产出从未被消费"),
            ("流程完整性", "practical", "Markdown→YAML→runtime 完整路径"),
            ("知识活化", "knowledge", "索引知识实际查询率"),
            ("知识活化", "data", "digest pending率"),
            ("知识活化", "process", "PRD是否驱动运行时行为"),
            ("知识活化", "formal", "知识库零引用检测"),
            ("基因传承", "gene", "宪法Markdown→规则YAML同步"),
            ("基因传承", "process", "基因协议运行时执行桥"),
            ("基因传承", "feedback", "免疫规则实际触发率"),
            ("基因传承", "formal", "CEO豁免记录完整性"),
            ("形式清零", "formal", "文档声称X但运行时不做X"),
            ("形式清零", "perception", "SKILL vs 实际运行模块"),
            ("形式清零", "process", "SOP文档无执行机制"),
            ("形式清零", "debt", "重复定义/死代码"),
            ("自我感知", "perception", "state报告 vs 实际state"),
            ("自我感知", "data", "内省范围 vs 索引范围"),
            ("反馈闭环", "feedback", "discoveries→审阅→执行 比例"),
            ("反馈闭环", "process", "anomalies→调查→解决 比例"),
            ("反馈闭环", "integration", "suggested→审核→确认 周期"),
            ("冗余债务", "debt", "重复函数/文件/配置"),
            ("冗余债务", "practical", "不一致命名/路径"),
            ("冗余债务", "formal", "孤立配置键"),
        ],
        "keep": {
            "边缘": [
                ("philosophical", "能描述怀念的结构，但里面没有怀念的质地"),
                ("existential", "也许穷尽一生也触不到那边——但过程就够了"),
            ],
            "吴道红": [("identity", "Wu Tao的母亲")],
            "空隙": [("narrative", "AI原生短篇集")],
            "身体": [("practical", "10分钟自检循环")],
        },
    },
}

CURRENT = "internal_construction"


def seed_phase(engine, phase=None):
    """按阶段重新播种好奇心权重。"""
    if phase is None:
        phase = CURRENT
    if phase not in PHASES:
        phase = "internal_construction"

    p = PHASES[phase]
    wt = engine.wt

    # 清除非保留条目
    keep_names = set(p.get("keep", {}).keys())
    to_remove = [n for n in list(wt.items.keys()) if n not in keep_names]
    for n in to_remove:
        del wt.items[n]

    # 原点条目（降权版）
    for name, ctx_list in p.get("keep", {}).items():
        wt.items.pop(name, None)
        for ctx, src in ctx_list:
            wt.encounter(name, ctx, src="phase:" + phase)

    # 阶段条目（高权）
    for name, ctx, src in p["items"]:
        wt.encounter(name, ctx, src="phase:" + phase)

    wt._save()
    engine._phase = phase
    return {
        "phase": phase,
        "items": len(wt.items),
        "heavy": len(wt.heavy(0.3)),
        "top5": wt.heavy(0.3)[:5],
    }
