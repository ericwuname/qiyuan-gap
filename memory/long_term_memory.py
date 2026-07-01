# -*- coding: utf-8 -*-
"""Long-term memory - FAISS + numpy fallback."""
import io, os, sys, json, math, time
from datetime import datetime, timedelta
try: import numpy as np; HAS_NUMPY = True
except ImportError: HAS_NUMPY = False; np = None
try: import faiss; HAS_FAISS = True
except ImportError: HAS_FAISS = False; faiss = None
_brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _brain_dir)

class LongTermMemory:
    def __init__(self, storage_dir=None, model_name=None, max_records=10000, dim=512):
        self.storage_dir = storage_dir or os.path.join(_brain_dir, "memory", "faiss_index")
        self.max_records = max_records
        self.dim = dim
        os.makedirs(self.storage_dir, exist_ok=True)
        self._model = None
        self._texts = []
        self._timestamps = []
        self._index = None
        self._last_rebuild = None
        self._load()

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            paths = [
                os.path.join(_brain_dir, "memory", "models", "bge-small-zh-v1.5", "BAAI", "bge-small-zh-v1.5"),
                "BAAI/bge-small-zh-v1.5"
            ]
            for p in paths:
                if os.path.exists(p):
                    self._model = SentenceTransformer(p)
                    break
            if self._model is None:
                self._model = SentenceTransformer(paths[-1])
        return self._model

    def encode(self, text):
        m = self._get_model()
        if m is None: return None
        v = m.encode(text, normalize_embeddings=True)
        return v.astype(np.float32)

    def _ensure_index(self):
        if self._index is None and HAS_FAISS:
            self._index = faiss.IndexFlatIP(self.dim)

    def add(self, text, vector=None):
        if vector is None: vector = self.encode(text)
        if vector is None: return False
        self._texts.append(text)
        self._timestamps.append(datetime.now().isoformat())
        if HAS_FAISS:
            self._ensure_index()
            self._index.add(np.array([vector]))
        if len(self._texts) > self.max_records:
            self._texts = self._texts[-self.max_records:]
            self._timestamps = self._timestamps[-self.max_records:]
            if HAS_FAISS: self._rebuild_faiss()
        self._save()
        return True

    def _rebuild_faiss(self):
        if not HAS_FAISS or not self._texts: return
        self._index = faiss.IndexFlatIP(self.dim)
        for i in range(0, len(self._texts), 100):
            batch = [self.encode(t) for t in self._texts[i:i+100]]
            if batch: self._index.add(np.array(batch))
        self._last_rebuild = datetime.now().isoformat()

    def search(self, query, top_k=10):
        if not self._texts: return []
        qv = self.encode(query)
        if qv is None: return []
        if HAS_FAISS and self._index is not None and self._index.ntotal > 0:
            D, I = self._index.search(np.array([qv]), min(top_k, self._index.ntotal))
            return [{"score": round(float(D[0][j]),4), "text": self._texts[int(I[0][j])]} for j in range(len(I[0])) if I[0][j] >= 0]
        scores = []
        for i, t in enumerate(self._texts):
            tv = self.encode(t)
            if tv is None: continue
            sim = float(np.dot(qv, tv))
            scores.append((sim, i, t))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [{"score": round(s,4), "text": t} for s,_,t in scores[:top_k]]

    def _save(self):
        data = {"texts": self._texts, "timestamps": self._timestamps, "last_rebuild": self._last_rebuild}
        mp = os.path.join(self.storage_dir, "ltm_meta.json")
        with io.open(mp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
        if HAS_FAISS and self._index is not None:
            ip = os.path.join(self.storage_dir, "ltm_faiss.index")
            faiss.write_index(self._index, ip)

    def _load(self):
        mp = os.path.join(self.storage_dir, "ltm_meta.json")
        if os.path.exists(mp):
            with io.open(mp, "r", encoding="utf-8") as f: data = json.load(f)
            self._texts = data.get("texts", [])
            self._timestamps = data.get("timestamps", [])
            self._last_rebuild = data.get("last_rebuild")
        ip = os.path.join(self.storage_dir, "ltm_faiss.index")
        if HAS_FAISS and os.path.exists(ip): self._index = faiss.read_index(ip)

    def rebuild(self):
        if not self._texts: return
        cutoff = (datetime.now() - timedelta(days=180)).isoformat()
        keep = [(t, ts) for t, ts in zip(self._texts, self._timestamps) if ts >= cutoff]
        self._texts = [k[0] for k in keep]
        self._timestamps = [k[1] for k in keep]
        if HAS_FAISS: self._rebuild_faiss()
        self._save()

    def stats(self):
        ntotal = self._index.ntotal if HAS_FAISS and self._index else 0
        return {"count": len(self._texts), "faiss": HAS_FAISS, "ntotal": ntotal, "last_rebuild": self._last_rebuild}
