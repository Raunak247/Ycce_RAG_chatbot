# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import requests
from urllib.parse import urlparse

# ═══════════════════════════════════════════════════════════════
# ✅ COMPREHENSIVE C-DRIVE PREVENTION - ALL DATA TO E DRIVE ONLY
# ═══════════════════════════════════════════════════════════════

# CRITICAL: Redirect ALL system temp directories to E drive
os.environ['TEMP'] = r'E:\temp'
os.environ['TMP'] = r'E:\temp'
os.environ['TMPDIR'] = r'E:\temp'

# CRITICAL: Redirect ALL pip cache to E drive
os.environ['PIP_CACHE_DIR'] = r'E:\.cache\pip'

# CRITICAL: Redirect HuggingFace models to E drive
os.environ['HUGGINGFACE_HUB_CACHE'] = r'E:\.cache\huggingface'
os.environ['HF_HOME'] = r'E:\.cache\huggingface'

# CRITICAL: Redirect PyTorch to E drive
os.environ['TORCH_HOME'] = r'E:\.cache\torch'

# CRITICAL: Redirect Transformers to E drive
os.environ['TRANSFORMERS_CACHE'] = r'E:\.cache\transformers'

# CRITICAL: Redirect other ML caches to E drive
os.environ['KERAS_HOME'] = r'E:\.cache\keras'
os.environ['MPLCONFIGDIR'] = r'E:\.cache\matplotlib'
os.environ['NLTK_DATA'] = r'E:\.cache\nltk_data'

# Create all E-drive temp/cache directories (NEVER C drive!)
os.makedirs(r'E:\temp', exist_ok=True)
os.makedirs(r'E:\.cache\huggingface', exist_ok=True)
os.makedirs(r'E:\.cache\torch', exist_ok=True)
os.makedirs(r'E:\.cache\transformers', exist_ok=True)
os.makedirs(r'E:\.cache\pip', exist_ok=True)
os.makedirs(r'E:\.cache\keras', exist_ok=True)
os.makedirs(r'E:\.cache\matplotlib', exist_ok=True)
os.makedirs(r'E:\.cache\nltk_data', exist_ok=True)

print('[STARTUP] ✅ All system paths redirected to E drive - C drive protected!')

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from crawler.bfs_crawler import bfs_crawl
from detector.change_detector import detect_changes
from ingestion.ingest_pipeline import ingest_items
from vectordb.vectordb_manager import VectorDBManager
from config import BASE_URL


# ==================================================
# CONFIGURATION
# ==================================================
DATA_DIR = "data"
PROGRESS_FILE = os.path.join(DATA_DIR, "pipeline_progress.json")
CRAWL_FILE = os.path.join(DATA_DIR, "discovered_urls.json")
REGISTRY_FILE = os.path.join(DATA_DIR, "url_registry.json")
FAISS_PATH = os.path.join(DATA_DIR, "faiss_index")


# ==================================================
# PROGRESS HELPERS
# ==================================================
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "crawl_done": False,
        "change_detection_done": False,
        "ingestion_done": False
    }


def save_progress(progress):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


# ==================================================
# IMAGE HELPERS (LIGHTWEIGHT - DETECTION ONLY)
# ==================================================
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def is_image(url: str) -> bool:
    """Check if URL points to an image file (no download)."""
    return url.lower().endswith(IMAGE_EXTENSIONS)


# ==================================================
# MAIN PIPELINE
# ==================================================
def main():
    print("=" * 60)
    print("[INIT] YCCE Smart Knowledge Build Started")
    print("=" * 60)

    start_time = time.time()
    progress = load_progress()
    os.makedirs(DATA_DIR, exist_ok=True)

    # ==================================================
    # STEP 1 — BFS CRAWL
    # ==================================================
    print("\n[STEP 1] Crawling website...")

    try:
        if os.path.exists(CRAWL_FILE):
            print("[INFO] Existing discovered_urls.json found - skipping crawl")

            with open(CRAWL_FILE, "r", encoding="utf-8") as f:
                crawled_items = json.load(f)

            progress["crawl_done"] = True
            save_progress(progress)

        else:
            print("[INFO] Starting BFS crawl...")
            crawled_items = bfs_crawl(BASE_URL)

            progress["crawl_done"] = True
            save_progress(progress)

        print(f"[OK] Crawled URLs available: {len(crawled_items)}")

    except Exception as e:
        print(f"[ERROR] Crawl step failed: {e}")
        return

    # ==================================================
    # STEP 2 — CHANGE DETECTION (SMART)
    # ==================================================
    print("\n[STEP 2] Detecting new/updated content...")

    try:
        # CASE 1: Registry already exists → skip detection
        if os.path.exists(REGISTRY_FILE):
            print("[INFO] url_registry.json found - Step 2 already completed")

            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                registry_data = json.load(f)

            print(f"[OK] Registered URLs: {len(registry_data)}")

            # For ingestion we still use discovered items
            changed_items = crawled_items

            progress["change_detection_done"] = True
            save_progress(progress)

        # CASE 2: Need to run detection
        else:
            print("[INFO] Running change detection...")
            changed_items = detect_changes(crawled_items)

            progress["change_detection_done"] = True
            save_progress(progress)

            print(f"[OK] New/Changed items: {len(changed_items)}")

    except Exception as e:
        print(f"[ERROR] Change detection step failed: {e}")
        return

    # ==================================================
    # STEP 3 — INGESTION WITH IMAGES & FAISS
    # ==================================================
    print("\n[STEP 3] Enhanced ingestion with images and FAISS...")

    try:
        if not changed_items:
            print("[WARN] Nothing to ingest")
            return

        if progress["ingestion_done"]:
            print("[INFO] Ingestion already completed - skipping FAISS update")
        else:
            # -------- CLASSIFY URLs FOR IMAGES & TEXT --------
            print("\n[INFO] Classifying URLs...")
            text_urls = []
            image_urls = []
            media_records = []
            
            # Track already-embedded images to avoid duplicates
            embedded_images = set()

            for item in changed_items:
                # Handle both string URLs and dict-based URLs
                url = item if isinstance(item, str) else item.get("url", str(item))

                # Handle images (CLIP embedding - NO local download)
                if is_image(url):
                    if url not in embedded_images:
                        image_urls.append(url)
                        embedded_images.add(url)
                    continue

                # Otherwise send for text ingestion - preserve dict if available
                if isinstance(item, dict):
                    text_urls.append(item)
                else:
                    # Create dict with inferred type from URL extension
                    ext = url.lower().split(".")[-1] if "." in url else ""
                    if ext == "pdf":
                        url_type = "pdf"
                    elif ext in ["xlsx", "xls", "csv"]:
                        url_type = "excel"
                    else:
                        url_type = "html"
                    text_urls.append({"url": url, "type": url_type})

            # -------- TEXT INGESTION (EXISTING LOGIC UNTOUCHED) --------
            if text_urls:
                print(f"[INFO] Ingesting {len(text_urls)} text/PDF URLs...")
                ingest_items(text_urls)
                print("[OK] Text ingestion completed")
            else:
                print("[WARN] No text URLs to ingest")

            # -------- IMAGE EMBEDDING INTO FAISS (NEW - NO LOCAL SAVE) --------
            if image_urls:
                print(f"\n[IMG] Processing {len(image_urls)} image URLs for FAISS...")
                try:
                    from vectordb.image_embeddings import embed_image_from_url
                    
                    embedded_count = 0
                    skipped_count = 0
                    failed_count = 0
                    
                    # Initialize VectorDB for image embeddings
                    db = VectorDBManager(persist_directory=FAISS_PATH)
                    
                    for idx, img_url in enumerate(image_urls):
                        # Embed image (in-memory, NO download)
                        embedding = embed_image_from_url(img_url)
                        
                        if embedding:
                            # Upsert to FAISS with metadata
                            metadata = {
                                "source_url": img_url,
                                "content_type": "image"
                            }
                            db.upsert_image_embedding(embedding, metadata)
                            media_records.append(metadata)
                            embedded_count += 1
                        else:
                            failed_count += 1
                        
                        # Progress logging
                        if (idx + 1) % max(10, len(image_urls) // 5) == 0:
                            print(f"  [IMG] {idx + 1}/{len(image_urls)} processed")
                    
                    print(f"\n[IMG] Embedded: {embedded_count}")
                    print(f"[IMG] Failed: {failed_count}")
                    
                except Exception as e:
                    print(f"[ERROR] Image embedding failed: {e}")
                    print("[INFO] Continuing with text-only FAISS...")
            else:
                print("[WARN] No image URLs found")
                db = VectorDBManager(persist_directory=FAISS_PATH)

            # -------- CREATE MEDIA REGISTRY (URL ONLY, NO LOCAL PATHS) --------
            if media_records:
                media_registry_path = os.path.join(DATA_DIR, "media_registry.json")
                with open(media_registry_path, "w", encoding="utf-8") as f:
                    json.dump(media_records, f, indent=2)
                print(f"[REGISTRY] Saved {len(media_records)} media URLs to media_registry.json")

            # -------- FINAL FAISS PERSIST --------
            print("\n[INFO] Final FAISS persistence...")
            try:
                db.persist()
                print("[OK] FAISS index persisted to disk")
            except Exception as e:
                print(f"[ERROR] FAISS persist failed: {e}")

            progress["ingestion_done"] = True
            save_progress(progress)

    except Exception as e:
        print(f"[ERROR] Ingestion failed: {e}")
        return

    # ==================================================
    # FINAL SUMMARY
    # ==================================================
    end_time = time.time()
    duration = round(end_time - start_time, 2)

    print("\n" + "=" * 60)
    print("[SUCCESS] SMART PIPELINE COMPLETED")
    print(f"[STAT] Total time: {duration} seconds")
    print("[STAT] Outputs:")
    print(f"       - FAISS index: {FAISS_PATH}")
    media_registry = os.path.join(DATA_DIR, "media_registry.json")
    if os.path.exists(media_registry):
        print(f"       - Media registry: {media_registry}")
    print("=" * 60)


if __name__ == "__main__":
    main()