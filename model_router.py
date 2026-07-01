# -*- coding: utf-8 -*-
"""
模型路由器 · Model Router V1.0
三层自动路由：Flash(简单) → V3.2 Pro(日常) → V4 Pro(关键战役)
分类器用Flash（几乎免费），高置信度自动路由，低置信度提醒用户。
"""
import io, json, urllib.request, sys, os
from datetime import datetime

# === 配置（从config.yaml读取，硬编码兜底） ===
API_KEY = "sk-hqnbxswksdpuxoukplgjgjndmtclqfskycunkfplenclzxcz"
BASE_URL = "https://api.siliconflow.cn/v1"

MODELS = {
    "flash": "deepseek-ai/DeepSeek-V4-Flash",
    "v3.2": "Pro/deepseek-ai/DeepSeek-V3.2",
    "v4": "deepseek-ai/DeepSeek-V4-Pro",
}

# 路由阈值
AUTO_ROUTE_CONFIDENCE = 0.8  # 高于此值自动路由，低于则提醒用户


def _call_api(model, messages, temperature=0.7, max_tokens=2000, timeout=120):
    """通用API调用"""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + API_KEY
        }
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    result = json.loads(resp.read().decode("utf-8"))
    return {
        "content": result["choices"][0]["message"]["content"],
        "model": result.get("model", "?"),
        "usage": result.get("usage", {})
    }


def classify(task):
    """
    用Flash对任务分类（几乎免费）。
    返回: {"tier": "flash"|"v3.2"|"v4", "confidence": 0.0-1.0, "reason": "..."}
    """
    prompt = """你是一个任务分类器。分析用户的问题，判断应该用哪个模型回答。只输出JSON，不要其他文字。

分类标准：
- "flash": 简单查询、事实问题、代码片段、计算、定义、是/否判断、日常信息
- "v3.2": 创作陪练、项目梳理、分析讨论、写作建议、学习思考、方案设计（常规复杂度）
- "v4": 关键决策、复杂架构、多步长链推理、需要"不跑偏"的高风险任务、一团乱麻需要厘清

JSON格式：{"tier": "flash", "confidence": 0.85, "reason": "这是一个简单的..."}

用户问题：""" + task[:500]

    try:
        result = _call_api(MODELS["flash"], [
            {"role": "user", "content": prompt}
        ], temperature=0.1, max_tokens=200)
        content = result["content"].strip()
        # 提取JSON
        if "{" in content:
            start = content.index("{")
            end = content.rindex("}") + 1
            parsed = json.loads(content[start:end])
            return {
                "tier": parsed.get("tier", "v3.2"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reason": parsed.get("reason", ""),
                "classify_cost": result["usage"]
            }
    except Exception as e:
        pass
    # 降级：默认用V3.2
    return {"tier": "v3.2", "confidence": 0.3, "reason": f"分类失败，降级: {e}"}


def route(task, tier=None):
    """
    完整路由流水线：分类 → 路由 → 返回结果。
    如果tier已指定则跳过分类。
    返回: {"tier": ..., "confidence": ..., "result": ..., "classification": ...}
    """
    if tier is None:
        classification = classify(task)
        tier = classification["tier"]
    else:
        classification = {"tier": tier, "confidence": 1.0, "reason": "手动指定"}
    
    MODEL_NAME = {"flash": "V4 Flash", "v3.2": "V3.2 Pro", "v4": "V4 Pro"}
    
    try:
        result = _call_api(MODELS[tier], [
            {"role": "user", "content": task}
        ], max_tokens=3000 if tier == "v4" else 2000)
        return {
            "tier": tier,
            "tier_name": MODEL_NAME.get(tier, tier),
            "confidence": classification["confidence"],
            "reason": classification.get("reason", ""),
            "result": result,
            "classification": classification
        }
    except Exception as e:
        # 降级：如果指定模型失败，降级到下一个
        fallback_order = {"v4": "v3.2", "v3.2": "flash", "flash": None}
        fallback = fallback_order.get(tier)
        if fallback:
            print(f"[ROUTER] {tier} 调用失败，降级到 {fallback}: {e}")
            return route(task, tier=fallback)
        raise


def ask(task, auto_threshold=AUTO_ROUTE_CONFIDENCE):
    """
    智能问答：自动分类+路由。低置信度时返回路由建议让用户确认。
    返回: {"auto_routed": bool, ...}
    """
    classification = classify(task)
    tier = classification["tier"]
    confidence = classification["confidence"]
    
    if confidence >= auto_threshold:
        # 自动路由
        result = route(task, tier=tier)
        result["auto_routed"] = True
        return result
    else:
        # 低置信度，返回建议让用户确认
        return {
            "auto_routed": False,
            "needs_confirm": True,
            "suggested_tier": tier,
            "suggested_name": {"flash": "V4 Flash", "v3.2": "V3.2 Pro", "v4": "V4 Pro"}.get(tier, tier),
            "confidence": confidence,
            "reason": classification.get("reason", ""),
            "classification": classification
        }


# === 命令行入口 ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python model_router.py ask <问题>")
        print("      python model_router.py classify <问题>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read().strip()
    
    if cmd == "classify":
        result = classify(question)
        print(f"分级: {result['tier']}")
        print(f"置信度: {result['confidence']}")
        print(f"原因: {result['reason']}")
    elif cmd == "ask":
        result = ask(question)
        if result.get("auto_routed"):
            print(f"[{result['tier_name']} · 自动路由 · 置信度{result['confidence']:.0%}]")
            print()
            print(result["result"]["content"])
        else:
            print(f"[建议使用 {result['suggested_name']} · 置信度{result['confidence']:.0%}]")
            print(f"原因: {result['reason']}")
            print()
            print("请确认模型选择后重新调用。")
    else:
        print(f"未知命令: {cmd}")
