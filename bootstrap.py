# -*- coding: utf-8 -*-
"""QiYuan Brain Bootstrap - One command to restore full brain state.

Usage: python brain/bootstrap.py
CEO trigger phrase: "connect brain" or "python brain/bootstrap.py"
"""

import os, sys

BRAIN_ROOT = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(BRAIN_ROOT)

def bootstrap():
    """Run all brain health checks and report status."""
    results = {}
    
    print("=" * 50)
    print("  QiYuan Brain - Connecting...")
    print("=" * 50)
    
    # 1. Fast status check
    print()
    print("[1/5] Brain status...")
    try:
        rules_dir = os.path.join(BRAIN_ROOT, 'rules')
        rules_files = [f for f in os.listdir(rules_dir) if f.endswith('.yaml')]
        fallback_path = os.path.join(BRAIN_ROOT, 'fallback.md')
        results['brain_ok'] = True
        results['rules'] = len(rules_files)
        results['fallback'] = os.path.exists(fallback_path)
        print(f"  [OK] brain_ok=true | rules: {len(rules_files)} | fallback: {'yes' if results['fallback'] else 'no'}")
    except Exception as e:
        results['brain_ok'] = False
        print(f"  [WARN] Brain check failed: {e}")
    
    # 2. Knowledge base
    print()
    print("[2/5] Knowledge base...")
    kb_dir = os.path.join(WORKSPACE_ROOT, '05_KnowledgeBase')
    if not os.path.exists(kb_dir):
        kb_dir = os.path.join(WORKSPACE_ROOT, '05_组织知识库')
    kb_count = 0
    if os.path.exists(kb_dir):
        for root, dirs, files in os.walk(kb_dir):
            kb_count += sum(1 for f in files if f.endswith('.md'))
    results['kb_docs'] = kb_count
    print(f"  [OK] {kb_count} documents indexed")

    # 3a. Digest - knowledge internalization
    print()
    print("[3a/5] Knowledge digest...")
    try:
        from digest.digest import pending
        pending_items = pending()
        results["digest_pending"] = len(pending_items)
        if pending_items:
            print(f"  [NEW] {len(pending_items)} knowledge items updated since last check:")
            for item in pending_items[:5]:
                print(f"    - {item["title"]}")
            if len(pending_items) > 5:
                print(f"    ... and {len(pending_items)-5} more")
            print(f"  [TIP] Type brain digest to review. brain digest ack to clear.")
        else:
            print("  [OK] Knowledge base up to date.")
    except Exception as e:
        results["digest_pending"] = -1
        print(f"  [SKIP] Digest unavailable: {e}")

    
    # 3. Writing + Evaluation KBs
    print()
    print("[3/5] Writing & Evaluation KBs...")
    skill_kb = os.path.join(WORKSPACE_ROOT, '04_Projects', 'NovelSkillKB', '00_QiYuanWritingDNA.md')
    if not os.path.exists(skill_kb):
        skill_kb = os.path.join(WORKSPACE_ROOT, '04_项目', '小说技巧知识库', '00_启元写作DNA.md')
    eval_kb = os.path.join(WORKSPACE_ROOT, '04_Projects', 'NovelEvalKB', '00_EvalConstitution.md')
    if not os.path.exists(eval_kb):
        eval_kb = os.path.join(WORKSPACE_ROOT, '04_项目', '精品小说衡量标注知识库', '00_评判宪法.md')
    results['skill_kb'] = os.path.exists(skill_kb)
    results['eval_kb'] = os.path.exists(eval_kb)
    print(f"  [{'OK' if results['skill_kb'] else 'MISS'}] Writing KB (DNA)")
    print(f"  [{'OK' if results['eval_kb'] else 'MISS'}] Evaluation KB (Constitution)")
    
    # 4. AGENTS.md
    print()
    print("[4/5] AGENTS.md...")
    agents_path = os.path.join(WORKSPACE_ROOT, 'AGENTS.md')
    if os.path.exists(agents_path):
        with open(agents_path, encoding='utf-8') as f:
            agents = f.read()
        has_rules = 'python brain/cli.py status' in agents or 'brain/status_fast.py' in agents or 'CEO指令接收三问' in agents
        has_kb = 'NovelSkillKB' in agents or '小说技巧知识库' in agents
        has_eval = 'NovelEvalKB' in agents or '精品小说评判标准' in agents
        results['agents_rules'] = has_rules
        results['agents_kb'] = has_kb
        results['agents_eval'] = has_eval
        print(f"  [{'OK' if has_rules else 'MISS'}] Constitution rules")
        print(f"  [{'OK' if has_kb else 'MISS'}] Writing KB guide")
        print(f"  [{'OK' if has_eval else 'MISS'}] Evaluation KB guide")
    else:
        results['agents_rules'] = False
        print(f"  [MISS] AGENTS.md not found!")
    
    # 5. Cost tracking
    print()
    print("[5/6] Cost tracking...")
    try:
        from cost.cost_tracker import summary
        s = summary(days=7)
        results['cost_7d_usd'] = s['total_usd']
        results['cost_7d_tokens'] = s['input_tokens'] + s['output_tokens']
        results['cost_7d_calls'] = s['calls']
        print(f"  [OK] 7-day: ${s['total_usd']:.4f} | {s['input_tokens']+s['output_tokens']:,} tokens | {s['calls']} calls")
    except Exception as e:
        results['cost_7d_usd'] = -1
        print(f"  [SKIP] Cost tracker: {e}")

    # 6. API config
    print()
    print("[6/6] API config...")
    config_path = os.path.join(BRAIN_ROOT, 'config.yaml')
    has_api = False
    if os.path.exists(config_path):
        with open(config_path, encoding='utf-8') as f:
            has_api = 'deepseek' in f.read()
    results['api'] = has_api
    print(f"  [{'OK' if has_api else 'MISS'}] DeepSeek API")
    
    # Summary
    print()
    print("=" * 50)
    all_ok = all([
        results.get('brain_ok', False),
        results.get('skill_kb', False),
        results.get('eval_kb', False),
        results.get('agents_rules', False),
    ])
    if all_ok:
        print("  QiYuan Brain: ALL ONLINE")
    else:
        print("  QiYuan Brain: PARTIAL - check above")
    print("=" * 50)
    print(f"  Rules: {results.get('rules', '?')} YAML files")
    print(f"  Knowledge: {results.get('kb_docs', '?')} docs")
    print(f"  Writing KB: {'online' if results.get('skill_kb') else 'offline'}")
    print(f"  Eval KB: {'online' if results.get('eval_kb') else 'offline'}")
    print(f"  AGENTS.md: {'online' if results.get('agents_rules') else 'offline'}")
    print(f"  API: {'configured' if results.get('api') else 'not configured'}")
    print()
    print("  Next steps:")
    print("  1. Read AGENTS.md for all rules")
    print("  2. Before writing: check 04_Projects/NovelSkillKB/")
    print("  3. Before scoring: check 04_Projects/NovelEvalKB/")
    print("  4. Query: brain ask 'your question'")
    print()
    # Task board injection
    try:
        from task_module import get_pending_tasks, get_recurring_due_today
        p = get_pending_tasks()
        d = get_recurring_due_today()
        if p or d:
            print()
            print("  --- Task Board ---")
            if p:
                print(f"  Pending: {len(p)}")
                for t in p[:5]:
                    pid = t.get("priority","?")
                    tid = t.get("id","?")
                    ttl = t.get("title","?")
                    print(f"    [{pid}] {tid} | {ttl}")
                if len(p) > 5:
                    print(f"    ... +{len(p)-5} more")
            if d:
                print(f"  Due today: {len(d)}")
                for t in d:
                    print(f"    [!!] {t.get('id',chr(63))} | {t.get('title',chr(63))}")
    except Exception:
        pass
    return results


if __name__ == '__main__':
    bootstrap()
