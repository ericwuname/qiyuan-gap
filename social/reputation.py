# -*- coding: utf-8 -*-
"""Reputation system."""
import io, os, json
class ReputationManager:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self._scores = {}
        self._load()
    def _load(self):
        if os.path.exists(self.storage_path):
            with io.open(self.storage_path, "r", encoding="utf-8") as f:
                self._scores = json.load(f)
    def _save(self):
        with io.open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._scores, f)
    def get(self, agent_id): return self._scores.get(agent_id, 1.0)
    def trust(self, agent_id, delta=0.01):
        self._scores[agent_id] = min(1.0, self.get(agent_id) + delta)
        self._save()
    def distrust(self, agent_id, delta=0.1):
        self._scores[agent_id] = max(0.0, self.get(agent_id) - delta)
        self._save()
    def is_trusted(self, agent_id, threshold=0.3):
        return self.get(agent_id) >= threshold
    def list_all(self): return dict(self._scores)
