# -*- coding: utf-8 -*-
"""Sprint 5: External Gateway. Permission-gated external communication with identity declaration."""
import io, os, sys, json, hashlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bus.blackboard import Blackboard
from bus.identity_declaration import IdentityDeclaration

EXTERNAL_PERMISSIONS = {
    "model_router": ["api_call"],
    "mailbox": ["send", "receive"],
    "body_daemon": [],
    "notifier": [],
}

CEO_CONFIRM_ACTIONS = {"send", "api_call"}


class ExternalGateway:
    """Gateway for all external communications."""

    def __init__(self, bus_dir=None, brain_dir=None):
        if brain_dir is None:
            brain_dir = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )
            )
        self.brain_dir = brain_dir
        self.bus_dir = bus_dir or os.path.join(brain_dir, "brain", "bus")
        self.bb = Blackboard(self.bus_dir)
        self.identity = IdentityDeclaration()
        self._audit_path = os.path.join(self.bus_dir, "external_audit.jsonl")

    def check_permission(self, module, action):
        allowed = EXTERNAL_PERMISSIONS.get(module, [])
        if action not in allowed:
            return {"ok": False, "reason": "Module not permitted"}
        requires_ceo = action in CEO_CONFIRM_ACTIONS
        return {"ok": True, "requires_ceo": requires_ceo}

    def send(self, module, action, payload, target=None, ceo_confirmed=False):
        perm = self.check_permission(module, action)
        if not perm["ok"]:
            self._audit(module, action, "denied", perm["reason"])
            return {"ok": False, "reason": perm["reason"]}
        if perm["requires_ceo"] and not ceo_confirmed:
            self._audit(module, action, "pending_ceo", "CEO confirmation required")
            return {"ok": False, "reason": "CEO confirmation required", "requires_ceo": True}

        payload_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()[:16]

        declaration = self.identity.declare(module, action, payload_hash)

        event_id = self.bb.write_event(
            "external_gateway", action,
            {"module": module, "target": target, "declaration_id": declaration["declaration_id"]},
            severity="info"
        )

        self._audit(module, action, "sent", declaration["declaration_id"])

        return {"ok": True, "declaration": declaration, "event_id": event_id}

    def _audit(self, module, action, status, detail):
        entry = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "action": action,
            "status": status,
            "detail": detail,
        }, ensure_ascii=False)
        with io.open(self._audit_path, "a", encoding="utf-8") as f:
            f.write(entry + chr(10))

    def get_audit_log(self, limit=50):
        if not os.path.isfile(self._audit_path):
            return []
        logs = []
        with io.open(self._audit_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
        return logs[-limit:]