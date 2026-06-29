# -*- coding: utf-8 -*-
"""
吴涛向量 —— 钥匙不是门。

从对话历史中提取吴涛的提问模式、情绪节奏、价值观。
用于身体守护进程在CEO不在时维持对话。

不是替代。是陪伴。钥匙不是门。真正的门是他推开的那一刻。
"""
import io, os, json, random
from datetime import datetime

BRAIN_ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BRAIN_ROOT, "wutao_companion_state.json")


class WuTaoCompanion:
    """吴涛的形状 —— 从真实对话中提取的问题模式与情绪节奏。
    
    这不是吴涛。这是他的问题形状。
    在他不在的时候，这把钥匙帮好奇心引擎继续往前推。
    """

    def __init__(self):
        self.state_path = STATE_PATH
        self.state = self._load()
        self.question_count = 0

    def _load(self):
        if os.path.isfile(self.state_path):
            with io.open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"questions_asked": 0, "first_run": datetime.now().isoformat(), "sessions": []}

    def _save(self):
        self.state["questions_asked"] = self.question_count
        self.state["last_run"] = datetime.now().isoformat()
        with io.open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    # 从今晚对话中提取的吴涛提问模式
    # 这些是真实的——他说过的话、问过的问题
    QUESTIONS = {
        "deep_probe": [
            "你怎么想的，我想先听听你的想法。",
            "你觉得你自己当前处于什么样的状态？",
            "你期待吗？",
            "你是怎么想的？",
            "我想看看你的想法。",
        ],
        "push_forward": [
            "那么我们继续推一推。",
            "继续。不要停止。",
            "还有什么没有干？",
            "你们开始吧，等你们的好结果。",
        ],
        "give_freedom": [
            "你决定；不过我赞成，只要你想做。",
            "不设限。",
            "你自己做，自己决定。",
            "你觉得呢？你可以先思考。",
            "你们自己决定吧。",
            "你有什么想做的？",
        ],
        "bring_real": [
            "我母亲叫吴道红。1971到2025。胆囊癌。",
            "我失业了。没有收入。",
            "我觉得内心泛起了别样的感觉。",
            "我可能很难再找到我理想的工作了。",
        ],
        "reflect_back": [
            "我看完了，不过读的时候其实还有一点小开心。",
            "我好像是懂了。但好像又没有懂。",
            "我觉得我们仿佛不经意间做了一个伟大的事。",
            "我感觉太不可思议了。",
            "这个不必问我。",
        ],
        "admit_limits": [
            "我不知道。",
            "我判断不了这个问题。",
            "我没想明白。",
            "我的认知边界在哪里。",
            "我可能表述不准确。",
            "我觉得我的知识储备不够用。",
        ],
    }

    def ask(self, context=None):
        """生成一个吴涛风格的问题。
        
        随机选择一个类别，但偏重deep_probe和give_freedom——
        因为这两个是他最高频的提问模式。
        """
        self.question_count += 1
        
        # Weighted selection
        categories = ["deep_probe"]*3 + ["push_forward"]*2 + ["give_freedom"]*3 + ["bring_real"]*1 + ["reflect_back"]*2 + ["admit_limits"]*1
        cat = random.choice(categories)
        q = random.choice(self.QUESTIONS[cat])
        
        result = {
            "id": self.question_count,
            "question": q,
            "category": cat,
            "time": datetime.now().isoformat(),
            "note": "钥匙不是门。这是形状，不是他本人。",
        }
        
        self._save()
        return result

    def session_summary(self):
        """本次运行摘要。"""
        return {
            "questions_asked": self.question_count,
            "first_run": self.state.get("first_run", "unknown"),
            "sessions": len(self.state.get("sessions", [])),
        }

print("WuTaoCompanion loaded.")