import os
import pickle
import shutil
import hashlib
import math
import time
import uuid
import threading
from contextlib import contextmanager
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from config import FAISS_PATH

try:
    from langchain.embeddings import HuggingFaceEmbeddings
except Exception:
    HuggingFaceEmbeddings = None


class HashEmbeddings(Embeddings):
    """Deterministic offline-only fallback with stable vector dimension."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _tokenize(self, text: str) -> List[str]:
        return [tok for tok in (text or "").lower().split() if tok]

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = self._tokenize(text)
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

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def __call__(self, text: str) -> List[float]:
        return self.embed_query(text)


class SentenceTransformerWrapper(Embeddings):
    """Minimal wrapper providing `embed_documents` and `embed_query` using
    `sentence_transformers.SentenceTransformer` so FAISS can use it in place
    of LangChain's HuggingFaceEmbeddings.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", local_files_only: bool = False):
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise ImportError(
                "sentence-transformers is required for the fallback embeddings. "
                "Install it with `pip install sentence-transformers`"
            ) from e
        self.model = SentenceTransformer(model_name, local_files_only=local_files_only)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=False)
        if hasattr(vectors, "tolist"):
            return vectors.tolist()
        return [list(v) for v in vectors]

    def embed_query(self, text: str) -> List[float]:
        vector = self.model.encode([text], show_progress_bar=False, convert_to_numpy=False)[0]
        if hasattr(vector, "tolist"):
            return vector.tolist()
        return list(vector)

    def __call__(self, text: str) -> List[float]:
        # Compatibility with call-sites expecting a callable embedding function.
        return self.embed_query(text)


class EmbeddingsAdapter(Embeddings):
    """Wrap legacy embedding providers as a LangChain Embeddings object."""

    def __init__(self, inner):
        self.inner = inner

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.inner.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.inner.embed_query(text)


def _ensure_embeddings_object(obj):
    if isinstance(obj, Embeddings):
        return obj
    if hasattr(obj, "embed_documents") and hasattr(obj, "embed_query"):
        return EmbeddingsAdapter(obj)
    raise TypeError(f"Unsupported embeddings provider type: {type(obj).__name__}")


def _build_embeddings():
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    os.environ.setdefault("HF_HUB_DISABLE_HTTPX", "1")

    # 1) Prefer already-cached local model so startup does not depend on internet.
    try:
        return _ensure_embeddings_object(SentenceTransformerWrapper(model_name, local_files_only=True))
    except Exception as e:
        print(f"[WARN] Local embedding model unavailable ({model_name}): {e}")

    # 2) Try normal HuggingFace pipeline (may download when internet is available).
    if HuggingFaceEmbeddings is not None:
        try:
            return _ensure_embeddings_object(HuggingFaceEmbeddings(model_name=model_name))
        except Exception as e:
            print(f"[WARN] HuggingFaceEmbeddings initialization failed: {e}")

    # 3) Try sentence-transformers with downloads enabled.
    try:
        return _ensure_embeddings_object(SentenceTransformerWrapper(model_name, local_files_only=False))
    except Exception as e:
        print(f"[WARN] SentenceTransformer online initialization failed: {e}")

    # 4) Final offline fallback that keeps crawl/ingestion operational.
    print("[WARN] Falling back to deterministic hash embeddings (offline mode).")
    return _ensure_embeddings_object(HashEmbeddings(dim=384))


embeddings = _build_embeddings()


class ResilientInMemoryDocstore(InMemoryDocstore):
    """Docstore that returns placeholder documents for recovered legacy IDs."""

    def search(self, search: str):
        doc = super().search(search)
        if isinstance(doc, str):
            return Document(
                id=search,
                page_content="[Recovered legacy document]",
                metadata={"recovered": True, "doc_id": search},
            )
        return doc


_db_cache = None
_save_lock = threading.Lock()
_existing_doc_keys = None


def _faiss_file(path: str) -> str:
    return os.path.join(path, "index.faiss")


def _pkl_file(path: str) -> str:
    return os.path.join(path, "index.pkl")


def _replace_with_retry(src: str, dst: str, attempts: int = 30, delay: float = 0.2):
    last_error = None
    for _ in range(attempts):
        try:
            os.replace(src, dst)
            return
        except (PermissionError, FileNotFoundError, OSError) as e:
            last_error = e
            time.sleep(delay)
    raise last_error if last_error else RuntimeError(f"Failed to replace {src} -> {dst}")


def _copy_with_retry(src: str, dst: str, attempts: int = 20, delay: float = 0.15):
    last_error = None
    for _ in range(attempts):
        try:
            shutil.copy2(src, dst)
            return
        except (PermissionError, OSError) as e:
            last_error = e
            time.sleep(delay)
    raise last_error if last_error else RuntimeError(f"Failed to backup {src} -> {dst}")


@contextmanager
def _cross_process_lock(path: str, timeout_sec: int = 180):
    """Best-effort process lock to serialize FAISS writes on Windows."""
    lock_path = os.path.join(path, ".faiss_write.lock")
    os.makedirs(path, exist_ok=True)

    if os.name != "nt":
        # Non-Windows path: keep thread-level lock only.
        yield
        return

    import msvcrt

    start = time.time()
    lock_file = open(lock_path, "a+b")
    try:
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)

        while True:
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.time() - start >= timeout_sec:
                    raise TimeoutError(f"Timed out acquiring FAISS write lock: {lock_path}")
                time.sleep(0.2)

        yield
    finally:
        try:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        lock_file.close()


def _load_from_files(faiss_file: str, pkl_file: str):
    import faiss

    index = faiss.read_index(faiss_file)
    with open(pkl_file, "rb") as f:
        docstore, index_to_docstore_id = pickle.load(f)
    return FAISS(embeddings, index, docstore, index_to_docstore_id)


def _recover_from_faiss_only(path: str):
    import faiss

    index = faiss.read_index(_faiss_file(path))
    ntotal = int(index.ntotal)
    # Build a full mapping so existing vectors remain addressable after recovery.
    index_to_docstore_id = {i: f"legacy_{i}" for i in range(ntotal)}
    docstore = ResilientInMemoryDocstore()
    print(f"[WARN] Recovered FAISS from index.faiss only; preserved {ntotal} vectors")
    return FAISS(embeddings, index, docstore, index_to_docstore_id)


def _load_db_resilient(path: str):
    faiss_main = _faiss_file(path)
    pkl_main = _pkl_file(path)

    try:
        return FAISS.load_local(
            path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
    except Exception as e:
        print(f"[WARN] Primary FAISS metadata load failed: {e}")

    faiss_bak = faiss_main + ".bak"
    pkl_bak = pkl_main + ".bak"
    if os.path.exists(faiss_bak) and os.path.exists(pkl_bak):
        try:
            print("[INFO] Attempting FAISS metadata recovery from .bak files")
            return _load_from_files(faiss_bak, pkl_bak)
        except Exception as e:
            print(f"[WARN] Backup recovery failed: {e}")

    if os.path.exists(faiss_main):
        return _recover_from_faiss_only(path)

    return None


def _safe_save_local(db: FAISS, path: str):
    import faiss

    os.makedirs(path, exist_ok=True)
    faiss_main = _faiss_file(path)
    pkl_main = _pkl_file(path)

    with _save_lock:
        with _cross_process_lock(path):
            # Keep latest backups before any write attempt.
            if os.path.exists(faiss_main):
                _copy_with_retry(faiss_main, faiss_main + ".bak")
            if os.path.exists(pkl_main):
                _copy_with_retry(pkl_main, pkl_main + ".bak")

            token = f"{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex}"
            tmp_faiss = faiss_main + f".{token}.tmp"
            tmp_pkl = pkl_main + f".{token}.tmp"

            try:
                faiss.write_index(db.index, tmp_faiss)
                if not os.path.exists(tmp_faiss):
                    raise FileNotFoundError(f"Temporary FAISS file was not created: {tmp_faiss}")

                with open(tmp_pkl, "wb") as f:
                    pickle.dump((db.docstore, db.index_to_docstore_id), f)
                    f.flush()
                    os.fsync(f.fileno())

                if not os.path.exists(tmp_pkl):
                    raise FileNotFoundError(f"Temporary metadata file was not created: {tmp_pkl}")

                _replace_with_retry(tmp_faiss, faiss_main)
                _replace_with_retry(tmp_pkl, pkl_main)
            finally:
                # Clean up orphan temp files when a write fails mid-way.
                if os.path.exists(tmp_faiss):
                    try:
                        os.remove(tmp_faiss)
                    except OSError:
                        pass
                if os.path.exists(tmp_pkl):
                    try:
                        os.remove(tmp_pkl)
                    except OSError:
                        pass


def _get_or_create_db(documents):
    global _db_cache

    if _db_cache is not None:
        return _db_cache, False

    if os.path.exists(FAISS_PATH):
        db = _load_db_resilient(FAISS_PATH)
        if db is not None:
            _db_cache = db
            return _db_cache, False

    _db_cache = FAISS.from_documents(documents, embeddings)
    return _db_cache, True


def _normalize_meta_value(value: str) -> str:
    return (value or "").strip().lower()


def _build_doc_key_from_parts(source_url: str, local_path: str, chunk_id: str, content_hash: str) -> str:
    src = _normalize_meta_value(source_url)
    lpath = _normalize_meta_value(local_path)
    cid = _normalize_meta_value(chunk_id)
    chash = _normalize_meta_value(content_hash)
    return f"{src}|{lpath}|{cid}|{chash}"


def _build_doc_key(doc) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    source_url = metadata.get("source_url") or metadata.get("source") or ""
    local_path = metadata.get("local_path") or ""
    chunk_id = metadata.get("chunk_id") or ""
    content = getattr(doc, "page_content", "") or ""
    content_hash = hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest() if content else ""
    return _build_doc_key_from_parts(source_url, local_path, chunk_id, content_hash)


def _ensure_existing_doc_keys(db: FAISS):
    global _existing_doc_keys
    if _existing_doc_keys is not None:
        return _existing_doc_keys

    keys = set()
    docstore_dict = getattr(getattr(db, "docstore", None), "_dict", {}) or {}
    for doc in docstore_dict.values():
        try:
            keys.add(_build_doc_key(doc))
        except Exception:
            continue

    _existing_doc_keys = keys
    print(f"[DEDUPE] Loaded {len(_existing_doc_keys)} existing document keys from FAISS docstore")
    return _existing_doc_keys


def _filter_new_documents(db: FAISS, documents):
    existing_keys = _ensure_existing_doc_keys(db)
    unique = []
    skipped = 0

    for doc in documents:
        try:
            key = _build_doc_key(doc)
        except Exception:
            unique.append(doc)
            continue

        if key in existing_keys:
            skipped += 1
            continue

        existing_keys.add(key)
        unique.append(doc)

    return unique, skipped


def upsert_documents(documents):
    if not documents:
        return

    db, created_with_initial_docs = _get_or_create_db(documents)
    if created_with_initial_docs:
        # Newly created from_documents already contains the initial documents.
        _ensure_existing_doc_keys(db)
        _safe_save_local(db, FAISS_PATH)
        return

    new_docs, skipped_duplicates = _filter_new_documents(db, documents)
    if skipped_duplicates:
        print(f"[DEDUPE] Skipped {skipped_duplicates} duplicate chunks before FAISS upsert")

    if not new_docs:
        print("[DEDUPE] All candidate chunks already exist in FAISS; skipping write")
        return

    db.add_documents(new_docs)
    _safe_save_local(db, FAISS_PATH)