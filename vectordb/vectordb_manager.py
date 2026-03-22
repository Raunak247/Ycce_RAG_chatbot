# -*- coding: utf-8 -*-
import os
import sys

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
        # choose embedding engine
        if HuggingFaceEmbeddings is not None:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        else:
            # fallback wrapper copied from faiss_stores
            from sentence_transformers import SentenceTransformer
            class SimpleWrapper:
                def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
                    self.model = SentenceTransformer(model_name)
                def embed_documents(self, texts):
                    return self.model.encode(texts, show_progress_bar=False, convert_to_numpy=False).tolist()
                def embed_query(self, text):
                    return self.model.encode([text], show_progress_bar=False, convert_to_numpy=False)[0].tolist()
            self.embeddings = SimpleWrapper()
        self.db = None
        self._load_db()
    # --------------------------------------------------
    # LOAD DB
    # --------------------------------------------------
    def _load_db(self):
        if os.path.exists(self.persist_directory):
            self.db = FAISS.load_local(
                self.persist_directory,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            print("[OK] FAISS loaded")
        else:
            print("[WARN] No FAISS index found - will create new")

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
            
            # Create document: use URL as searchable text content
            doc = Document(
                page_content=f"[Image] {metadata.get('source_url', 'unknown')}",
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
_vectordb = VectorDBManager()


def upsert_documents(documents):
    """Used by ingest pipeline"""
    _vectordb.add_documents(documents)