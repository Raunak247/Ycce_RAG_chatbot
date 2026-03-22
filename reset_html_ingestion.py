"""
Reset HTML ingestion tracking so all HTML pages are re-processed.

Why this is needed:
  A previous FAISS metadata recovery (index.pkl corruption → _recover_from_faiss_only)
  orphaned ~13,000 HTML page entries. Those URL keys still appear as 'ingested' in
  ingested_urls.json, so the pipeline skips them. Resetting them to 'needs_reingest'
  forces a clean re-index with the improved HTML content extractor.

Run once BEFORE starting the next main_initial_crawl.py / ingestion run.
"""

import json
import os
import sys

INGEST_TRACK_FILE = os.path.join("data", "ingested_urls.json")


def main():
    if not os.path.exists(INGEST_TRACK_FILE):
        print("[INFO] ingested_urls.json not found - nothing to reset.")
        return

    with open(INGEST_TRACK_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    reset_count = 0
    kept = []
    for item in data:
        if not isinstance(item, dict):
            kept.append(item)
            continue

        folder = item.get("folder", "")
        status = item.get("status", "")

        # Remove folder_complete markers for html so the pipeline re-enters html folder
        if status == "folder_complete" and folder == "html":
            print(f"  [REMOVE] folder_complete marker for '{folder}'")
            reset_count += 1
            continue  # drop this entry

        # Mark previously 'ingested' html items as needing re-ingestion.
        # Items that have a local_path are handled by local_path skip logic
        # and will be re-skipped correctly once properly ingested.
        if folder == "html" and status == "ingested":
            item["status"] = "needs_reingest"
            reset_count += 1

        kept.append(item)

    with open(INGEST_TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2)

    print(f"[DONE] Reset {reset_count} HTML entries in {INGEST_TRACK_FILE}")
    print("       You can now re-run main_initial_crawl.py to re-ingest HTML content.")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
