import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
import hashlib
import shutil
from datetime import datetime
from typing import Tuple, Set

from loaders.loader_routers import route_loader
from vectordb.faiss_stores import upsert_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter


INGEST_TRACK_FILE = "data/ingested_urls.json"
BATCH_SIZE = 50  # Upsert every N documents to avoid memory buildup
MIN_DISK_MB = 500  # Require at least 500 MB free
SINGLE_FOLDER_PER_RUN = os.getenv("SINGLE_FOLDER_PER_RUN", "0") == "1"  # Set 1 to pause after each folder
FOLDER_ORDER = ["xlsx", "html", "pdf", "image"]  # Process html before pdf so web content is searchable
HTML_REINGEST_CANDIDATES_FILE = "data/html_reingest_candidates.json"
ACTIVE_PENDING_STATUSES = {"parsed", "failed", "needs_reingest"}


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


def get_ingested_local_paths_set(ingested_list):
    """Return a set of local_path values for successfully ingested items."""
    paths = set()
    for item in ingested_list:
        if isinstance(item, dict) and item.get("status") == "ingested":
            lp = item.get("local_path")
            if lp:
                paths.add(os.path.abspath(lp).lower())
    return paths


def get_completed_folders(ingested_list):
    """Return folders explicitly marked complete."""
    completed = set()
    for item in ingested_list:
        if isinstance(item, dict) and item.get("status") == "folder_complete":
            completed.add(item.get("folder", "unknown"))
    return completed


def get_last_processed_folder(ingested_list):
    """Determine next folder to process based on explicit completion markers."""
    processed_folders = get_completed_folders(ingested_list)

    for folder in FOLDER_ORDER:
        if folder not in processed_folders:
            return folder

    return None  # All done


def _get_latest_item_statuses(ingested_list):
    """Return latest status per item key (url/local_path) based on append order."""
    latest = {}

    for item in ingested_list:
        if not isinstance(item, dict):
            continue

        status = item.get("status")
        if status == "folder_complete":
            continue

        folder = item.get("folder", "unknown")
        local_path = (item.get("local_path") or "").strip()
        url = (item.get("url") or "").strip()

        if local_path:
            key = f"local_path::{os.path.abspath(local_path).lower()}"
        elif url:
            key = f"url::{url}"
        else:
            continue

        latest[key] = {
            "folder": folder,
            "status": status,
        }

    return latest


def has_pending_ingestion_items(ingested_list):
    """True when latest item statuses still include active pending work."""
    latest = _get_latest_item_statuses(ingested_list)
    for value in latest.values():
        if value.get("folder") in FOLDER_ORDER and value.get("status") in ACTIVE_PENDING_STATUSES:
            return True
    return False


def is_ingestion_complete(ingested_list):
    """Strict completion: all folder markers done and no active pending item statuses."""
    return get_last_processed_folder(ingested_list) is None and not has_pending_ingestion_items(ingested_list)


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


def _load_priority_html_reingest_sets() -> Tuple[Set[str], Set[str]]:
    """Load HTML files/URLs that must be re-ingested first due index.pkl mismatch."""
    priority_urls: Set[str] = set()
    priority_local_paths: Set[str] = set()

    if not os.path.exists(HTML_REINGEST_CANDIDATES_FILE):
        return priority_urls, priority_local_paths

    try:
        with open(HTML_REINGEST_CANDIDATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("missing_but_marked_ingested", []):
            if not isinstance(item, dict):
                continue

            mapped_url = (item.get("mapped_url") or "").strip()
            local_path = (item.get("local_path") or "").strip()
            if mapped_url:
                priority_urls.add(mapped_url)
            if local_path:
                priority_local_paths.add(os.path.abspath(local_path).lower())
    except Exception as e:
        print(f"[WARN] Could not load priority HTML reingest candidates: {e}")

    return priority_urls, priority_local_paths


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
    ingested_local_paths = get_ingested_local_paths_set(ingested_list)
    
    # Determine resume point from checkpoint markers.
    resume_folder = get_last_processed_folder(ingested_list)
    folder_order = list(FOLDER_ORDER)

    # If checkpoint points to a later folder but earlier folders still have pending items,
    # prefer the earliest pending folder to avoid false "paused at image" behavior.
    first_pending_folder = None
    for candidate_folder in folder_order:
        candidate_items = items_by_folder.get(candidate_folder, []) or []
        if not candidate_items:
            continue

        has_pending = False
        for candidate_item in candidate_items:
            if not isinstance(candidate_item, dict):
                has_pending = True
                break

            candidate_url = (candidate_item.get("url") or "").strip()
            candidate_lp = (candidate_item.get("local_path") or "").strip()
            candidate_lp_norm = os.path.abspath(candidate_lp).lower() if candidate_lp else ""

            if candidate_url and candidate_url in ingested_urls:
                continue
            if candidate_lp_norm and candidate_lp_norm in ingested_local_paths:
                continue

            has_pending = True
            break

        if has_pending:
            first_pending_folder = candidate_folder
            break

    if first_pending_folder:
        if (
            resume_folder is None
            or folder_order.index(first_pending_folder) < folder_order.index(resume_folder)
        ):
            if resume_folder:
                print(
                    f"[RESUME-OVERRIDE] Checkpoint suggested '{resume_folder}', "
                    f"but pending items exist in earlier folder '{first_pending_folder}'."
                )
            resume_folder = first_pending_folder
    
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
            # Mark empty folder as complete so resume pointer can move forward.
            if not disk_full:
                mark_folder_complete(ingested_list, folder)
                save_ingested_urls(ingested_list)
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
            is_priority_reingest = bool(isinstance(item, dict) and item.get("priority_reingest"))
            
            # ✅ SKIP IF ALREADY INGESTED
            if url in ingested_urls:
                print(f"  [SKIP] {idx+1}/{len(items)}: Already ingested - {url[:80]}")
                folder_skipped += 1
                total_skipped += 1
                continue
            # Also skip if local file was already ingested (even if URL differs)
            if local_path and os.path.abspath(local_path).lower() in ingested_local_paths:
                print(f"  [SKIP] {idx+1}/{len(items)}: Local file already ingested - {os.path.basename(local_path)}")
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
                
                if folder == "html" and is_priority_reingest:
                    print(f"  [INGEST-PRIORITY-HTML] {idx+1}/{len(items)}: {url[:70]}")
                else:
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
                if local_path:
                    record["local_path"] = os.path.abspath(local_path)
                save_ingested_urls(ingested_list)
                ingested_urls.add(url)
                if local_path:
                    ingested_local_paths.add(os.path.abspath(local_path).lower())
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
    
    # Check if all folders done (strict): markers complete + no pending statuses.
    resume_folder = get_last_processed_folder(ingested_list)
    pending_items_left = has_pending_ingestion_items(ingested_list)
    if resume_folder is None and not pending_items_left:
        print("\n[SUCCESS] ingestion into faiss.index finally done")
        print("\n[SUCCESS] Your FAISS index is ready for the chatbot!")
        print(f"   Path: data/faiss_index/")
        print(f"   Total URLs ingested: {len(ingested_urls)}")
        return True
    elif resume_folder is None and pending_items_left:
        print("\n[PAUSE] Folder markers are complete, but pending parsed/failed items still exist")
        print("   Re-run the command to continue processing pending items")
        return False
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
    
    # Load already-ingested tracking FIRST
    ingested_list = load_ingested_urls()
    ingested_urls = get_ingested_urls_set(ingested_list)
    ingested_local_paths = get_ingested_local_paths_set(ingested_list)
    
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

    # Load priority reingest sets once (used for both queue enrichment and ordering).
    priority_urls, priority_local_paths = _load_priority_html_reingest_sets()

    # NOTE: Do NOT force-add local PDFs from data/input/pdf
    # discovered_urls.json is the source of truth for what SHOULD be ingested.
    # Local files in data/input/pdf are the download cache, not source of truth.
    # Only PDFs from discovered_urls will be ingested via checkpoint system.

    # Prefer existing local HTML cache for current HTML items, but do NOT append the full html cache.
    # Appending every file from data/input/html can inflate queue size with stale entries.
    html_root = os.path.join("data", "input", "html")
    existing_html_local_paths = set()
    for item in items_by_folder["html"]:
        if isinstance(item, dict) and item.get("local_path"):
            existing_html_local_paths.add(os.path.abspath(item["local_path"]).lower())

    def _canonical_url_no_fragment(url: str) -> str:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url or "")
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))

    def _local_html_path_for_url(url: str) -> str:
        canonical = _canonical_url_no_fragment(url)
        from urllib.parse import urlparse
        base_name = os.path.basename(urlparse(canonical).path) or "index"
        base_name = "".join(ch for ch in base_name if ch.isalnum() or ch in ("-", "_", ".")) or "file"
        url_hash = hashlib.md5(canonical.encode("utf-8")).hexdigest()[:10]
        return os.path.abspath(os.path.join(html_root, f"{base_name}_{url_hash}.html"))

    linked_cached_html_count = 0
    for item in items_by_folder["html"]:
        if not isinstance(item, dict):
            continue
        if item.get("local_path"):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        expected_path = _local_html_path_for_url(url)
        if os.path.exists(expected_path):
            item["local_path"] = expected_path
            existing_html_local_paths.add(expected_path.lower())
            linked_cached_html_count += 1

    if linked_cached_html_count:
        print(f"  [html-cache] Linked {linked_cached_html_count} HTML URLs to existing local cache")

    # Add only priority local HTML files missing from the current queue.
    added_priority_local_html_count = 0
    if priority_local_paths:
        represented_local_paths = set()
        for item in items_by_folder["html"]:
            if not isinstance(item, dict):
                continue
            lp = (item.get("local_path") or "").strip()
            if lp:
                represented_local_paths.add(os.path.abspath(lp).lower())

        for lp in sorted(priority_local_paths):
            abs_lp = os.path.abspath(lp)
            lp_norm = abs_lp.lower()
            if not os.path.exists(abs_lp):
                continue
            if lp_norm in represented_local_paths:
                continue

            items_by_folder["html"].append(
                {
                    "url": f"local://html/{os.path.basename(abs_lp)}",
                    "type": "html",
                    "local_path": abs_lp,
                    "priority_reingest": True,
                }
            )
            represented_local_paths.add(lp_norm)
            added_priority_local_html_count += 1

    if added_priority_local_html_count:
        print(f"  [html-priority] +{added_priority_local_html_count} priority local HTML files added")

    # De-duplicate HTML queue by local_path first, then URL (for URL-only entries).
    deduped_html_items = []
    seen_html_local_paths = set()
    seen_html_urls = set()
    removed_html_dupes = 0
    for item in items_by_folder["html"]:
        if not isinstance(item, dict):
            deduped_html_items.append(item)
            continue

        url = (item.get("url") or "").strip()
        lp = (item.get("local_path") or "").strip()
        lp_norm = os.path.abspath(lp).lower() if lp else ""

        if lp_norm:
            if lp_norm in seen_html_local_paths:
                removed_html_dupes += 1
                continue
            seen_html_local_paths.add(lp_norm)
        elif url:
            if url in seen_html_urls:
                removed_html_dupes += 1
                continue
            seen_html_urls.add(url)

        deduped_html_items.append(item)

    items_by_folder["html"] = deduped_html_items
    if removed_html_dupes:
        print(f"  [html-dedupe] Removed {removed_html_dupes} duplicate HTML queue entries")

    # Priority-first HTML queue: ingest known index.pkl-missing HTML items before the normal HTML queue.
    # This preserves old logic and ordering for all non-priority items.
    if items_by_folder["html"] and (priority_urls or priority_local_paths):
        priority_html_items = []
        regular_html_items = []

        for item in items_by_folder["html"]:
            if not isinstance(item, dict):
                regular_html_items.append(item)
                continue

            url = (item.get("url") or "").strip()
            lp = (item.get("local_path") or "").strip()
            lp_norm = os.path.abspath(lp).lower() if lp else ""

            if url in priority_urls or (lp_norm and lp_norm in priority_local_paths):
                tagged = dict(item)
                tagged["priority_reingest"] = True
                priority_html_items.append(tagged)
            else:
                regular_html_items.append(item)

        items_by_folder["html"] = priority_html_items + regular_html_items
        if priority_html_items:
            print(f"  [html-priority] {len(priority_html_items)} index.pkl-missing HTML items will be ingested first")
            print(f"  [html-normal] {len(regular_html_items)} remaining HTML items will follow old ingestion flow")

    # Print breakdown
    for folder, items_list in items_by_folder.items():
        if items_list:
            print(f"  [{folder}] {len(items_list)} items")
    
    # Call folder-ordered ingestion
    return ingest_items_ordered(items_by_folder)