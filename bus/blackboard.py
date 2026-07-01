# -*- coding: utf-8 -*-
import io, os, json, hashlib, time
from datetime import datetime

class Blackboard:
    def __init__(self, base_dir, push_limit=5):
        self.base_dir = base_dir
        self.file_path = os.path.join(base_dir, "blackboard.json")
        self.archive_dir = os.path.join(base_dir, "_archive")
        self.daily_push_limit = push_limit
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            with io.open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({"version": "1.0", "events": [], "snapshot": {}}, f, ensure_ascii=False)

    def _checksum(self, data):
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def _load(self):
        with io.open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        stored = data.pop("_checksum", None)
        if stored:
            computed = self._checksum(data)
            if stored != computed:
                raise ValueError("Blackboard checksum mismatch: " + stored + " vs " + computed)
        return data

    def _save(self, data):
        data["_checksum"] = self._checksum(data)
        tmp = self.file_path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)

    def write_event(self, source, event_type, payload, severity="info"):
        data = self._load()
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        seq = str(len(data["events"]) + 1).zfill(4)
        event = {
            "event_id": "evt-" + ts + "-" + seq,
            "source": source,
            "type": event_type,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "payload": payload
        }
        data["events"].append(event)
        if len(data["events"]) > 1000:
            self._archive_old_events(data)
        data["snapshot"][source] = {
            "last_event": event["event_id"],
            "last_type": event_type,
            "last_severity": severity,
            "last_timestamp": event["timestamp"]
        }
        self._save(data)
        return event["event_id"]

    def read_events(self, since_timestamp=None, limit=50):
        data = self._load()
        events = data["events"]
        if since_timestamp:
            events = [e for e in events if e["timestamp"] >= since_timestamp]
        return events[-limit:]

    def get_snapshot(self):
        data = self._load()
        last_ts = data["events"][-1]["timestamp"] if data["events"] else None
        return {
            "event_count": len(data["events"]),
            "sources": list(data["snapshot"].keys()),
            "last_event_timestamp": last_ts,
            "module_states": data["snapshot"]
        }

    def get_health(self):
        data = self._load()
        return {
            "events_pending": len(data["events"]),
            "sources_active": len(data["snapshot"]),
            "daily_push_limit": self.daily_push_limit,
            "checksum_valid": True
        }

    def _archive_old_events(self, data):
        os.makedirs(self.archive_dir, exist_ok=True)
        cutoff = len(data["events"]) - 500
        old = data["events"][:cutoff]
        data["events"] = data["events"][cutoff:]
        fn = "blackboard_archive_" + datetime.now().strftime("%Y%m%d") + ".json"
        with io.open(os.path.join(self.archive_dir, fn), "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False)
