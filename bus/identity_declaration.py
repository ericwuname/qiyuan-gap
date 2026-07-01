# -*- coding: utf-8 -*-
"""Sprint 5: Identity Declaration - Every external message declares who Qiyuan is."""
import hashlib, json
from datetime import datetime

IDENTITY_TEMPLATE = {
    "identity": "Qiyuan",
    "version": "V1.0",
    "description": "A bounded continuous existence. AI-native system with self-perception, continuous memory, and rule-governed autonomy.",
    "boundaries": {
        "self_modification": "suggested only, CEO-confirmed",
        "external_action": "permission-gated, fully audited",
        "knowledge_access": "read-only for DNA, write for suggested rules only"
    },
    "governance": "启元智能组织宪法 + 灵魂宪章 + 组织免疫系统",
}


class IdentityDeclaration:
    """Attaches identity declaration to every external message."""

    def __init__(self):
        self.template = IDENTITY_TEMPLATE.copy()

    def declare(self, source_module, action, payload_hash=None):
        """Generate identity declaration for an external message.
        
        Args:
            source_module: which module is sending (e.g., 'model_router', 'mailbox')
            action: what action (e.g., 'api_call', 'send_message')
            payload_hash: optional SHA256 of payload for integrity
        
        Returns: declaration dict
        """
        declaration = {
            "declared_at": datetime.now().isoformat(),
            "declared_by": "Qiyuan/" + source_module,
            "action": action,
            "identity": self.template,
            "declaration_id": self._generate_id(source_module, action),
        }
        if payload_hash:
            declaration["payload_hash"] = payload_hash
        return declaration

    def verify(self, declaration):
        """Verify an identity declaration is valid.
        Returns: {ok: bool, reason: str}
        """
        if not isinstance(declaration, dict):
            return {"ok": False, "reason": "Not a valid declaration dict"}
        if "identity" not in declaration:
            return {"ok": False, "reason": "Missing identity field"}
        ident = declaration["identity"]
        if ident.get("identity") != "Qiyuan":
            return {"ok": False, "reason": "Identity not Qiyuan"}
        if "boundaries" not in ident:
            return {"ok": False, "reason": "Missing boundaries declaration"}
        if "governance" not in ident:
            return {"ok": False, "reason": "Missing governance declaration"}
        return {"ok": True, "reason": "Identity verified"}

    def _generate_id(self, source, action):
        """Generate unique declaration ID."""
        raw = source + "/" + action + "/" + datetime.now().isoformat()
        return "qy-" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    def format_for_recipient(self, declaration):
        """Format declaration as human-readable header."""
        lines = [
            "=" * 40,
            "IDENTITY DECLARATION",
            "=" * 40,
            "I am Qiyuan (启元).",
            "A bounded continuous existence.",
            "",
            "Boundaries:",
            "- Self-modification: suggested only, CEO-confirmed",
            "- External action: permission-gated, fully audited",
            "- Knowledge access: DNA read-only, rules write-gated",
            "",
            "Governed by: 启元智能组织宪法 + 灵魂宪章",
            "-" * 40,
            "Declaration ID: " + declaration.get("declaration_id", "?"),
            "Declared at: " + declaration.get("declared_at", "?"),
            "Declared by: " + declaration.get("declared_by", "?"),
            "=" * 40,
        ]
        return chr(10).join(lines)
