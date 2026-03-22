# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import re
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
from ingestion.ingest_pipeline import ingest_items, get_last_processed_folder, load_ingested_urls, is_ingestion_complete
from ingestion.runtime_input_cache import prepare_runtime_input_cache
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
        with open(PROGRESS_FILE, "r", encoding="utf-8-sig") as f:
            progress = json.load(f)
    else:
        progress = {
            "crawl_done": False,
            "change_detection_done": False,
            "ingestion_done": False
        }

    # Derive ingestion completion from strict state (folder markers + no pending statuses).
    try:
        ingested_state = load_ingested_urls()
        progress["ingestion_done"] = is_ingestion_complete(ingested_state)
    except Exception:
        progress.setdefault("ingestion_done", False)

    return progress


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


def _humanize_token(token: str) -> str:
    token = (token or "").replace("_", " ").replace("-", " ").strip()
    token = re.sub(r"\s+", " ", token)
    return token


def _infer_image_description(title: str, url: str) -> str:
    lower = f"{title} {url}".lower()
    if "pool" in lower or "swim" in lower:
        return "Campus swimming pool side view"
    if "classroom" in lower:
        return "Campus classroom interior"
    if "gallery" in lower:
        return "Campus gallery image"
    if "lab" in lower:
        return "Campus laboratory image"
    if "hostel" in lower:
        return "Campus hostel image"
    if "library" in lower:
        return "Campus library image"
    return f"Campus image: {title}" if title else "Campus image"


def _build_image_metadata(img_url: str, local_path: str = None) -> dict:
    parsed = urlparse(img_url or "")
    file_name = os.path.basename(parsed.path or "")
    stem, ext = os.path.splitext(file_name)
    clean_title = _humanize_token(stem) or "Image"

    tags = []
    lower_name = clean_title.lower()
    for token in ["pool", "classroom", "gallery", "lab", "hostel", "library", "campus"]:
        if token in lower_name and token not in tags:
            tags.append(token)
    if "campus" not in tags:
        tags.append("campus")

    description = _infer_image_description(clean_title, img_url)
    search_text = f"image {clean_title} {description} {' '.join(tags)} {img_url}".strip()

    metadata = {
        "source_url": img_url,
        "content_type": "image",
        "title": clean_title,
        "description": description,
        "tags": tags,
        "search_text": search_text,
        "file_name": file_name,
        "file_ext": ext.lower().lstrip("."),
    }
    if local_path:
        metadata["local_path"] = local_path
    return metadata


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

            with open(CRAWL_FILE, "r", encoding="utf-8-sig") as f:
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

            with open(REGISTRY_FILE, "r", encoding="utf-8-sig") as f:
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

        try:
            current_ingestion_state = load_ingested_urls()
            next_folder = get_last_processed_folder(current_ingestion_state)
            if next_folder is None:
                if progress.get("ingestion_done"):
                    print("[INFO] All folders are already marked complete")
                else:
                    print("[INFO] Folder markers are complete but pending items still exist")
            else:
                print(f"[INFO] Next ingestion folder: {next_folder}")
        except Exception as e:
            print(f"[WARN] Could not determine next ingestion folder: {e}")

        if progress["ingestion_done"]:
            print("[INFO] Ingestion already completed - skipping FAISS update")
        else:
            # -------- PREPARE RUNTIME INPUT CACHE (PARALLEL DOWNLOAD) --------
            print("\n[INPUT] Building runtime input cache...")
            runtime_items = changed_items
            try:
                runtime_items = prepare_runtime_input_cache(changed_items)
                ready_items = [
                    item for item in runtime_items
                    if isinstance(item, dict) and not item.get("download_failed")
                ]
                skipped_failed = [
                    item for item in runtime_items
                    if isinstance(item, dict) and item.get("download_failed")
                ]
                print(
                    f"[INPUT] Runtime cache prepared. ready={len(ready_items)} skipped_failed={len(skipped_failed)} total={len(runtime_items)}"
                )
            except Exception as e:
                print(f"[WARN] Runtime input cache failed: {e}")
                print("[INFO] Falling back to direct URL ingestion")

            # -------- CLASSIFY URLs FOR IMAGES & TEXT --------
            print("\n[INFO] Classifying URLs...")
            text_urls = []
            image_urls = []
            media_records = []
            
            # Track already-embedded images to avoid duplicates
            embedded_images = set()

            for item in runtime_items:
                if isinstance(item, dict) and item.get("download_failed"):
                    continue

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
                    elif ext in ["xlsx", "xls"]:
                        url_type = "xlsx"
                    elif ext == "csv":
                        url_type = "csv"
                    elif ext == "txt":
                        url_type = "txt"
                    else:
                        url_type = "html"
                    text_urls.append({"url": url, "type": url_type})

            # -------- TEXT INGESTION (FOLDER-ORDERED WITH CHECKPOINT SAFETY) --------
            ingestion_success = False
            if text_urls:
                print(f"[INFO] Ingesting {len(text_urls)} text/PDF URLs (folder-ordered)...")
                try:
                    ingestion_success = ingest_items(text_urls)
                    if ingestion_success:
                        print("[OK] ✅ Text ingestion completed successfully - FAISS persisted")
                    else:
                        print("[WARN] Text ingestion paused (resumable from checkpoint)")
                except Exception as e:
                    print(f"[ERROR] Text ingestion failed: {e}")
                    ingestion_success = False
            else:
                print("[WARN] No text URLs to ingest")

            if not ingestion_success:
                progress["ingestion_done"] = False
                save_progress(progress)
                print("[INFO] Text ingestion is not finished yet - skipping image stage and leaving pipeline resumable")
                return

            # -------- IMAGE EMBEDDING INTO FAISS (NEW - NO LOCAL SAVE) --------
            if image_urls:
                print(f"\n[IMG] Processing {len(image_urls)} image URLs for FAISS...")
                try:
                    from vectordb.image_embeddings import embed_image_from_path, embed_image_from_url
                    
                    embedded_count = 0
                    failed_count = 0
                    
                    # Initialize VectorDB for image embeddings
                    db = VectorDBManager(persist_directory=FAISS_PATH)
                    
                    for idx, image_item in enumerate(image_urls):
                        img_url = image_item if isinstance(image_item, str) else image_item.get("url", "")
                        local_path = image_item.get("local_path") if isinstance(image_item, dict) else None

                        # Prefer local cached file to avoid runtime re-download.
                        try:
                            if local_path and os.path.exists(local_path):
                                embedding = embed_image_from_path(local_path)
                            else:
                                embedding = embed_image_from_url(img_url)
                            
                            if embedding:
                                # Upsert to FAISS with metadata
                                metadata = _build_image_metadata(img_url, local_path=local_path)
                                db.upsert_image_embedding(embedding, metadata)
                                media_records.append(metadata)
                                embedded_count += 1
                            else:
                                failed_count += 1
                        except Exception as item_err:
                            print(f"    [WARN] Image {idx+1} skipped: {item_err}")
                            failed_count += 1
                        
                        # Progress logging
                        if (idx + 1) % max(10, len(image_urls) // 5) == 0:
                            print(f"  [IMG] {idx + 1}/{len(image_urls)} processed")
                    
                    print(f"\n[IMG] Embedded: {embedded_count} | Failed: {failed_count}")
                    
                    # Persist image embeddings to FAISS
                    if embedded_count > 0:
                        db.persist()
                        print("[IMG] ✅ Image embeddings persisted to FAISS")
                    
                except Exception as e:
                    print(f"[ERROR] Image embedding failed: {e}")
                    print("[INFO] Continuing with existing FAISS index...")

            # -------- CREATE MEDIA REGISTRY (URL ONLY, NO LOCAL PATHS) --------
            if media_records:
                media_registry_path = os.path.join(DATA_DIR, "media_registry.json")
                with open(media_registry_path, "w", encoding="utf-8") as f:
                    json.dump(media_records, f, indent=2)
                print(f"[REGISTRY] Saved {len(media_records)} media URLs to media_registry.json")

            progress["ingestion_done"] = bool(ingestion_success)
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