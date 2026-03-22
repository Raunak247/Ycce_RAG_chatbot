"""
rebuild_faiss.py — Rebuild a clean FAISS index from all real documents in index.pkl.

WHY: The current FAISS index has 906,403 vectors but the docstore only has 539,197
real documents.  The other ~367,206 "zombie" vectors have no content, waste search
slots, and dilute retrieval quality.

WHAT THIS SCRIPT DOES:
1. Loads all 539,197 real Document objects from data/faiss_index/index.pkl
2. Re-embeds them in batches using sentence-transformers/all-MiniLM-L6-v2
3. Saves a brand-new clean FAISS index to data/faiss_index/
4. Backs up the old index first

Expected runtime: 30-90 minutes depending on hardware.
Progress is printed every 500 documents.

Usage (from YCCE_Chatbot folder):
    d:/ycce_chatbot/.venv/Scripts/python.exe rebuild_faiss.py
"""

import os, sys, pickle, shutil, time

# ── path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Redirect caches to E drive (keep C drive free)
for var, path in [
    ("TEMP", r"E:\temp"), ("TMP", r"E:\temp"),
    ("HF_HOME", r"E:\.cache\huggingface"),
    ("HUGGINGFACE_HUB_CACHE", r"E:\.cache\huggingface"),
    ("TRANSFORMERS_CACHE", r"E:\.cache\transformers"),
]:
    os.environ[var] = path
    os.makedirs(path, exist_ok=True)

os.environ.setdefault("HF_HUB_DISABLE_HTTPX", "1")

FAISS_DIR = os.path.join("data", "faiss_index")
PKL_FILE  = os.path.join(FAISS_DIR, "index.pkl")
IDX_FILE  = os.path.join(FAISS_DIR, "index.faiss")
BATCH_SIZE = 512

# ── load real docs from PKL ──────────────────────────────────────────────────
print("Loading index.pkl …")
t0 = time.time()
with open(PKL_FILE, "rb") as f:
    docstore, id_map = pickle.load(f)

real_dict = docstore._dict if hasattr(docstore, "_dict") else {}
real_uuids = set(real_dict.keys())

# Build ordered list: only vectors whose uuid is in real_dict
ordered_docs = []
for int_idx in sorted(id_map.keys()):
    uuid = id_map[int_idx]
    if uuid in real_dict:
        ordered_docs.append(real_dict[uuid])

print(f"  Total vectors in old index : {len(id_map):,}")
print(f"  Real documents in docstore : {len(real_dict):,}")
print(f"  Zombie vectors (skipped)   : {len(id_map) - len(real_dict):,}")
print(f"  Docs to re-embed           : {len(ordered_docs):,}")
print(f"  Loaded in {time.time()-t0:.1f}s")

# ── load embedding model ─────────────────────────────────────────────────────
print("\nLoading embedding model …")
model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name, local_files_only=True)
    print(f"  Using cached model: {model_name}")
except Exception as e:
    print(f"  Local cache miss ({e}), downloading …")
    model = SentenceTransformer(model_name, local_files_only=False)
    print(f"  Downloaded: {model_name}")

# ── build new FAISS index ────────────────────────────────────────────────────
import faiss, numpy as np
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore

DIM = 384
new_index = faiss.IndexFlatIP(DIM)   # Inner-product on L2-normalised vectors ≡ cosine similarity

new_id_map     = {}
new_docstore   = {}
total = len(ordered_docs)

print(f"\nEmbedding {total:,} documents in batches of {BATCH_SIZE} …")
t1 = time.time()

for start in range(0, total, BATCH_SIZE):
    batch_docs = ordered_docs[start : start + BATCH_SIZE]
    texts = [d.page_content for d in batch_docs]

    vecs = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False,
                        normalize_embeddings=True, convert_to_numpy=True)
    vecs = vecs.astype("float32")

    base = new_index.ntotal
    new_index.add(vecs)

    for i, doc in enumerate(batch_docs):
        import uuid as _uuid
        uid = str(_uuid.uuid4())
        new_id_map[base + i] = uid
        new_docstore[uid] = doc

    if (start // BATCH_SIZE) % 10 == 0 or start + BATCH_SIZE >= total:
        done = min(start + BATCH_SIZE, total)
        elapsed = time.time() - t1
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        print(f"  [{done:>7,}/{total:,}]  {elapsed/60:.1f}min elapsed  ETA {eta/60:.0f}min")

print(f"\nEmbedding complete in {(time.time()-t1)/60:.1f} min")
print(f"New index has {new_index.ntotal:,} vectors (dim={new_index.d})")

# ── backup old files ─────────────────────────────────────────────────────────
bak_dir = FAISS_DIR + "_backup_" + time.strftime("%Y%m%d_%H%M%S")
print(f"\nBacking up old index to {bak_dir} …")
shutil.copytree(FAISS_DIR, bak_dir)
print("  Backup done.")

# ── save new index ────────────────────────────────────────────────────────────
print("Saving new FAISS index …")
faiss.write_index(new_index, IDX_FILE)

from langchain_community.docstore.in_memory import InMemoryDocstore
ds = InMemoryDocstore(new_docstore)

with open(PKL_FILE, "wb") as f:
    pickle.dump((ds, new_id_map), f)

print("  Saved index.faiss and index.pkl")
print(f"\n✅  Rebuild complete!  Clean vectors: {new_index.ntotal:,}  (was 906,403)")
print("Restart the chatbot server to use the new index.")
