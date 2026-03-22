# -*- coding: utf-8 -*-
import os
import sys
import time
import pickle
import hashlib
import math
from pathlib import Path
from langchain_core.documents import Document

# ✅ REDIRECT ALL PATHS TO E DRIVE (C-drive protection)
os.environ['TEMP'] = r'E:\temp'
os.environ['TMP'] = r'E:\temp'
os.environ['TMPDIR'] = r'E:\temp'
os.environ['PIP_CACHE_DIR'] = r'E:\.cache\pip'
os.environ['HUGGINGFACE_HUB_CACHE'] = r'E:\.cache\huggingface'
os.environ['HF_HOME'] = r'E:\.cache\huggingface'
os.environ['TORCH_HOME'] = r'E:\.cache\torch'
os.environ['TRANSFORMERS_CACHE'] = r'E:\.cache\transformers'
os.environ['KERAS_HOME'] = r'E:\.cache\keras'
os.environ['MPLCONFIGDIR'] = r'E:\.cache\matplotlib'
os.environ['NLTK_DATA'] = r'E:\.cache\nltk_data'
os.makedirs(r'E:\temp', exist_ok=True)
os.makedirs(r'E:\.cache\huggingface', exist_ok=True)

from langchain_community.vectorstores import FAISS
from config import FAISS_PATH

# Attempt to import huggingface wrapper; fall back to direct sentence-transformers
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except Exception as e:
    HuggingFaceEmbeddings = None
    print(f"[WARN] langchain_huggingface import failed: {e}, falling back to plain sentence-transformers")

# Fix Windows console encoding
if sys.platform == "win32":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')


class VectorDBManager:

    def __init__(self, persist_directory=None):
        self.persist_directory = persist_directory or FAISS_PATH
        self.index_health = {
            "exists": False,
            "faiss_file": "",
            "pkl_file": "",
            "vector_count": 0,
            "id_map_count": 0,
            "docstore_count": 0,
            "balanced": False,
        }
        os.environ.setdefault("HF_HUB_DISABLE_HTTPX", "1")

        class HashEmbeddings:
            def __init__(self, dim=384):
                self.dim = dim

            def _embed(self, text):
                vec = [0.0] * self.dim
                tokens = [t for t in (text or "").lower().split() if t]
                if not tokens:
                    return vec
                for tok in tokens:
                    digest = hashlib.md5(tok.encode("utf-8")).digest()
                    idx = int.from_bytes(digest[:4], "little") % self.dim
                    sign = 1.0 if (digest[4] & 1) == 0 else -1.0
                    vec[idx] += sign
                norm = math.sqrt(sum(v * v for v in vec))
                if norm > 0:
                    vec = [v / norm for v in vec]
                return vec

            def embed_documents(self, texts):
                return [self._embed(t) for t in texts]

            def embed_query(self, text):
                return self._embed(text)

            def __call__(self, text):
                return self.embed_query(text)

        # choose embedding engine
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

        try:
            from sentence_transformers import SentenceTransformer

            class SimpleWrapper:
                def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2", local_files_only=False):
                    self.model = SentenceTransformer(model_name, local_files_only=local_files_only)

                def embed_documents(self, texts):
                    vectors = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=False)
                    return vectors.tolist() if hasattr(vectors, "tolist") else [list(v) for v in vectors]

                def embed_query(self, text):
                    vector = self.model.encode([text], show_progress_bar=False, convert_to_numpy=False)[0]
                    return vector.tolist() if hasattr(vector, "tolist") else list(vector)

                def __call__(self, text):
                    return self.embed_query(text)

            # First try local cache only.
            self.embeddings = SimpleWrapper(model_name=model_name, local_files_only=True)
        except Exception as local_err:
            print(f"[WARN] Local embedding model unavailable ({model_name}): {local_err}")
            if HuggingFaceEmbeddings is not None:
                try:
                    self.embeddings = HuggingFaceEmbeddings(model_name=model_name)
                except Exception as hf_err:
                    print(f"[WARN] HuggingFaceEmbeddings init failed: {hf_err}")
                    try:
                        self.embeddings = SimpleWrapper(model_name=model_name, local_files_only=False)
                    except Exception as st_err:
                        print(f"[WARN] SentenceTransformer online init failed: {st_err}")
                        print("[WARN] Falling back to deterministic hash embeddings (offline mode).")
                        self.embeddings = HashEmbeddings(dim=384)
            else:
                print("[WARN] Falling back to deterministic hash embeddings (offline mode).")
                self.embeddings = HashEmbeddings(dim=384)
        self.db = None
        self._load_db()

    def _index_files(self):
        base = Path(self.persist_directory)
        return base / "index.faiss", base / "index.pkl"

    def _refresh_index_health(self):
        faiss_file, pkl_file = self._index_files()
        health = {
            "exists": bool(faiss_file.exists() and pkl_file.exists()),
            "faiss_file": str(faiss_file),
            "pkl_file": str(pkl_file),
            "vector_count": 0,
            "id_map_count": 0,
            "docstore_count": 0,
            "balanced": False,
        }

        db = getattr(self, "db", None)
        if db is not None:
            try:
                health["vector_count"] = int(getattr(db.index, "ntotal", 0) or 0)
            except Exception:
                health["vector_count"] = 0

            try:
                id_map = getattr(db, "index_to_docstore_id", {}) or {}
                health["id_map_count"] = len(id_map)
            except Exception:
                health["id_map_count"] = 0

            try:
                docstore_dict = getattr(getattr(db, "docstore", None), "_dict", {}) or {}
                health["docstore_count"] = len(docstore_dict)
            except Exception:
                health["docstore_count"] = 0

            vc = health["vector_count"]
            ic = health["id_map_count"]
            dc = health["docstore_count"]
            health["balanced"] = vc > 0 and vc == ic == dc

        self.index_health = health
        return health

    def _repair_index_balance(self):
        """Repair metadata gaps when FAISS vectors outnumber id/docstore entries."""
        db = getattr(self, "db", None)
        if db is None:
            return False

        health = self._refresh_index_health()
        if health.get("balanced"):
            return True

        vectors = int(health.get("vector_count", 0) or 0)
        if vectors <= 0:
            return False

        id_map = getattr(db, "index_to_docstore_id", None)
        docstore = getattr(getattr(db, "docstore", None), "_dict", None)
        if not isinstance(id_map, dict) or not isinstance(docstore, dict):
            return False

        for i in range(vectors):
            doc_id = id_map.get(i)
            if not doc_id:
                doc_id = f"recovered_{i}"
                id_map[i] = doc_id
            if doc_id not in docstore:
                docstore[doc_id] = Document(
                    page_content="[Recovered metadata placeholder]",
                    metadata={
                        "recovered": True,
                        "recovered_from": "index.faiss",
                        "vector_position": i,
                    },
                )

        try:
            self.db.save_local(self.persist_directory)
            repaired = self._refresh_index_health()
            return bool(repaired.get("balanced"))
        except Exception as e:
            print(f"[WARN] Auto-repair save failed: {e}")
            return False

    def is_index_ready(self) -> bool:
        health = self._refresh_index_health()
        return bool(health.get("exists") and health.get("balanced"))
    # --------------------------------------------------
    # LOAD DB
    # --------------------------------------------------
    def _load_db(self):
        if os.path.exists(self.persist_directory):
            last_error = None
            for attempt in range(1, 7):
                try:
                    self.db = FAISS.load_local(
                        self.persist_directory,
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                    health = self._refresh_index_health()
                    if not health.get("exists"):
                        raise RuntimeError("Missing index.faiss or index.pkl in FAISS directory")
                    if not health.get("balanced"):
                        print(
                            "[WARN] FAISS index mismatch detected: "
                            f"vectors={health.get('vector_count')} "
                            f"id_map={health.get('id_map_count')} "
                            f"docstore={health.get('docstore_count')}"
                        )
                        repaired = self._repair_index_balance()
                        if repaired:
                            print("[OK] FAISS metadata auto-repair completed")
                        else:
                            print("[WARN] FAISS metadata remains unbalanced; strict quality gate may block answers")
                    print("[OK] FAISS loaded (index.faiss + index.pkl validated)")
                    return
                except (pickle.UnpicklingError, EOFError) as e:
                    last_error = e
                    print(f"[WARN] FAISS metadata read interrupted (attempt {attempt}/6), retrying...")
                    time.sleep(1.0)
                except Exception as e:
                    last_error = e
                    print(f"[WARN] FAISS load validation failed (attempt {attempt}/6): {e}")
                    time.sleep(1.0)
            raise RuntimeError(f"Unable to load FAISS metadata after retries: {last_error}")
        else:
            print("[WARN] No FAISS index found - will create new")
            self._refresh_index_health()

    # --------------------------------------------------
    # ⭐⭐⭐ THIS WAS MISSING ⭐⭐⭐
    # --------------------------------------------------
    def add_documents(self, documents):
        """Add documents to FAISS (create if not exists)"""

        if not documents:
            return

        # 🆕 First time create
        if self.db is None:
            print("[NEW] Creating new FAISS index...")
            self.db = FAISS.from_documents(documents, self.embeddings)

        # ➕ Incremental add
        else:
            print(f"[ADD] Adding {len(documents)} chunks to FAISS...")
            self.db.add_documents(documents)

        # 💾 Always save
        self.db.save_local(self.persist_directory)
        self._refresh_index_health()
        print("[SAVE] FAISS saved")

    # --------------------------------------------------
    # SEARCH
    # --------------------------------------------------
    def similarity_search(self, query):
        """Helper for interactive debugging: returns best document & score."""
        if not self.db:
            return None, 999

        docs = self.db.similarity_search_with_score(query, k=1)

        if not docs:
            return None, 999

        doc, score = docs[0]
        return doc.page_content, score

    def debug_search(self, query, k=5):
        """Return top-k documents with scores for investigation."""
        if not self.db:
            return []
        return self.db.similarity_search_with_score(query, k=k)


    # --------------------------------------------------
    # IMAGE EMBEDDING (NEW - MULTIMODAL EXTENSION)
    # --------------------------------------------------
    def upsert_image_embedding(self, clip_embedding: list, metadata: dict):
        """
        Add image to FAISS for hybrid search (text index + image metadata).
        
        For now, we store images as documents with URL text and metadata.
        The CLIP embedding is stored in metadata for future vector comparison.
        
        Args:
            clip_embedding: Pre-computed CLIP image embedding (stored in metadata)
            metadata: Dict with 'source_url' and 'content_type': 'image'
        """
        if not metadata:
            return
        
        try:
            from langchain_core.documents import Document
            
            # Store CLIP embedding in metadata for future use
            metadata_with_embedding = {
                **metadata,
                "clip_embedding": clip_embedding  # Store raw for potential future multimodal search
            }

            title = str(metadata.get("title") or "").strip()
            description = str(metadata.get("description") or "").strip()
            tags = metadata.get("tags") or []
            if isinstance(tags, list):
                tags_text = " ".join(str(t).strip() for t in tags if str(t).strip())
            else:
                tags_text = str(tags).strip()
            search_text = str(metadata.get("search_text") or "").strip()
            source_url = str(metadata.get("source_url") or "unknown").strip()

            # Build richer searchable text so image prompts can match semantic intent.
            page_content = (
                f"[Image] {title}\n"
                f"Description: {description}\n"
                f"Tags: {tags_text}\n"
                f"SearchText: {search_text}\n"
                f"SourceURL: {source_url}"
            )

            doc = Document(
                page_content=page_content,
                metadata=metadata_with_embedding
            )
            
            # Add to FAISS (will be indexed by text embedding of URL)
            self.add_documents([doc])
            
        except Exception as e:
            print(f"[ERROR] Image metadata upsert failed: {e}")

    # --------------------------------------------------
    # PERSIST
    # --------------------------------------------------
    def persist(self):
        """Explicitly persist FAISS to disk."""
        if self.db is not None:
            self.db.save_local(self.persist_directory)
            self._refresh_index_health()
            print("[SAVE] FAISS persisted")

    def count(self):
        """Return number of vectors / documents in the index."""
        if self.db is None:
            return 0
        try:
            return self.db.index.ntotal
        except Exception:
            # FAISS stores number differently
            return len(self.db.docstore._dict)

    def clear(self):
        """Remove existing index (for re-indexing)."""
        if os.path.exists(self.persist_directory):
            import shutil
            shutil.rmtree(self.persist_directory)
            print(f"[CLEAR] Removed FAISS directory {self.persist_directory}")
        self.db = None


    # --------------------------------------------------
    # REFRESH
    # --------------------------------------------------
    def refresh(self):
        self._load_db()


# --------------------------------------------------
# GLOBAL HELPER (used by ingestion)
# --------------------------------------------------
_vectordb = None


def _get_vectordb():
    global _vectordb
    if _vectordb is None:
        _vectordb = VectorDBManager()
    return _vectordb


def upsert_documents(documents):
    """Used by ingest pipeline"""
    _get_vectordb().add_documents(documents)