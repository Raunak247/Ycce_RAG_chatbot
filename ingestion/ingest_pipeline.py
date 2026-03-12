import os
import json
import hashlib
import shutil
from datetime import datetime

from loaders.loader_routers import route_loader
from vectordb.faiss_stores import upsert_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter


INGEST_TRACK_FILE = "data/ingested_urls.json"
BATCH_SIZE = 50  # Upsert every N documents to avoid memory buildup
MIN_DISK_MB = 500  # Require at least 500 MB free
SINGLE_FOLDER_PER_RUN = True  # Stop after one full folder so FAISS can be tested safely


# -------------------------------------------------
# helpers
# -------------------------------------------------
def load_ingested_urls():
    """Load ingested URLs with per-file tracking (list of dicts with folder info)."""
    if os.path.exists(INGEST_TRACK_FILE):
        with open(INGEST_TRACK_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            # Support both legacy (list of strings) and new format (list of dicts)
            if data and isinstance(data[0], dict):
                return data
            # If old format, convert to new format
            return [{"url": url, "folder": "unknown", "status": "ingested"} for url in data] if data else []
    return []


def save_ingested_urls(ingested_list):
    """Save ingested URLs list with metadata (folder, status, timestamp)."""
    os.makedirs("data", exist_ok=True)
    with open(INGEST_TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(ingested_list, f, indent=2)


def get_ingested_urls_set(ingested_list):
    """Convert ingested list to set of successfully ingested URLs for fast lookup."""
    ingested_urls = set()
    for item in ingested_list:
        if isinstance(item, dict):
            if item.get("status") == "ingested" and item.get("url"):
                ingested_urls.add(item["url"])
        elif isinstance(item, str):
            # Legacy format treated as successfully ingested.
            ingested_urls.add(item)
    return ingested_urls


def get_completed_folders(ingested_list):
    """Return folders explicitly marked complete."""
    completed = set()
    for item in ingested_list:
        if isinstance(item, dict) and item.get("status") == "folder_complete":
            completed.add(item.get("folder", "unknown"))
    return completed


def get_last_processed_folder(ingested_list):
    """Determine next folder to process based on explicit completion markers."""
    folder_order = ["xlsx", "html", "pdf", "image"]
    processed_folders = get_completed_folders(ingested_list)

    for folder in folder_order:
        if folder not in processed_folders:
            return folder

    return None  # All done


def mark_folder_complete(ingested_list, folder):
    """Persist a single completion marker per folder."""
    for item in ingested_list:
        if isinstance(item, dict) and item.get("status") == "folder_complete" and item.get("folder") == folder:
            item["timestamp"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            return

    ingested_list.append(
        {
            "url": f"__folder_complete__::{folder}",
            "folder": folder,
            "status": "folder_complete",
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    )


def check_disk_space():
    """Check available disk space, return MB free."""
    try:
        stat = shutil.disk_usage("data" if os.path.exists("data") else ".")
        free_mb = stat.free / (1024 * 1024)
        return free_mb
    except Exception:
        return float('inf')  # If we can't check, assume plenty


def batch_upsert(chunks, batch_size=BATCH_SIZE):
    """Upsert chunks in batches to manage memory."""
    if not chunks:
        return
    
    print(f"[UPSERT] Upserting {len(chunks)} chunks to FAISS (batch size: {batch_size})...")
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        try:
            upsert_documents(batch)
            print(f"   [OK] Batch {i//batch_size + 1}: {len(batch)} chunks upserted")
        except Exception as e:
            if "No space left" in str(e) or "Errno 28" in str(e):
                print(f"   [WARN] Disk space error at batch {i//batch_size + 1}: {e}")
                free_mb = check_disk_space()
                print(f"   [DISK] Free disk space: {free_mb:.1f} MB")
                raise
            else:
                raise


# -------------------------------------------------
# FOLDER-ORDERED INGESTION
# -------------------------------------------------
def ingest_items_ordered(items_by_folder):
    """
    Ingest items in folder order: xlsx → html → pdf → image
    Safe on resume - tracks per-file status in ingested_urls.json
    Only commits to FAISS after successful parse & chunk
    """
    print("[INPUT] Starting FOLDER-ORDERED ingestion...")
    
    # Check initial disk space
    free_mb = check_disk_space()
    print(f"[DISK] Available disk space: {free_mb:.1f} MB")
    if free_mb < MIN_DISK_MB:
        print(f"[WARN] Low disk space ({free_mb:.1f} MB < {MIN_DISK_MB} MB threshold)")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    # Load existing progress
    ingested_list = load_ingested_urls()
    ingested_urls = get_ingested_urls_set(ingested_list)
    
    # Determine resume point
    resume_folder = get_last_processed_folder(ingested_list)
    folder_order = ["xlsx", "html", "pdf", "image"]
    
    if resume_folder:
        print(f"[RESUME] Starting/resuming from folder: {resume_folder}")
    else:
        print("[INFO] All folders previously completed or starting fresh")
    
    total_new = 0
    total_skipped = 0
    total_failed = 0
    disk_full = False
    
    # Process folders in order
    for folder in folder_order:
        if resume_folder and folder_order.index(folder) < folder_order.index(resume_folder):
            print(f"[SKIP] Folder '{folder}' already processed - skipping")
            continue
        
        items = items_by_folder.get(folder, [])
        if not items:
            print(f"[SKIP] No items in folder '{folder}'")
            continue
        
        print(f"\n{'='*60}")
        print(f"[FOLDER] Processing '{folder}' ({len(items)} items)...")
        print(f"{'='*60}")
        
        folder_new = 0
        folder_skipped = 0
        folder_failed = 0
        
        for idx, item in enumerate(items):
            url = item["url"]
            file_type = item["type"]
            local_path = item.get("local_path") if isinstance(item, dict) else None
            load_source = local_path if local_path else url
            
            # ✅ SKIP IF ALREADY INGESTED
            if url in ingested_urls:
                print(f"  [SKIP] {idx+1}/{len(items)}: Already ingested - {url[:80]}")
                folder_skipped += 1
                total_skipped += 1
                continue
            
            try:
                # Check disk space before processing
                free_mb = check_disk_space()
                if free_mb < MIN_DISK_MB:
                    print(f"\n[WARN] DISK SPACE CRITICAL: {free_mb:.1f} MB remaining")
                    print(f"   Stopping {folder} folder processing to prevent corruption")
                    disk_full = True
                    break
                
                print(f"  [INGEST] {idx+1}/{len(items)}: {url[:70]}")
                docs = route_loader(load_source, file_type)
                
                if not docs:
                    print(f"         [WARN] No docs loaded")
                    folder_failed += 1
                    total_failed += 1
                    continue
                
                chunks = splitter.split_documents(docs)
                
                # Add metadata to all chunks
                for c in chunks:
                    c.metadata["source_url"] = url
                    c.metadata["file_type"] = file_type
                    if local_path:
                        c.metadata["local_path"] = local_path
                    
                    # Content hash for dedup
                    content_hash = hashlib.md5(c.page_content.encode()).hexdigest()
                    c.metadata["chunk_id"] = content_hash
                
                # Save per-file checkpoint first so progress is visible immediately.
                record = {
                    "url": url,
                    "folder": folder,
                    "status": "parsed",
                    "chunks": len(chunks),
                    "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z"
                }
                ingested_list.append(record)
                save_ingested_urls(ingested_list)
                print(f"         [OK] Parsed ({len(chunks)} chunks) and checkpointed")

                try:
                    batch_upsert(chunks, batch_size=BATCH_SIZE)
                except Exception as e:
                    record["status"] = "failed"
                    record["error"] = str(e)
                    save_ingested_urls(ingested_list)
                    if "No space left" in str(e) or "Errno 28" in str(e):
                        print(f"\n[ERROR] Disk full during upsert: {e}")
                        disk_full = True
                        break
                    raise

                record["status"] = "ingested"
                record["timestamp"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                save_ingested_urls(ingested_list)
                ingested_urls.add(url)
                folder_new += 1
                total_new += 1
            
            except Exception as e:
                print(f"         [ERROR] Failed: {e}")
                folder_failed += 1
                total_failed += 1
                continue
        
        # Save after folder complete
        if not disk_full:
            mark_folder_complete(ingested_list, folder)
        save_ingested_urls(ingested_list)
        
        print(f"[FOLDER] '{folder}' complete:")
        print(f"         New: {folder_new} | Skipped: {folder_skipped} | Failed: {folder_failed}")

        if SINGLE_FOLDER_PER_RUN and not disk_full:
            print(f"\n[PAUSE] Stopping after completed folder '{folder}' by design")
            print("   Test the chatbot/FAISS now, then re-run to continue with the next folder")
            return False
        
        if disk_full:
            print(f"\n[WARN] Stopping ingestion due to disk space (resume later)")
            break
    
    # Final summary
    print(f"\n{'='*60}")
    print("[INGESTION] SUMMARY:")
    print(f"  Total new ingested: {total_new}")
    print(f"  Total skipped: {total_skipped}")
    print(f"  Total failed: {total_failed}")
    print(f"{'='*60}")
    
    # Check if all folders done
    resume_folder = get_last_processed_folder(ingested_list)
    if resume_folder is None:
        print("\n[SUCCESS] ingestion into faiss.index finally done")
        print("\n[SUCCESS] Your FAISS index is ready for the chatbot!")
        print(f"   Path: data/faiss_index/")
        print(f"   Total URLs ingested: {len(ingested_urls)}")
        return True
    else:
        print(f"\n[PAUSE] Ingestion paused at folder '{resume_folder}'")
        print(f"   Re-run the command to resume from this folder")
        return False


# -------------------------------------------------
# LEGACY SINGLE-FOLDER INGESTION (kept for backward compatibility)
# -------------------------------------------------
def ingest_items(items):
    """
    Wrapper that organizes items by folder and calls folder-ordered ingestion.
    Supports both dict-style items (new format) and legacy formats.
    """
    print("\n[WRAPPER] Organizing items by folder...")
    
    # Organize by folder
    items_by_folder = {
        "xlsx": [],
        "html": [],
        "pdf": [],
        "image": []
    }
    
    for item in items:
        file_type = item.get("type") if isinstance(item, dict) else "unknown"
        
        # Map file type to folder
        if file_type in ["xlsx", "xls"]:
            folder = "xlsx"
        elif file_type in ["html", "htm"]:
            folder = "html"
        elif file_type in ["pdf"]:
            folder = "pdf"
        elif file_type in ["png", "jpg", "jpeg", "gif", "webp"]:
            folder = "image"
        else:
            folder = file_type  # fallback
        
        items_by_folder[folder].append(item)
    
    # Print breakdown
    for folder, items_list in items_by_folder.items():
        if items_list:
            print(f"  [{folder}] {len(items_list)} items")
    
    # Call folder-ordered ingestion
    return ingest_items_ordered(items_by_folder)