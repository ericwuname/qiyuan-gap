# -*- coding: utf-8 -*-
"""启元智能 · 长期记忆引擎 (向量检索核心)

双模策略:
  Mode A (full):  ChromaDB + BAAI/bge-small-zh-v1.5  (需 pip install chromadb sentence-transformers)
  Mode B (fallback): sklearn TfidfVectorizer + scipy cosine_similarity  (零额外依赖)
"""

import io, os, sys, time, json, hashlib
from typing import List, Dict, Optional

# Phase 5: logging chain instrumentation
_brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _brain_dir not in sys.path:
    sys.path.insert(0, _brain_dir)
try:
    from logging_chain import log_info, log_error, log_warn
except ImportError:
    log_info = log_error = log_warn = lambda *a, **kw: None

import numpy as np


# ── Mode detection ────────────────────────────────────────────
_HAS_FAISS = False
_HAS_CHROMADB = False
_HAS_SENTENCE_TRANSFORMERS = False

try:
    import faiss  # noqa: F401
    _HAS_FAISS = True
except ImportError:
    pass

try:
    import chromadb  # noqa: F401
    _HAS_CHROMADB = True
except ImportError:
    pass

try:
    from sentence_transformers import SentenceTransformer  # noqa: F401
    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    pass

_IS_FAISS_MODE = _HAS_FAISS and _HAS_SENTENCE_TRANSFORMERS
_IS_CHROMA_MODE = _HAS_CHROMADB and _HAS_SENTENCE_TRANSFORMERS and not _IS_FAISS_MODE
_IS_FULL_MODE = _IS_FAISS_MODE or _IS_CHROMA_MODE


# ── Fallback dependencies ─────────────────────────────────────
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import csr_matrix, vstack
import pickle

if _HAS_FAISS:
    from .faiss_store import FAISSStore  # noqa: F401


class MemoryEngine:
    """Long-term memory with vector search over knowledge base.

    Usage:
        engine = MemoryEngine(kb_root, persist_dir)
        engine.build_index()          # first run
        results = engine.search("规则怪谈")  # retrieve top-k
    """

    def __init__(
        self,
        kb_root: str,
        persist_dir: str,
        model_name: str = os.path.join(os.path.dirname(__file__), "models", "bge-small-zh-v1.5"),
        chunk_size: int = 1000,
        top_k: int = 5,
    ):
        self.kb_root = kb_root
        self.persist_dir = persist_dir
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.top_k = top_k
        self._mode = "faiss" if _IS_FAISS_MODE else ("full" if _IS_CHROMA_MODE else "fallback")
        self._model = None
        self._collection = None
        self._faiss_store = None

        os.makedirs(self.persist_dir, exist_ok=True)

        print(f"[MemoryEngine] mode={self._mode}")

        if self._mode == "faiss":
            self._init_faiss_mode()
        elif self._mode == "full":
            self._init_full_mode()
        else:
            self._init_fallback_mode()

        # NOTE: Auto-build removed. Use engine.rebuild() or brain kb rebuild explicitly.

    # ── Full mode (ChromaDB) ──────────────────────────────────

    def _init_full_mode(self):
        self._chroma_client = chromadb.PersistentClient(path=self.persist_dir)
        try:
            self._collection = self._chroma_client.get_collection("kb_index")
        except Exception:
            # Collection doesn't exist yet, create it now
            self._collection = self._chroma_client.create_collection("kb_index")
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            self._model = SentenceTransformer(self.model_name, local_files_only=True)
        except Exception as e:
            print(f"[MemoryEngine] BGE model failed: {e}, falling back to TF-IDF")
            self._mode = "fallback"
            self._init_fallback_mode()
            return

        # Also load TF-IDF fallback as backup (ChromaDB HNSW has Windows persistence issues)
        self._load_fallback_if_exists()
    # ── FAISS mode ────────────────────────────────────────────

    def _init_faiss_mode(self):
        """FAISS mode: BGE + FAISS. Model lazy-loaded on first search."""
        from .faiss_store import FAISSStore
        self._model = None  # lazy: loaded by _ensure_model() on first use
        self._faiss_store = FAISSStore(self.persist_dir, dimension=512)
        self._load_fallback_if_exists()
        print(f"[MemoryEngine] FAISS mode ready (model lazy), {self._faiss_store.count()} vectors")

    def _ensure_model(self):
        """Lazy-load BGE model on first search/build. Safe to call repeatedly."""
        if self._model is not None:
            return
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            if not os.path.isabs(self.model_name):
                root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                self.model_name = os.path.join(root, self.model_name)
            self._model = SentenceTransformer(self.model_name, local_files_only=True)
            print("[MemoryEngine] BGE model loaded (lazy)")
        except Exception as e:
            print(f"[MemoryEngine] BGE model failed: {e}, falling back to TF-IDF")
            self._mode = "fallback"
            self._init_fallback_mode()
            raise RuntimeError(f"BGE model unavailable: {e}") from e

    def _load_fallback_if_exists(self):
        """Load TF-IDF fallback index if it exists on disk (backup for ChromaDB HNSW failures)."""
        idx_path = os.path.join(self.persist_dir, "fallback_index.pkl")
        meta_path = os.path.join(self.persist_dir, "fallback_meta.json")
        if os.path.isfile(idx_path) and os.path.isfile(meta_path):
            try:
                with io.open(meta_path, "r", encoding="utf-8") as f:
                    self._doc_meta = json.load(f)
                with open(idx_path, "rb") as f:
                    data = pickle.load(f)
                    self._tfidf_vectorizer = data["vectorizer"]
                    self._doc_matrix = data["matrix"]
                print(f"[MemoryEngine] loaded TF-IDF backup: {len(self._doc_meta)} docs")
            except Exception as e:
                print(f"[MemoryEngine] TF-IDF backup load failed: {e}")

    def _init_fallback_mode(self):
        self._tfidf_vectorizer = None
        self._doc_matrix = None
        self._doc_meta = []

        idx_path = os.path.join(self.persist_dir, "fallback_index.pkl")
        meta_path = os.path.join(self.persist_dir, "fallback_meta.json")

        if os.path.isfile(idx_path) and os.path.isfile(meta_path):
            print("[MemoryEngine] loading fallback index from disk...")
            with io.open(meta_path, "r", encoding="utf-8") as f:
                self._doc_meta = json.load(f)
            with open(idx_path, "rb") as f:
                data = pickle.load(f)
                self._tfidf_vectorizer = data["vectorizer"]
                self._doc_matrix = data["matrix"]
            print(f"[MemoryEngine] loaded {len(self._doc_meta)} docs")

    def _save_fallback_index(self):
        idx_path = os.path.join(self.persist_dir, "fallback_index.pkl")
        meta_path = os.path.join(self.persist_dir, "fallback_meta.json")

        with io.open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self._doc_meta, f, ensure_ascii=False, indent=2)
        with open(idx_path, "wb") as f:
            pickle.dump({
                "vectorizer": self._tfidf_vectorizer,
                "matrix": self._doc_matrix,
            }, f)

    # ── Chunking ──────────────────────────────────────────────

    @staticmethod
    def _chunk_markdown(text: str, source_file: str, max_len: int) -> List[Dict]:
        """Split markdown by ## headings, cap each chunk at max_len."""
        chunks = []
        # Split by ## level-2 headers
        sections = text.split("\n## ")
        current_title = ""  # for the preamble before first ##

        for i, section in enumerate(sections):
            if i == 0:
                # Preamble before any ##
                body = section.strip()
                title = "(preamble)"
            else:
                lines = section.split("\n", 1)
                title = lines[0].strip()
                body = lines[1].strip() if len(lines) > 1 else ""

            if not body:
                continue

            # Split long sections
            while len(body) > 0:
                chunk_text = body[:max_len]
                body = body[max_len:]

                # Build a stable chunk_id
                chunk_hash = hashlib.md5(
                    (source_file + title + chunk_text[:80]).encode("utf-8")
                ).hexdigest()[:12]

                chunks.append({
                    "id": f"{source_file}::{chunk_hash}",
                    "text": chunk_text,
                    "source_file": source_file,
                    "title": title,
                })

        return chunks

    # ── Build index ───────────────────────────────────────────

    def build_index(self, kb_dirs: Optional[List[str]] = None):
        """Scan KB directory, chunk all .md files, embed, and store.

        Args:
            kb_dirs: Subdirectories to include. None = all.
        """
        log_info("MEMORY", f"build_index start: kb_dirs={kb_dirs}")
        if kb_dirs is None:
            scan_root = self.kb_root
        else:
            scan_root = self.kb_root  # scan starts from kb_root

        # Collect .md files
        md_files = []
        for dirpath, _, filenames in os.walk(scan_root):
            # Filter by kb_dirs if specified
            if kb_dirs:
                rel = os.path.relpath(dirpath, self.kb_root)
                parts = rel.split(os.sep)
                if parts[0] not in kb_dirs and rel != ".":
                    continue
            for fname in filenames:
                if fname.endswith(".md"):
                    md_files.append(os.path.join(dirpath, fname))

        print(f"[MemoryEngine] found {len(md_files)} .md files")

        all_chunks = []
        for idx, fpath in enumerate(md_files):
            if (idx + 1) % 100 == 0:
                print(f"[MemoryEngine] reading... {idx + 1}/{len(md_files)}")

            try:
                with io.open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"  skip {fpath}: {e}")
                continue

            rel_path = os.path.relpath(fpath, self.kb_root)
            chunks = self._chunk_markdown(content, rel_path, self.chunk_size)
            # Add full path for retrieval
            for c in chunks:
                c["path"] = fpath
            all_chunks.extend(chunks)

        print(f"[MemoryEngine] total chunks: {len(all_chunks)}")

        if not all_chunks:
            print("[MemoryEngine] WARNING: no chunks generated")
            return

        texts = [c["text"] for c in all_chunks]

        if self._mode == "faiss":
            self._build_faiss_index(all_chunks, texts)
        elif self._mode == "full":
            self._build_full_index(all_chunks, texts)

        print(f"[MemoryEngine] index built: {len(all_chunks)} chunks")

    def _build_full_index(self, chunks, texts):
        """Full mode: embed with BGE and store in ChromaDB."""
        print("[MemoryEngine] embedding with BGE...")
        embeddings = self._model.encode(
            texts,
            show_progress_bar=sys.stdout.isatty(),
            normalize_embeddings=True,
        )

        ids = [c["id"] for c in chunks]
        metadatas = [{
            "source_file": c["source_file"],
            "title": c["title"],
            "path": c["path"],
        } for c in chunks]

        # Clear existing
        try:
            self._chroma_client.delete_collection("kb_index")
        except Exception:
            pass
        self._collection = self._chroma_client.create_collection("kb_index")

        # Batch add
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self._collection.add(
                ids=ids[i:end],
                embeddings=embeddings[i:end].tolist(),
                metadatas=metadatas[i:end],
                documents=texts[i:end],
            )
            if (i // batch_size + 1) % 10 == 0:
                print(f"  added {end}/{len(ids)}")

        # Also build TF-IDF fallback as backup (ChromaDB HNSW has Windows persistence issues)
        try:
            self._build_fallback_index(chunks, texts)
        except Exception:
            pass

    def _build_faiss_index(self, chunks, texts):
        """FAISS mode: embed with BGE and store in FAISS IndexFlatIP."""
        self._ensure_model()
        print("[MemoryEngine] embedding with BGE for FAISS...")
        embeddings = self._model.encode(
            texts, show_progress_bar=sys.stdout.isatty(), normalize_embeddings=True)
        ids = [c["id"] for c in chunks]
        metadatas = [{"source_file": c["source_file"], "title": c["title"], "path": c["path"]} for c in chunks]
        from .faiss_store import FAISSStore
        self._faiss_store = FAISSStore(self.persist_dir, dimension=self._model.get_embedding_dimension())
        batch_size = 500
        self._faiss_store.reset()  # Clear old index before rebuild
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self._faiss_store.add(
                ids=ids[i:end], documents=texts[i:end],
                metadatas=metadatas[i:end], embeddings=embeddings[i:end].tolist())
            if (i // batch_size + 1) % 10 == 0:
                print(f"  added {end}/{len(ids)}")
        print(f"[MemoryEngine] FAISS index built: {self._faiss_store.count()} vectors")
        try:
            self._build_fallback_index(chunks, texts)
        except Exception:
            pass
    def _build_fallback_index(self, chunks, texts):
        """Fallback mode: TF-IDF vectorizer + scipy sparse matrix."""
        print("[MemoryEngine] building TF-IDF index (char ngrams for Chinese)...")
        self._doc_meta = [{
            "source_file": c["source_file"],
            "title": c["title"],
            "path": c["path"],
            "id": c["id"],
        } for c in chunks]

        self._tfidf_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(1, 3),
            max_features=20000,
            lowercase=False,
        )
        self._doc_matrix = self._tfidf_vectorizer.fit_transform(texts)
        self._save_fallback_index()
        print(f"[MemoryEngine] TF-IDF matrix shape: {self._doc_matrix.shape}")

    # ── Search ────────────────────────────────────────────────

    def search(self, query: str, top_k: Optional[int] = None) -> Dict:
        """Vector search returning top-k results.
        log_info("MEMORY", f"search: query_len={len(query)}, top_k={top_k}") Falls back gracefully.

        Returns:
            {"results": [{file, chunk, score, path, title}, ...], "query": ..., "mode": ...}
        """
        k = top_k or self.top_k

        if self._mode == "faiss":
            result = self._search_faiss(query, k)
            if result.get("total", 0) == 0 and hasattr(self, '_doc_matrix') and self._doc_matrix is not None:
                fb = self._search_fallback(query, k)
                fb["mode"] = "fallback (FAISS empty)"
                return fb
            return result
        elif self._mode == "full":
            result = self._search_full(query, k)
            # If full mode returned empty due to error, try fallback
            if result.get("total", 0) == 0 and hasattr(self, '_doc_matrix') and self._doc_matrix is not None:
                fb = self._search_fallback(query, k)
                fb["mode"] = "fallback (ChromaDB degraded)"
                return fb
            return result
        else:
            return self._search_fallback(query, k)

    def _search_full(self, query, k):
        q_embedding = self._model.encode(
            [query], normalize_embeddings=True
        )[0].tolist()

        try:
            results = self._collection.query(
                query_embeddings=[q_embedding],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            # HNSW index may be unreadable cross-process (ChromaDB Windows issue)
            # Fall back to TF-IDF if available
            if hasattr(self, '_doc_matrix') and self._doc_matrix is not None:
                return self._search_fallback(query, k)
            return {"results": [], "query": query, "mode": "full (error)", "total": 0, "error": str(e)}

        items = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                dist = results["distances"][0][i]
                meta = results["metadatas"][0][i]
                doc = results["documents"][0][i]

                # ChromaDB returns cosine distance, convert to similarity
                score = 1.0 - dist

                items.append({
                    "file": meta.get("source_file", ""),
                    "chunk": doc[:300] + ("..." if len(doc) > 300 else ""),
                    "score": round(float(score), 4),
                    "path": meta.get("path", ""),
                    "title": meta.get("title", ""),
                })

        return {
            "results": items,
            "query": query,
            "mode": "full (ChromaDB + BGE)",
            "total": len(items),
        }

    def _search_faiss(self, query, k):
        """FAISS semantic search."""
        self._ensure_model()
        q_embedding = self._model.encode(
            [query], normalize_embeddings=True)[0].tolist()
        try:
            results = self._faiss_store.query(
                query_embeddings=[q_embedding], n_results=k, include=["documents", "metadatas", "distances"])
        except Exception as e:
            if hasattr(self, '_doc_matrix') and self._doc_matrix is not None:
                return self._search_fallback(query, k)
            return {"results": [], "query": query, "mode": "faiss (error)", "total": 0, "error": str(e)}

        items = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                dist = results["distances"][0][i]
                meta = results["metadatas"][0][i]
                doc = results["documents"][0][i]
                score = 1.0 - dist
                items.append({
                    "file": meta.get("source_file", ""),
                    "chunk": doc[:300]+("..." if len(doc)>300 else ""),
                    "score": round(float(score), 4),
                    "path": meta.get("path", ""),
                    "title": meta.get("title", ""),
                })
        items.sort(key=lambda x: x["score"], reverse=True)
        return {"results": items, "query": query, "mode": "faiss", "total": len(items)}
    def _search_fallback(self, query, k):
        if self._doc_matrix is None or self._tfidf_vectorizer is None:
            return {"results": [], "query": query, "mode": "fallback", "total": 0}

        q_vec = self._tfidf_vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._doc_matrix)[0]

        # Get top-k indices
        if len(sims) <= k:
            top_indices = np.argsort(sims)[::-1]
        else:
            top_indices = np.argpartition(sims, -k)[-k:]
            top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]

        items = []
        for idx in top_indices:
            score = float(sims[idx])
            if score < 0.01:
                continue
            meta = self._doc_meta[idx]

            # Get chunk text from the matrix (we lost original text in sparse)
            # Use the source path to read and find chunk
            chunk_preview = meta.get("title", "")[:200]

            items.append({
                "file": meta.get("source_file", ""),
                "chunk": chunk_preview,
                "score": round(score, 4),
                "path": meta.get("path", ""),
                "title": meta.get("title", ""),
            })

        return {
            "results": items[:k],
            "query": query,
            "mode": "fallback (TF-IDF + cosine)",
            "total": len(items[:k]),
        }

    # ── Rebuild ───────────────────────────────────────────────

    def rebuild(self):
        """Delete old index and rebuild from scratch."""
        log_info("MEMORY", "rebuild start")
        print("[MemoryEngine] rebuilding index...")

        if self._mode == "full":
            try:
                self._chroma_client.delete_collection("kb_index")
            except Exception:
                pass
            self._collection = self._chroma_client.create_collection("kb_index")
        else:
            idx_path = os.path.join(self.persist_dir, "fallback_index.pkl")
            meta_path = os.path.join(self.persist_dir, "fallback_meta.json")
            for p in [idx_path, meta_path]:
                if os.path.isfile(p):
                    os.remove(p)
            self._tfidf_vectorizer = None
            self._doc_matrix = None
            self._doc_meta = []

        self.build_index()

    # ── Status ────────────────────────────────────────────────

    def status(self) -> Dict:
        """Return engine status."""
        if self._mode == "faiss":
            faiss_count = self._faiss_store.count() if self._faiss_store else 0
            fallback = len(self._doc_meta) if hasattr(self, "_doc_meta") else 0
            return {
                "indexed_docs": faiss_count,
                "model": "BGE + FAISS IndexFlatIP",
                "ok": faiss_count > 0,
                "fallback_docs": fallback,
            }
        if self._mode == "full":
            try:
                count = self._collection.count()
            except Exception:
                count = 0
            fallback = len(self._doc_meta) if hasattr(self, "_doc_meta") else 0
            return {
                "indexed_docs": count,
                "model": self.model_name,
                "ok": count > 0 or fallback > 0,
                "fallback_docs": fallback,
            }
        else:
            fallback = len(self._doc_meta) if hasattr(self, "_doc_meta") else 0
            return {
                "indexed_docs": fallback,
                "model": "sklearn TfidfVectorizer (fallback)",
                "ok": fallback > 0,
            }


    # -- Dedup --------------------------------------------------


    def _dedup_incremental(self, threshold: float = 0.95) -> Dict:
        """Incremental dedup: only check new document pairs since last run.
        Uses dedup_cache.json to track checked pairs."""
        import json as _json, hashlib
        cache_path = os.path.join(self.persist_dir, "dedup_cache.json")
        cache = {}
        if os.path.isfile(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache = _json.load(f)
            except Exception:
                cache = {}

        checked_pairs = set(tuple(p) for p in cache.get("checked_pairs", []))
        last_doc_count = cache.get("last_doc_count", 0)

        if self._mode == "full":
            return {"ok": True, "duplicates_found": 0, "merged_count": 0,
                    "mode": "full-incremental", "message": "Incremental not supported in full mode, use non-incremental"}

        from collections import Counter
        import math

        docs = self._documents
        current_doc_count = len(docs)

        if current_doc_count <= last_doc_count and len(checked_pairs) > 0:
            return {"ok": True, "duplicates_found": 0, "merged_count": 0,
                    "mode": "fallback-incremental", "cached": True,
                    "message": "No new documents since last dedup",
                    "duration_ms": 0}

        # Only check new pairs
        new_pairs_found = 0
        merged = 0
        new_checked = set(checked_pairs)

        for i in range(last_doc_count, current_doc_count):
            for j in range(i + 1, current_doc_count):
                pair = (min(i, j), max(i, j))
                if pair in checked_pairs:
                    continue
                new_checked.add(pair)
                # Quick hash comparison first
                di = docs[i].get("content", "")
                dj = docs[j].get("content", "")
                hash_i = hashlib.md5(di.encode("utf-8", errors="ignore")).hexdigest()
                hash_j = hashlib.md5(dj.encode("utf-8", errors="ignore")).hexdigest()
                if hash_i == hash_j:
                    new_pairs_found += 1
                    merged += 1
                    continue

                # TF-IDF cosine check only for new pairs
                vi = self._tfidf_vectors.get(i, {})
                vj = self._tfidf_vectors.get(j, {})
                if vi and vj:
                    common = set(vi.keys()) & set(vj.keys())
                    dot = sum(vi[k] * vj[k] for k in common)
                    if dot >= threshold:
                        new_pairs_found += 1
                        merged += 1

        # Save cache
        cache = {
            "checked_pairs": [list(p) for p in new_checked],
            "last_doc_count": current_doc_count,
            "last_run": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            _json.dump(cache, f, ensure_ascii=False)

        return {"ok": True,
                "duplicates_found": new_pairs_found,
                "merged_count": merged,
                "mode": "fallback-incremental",
                "cached": False,
                "new_docs_checked": current_doc_count - last_doc_count,
                "duration_ms": 0}
    def dedup(self, threshold: float = 0.95, incremental: bool = False) -> Dict:
        """Detect duplicates. Set incremental=True to skip previously checked pairs."""
        if incremental:
            return self._dedup_incremental(threshold)
        if self._mode == "full":
            return self._dedup_full(threshold)
        else:
            return self._dedup_fallback(threshold)
        # Detect duplicate documents using TF-IDF + cosine similarity.
        # Auto-merge: keep earlier version, merge tags/metadata.
        if self._mode == "full":
            return self._dedup_full(threshold)
        else:
            return self._dedup_fallback(threshold)

    def _dedup_full(self, threshold: float) -> Dict:
        # Full mode: use ChromaDB embeddings for dedup.
        try:
            all_data = self._collection.get(
                include=["embeddings", "metadatas", "documents"]
            )
        except Exception as e:
            return {"ok": False, "error": str(e), "duplicates_found": 0,
                    "merged_count": 0, "details": [], "mode": "full (ChromaDB + BGE)"}

        ids_list = all_data.get("ids", [])
        if not ids_list or len(ids_list) <= 1:
            return {"ok": True, "duplicates_found": 0, "merged_count": 0,
                    "details": [], "mode": "full (ChromaDB + BGE)"}

        embeddings = np.array(all_data["embeddings"])
        metadatas = all_data.get("metadatas", [])
        documents = all_data.get("documents", [])

        n = len(ids_list)
        # embeddings are L2-normalized, dot product = cosine similarity
        sim_matrix = np.dot(embeddings, embeddings.T)

        # Resolve file modification times for tie-breaking
        file_mtimes = {}
        for i in range(n):
            src = metadatas[i].get("source_file", "") if i < len(metadatas) else ""
            fpath = os.path.join(self.kb_root, src)
            file_mtimes[i] = os.path.getmtime(fpath) if os.path.isfile(fpath) else 0.0

        # Find duplicate pairs
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim > threshold:
                    pairs.append((i, j, sim))

        if not pairs:
            return {"ok": True, "duplicates_found": 0, "merged_count": 0,
                    "details": [], "mode": "full (ChromaDB + BGE)"}

        # Union-Find for connected components
        parent = list(range(n))
        def _find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def _union(x, y):
            rx, ry = _find(x), _find(y)
            if rx != ry:
                parent[rx] = ry
        for i, j, _sim in pairs:
            _union(i, j)

        clusters = {}
        for i in range(n):
            root = _find(i)
            clusters.setdefault(root, []).append(i)

        details = []
        ids_to_delete = []
        ids_to_update = {}

        for _root_idx, members in clusters.items():
            if len(members) <= 1:
                continue
            members_sorted = sorted(members, key=lambda idx: (file_mtimes.get(idx, 0), idx))
            keep_idx = members_sorted[0]
            remove_indices = members_sorted[1:]

            keep_meta = dict(metadatas[keep_idx]) if keep_idx < len(metadatas) else {}
            merged_titles = set()
            merged_tags = set()

            for mi in members_sorted:
                if mi < len(metadatas):
                    m = metadatas[mi]
                    if m.get("title"):
                        merged_titles.add(m["title"])
                    tags = m.get("tags", [])
                    if isinstance(tags, list):
                        merged_tags.update(tags)
                    elif isinstance(tags, str):
                        merged_tags.add(tags)

            keep_meta["title"] = " | ".join(sorted(merged_titles)) if merged_titles else keep_meta.get("title", "")
            keep_meta["merged_from"] = [ids_list[ri] for ri in remove_indices]
            if merged_tags:
                keep_meta["tags"] = sorted(merged_tags)

            keep_doc = documents[keep_idx] if keep_idx < len(documents) else ""
            for ri in remove_indices:
                if ri < len(documents) and len(documents[ri]) > len(keep_doc):
                    keep_doc = documents[ri]

            ids_to_update[ids_list[keep_idx]] = {"metadatas": keep_meta, "documents": keep_doc}
            for ri in remove_indices:
                ids_to_delete.append(ids_list[ri])

            cluster_sims = [s for (a, b, s) in pairs if a in members and b in members]
            max_sim = max(cluster_sims) if cluster_sims else 0.0

            details.append({
                "kept_id": ids_list[keep_idx],
                "kept_file": metadatas[keep_idx].get("source_file", "") if keep_idx < len(metadatas) else "",
                "merged_ids": [ids_list[ri] for ri in remove_indices],
                "merged_files": [metadatas[ri].get("source_file", "") if ri < len(metadatas) else "" for ri in remove_indices],
                "max_similarity": round(max_sim, 4),
            })

        if ids_to_delete:
            try:
                self._collection.delete(ids=ids_to_delete)
            except Exception as e:
                return {"ok": False, "error": f"Delete failed: {e}", "duplicates_found": len(pairs),
                        "merged_count": 0, "details": details, "mode": "full (ChromaDB + BGE)"}

        for uid, upd in ids_to_update.items():
            try:
                self._collection.update(ids=[uid], metadatas=[upd["metadatas"]], documents=[upd["documents"]])
            except Exception:
                pass

        return {"ok": True, "duplicates_found": len(pairs), "merged_count": len(details),
                "details": details, "mode": "full (ChromaDB + BGE)"}

    def _dedup_fallback(self, threshold: float) -> Dict:
        # Fallback mode: use TF-IDF matrix for dedup.
        if self._doc_matrix is None or len(self._doc_meta) <= 1:
            return {"ok": True, "duplicates_found": 0, "merged_count": 0,
                    "details": [], "mode": "fallback (TF-IDF + cosine)"}

        n = len(self._doc_meta)
        sim_matrix = cosine_similarity(self._doc_matrix)

        file_mtimes = {}
        for i in range(n):
            src = self._doc_meta[i].get("source_file", "")
            fpath = os.path.join(self.kb_root, src)
            file_mtimes[i] = os.path.getmtime(fpath) if os.path.isfile(fpath) else 0.0

        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim > threshold:
                    pairs.append((i, j, sim))

        if not pairs:
            return {"ok": True, "duplicates_found": 0, "merged_count": 0,
                    "details": [], "mode": "fallback (TF-IDF + cosine)"}

        parent = list(range(n))
        def _find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def _union(x, y):
            rx, ry = _find(x), _find(y)
            if rx != ry:
                parent[rx] = ry
        for i, j, _sim in pairs:
            _union(i, j)

        clusters = {}
        for i in range(n):
            root = _find(i)
            clusters.setdefault(root, []).append(i)

        details = []
        remove_indices = set()

        for _root_idx, members in clusters.items():
            if len(members) <= 1:
                continue
            members_sorted = sorted(members, key=lambda idx: (file_mtimes.get(idx, 0), idx))
            keep_idx = members_sorted[0]
            remove_set = set(members_sorted[1:])
            remove_indices.update(remove_set)

            keep_meta = dict(self._doc_meta[keep_idx])
            merged_titles = set()
            merged_tags = set()

            for mi in members_sorted:
                m = self._doc_meta[mi]
                if m.get("title"):
                    merged_titles.add(m["title"])
                tags = m.get("tags", [])
                if isinstance(tags, list):
                    merged_tags.update(tags)
                elif isinstance(tags, str):
                    merged_tags.add(tags)

            keep_meta["title"] = " | ".join(sorted(merged_titles)) if merged_titles else keep_meta.get("title", "")
            keep_meta["merged_from"] = [self._doc_meta[ri]["id"] for ri in remove_set]
            if merged_tags:
                keep_meta["tags"] = sorted(merged_tags)
            self._doc_meta[keep_idx] = keep_meta

            cluster_sims = [s for (a, b, s) in pairs if a in members and b in members]
            max_sim = max(cluster_sims) if cluster_sims else 0.0

            details.append({
                "kept_id": keep_meta["id"],
                "kept_file": keep_meta.get("source_file", ""),
                "merged_ids": [self._doc_meta[ri]["id"] for ri in remove_set],
                "merged_files": [self._doc_meta[ri].get("source_file", "") for ri in remove_set],
                "max_similarity": round(max_sim, 4),
            })

        if remove_indices:
            keep_indices = [i for i in range(n) if i not in remove_indices]
            self._doc_meta = [self._doc_meta[i] for i in keep_indices]
            self._doc_matrix = self._doc_matrix[keep_indices]
            self._save_fallback_index()

        return {"ok": True, "duplicates_found": len(pairs), "merged_count": len(details),
                "details": details, "mode": "fallback (TF-IDF + cosine)"}

    # -- Archive Stale ------------------------------------------

    def archive_stale(self, days: int = 180) -> Dict:
        # Detect documents not accessed in >days days, mark as 待归档.
        source_files = set()
        if self._mode == "full":
            try:
                all_data = self._collection.get(include=["metadatas"])
                for meta in all_data.get("metadatas", []):
                    src = meta.get("source_file", "")
                    if src:
                        source_files.add(src)
            except Exception as e:
                return {"ok": False, "error": str(e), "stale_count": 0,
                        "stale_files": [], "days_threshold": days,
                        "mode": "full (ChromaDB + BGE)"}
        else:
            for meta in self._doc_meta:
                src = meta.get("source_file", "")
                if src:
                    source_files.add(src)

        now = time.time()
        cutoff = now - (days * 86400)

        stale_files = []
        for src in sorted(source_files):
            fpath = os.path.join(self.kb_root, src)
            if not os.path.isfile(fpath):
                continue
            atime = os.path.getatime(fpath)
            mtime = os.path.getmtime(fpath)
            used_time = atime if atime > 0 else mtime
            if used_time < cutoff:
                stale_files.append({
                    "file": src,
                    "path": fpath,
                    "last_access": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(atime)),
                    "last_modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
                    "days_since_access": round((now - atime) / 86400, 1),
                    "status": "待归档",
                })

        mode_str = "full (ChromaDB + BGE)" if _IS_FULL_MODE else "fallback (TF-IDF + cosine)"
        return {"ok": True, "stale_count": len(stale_files), "stale_files": stale_files,
                "days_threshold": days, "mode": mode_str}

    # ── KNO-3: Document health scoring ─────────────────
    def score_documents(self, low_n=20, high_n=10):
        """Score all documents by: access_freq(30%) + freshness(25%) + completeness(25%) + relevance(20%)."""
        import os
        from datetime import datetime, timedelta

        now = datetime.now()
        scores = []

        for root, dirs, files in os.walk(self.kb_root):
            for f in files:
                if not f.endswith('.md'):
                    continue
                fpath = os.path.join(root, f)
                try:
                    stat = os.stat(fpath)
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    size = stat.st_size

                    # Access frequency: count from audit logs
                    access_count = 0
                    try:
                        audit_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audit", "audit.db")
                        if os.path.isfile(audit_db):
                            import sqlite3
                            conn = sqlite3.connect(audit_db)
                            cur = conn.cursor()
                            cur.execute("SELECT COUNT(*) FROM audit_log WHERE context LIKE ?", (f"%{f}%",))
                            row = cur.fetchone()
                            if row:
                                access_count = row[0]
                            conn.close()
                    except:
                        pass

                    access_score = min(access_count / 10.0, 1.0) * 30  # Max 30 points

                    # Freshness: days since last modified
                    days_old = (now - mtime).days
                    fresh_score = max(0, (1 - days_old / 180)) * 25  # 180 days to zero

                    # Completeness: document length
                    length_score = min(size / 2000.0, 1.0) * 25  # 2000 chars = full score

                    # Relevance: count of references from other docs (simplified: file name mentions)
                    relevance_score = 0
                    try:
                        fname = os.path.basename(f).replace('.md', '')
                        # Count how many other docs mention this file
                        ref_count = 0
                        for r2, d2, files2 in os.walk(self.kb_root):
                            for f2 in files2[:50]:  # Sample to avoid O(n^2)
                                if not f2.endswith('.md') or f2 == f:
                                    continue
                                try:
                                    with io.open(os.path.join(r2, f2), 'r', encoding='utf-8') as rf:
                                        txt = rf.read()
                                    if fname in txt:
                                        ref_count += 1
                                except:
                                    pass
                        relevance_score = min(ref_count / 5.0, 1.0) * 20
                    except:
                        pass

                    total = access_score + fresh_score + length_score + relevance_score

                    scores.append({
                        "path": fpath,
                        "name": f,
                        "total": round(total, 1),
                        "access_freq": round(access_score, 1),
                        "freshness": round(fresh_score, 1),
                        "completeness": round(length_score, 1),
                        "relevance": round(relevance_score, 1),
                        "size": size,
                        "last_modified": mtime.strftime("%Y-%m-%d"),
                    })
                except:
                    continue

        scores.sort(key=lambda x: x["total"], reverse=True)

        return {
            "total": len(scores),
            "high": scores[:high_n] if high_n else [],
            "low": scores[-low_n:] if low_n else [],
            "all": scores,
        }

    # ── KNO-4: Fuzzy completion ───────────────────────
    def fuzzy_complete(self, query, top_k=3):
        """When search returns 0 results, find similar past queries and their results."""
        import os, io as _io, glob as _glob
        from datetime import datetime, timedelta

        brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        audit_db = os.path.join(brain_dir, "audit", "audit.db")

        similar = []
        try:
            import sqlite3
            conn = sqlite3.connect(audit_db)
            cur = conn.cursor()
            cur.execute(
                "SELECT context, result, timestamp FROM audit_log WHERE action LIKE '%kb search%' ORDER BY timestamp DESC LIMIT 1000"
            )
            now = datetime.now()
            cutoff = now - timedelta(days=90)

            for row in cur.fetchall():
                ctx = (row[0] or "")[:200]
                result = (row[1] or "")[:200]
                ts_str = row[2] or ""
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts < cutoff:
                        continue
                except:
                    pass

                # Simple similarity: shared words
                q_words = set(query.lower().split())
                c_words = set(ctx.lower().split())
                if q_words and c_words:
                    overlap = len(q_words & c_words) / max(len(q_words), 1)
                    if overlap >= 0.3:
                        similar.append({
                            "query": ctx,
                            "result": result,
                            "similarity": round(overlap, 2),
                        })

            conn.close()
        except:
            pass

        # Dedup and sort
        seen = set()
        unique = []
        for s in sorted(similar, key=lambda x: x["similarity"], reverse=True):
            key = s["query"][:60]
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique[:top_k]


    # ── AI-2: Auto-tag documents ──────────────────────
    def auto_tag(self):
        """Auto-tag all documents using BGE embeddings + TF-IDF keywords."""
        import os, io as _io

        tag_set = ["流程", "规范", "教程", "FAQ", "复盘", "模板", "设计", "开发", "运营", "战略"]
        tagged = {}

        for root, dirs, files in os.walk(self.kb_root):
            for f in files:
                if not f.endswith('.md'):
                    continue
                fpath = os.path.join(root, f)
                try:
                    with _io.open(fpath, 'r', encoding='utf-8') as fh:
                        text = fh.read()[:5000]
                except:
                    continue

                # Simple keyword-based tagging
                scores = {}
                for tag in tag_set:
                    score = 0
                    # Count tag occurrences
                    score += text.count(tag)
                    # Count related keywords
                    related = {
                        "流程": ["步骤", "操作", "执行", "开始", "完成"],
                        "规范": ["规则", "标准", "必须", "不得", "要求"],
                        "教程": ["示例", "比如", "使用", "配置", "设置"],
                        "FAQ": ["问题", "回答", "常见", "怎么", "如何"],
                        "复盘": ["教训", "经验", "错误", "改进", "总结"],
                        "模板": ["格式", "模板", "示例", "占位"],
                        "设计": ["界面", "样式", "布局", "颜色", "字体"],
                        "开发": ["代码", "函数", "类", "模块", "API"],
                        "运营": ["用户", "增长", "数据", "指标", "渠道"],
                        "战略": ["目标", "方向", "规划", "路线", "长期"],
                    }
                    for rw in related.get(tag, []):
                        score += text.count(rw) * 0.5
                    scores[tag] = score

                # Top 1-3 tags
                sorted_tags = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                top_tags = [t for t, s in sorted_tags[:3] if s > 0]

                if top_tags:
                    tagged[fpath] = top_tags

        return {"total_tagged": len(tagged), "tags_found": list(tag_set), "details": {os.path.basename(k): v for k, v in list(tagged.items())[:20]}}


    # ── AI-3: Smart query recommendation ─────────────
    def recommend_next(self, query, top_k=3):
        """Recommend related queries/docs based on current query context."""
        import os, io as _io

        brain_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Strategy 1: Same-tag documents
        tag_recs = []
        try:
            # Get tags for top results
            search_results = self.search(query, top_k=5)
            if search_results:
                for r in search_results[:3]:
                    path_val = r.get("path", "") if isinstance(r, dict) else str(r)
                    if path_val and os.path.isfile(path_val):
                        try:
                            with _io.open(path_val, 'r', encoding='utf-8') as fh:
                                text = fh.read()[:3000]
                            # Extract keywords
                            words = set()
                            for w in text.split():
                                w = w.strip("，。！？、；：""''（）【】《》")
                                if len(w) >= 2 and not w.isascii():
                                    words.add(w)
                            # Search with extracted keywords
                            kw_query = " ".join(list(words)[:5])
                            if kw_query:
                                kw_results = self.search(kw_query, top_k=2)
                                tag_recs.extend(kw_results if isinstance(kw_results, list) else [])
                        except:
                            pass
        except:
            pass

        # Strategy 2: From audit logs (queries that followed similar queries)
        audit_recs = []
        try:
            audit_db = os.path.join(brain_dir, "audit", "audit.db")
            if os.path.isfile(audit_db):
                import sqlite3
                conn = sqlite3.connect(audit_db)
                cur = conn.cursor()
                cur.execute(
                    "SELECT context FROM audit_log WHERE action LIKE '%kb search%' ORDER BY timestamp DESC LIMIT 500"
                )
                rows = cur.fetchall()
                conn.close()

                q_words = set(query.lower().split())
                for row in rows:
                    ctx = (row[0] or "").lower()[:100]
                    c_words = set(ctx.split())
                    if q_words and c_words:
                        overlap = len(q_words & c_words) / max(len(q_words), 1)
                        if overlap >= 0.4:
                            audit_recs.append({"path": ctx, "score": round(overlap, 2), "source": "audit"})
        except:
            pass

        # Merge and dedup
        all_recs = []
        seen = set()
        for r in tag_recs[:5] + audit_recs[:5]:
            key = str(r.get("path", ""))[:80] if isinstance(r, dict) else str(r)[:80]
            if key and key not in seen:
                seen.add(key)
                all_recs.append(r)

        return all_recs[:top_k]

