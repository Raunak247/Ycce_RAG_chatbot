# -*- coding: utf-8 -*-
import os
import json
from collections import Counter

from ingestion.ingest_pipeline import ingest_items, load_ingested_urls


DATA_INPUT = os.path.join("data", "input")
FOLDERS = ["xlsx", "html", "pdf"]
PENDING_STATES = {"parsed", "failed", "needs_reingest"}


def scan_local_items():
    items = []
    folder_file_counts = Counter()

    for folder in FOLDERS:
        folder_dir = os.path.join(DATA_INPUT, folder)
        if not os.path.isdir(folder_dir):
            continue

        for name in os.listdir(folder_dir):
            file_path = os.path.join(folder_dir, name)
            if not os.path.isfile(file_path):
                continue

            folder_file_counts[folder] += 1
            items.append(
                {
                    "url": f"local://{folder}/{name}",
                    "type": folder,
                    "local_path": os.path.abspath(file_path),
                }
            )

    return items, folder_file_counts


def latest_status_counters(ingested_list):
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
            key = ("lp", os.path.abspath(local_path).lower())
        elif url:
            key = ("u", url)
        else:
            continue

        latest[key] = (folder, status)

    ingested_counts = Counter()
    pending_counts = Counter()
    for folder, status in latest.values():
        if status == "ingested":
            ingested_counts[folder] += 1
        if status in PENDING_STATES:
            pending_counts[folder] += 1

    return ingested_counts, pending_counts


def print_snapshot(label):
    state = load_ingested_urls()
    ingested_counts, pending_counts = latest_status_counters(state)
    _, folder_file_counts = scan_local_items()

    print(f"\n===== {label} =====")
    print("folder_files:", dict(folder_file_counts))
    print("latest_ingested:", {k: ingested_counts.get(k, 0) for k in ["xlsx", "html", "pdf", "image"]})
    print("latest_pending:", {k: pending_counts.get(k, 0) for k in ["xlsx", "html", "pdf", "image"]})


def main():
    print_snapshot("BEFORE")

    items, folder_file_counts = scan_local_items()
    if not items:
        print("[INFO] No local files found in data/input/{xlsx,html,pdf}")
        return

    print(f"\n[RUN] Ingesting from local folders. items={len(items)} breakdown={dict(folder_file_counts)}")
    result = ingest_items(items)
    print(f"[RUN] ingest_items returned: {result}")

    print_snapshot("AFTER")


if __name__ == "__main__":
    main()
