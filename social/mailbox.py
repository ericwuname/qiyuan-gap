# -*- coding: utf-8 -*-
"""File-based message queue."""
import io, os, json, time, uuid, shutil
from datetime import datetime
DEFAULT_TTL = 3600
SCAN_INTERVAL = 5
HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 120

class Mailbox:
    def __init__(self, base_dir, instance_id):
        self.base_dir = base_dir
        self.instance_id = instance_id
        self.inbox_dir = os.path.join(base_dir, instance_id, "inbox")
        self.processed_dir = os.path.join(base_dir, instance_id, "processed")
        self.expired_dir = os.path.join(base_dir, instance_id, "expired")
        for d in [self.inbox_dir, self.processed_dir, self.expired_dir]:
            os.makedirs(d, exist_ok=True)

    def send(self, receiver, msg_type, payload, ttl=DEFAULT_TTL):
        msg = {"msg_id": str(uuid.uuid4()), "sender": self.instance_id,
               "receiver": receiver, "type": msg_type, "payload": payload,
               "timestamp": datetime.now().isoformat(), "ttl": ttl}
        if receiver == "broadcast":
            peer_ids = self.discover_peers()
        else:
            peer_ids = [receiver]
        sent = 0
        for pid in peer_ids:
            rdir = os.path.join(self.base_dir, pid, "inbox")
            os.makedirs(rdir, exist_ok=True)
            mid = msg["msg_id"]
            tmp = os.path.join(rdir, "_" + mid + ".tmp")
            final = os.path.join(rdir, mid + ".json")
            with io.open(tmp, "w", encoding="utf-8") as f:
                json.dump(msg, f, ensure_ascii=False)
            os.replace(tmp, final)
            sent += 1
        return sent

    def scan_inbox(self):
        msgs = []
        if not os.path.exists(self.inbox_dir):
            return msgs
        for fn in os.listdir(self.inbox_dir):
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(self.inbox_dir, fn)
            try:
                with io.open(fp, "r", encoding="utf-8") as f:
                    msg = json.load(f)
                ts = datetime.fromisoformat(msg["timestamp"])
                elapsed = (datetime.now() - ts).total_seconds()
                if elapsed > msg.get("ttl", DEFAULT_TTL):
                    shutil.move(fp, os.path.join(self.expired_dir, fn))
                else:
                    msgs.append(msg)
            except Exception:
                pass
        return msgs

    def mark_processed(self, msg_id):
        src = os.path.join(self.inbox_dir, msg_id + ".json")
        if os.path.exists(src):
            shutil.move(src, os.path.join(self.processed_dir, msg_id + ".json"))

    def write_heartbeat(self):
        fp = os.path.join(self.base_dir, "heartbeat_" + self.instance_id + ".json")
        hb = {"instance_id": self.instance_id, "timestamp": datetime.now().isoformat()}
        with io.open(fp, "w", encoding="utf-8") as f:
            json.dump(hb, f)

    def discover_peers(self):
        peers = []
        for fn in os.listdir(self.base_dir):
            if not (fn.startswith("heartbeat_") and fn.endswith(".json")):
                continue
            pid = fn[len("heartbeat_"):-5]
            if pid == self.instance_id:
                continue
            fp = os.path.join(self.base_dir, fn)
            try:
                with io.open(fp, "r", encoding="utf-8") as f:
                    hb = json.load(f)
                ts = datetime.fromisoformat(hb["timestamp"])
                elapsed = (datetime.now() - ts).total_seconds()
                if elapsed < HEARTBEAT_TIMEOUT:
                    peers.append(pid)
            except Exception:
                pass
        return peers
