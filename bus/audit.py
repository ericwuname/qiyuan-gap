# -*- coding: utf-8 -*-
import io, os, json
from datetime import datetime

class AuditLog:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.file_path = os.path.join(base_dir, 'audit.jsonl')
        os.makedirs(base_dir, exist_ok=True)

    def record(self, operation, module, target, result='ok', extra=None):
        entry = {'timestamp': datetime.now().isoformat(), 'operation': operation, 'module': module, 'target': target, 'result': result, 'extra': extra or {}}
        with io.open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return entry

    def query(self, module=None, operation=None, limit=50):
        if not os.path.exists(self.file_path):
            return []
        results = []
        with io.open(self.file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except:
                    continue
                if module and entry.get('module') != module:
                    continue
                if operation and entry.get('operation') != operation:
                    continue
                results.append(entry)
        return results[-limit:]

    def get_stats(self):
        if not os.path.exists(self.file_path):
            return {'total_entries': 0, 'modules': [], 'operations': {}}
        entries = []
        with io.open(self.file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except:
                        pass
        modules = list(set(e.get('module', '?') for e in entries))
        ops = {}
        for e in entries:
            op = e.get('operation', '?')
            ops[op] = ops.get(op, 0) + 1
        return {'total_entries': len(entries), 'modules': modules, 'operations': ops}