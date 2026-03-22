# 🚀 YCCE MULTIMODAL RAG - EXECUTION GUIDE

## ✅ System Status: **PRODUCTION READY**

---

## Quick Start

### 1️⃣  Run Full Pipeline (Production)
```bash
cd e:\YCCE_RAG
python main_initial_crawl.py
```

**What happens:**
- STEP 1: BFS crawl (discovers URLs) - ~5-10 min
- STEP 2: Change detection (identifies new content) - ~1-2 min  
- STEP 3: Ingestion
  - Text processing: PDFs, HTML, Excel → FAISS - ~90-120 min
  - Image processing: CLIP embeddings → FAISS - ~3-5 min
- **Total time: ~2 hours for 27,890 URLs**

### 2️⃣  Test Multimodal Features (Quick Verification)
```bash
python test_multimodal.py
```

**Takes:** ~60 seconds  
**Output:** Validates CLIP + FAISS integration

### 3️⃣  Validate System (Pre-deployment Check)
```bash
python validate_system.py
```

**Checks:**
- ✓ File structure
- ✓ All imports available
- ✓ Data directory setup
- ✓ FAISS index (if exists)
- ✓ Multimodal components

---

## 📊 What Gets Created

After running the full pipeline:

```
data/
├── discovered_urls.json      (27,890 URLs discovered by crawler)
├── url_registry.json         (Change detection registry)
├── pipeline_progress.json    (Execution state - allows resume)
├── ingested_urls.json        (Deduplication tracking)
├── media_registry.json       (Image URLs for chatbot)
└── faiss_index/              (Multimodal FAISS store)
    ├── index.faiss           (Vector index - ~500MB)
    ├── index.pkl             (Metadata store)
    └── docstore.pkl          (Document content cache)
```

---

## 🎮 Control & Monitoring

### Monitor Progress
```powershell
# Watch progress in real-time
Get-Content data\pipeline_progress.json -Wait | ConvertFrom-Json

# Check ingestion stats
$progress = Get-Content data\pipeline_progress.json | ConvertFrom-Json
$progress | Select-Object *
```

**Example output:**
```json
{
  "crawl_done": true,
  "change_detection_done": true,
  "ingestion_done": false
}
```

### Resume Interrupted Pipeline
If the pipeline is interrupted (e.g., power loss):
1. **Run again** - will skip completed steps
2. **No data loss** - progress is tracked
3. **Automatic resume** - continues from where it left off

### Force Fresh Start
```powershell
# Remove progress marker to restart all steps
Remove-Item data\pipeline_progress.json
python main_initial_crawl.py  # Starts from STEP 1
```

---

## 🔍 Use FAISS Index (Programmatic Access)

### From Python
```python
from vectordb.vectordb_manager import VectorDBManager
import os

# Load existing FAISS
db = VectorDBManager(persist_directory=os.path.join("data", "faiss_index"))

# Search for similar content
query = "What are the CSE curriculum requirements?"
doc_content, score = db.similarity_search(query)

print(f"Best match: {doc_content[:100]}...")
print(f"Similarity score: {score:.4f}")
```

### From Chatbot/API
```python
# For Streamlit chatbot
import streamlit as st
from vectordb.vectordb_manager import VectorDBManager

db = VectorDBManager(persist_directory="data/faiss_index")

# Get user query
user_q = st.text_input("Ask about YCCE...")

if user_q:
    # Search FAISS
    result, score = db.similarity_search(user_q)
    
    # Check if result references images
    if score > 0.7:  # High confidence
        st.write(result)
        
        # Load media registry for image URLs
        import json
        media_reg = json.load(open("data/media_registry.json"))
        if media_reg:
            st.write("📸 Related media available:")
            for media in media_reg[:3]:
                st.image(media["source_url"])
```

---

## ⚙️ Configuration

### Modify Pipeline Behavior

Edit `main_initial_crawl.py`:

```python
# Line ~155: Adjust image timeout
embed_image_from_url(url, retries=3)  # More retries for slow connections

# Line ~160: Batch processing size
# (Future enhancement with ThreadPoolExecutor)
batch_size = 32  # Process 32 images in parallel
```

### Environment Setup

```powershell
# Optional: Set HF_TOKEN for faster downloads
$env:HF_TOKEN = "your-huggingface-token"

# Run pipeline with token set
python main_initial_crawl.py
```

---

## 🐛 Troubleshooting

### Issue: "FAISS index not found"
**Solution:** This is normal on first run. The index is created during STEP 3.

### Issue: "Out of memory" error
**Symptoms:** Process crashes during STEP 3  
**Solution:**
1. FAISS loading: Reduce `batch_size` from 32 to 8
2. CLIP loading: Run with fewer images (~50 at a time)
3. Upgrade RAM: System needs ~2GB for full pipeline

### Issue: Network timeouts (images fail to embed)
**Symptoms:** `[RETRY]` messages, then `[FAILED]`  
**Solution:**
1. Check internet connection
2. Increase timeout: Edit `image_embeddings.py` line 48 → `timeout=30`
3. Skip images: They're optional, pipeline continues

### Issue: PDF parsing errors
**Symptoms:** "invalid pdf header" messages  
**Solution:** These are non-critical warnings. Pipeline continues ingesting valid PDFs.

---

## 📈 Performance Tips

### Optimize for Speed
1. **Parallel processing** (future): Enable ThreadPoolExecutor in image loop
2. **Batch CLIP**: Process 32 images together instead of 1-by-1
3. **GPU support**: Install `torch` with CUDA for 10x faster embeddings

### Optimize for Memory
1. **Streaming ingestion**: Load 100 URLs at a time (vs. all)
2. **Smaller models**: Use `all-MiniLM-L6-v2` (already doing this - lightweight!)
3. **FAISS sharding**: Split index into multiple indices for 50k+ URLs

---

## 🎯 Next: Chatbot Integration

Once FAISS index is ready:

### 1. Deploy with Streamlit
```bash
streamlit run chatbot/streamlit_app.py
```

### 2. API Integration
```python
# FastAPI endpoint example
from fastapi import FastAPI

app = FastAPI()
db = VectorDBManager(persist_directory="data/faiss_index")

@app.post("/search")
def search(query: str):
    result, score = db.similarity_search(query)
    return {"answer": result, "confidence": score}
```

### 3. Enable Image Retrieval
```python
# In chatbot response
import json

# Load media registry
with open("data/media_registry.json") as f:
    media = json.load(f)

# Return text + image URLs
return {
    "text_answer": result,
    "images": [m["source_url"] for m in media[:5]]
}
```

---

## 📞 Support & Debugging

### Enable Verbose Logging
Edit `main_initial_crawl.py`:
```python
# Around line 150, add logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Processing: {item}")
```

### Monitor System Resources
```powershell
# Watch CPU/Memory during pipeline
while($true) {
    $proc = Get-Process python
    $proc | Select-Object ProcessName, CPU, WorkingSet | Format-Table
    Start-Sleep -Seconds 5
}
```

### Check FAISS Index Properties
```python
from vectordb.vectordb_manager import VectorDBManager

db = VectorDBManager(persist_directory="data/faiss_index")
if db.db:
    print(f"Index size: {db.db.index.ntotal} vectors")
    print(f"Dimension: {db.db.index.d} (text=384, image=768)")
```

---

## 🏁 Success Checklist

After pipeline completes:

- [ ] `data/discovered_urls.json` exists (27k+ URLs)
- [ ] `data/faiss_index/` directory created (500MB+ size)
- [ ] `data/media_registry.json` created with image URLs
- [ ] `pipeline_progress.json` shows all steps `true`
- [ ] `test_multimodal.py` passes
- [ ] Semantic search returns relevant results

---

## 🎓 System Architecture (Review)

```
User Query
    ↓
[Semantic Search] → FAISS Index
    ↓
[Text Results]         [Image Metadata]
    ↓                         ↓
Chunks from          URLs from media_registry
Text↓Images              ↓
    └─→ Chatbot Response + Downloads
```

---

**Status: ✅ Ready for Production Deployment**

*For questions or issues, check the logs in `data/` directory or review `MULTIMODAL_RAG_STATUS.md`*
