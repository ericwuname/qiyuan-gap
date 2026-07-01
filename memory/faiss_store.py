# -*- coding: utf-8 -*-
"""FAISS向量存储层 - ChromaDB的Windows兼容替代

接口与ChromaDB对齐: add(), query(), count()
存储: FAISS IndexFlatIP (内积=余弦相似度, 向量已归一化) + JSON元数据
"""

import os, json, io
import numpy as np

_HAS_FAISS = False
try:
    import faiss
    _HAS_FAISS = True
except ImportError:
    pass


class FAISSStore:
    """FAISS-backed vector store with ChromaDB-compatible interface."""

    def __init__(self, persist_dir: str, dimension: int = 512):
        self.persist_dir = persist_dir
        self.dimension = dimension
        self._index = None
        self._metadata = []       # list of {id, source_file, title, path}
        self._documents = []      # list of document strings
        self._index_path = os.path.join(persist_dir, "faiss_index.bin")
        self._meta_path = os.path.join(persist_dir, "faiss_meta.json")
        self._docs_path = os.path.join(persist_dir, "faiss_docs.json")

        # Use safe (non-Chinese) temp path for binary index to avoid FAISS C++ path bug
        self._safe_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "brain_faiss")
        self._index_path = os.path.join(self._safe_dir, "faiss_index.bin")
        os.makedirs(self._safe_dir, exist_ok=True)
        os.makedirs(persist_dir, exist_ok=True)

        if _HAS_FAISS:
            self._load_or_create()
        else:
            print("[FAISSStore] faiss-cpu not installed. Run: pip install faiss-cpu")

    # ── Load or create ──────────────────────────────────────

    def _load_or_create(self):
        if os.path.isfile(self._index_path) and os.path.isfile(self._meta_path):
            try:
                self._index = faiss.read_index(self._index_path)
                with io.open(self._meta_path, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                if os.path.isfile(self._docs_path):
                    with io.open(self._docs_path, "r", encoding="utf-8") as f:
                        self._documents = json.load(f)
                print(f"[FAISSStore] loaded index: {self._index.ntotal} vectors")
            except Exception as e:
                print(f"[FAISSStore] load failed, creating new: {e}")
                self._create_new()
        else:
            self._create_new()

    def _create_new(self):
        # IndexFlatIP: inner product. For normalized vectors, IP = cosine similarity.
        self._index = faiss.IndexFlatIP(self.dimension)
        self._metadata = []
        self._documents = []
        print(f"[FAISSStore] created new IndexFlatIP ({self.dimension}d)")

    # ── Persist ─────────────────────────────────────────────

    def _save(self):
        faiss.write_index(self._index, self._index_path)
        with io.open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)
        with io.open(self._docs_path, "w", encoding="utf-8") as f:
            json.dump(self._documents, f, ensure_ascii=False, indent=2)

    # ── ChromaDB-compatible interface ───────────────────────

    def add(self, ids: list, documents: list, metadatas: list, embeddings: list):
        """Add vectors to the index.

        Args:
            ids: list of chunk IDs
            documents: list of document strings
            metadatas: list of metadata dicts
            embeddings: list of numpy arrays or lists (already normalized)
        """
        if not ids:
            return

        # Convert embeddings to numpy
        embs = np.array(embeddings, dtype=np.float32)
        if embs.ndim == 1:
            embs = embs.reshape(1, -1)

        # Verify normalization (should already be done by BGE)
        # norms = np.linalg.norm(embs, axis=1)
        # if not np.allclose(norms, 1.0, atol=0.01):
        #     embs = embs / norms[:, np.newaxis]

        self._index.add(embs)
        for i, doc_id in enumerate(ids):
            self._metadata.append({
                "id": doc_id,
                "source_file": metadatas[i].get("source_file", "") if i < len(metadatas) else "",
                "title": metadatas[i].get("title", "") if i < len(metadatas) else "",
                "path": metadatas[i].get("path", "") if i < len(metadatas) else "",
            })
            self._documents.append(documents[i] if i < len(documents) else "")

        self._save()

    def query(self, query_embeddings: list, n_results: int = 5,
              include: list = None):
        """Query the index.

        Args:
            query_embeddings: list of numpy arrays
            n_results: number of results
            include: list of fields to include (ChromaDB compat)

        Returns:
            dict with keys: ids, documents, metadatas, distances
        """
        if self._index.ntotal == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        q_emb = np.array(query_embeddings, dtype=np.float32)
        if q_emb.ndim == 1:
            q_emb = q_emb.reshape(1, -1)

        k = min(n_results, self._index.ntotal)
        scores, indices = self._index.search(q_emb, k)

        result_ids = []
        result_docs = []
        result_meta = []
        result_distances = []

        for i in range(len(indices[0])):
            idx = indices[0][i]
            if idx < 0 or idx >= len(self._metadata):
                continue
            result_ids.append(self._metadata[idx]["id"])
            result_docs.append(self._documents[idx] if idx < len(self._documents) else "")
            result_meta.append(self._metadata[idx])
            # FAISS IndexFlatIP returns inner product (higher = more similar)
            # For normalized vectors, IP ∈ [-1, 1]. Convert to "distance" (0 = identical)
            result_distances.append(1.0 - float(scores[0][i]))

        return {
            "ids": [result_ids],
            "documents": [result_docs],
            "metadatas": [result_meta],
            "distances": [result_distances],
        }

    def reset(self):
        """Clear all data and recreate empty index."""
        self._index = faiss.IndexFlatIP(self.dimension)
        self._metadata = []
        self._documents = []
        self._save()

    def count(self) -> int:
        return self._index.ntotal if self._index else 0

    def is_empty(self) -> bool:
        return self.count() == 0
