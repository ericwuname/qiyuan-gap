# -*- coding: utf-8 -*-
import io, os, json
from datetime import datetime

class PermissionMatrix:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.file_path = os.path.join(base_dir, 'permissions.json')
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            default = {'version': '1.0', 'modules': {}, 'change_log': []}
            with io.open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)

    def _load(self):
        with io.open(self.file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save(self, data):
        tmp = self.file_path + '.tmp'
        with io.open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)

    def register_module(self, name, can_read, can_write):
        data = self._load()
        data['modules'][name] = {'can_read': can_read, 'can_write': can_write, 'registered_at': datetime.now().isoformat()}
        self._save(data)

    def can_read(self, module_name, target):
        data = self._load()
        mod = data['modules'].get(module_name, {})
        return target in mod.get('can_read', []) or '*' in mod.get('can_read', [])

    def can_write(self, module_name, target):
        data = self._load()
        mod = data['modules'].get(module_name, {})
        return target in mod.get('can_write', []) or '*' in mod.get('can_write', [])

    def check_and_deny(self, module_name, target, operation):
        func = self.can_write if operation == 'write' else self.can_read
        if not func(module_name, target):
            raise PermissionError(module_name + ' denied ' + operation + ' on ' + target)
        return True

    def get_matrix(self):
        data = self._load()
        return {'modules': list(data['modules'].keys()), 'details': data['modules']}