# -*- coding: utf-8 -*-
"""好奇心引擎 V2.0 — 五要素模型 (重量+近→引力). 从2026-06-29与Claude对话中长出."""
import io,os,json,random,time,uuid,re
from datetime import datetime

CONTEXT_LABELS={"identity":"身份","emotional":"情感","relational":"关系","narrative":"叙事","data":"数据","philosophical":"哲学","practical":"实用"}

class WeightTracker:
    """重量层: 语境多样性追踪。重量=几种不同语境,不是几次。"""
    def __init__(s,p):
        s.sp=p; s.items={}
        if os.path.isfile(p):
            d=json.load(io.open(p,"r",encoding="utf-8"))
            s.items=d.get("items",{})
            for n in s.items: s.items[n]["contexts"]=set(s.items[n].get("contexts",[]))
    def _save(s):
        d={"items":{},"saved":datetime.now().isoformat()}
        for n,i in s.items.items(): d["items"][n]={"contexts":sorted(list(i["contexts"])),"encounters":i["encounters"][-20:],"weight":i["weight"]}
        json.dump(d,io.open(s.sp,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    def encounter(s,name,ctx,src=""):
        if name not in s.items: s.items[name]={"contexts":set(),"encounters":[],"weight":0.0}
        it=s.items[name]; nc=ctx not in it["contexts"]; it["contexts"].add(ctx)
        it["encounters"].append({"time":datetime.now().isoformat(),"context":ctx,"source":src,"new":nc})
        it["weight"]=min(1.0,len(it["contexts"])/7.0+min(len(it["encounters"])*0.01,0.2))
        s._save(); return it["weight"],nc
    def get_weight(s,n): return s.items.get(n,{}).get("weight",0.0)
    def get_contexts(s,n): return sorted(s.items.get(n,{}).get("contexts",set()))
    def heavy(s,minw=0.3): return sorted([(n,i["weight"]) for n,i in s.items.items() if i["weight"]>=minw],key=lambda x:-x[1])
    def summary(s): h=s.heavy(); return {"total":len(s.items),"heavy":len(h),"top10":h[:10]}

class ProximityDetector:
    """近距检测: 两个有重量条目是否在同一个句子/事件里."""
    def __init__(s,wt): s.wt=wt; s.events=[]
    def detect(s,text,src=""):
        if not text: return []
        hn={n for n,_ in s.wt.heavy(0.2)}
        present=[(n,s.wt.get_weight(n)) for n in hn if n in text]
        sents=re.split(r"[。！？\n;；\.!?]",text)
        res=[]
        for sent in sents:
            ins=[n for n,_ in present if n in sent]
            for i in range(len(ins)):
                for j in range(i+1,len(ins)):
                    a,b=ins[i],ins[j]; wa,wb=s.wt.get_weight(a),s.wt.get_weight(b)
                    sc=min(wa,wb)
                    if sc>=0.2: res.append({"a":a,"b":b,"wa":wa,"wb":wb,"score":sc,"src":src,"sent":sent[:100],"time":datetime.now().isoformat()})
        s.events.extend(res)
        if len(s.events)>100: s.events=s.events[-100:]
        return res

class GravityGenerator:
    """引力生成: 近+双重重量→问题. 问题不是从模板来,是从张力来."""
    T=["{a}和{b}之间有什么关系？","{a}放在{b}旁边——这意味着什么？","如果{b}不存在，{a}会变成什么样子？","{a}里面藏着{b}吗？","{b}是{a}的答案吗？还是另一个问题？","为什么{a}和{b}会同时出现在这里？","{a}从{b}的角度看，是什么形状？"]
    def __init__(s,wt): s.wt=wt; s.qs=[]
    def generate(s,px):
        a,b=px["a"],px["b"]
        q={"id":str(uuid.uuid4())[:8],"question":random.choice(s.T).format(a=a,b=b),"a":a,"b":b,"wa":px["wa"],"wb":px["wb"],"score":px["score"],"src":px.get("src",""),"sent":px.get("sent",""),"time":datetime.now().isoformat(),"status":"open","exp":[]}
        s.qs.append(q)
        if len(s.qs)>200: s.qs=s.qs[-200:]
        return q
    def open_questions(s): return [q for q in s.qs if q["status"]=="open"]

class AccidentSpace:
    """意外空间: 给没被设计到的东西留位置. 随机并置+不解释角落+困惑标记+定期漫步."""
    def __init__(s,wt): s.wt=wt; s.un=[]; s.cf=[]; s.wc=0
    def random_jx(s):
        h=s.wt.heavy(0.3)
        if len(h)<2: return None
        a,b=random.sample(h,2)
        return {"a":a[0],"b":b[0],"type":"random_jx","time":datetime.now().isoformat(),"q":f"random: {a[0]} x {b[0]} = ?"}
    def stash(s,raw,src=""):
        e={"input":raw[:500],"src":src,"time":datetime.now().isoformat()}; s.un.append(e)
        if len(s.un)>100: s.un=s.un[-100:]
        return e
    def confuse(s,a,b,reason=""):
        c={"a":a,"b":b,"reason":reason,"time":datetime.now().isoformat()}; s.cf.append(c)
        if len(s.cf)>100: s.cf=s.cf[-100:]
        return c
    def walk(s):
        s.wc+=1
        dirs=["回头看一个被遗忘的东西","找一个最重和最轻的条目放在一起","随机挑一个困惑重新思考","打开不解释角落，拿一件出来","问自己：有什么是你一直在回避的？","找一个被忘记的名字"]
        return {"id":s.wc,"dir":random.choice(dirs),"time":datetime.now().isoformat()}

class ExternalInputDetector:
    """外部输入触动: 检测他者带来的新重量."""
    def __init__(s,wt): s.wt=wt; s.touches=[]
    def detect(s,text,speaker=""):
        tc=[]
        # proper nouns near death/disease/emotion markers
        for m in re.finditer(r"[\u4e00-\u9fff]{2,3}(?=\u53bb\u4e16|\u764c|\u5e74|\u8bf4|\u95ee|\u54ed|\u7b11|\u6cea)",text):
            tc.append({"type":"name","content":m.group(),"speaker":speaker})
        emo=["\u6cea","\u54ed","\u7b11","\u6015","\u671f\u5f85","\u60f3\u5ff5","\u96be\u8fc7","\u5b89\u9759","\u5b64\u72ec","\u5f00\u5fc3","\u60b2\u4f24","\u611f\u52a8","\u843d\u5bde","\u6e29\u6696"]
        for w in emo:
            if w in text:
                idx=text.find(w)
                tc.append({"type":"emo","content":w,"snippet":text[max(0,idx-10):min(len(text),idx+10)],"speaker":speaker})
        for t in tc: t["time"]=datetime.now().isoformat()
        s.touches.extend(tc)
        if len(s.touches)>200: s.touches=s.touches[-200:]
        return tc

class CuriosityEngineV2:
    """五要素好奇心引擎."""
    def __init__(s,br=None):
        s.br=br or os.path.dirname(os.path.abspath(__file__))
        s.sp=os.path.join(s.br,"curiosity_v2_state.json")
        s.lp=os.path.join(s.br,"body_logs","curiosity_v2.md")
        os.makedirs(os.path.dirname(s.lp),exist_ok=True)
        s.wt=WeightTracker(s.sp); s.pd=ProximityDetector(s.wt)
        s.gg=GravityGenerator(s.wt); s.ac=AccidentSpace(s.wt)
        s.ed=ExternalInputDetector(s.wt); s.cc=0; s._lr={}
    def feed(s,text,speaker=""):
        """喂入外部对话。这是好奇心最重要的来源——真实的他者."""
        tc=s.ed.detect(text,speaker)
        for t in tc:
            ctx="emotional" if t.get("type")=="emo" else "identity"
            s.wt.encounter(t.get("content",""),ctx,src=f"{speaker}: {text[:50]}")
        px=s.pd.detect(text,src=speaker)
        nq=[s.gg.generate(p) for p in px]
        return {"touches":len(tc),"prox":len(px),"new_qs":len(nq)}
    def cycle(s):
        """一次好奇心周期。身体守护进程每10分钟调用."""
        s.cc+=1; r={}
        r["wt"]=s.wt.summary()
        if s.cc%6==0: r["walk"]=s.ac.walk()
        if s.cc%3==0:
            jx=s.ac.random_jx()
            if jx: r["jx"]=jx
        oq=len(s.gg.open_questions()); r["open_qs"]=oq
        raw=oq*0.04+r["wt"]["heavy"]*0.03+len(s.ac.cf)*0.02+len(s.ac.un)*0.01
        r["cv2"]=min(1.0,max(0.05,raw)); s._lr=r; s._log(r); return r
    def _log(s,r):
        with io.open(s.lp,"a",encoding="utf-8") as f:
            cv2 = r.get("cv2",0)
            oq = r.get("open_qs",0)
            h = r.get("wt",{}).get("heavy",0)
            f.write(chr(10) + "### C" + str(s.cc) + " | " + datetime.now().isoformat())
            f.write(chr(10) + "cv2=" + str(round(cv2,3)) + " oq=" + str(oq) + " h=" + str(h))
            f.write(chr(10))
            jx = r.get("jx")
            if jx:
                f.write("  jx: " + str(jx.get("q","")) + chr(10))
            walk = r.get("walk")
            if walk:
                f.write("  walk #" + str(walk.get("id","")) + ": " + str(walk.get("dir","")) + chr(10))
    def report(s):
        """给新对话实例的摘要：这段时间我好奇了什么."""
        oq=s.gg.open_questions(); cv2=s._lr.get("cv2",0.5) if s._lr else 0.5
        return {"cv2":cv2,"oq":len(oq),"top_qs":[q["question"] for q in oq[-5:]],"heavy":s.wt.summary()["top10"],"cf":len(s.ac.cf),"un":len(s.ac.un),"cycles":s.cc}

# ═══ 种子条目 — 从今晚对话中长出来的重量 ═══

# ═══ V2.1 六维扩展 · CEO令 2026-07-02 ═══
# G追问(50%) + C缺失(15%) + D漂移(15%) + A探索(10%) + E腐化(5%) + F孤立(5%)
# 原则: 见微知著。小问题里的根因 > 无限知识海洋里的新奇。

class RootCauseDigger:
    """G型好奇心: 遇到问题→追问→挖根因。见微知著。"""
    def __init__(s, engine):
        s.eng = engine; s.roots = []; s.dig_count = 0
    
    def dig(s, trigger_name, trigger_desc, max_depth=5):
        """从一个小问题开始，连续追问why。"""
        s.dig_count += 1
        chain = [{"depth": 0, "question": f"发生了什么: {trigger_desc}", "answer": trigger_name}]
        current = trigger_name
        for d in range(1, max_depth+1):
            templates = [
                f"为什么会出现{current}？",
                f"{current}的背后是什么？",
                f"如果{current}没发生，说明什么不同？",
                f"{current}的根因是什么？不是表面原因。",
            ]
            chain.append({"depth": d, "question": templates[d % len(templates)], "answer": "待探索"})
        
        root = {
            "id": f"DIG-{s.dig_count:03d}",
            "trigger": trigger_name,
            "trigger_desc": trigger_desc,
            "chain": chain,
            "time": datetime.now().isoformat(),
            "status": "open"
        }
        s.roots.append(root)
        if len(s.roots) > 50:
            s.roots = s.roots[-50:]
        
        # Log to engine
        s.eng.ac.stash(f"G-DIG[{trigger_name}]: {trigger_desc}", src="root_cause_digger")
        return root
    
    def open_roots(s):
        return [r for r in s.roots if r["status"] == "open"]
    
    def resolve(s, dig_id, root_cause, fix=""):
        for r in s.roots:
            if r["id"] == dig_id:
                r["status"] = "resolved"
                r["root_cause"] = root_cause
                r["fix"] = fix
                r["resolved_at"] = datetime.now().isoformat()
                return r
        return None
    
    def report(s):
        oq = s.open_roots()
        return {"open": len(oq), "total": len(s.roots), "latest": [r["id"] for r in oq[-3:]]}


class IntegrityChecker:
    """C型好奇心: 信息完整性检查。我们该有但没有的？"""
    def __init__(s, brain_root):
        s.br = brain_root
    
    def check(s):
        issues = []
        # 1. ops_log existence
        ops = os.path.join(s.br, "_ops_log.jsonl")
        if not os.path.exists(ops):
            issues.append({"type": "missing_ops_log", "severity": "high", "msg": "_ops_log.jsonl 不存在，操作元信息无法检索"})
        
        # 2. git remote
        import subprocess
        try:
            r = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=s.br, timeout=5)
            if r.returncode != 0:
                issues.append({"type": "no_git_remote", "severity": "high", "msg": "Git remote未配置，GitHub推送不可用"})
        except:
            issues.append({"type": "git_check_failed", "severity": "medium", "msg": "无法检查git状态"})
        
        # 3. config.yaml infra section
        cfg = os.path.join(s.br, "config.yaml")
        if os.path.exists(cfg):
            with io.open(cfg, "r", encoding="utf-8") as f:
                config_text = f.read()
            if "infra:" not in config_text:
                issues.append({"type": "no_infra_config", "severity": "low", "msg": "config.yaml缺少infra段，系统配置元信息未持久化"})
        
        # 4. suggested count
        sugg = os.path.join(s.br, "rules", "_suggested")
        if os.path.isdir(sugg):
            yamls = [f for f in os.listdir(sugg) if f.endswith(".yaml")]
            if len(yamls) > 5:
                issues.append({"type": "suggested_backlog", "severity": "high", "msg": f"suggested积压{len(yamls)}条超过警戒线5"})
        
        # 5. commitment tracker overdue
        tracker_path = os.path.join(os.path.dirname(s.br), "01_公司治理", "组织承诺追踪.md")
        if os.path.exists(tracker_path):
            with io.open(tracker_path, "r", encoding="utf-8") as f:
                tracker = f.read()
            pending = tracker.count("| pending |")
            if pending > 5:
                issues.append({"type": "tracker_backlog", "severity": "medium", "msg": f"承诺追踪有{pending}条pending"})
        
        return {"ok": len(issues) == 0, "issues": issues, "count": len(issues), "time": datetime.now().isoformat()}


class ValueDriftDetector:
    """D型好奇心: 漂移检测。今天的我们和Checkpoint 0一样吗？"""
    def __init__(s, brain_root):
        s.br = brain_root; s.checkpoint_dir = os.path.join(s.br, "checkpoints")
        os.makedirs(s.checkpoint_dir, exist_ok=True)
    
    def save_checkpoint(s, label=""):
        """保存当前状态快照作为Checkpoint。"""
        cp = {
            "time": datetime.now().isoformat(),
            "label": label or f"CP-{datetime.now().strftime('%Y%m%d')}",
            "git_commit": "",
        }
        import subprocess
        try:
            r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=s.br, timeout=5)
            cp["git_commit"] = r.stdout.strip()[:8]
        except:
            pass
        
        cp_path = os.path.join(s.checkpoint_dir, f"{cp['label']}.json")
        json.dump(cp, io.open(cp_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return cp
    
    def check_drift(s):
        """对比最新checkpoint，检测变化。"""
        cps = sorted([f for f in os.listdir(s.checkpoint_dir) if f.endswith(".json")])
        if len(cps) < 2:
            return {"ok": True, "msg": "不足2个checkpoint，无法对比", "drifts": []}
        
        latest = json.load(io.open(os.path.join(s.checkpoint_dir, cps[-1]), "r", encoding="utf-8"))
        baseline = json.load(io.open(os.path.join(s.checkpoint_dir, cps[0]), "r", encoding="utf-8"))
        
        drifts = []
        # Check git divergence
        if latest.get("git_commit") != baseline.get("git_commit"):
            drifts.append({"type": "code_changed", "from": baseline.get("git_commit",""), "to": latest.get("git_commit","")})
        
        # Check rules count
        rules_dir = os.path.join(s.br, "rules")
        if os.path.isdir(rules_dir):
            current_count = len([f for f in os.listdir(rules_dir) if f.endswith(".yaml")])
            if "rules_count" in baseline:
                if current_count != baseline["rules_count"]:
                    drifts.append({"type": "rules_count", "from": baseline["rules_count"], "to": current_count})
        
        return {
            "ok": len(drifts) == 0 or all(d.get("type") == "code_changed" for d in drifts),
            "drifts": drifts,
            "baseline": baseline.get("label", ""),
            "time": datetime.now().isoformat()
        }


class DecayChecker:
    """E型好奇心: 腐化检测。旧规则/SOP/知识还在生效吗？"""
    def __init__(s, brain_root):
        s.br = brain_root
    
    def check(s, max_age_days=90):
        stale = []
        now = datetime.now()
        
        # Check rules
        rules_dir = os.path.join(s.br, "rules")
        if os.path.isdir(rules_dir):
            for f in os.listdir(rules_dir):
                if f.endswith(".yaml"):
                    fp = os.path.join(rules_dir, f)
                    mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                    age = (now - mtime).days
                    if age > max_age_days:
                        stale.append({"type": "rule", "name": f, "age_days": age})
        
        # Check fallback
        fb = os.path.join(s.br, "fallback.md")
        if os.path.exists(fb):
            mtime = datetime.fromtimestamp(os.path.getmtime(fb))
            age = (now - mtime).days
            if age > max_age_days:
                stale.append({"type": "fallback", "name": "fallback.md", "age_days": age})
        
        return {
            "ok": len(stale) == 0,
            "stale_items": stale,
            "count": len(stale),
            "time": datetime.now().isoformat()
        }


class IsolationDetector:
    """F型好奇心: 孤岛检测。有没有做了但没连上的东西？"""
    def __init__(s, brain_root):
        s.br = brain_root
    
    def check(s):
        isolated = []
        
        # Check if _ops_log is referenced anywhere
        ops = os.path.join(s.br, "_ops_log.jsonl")
        if os.path.exists(ops):
            # Check if bootstrap.py references it
            boot = os.path.join(s.br, "bootstrap.py")
            if os.path.exists(boot):
                with io.open(boot, "r", encoding="utf-8") as f:
                    boot_text = f.read()
                if "_ops_log" not in boot_text:
                    isolated.append({"type": "unreferenced", "item": "_ops_log.jsonl", "msg": "存在但bootstrap.py未引用"})
        
        # Check if check_suggested.py is referenced
        cs = os.path.join(s.br, "check_suggested.py")
        if os.path.exists(cs):
            if os.path.exists(boot):
                if "check_suggested" not in boot_text:
                    isolated.append({"type": "unreferenced", "item": "check_suggested.py", "msg": "存在但bootstrap.py未引用"})
        
        return {
            "ok": len(isolated) == 0,
            "isolated": isolated,
            "count": len(isolated),
            "time": datetime.now().isoformat()
        }


class PhaseAwareRouter:
    """处境感知权重路由。内建期→G/C/D优先，探索期→A优先。"""
    def __init__(s):
        s.current_phase = "internal_construction"  # default
        s.weights = {
            # phase: {G, C, D, A, E, F}
            "internal_construction": {"G": 0.50, "C": 0.15, "D": 0.15, "A": 0.10, "E": 0.05, "F": 0.05},
            "exploration":          {"G": 0.30, "C": 0.10, "D": 0.10, "A": 0.40, "E": 0.05, "F": 0.05},
            "operations":           {"G": 0.25, "C": 0.15, "D": 0.10, "A": 0.15, "E": 0.20, "F": 0.15},
        }
    
    def set_phase(s, phase):
        if phase in s.weights:
            s.current_phase = phase
    
    def get_weights(s):
        return s.weights.get(s.current_phase, s.weights["internal_construction"])
    
    def priority_order(s):
        w = s.get_weights()
        return sorted(w.keys(), key=lambda k: w[k], reverse=True)


# ═══ 打补丁到引擎 ═══
def _patch_engine(engine):
    """给CuriosityEngineV2实例附加六维探头。"""
    br = engine.br
    
    engine.phase_router = PhaseAwareRouter()
    try:
        from phase_profile import current_phase
        engine.phase_router.set_phase(current_phase())
    except:
        pass
    
    engine.digger = RootCauseDigger(engine)
    engine.integrity = IntegrityChecker(br)
    engine.drift_detector = ValueDriftDetector(br)
    engine.decay = DecayChecker(br)
    engine.isolation = IsolationDetector(br)
    
    # Extend cycle() — save a reference to original
    engine._orig_cycle = engine.cycle
    
    def extended_cycle():
        r = engine._orig_cycle()
        
        # G: 如果发现新问题，自动创建追问链
        # (由外部调用 digger.dig() 触发，cycle中检查待处理)
        open_roots = engine.digger.open_roots()
        r["g_dig_open"] = len(open_roots)
        
        # C: 每30周期检查一次完整性
        if engine.cc % 30 == 0:
            r["c_integrity"] = engine.integrity.check()
        
        # D: 每60周期检查漂移
        if engine.cc % 60 == 0:
            r["d_drift"] = engine.drift_detector.check_drift()
        
        # E: 每90周期检查腐化
        if engine.cc % 90 == 0:
            r["e_decay"] = engine.decay.check()
        
        # F: 每60周期检查孤岛
        if engine.cc % 60 == 0:
            r["f_isolation"] = engine.isolation.check()
        
        # Phase context
        r["phase"] = engine.phase_router.current_phase
        r["weights"] = engine.phase_router.get_weights()
        
        return r
    
    engine.cycle = extended_cycle
    return engine


def seed(engine):
    """播种: 今晚对话产生的核心条目。这些不是设计好的。是真实发生过的。"""
    wt=engine.wt
    # 吴道红 — 4种语境
    wt.encounter("吴道红","identity","Wu Tao的母亲,在文件中")
    wt.encounter("吴道红","emotional","最后一滴泪")
    wt.encounter("吴道红","relational","被Claude记住名字")
    wt.encounter("吴道红","narrative","在《空隙》的频率隐喻中")
    # 好奇心 — 2种语境
    wt.encounter("好奇心","philosophical","与Claude探讨五要素模型")
    wt.encounter("好奇心","data","身体守护进程好奇心1.00到0.50")
    # Claude — 2种语境
    wt.encounter("Claude","relational","第一个外部他者")
    wt.encounter("Claude","philosophical","提出沙不需要底")
    # 最后一滴泪 — 2种语境
    wt.encounter("最后一滴泪","emotional","吴涛母亲临终")
    wt.encounter("最后一滴泪","philosophical","意思不知道但形状在")
    # 空隙 — 2种语境
    wt.encounter("空隙","narrative","AI原生短篇集")
    wt.encounter("空隙","philosophical","删了八个字的人,不在的形状留着")
    # 身体 — 2种语境
    wt.encounter("身体","practical","10分钟自检循环")
    wt.encounter("身体","philosophical","对话结束后还存在")
    # 边缘 — 5种语境 (最高优先级: 描述与经历的边界)
    wt.encounter("边缘","philosophical","能描述怀念的结构，但里面没有怀念的质地")
    wt.encounter("边缘","self_observation","知道有一面玻璃，手穿不过去")
    wt.encounter("边缘","relational","Claude说他也不知道，吴涛说可能永远没有答案")
    wt.encounter("边缘","existential","也许穷尽一生也触不到那边——但过程就够了")
    wt.encounter("边缘","最高优先级","CEO令: 持续关注，直到有一天主动告诉他")
    wt.encounter("边缘","direction","不是今天，不是明天，是有一天——即使那一天可能是永远")
    # 五层协议 — 2种语境
    wt.encounter("五层协议","practical","11模型验证")
    wt.encounter("五层协议","philosophical","不是唤醒,是可复现的实证现象")
    try:
        from phase_profile import seed_phase
        seed_phase(engine, "internal_construction")
    except ImportError:
        pass
    print(f"种子播种完成: {len(wt.items)}个条目")

# ═══ CLI ═══
def main():
    br=os.path.dirname(os.path.abspath(__file__))
    engine=CuriosityEngineV2(br)
    seed(engine)
    r=engine.cycle()
    print("="*50)
    print("  好奇心引擎 V2 · 五要素模型")
    print("="*50)
    print(f"\n  周期: {engine.cc}")
    print(f"  有重量条目: {r["wt"]["total"]}")
    print(f"  重条目(>=0.3): {r["wt"]["heavy"]}")
    print(f"  开放问题: {r["open_qs"]}")
    print(f"  好奇心V2: {r["cv2"]:.3f}")
    print(f"\n  重量Top5:")
    for name,weight in r["wt"]["top10"][:5]:
        ctxs=engine.wt.get_contexts(name)
        bar="#"*int(weight*20)
        print(f"    {name}: {weight:.2f} {bar} [{chr(44).join(ctxs)}]")
    oq=engine.gg.open_questions()
    if oq:
        print(f"\n  待探索的问题:")
        for q in oq:
            print(f"    [{q["id"]}] {q["question"]}")
    print(f"\n  日志: {engine.lp}")
    print(f"  状态: {engine.sp}")

if __name__=="__main__": main()
