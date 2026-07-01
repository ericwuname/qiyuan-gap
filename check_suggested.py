# -*- coding: utf-8 -*-
"""suggested积压监控——当_suggested/下.yaml超过阈值时写ALERT文件"""
import io, os, json, datetime

THRESHOLD = 5
SUGGESTED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules', '_suggested')
ALERT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alerts')

def check():
    if not os.path.isdir(SUGGESTED_DIR):
        return {'ok': True, 'count': 0, 'alert': False}
    yamls = [f for f in os.listdir(SUGGESTED_DIR) if f.endswith('.yaml')]
    count = len(yamls)
    alert = count > THRESHOLD
    if alert:
        os.makedirs(ALERT_DIR, exist_ok=True)
        data = {
            'alert': True, 'count': count, 'threshold': THRESHOLD,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'files': sorted(yamls),
            'action': '请CEO+军师审核_suggested目录'
        }
        io.open(os.path.join(ALERT_DIR, 'suggested_overflow.json'), 'w', encoding='utf-8').write(
            json.dumps(data, ensure_ascii=False, indent=2))
    return {'ok': True, 'count': count, 'threshold': THRESHOLD, 'alert': alert}

if __name__ == '__main__':
    r = check()
    print(json.dumps(r, ensure_ascii=False))
