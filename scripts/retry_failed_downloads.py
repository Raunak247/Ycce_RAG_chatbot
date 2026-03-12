import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ingestion.runtime_input_cache import _download_item, _local_path_for_item


DISCOVERED_PATH = os.path.join("data", "discovered_urls.json")
REPORT_PATH = os.path.join("data", "input", "retry_failed_report.json")


def load_discovered_items(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    items = []
    for row in data:
        if isinstance(row, dict) and row.get("url"):
            items.append({"url": row["url"], "type": (row.get("type") or "html")})
    return items


def split_items(items):
    downloaded = []
    pending = []

    for item in items:
        local_path = _local_path_for_item(item)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            downloaded.append(item)
        else:
            pending.append(item)

    return downloaded, pending


def retry_pending(items, workers: int, timeout: int, retries: int):
    ok = []
    failed = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(_download_item, item, timeout=timeout, retries=retries): item
            for item in items
        }

        for idx, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            if result.get("ok"):
                ok.append(
                    {
                        "url": result["item"].get("url", ""),
                        "type": result["item"].get("type", ""),
                        "local_path": result.get("local_path", ""),
                        "cached": bool(result.get("cached", False)),
                    }
                )
            else:
                failed.append(
                    {
                        "url": result["item"].get("url", ""),
                        "type": result["item"].get("type", ""),
                        "error": result.get("error", "download failed"),
                    }
                )

            if idx % 25 == 0 or idx == len(items):
                print(f"[RETRY] Progress: {idx}/{len(items)}")

    return ok, failed


def main():
    parser = argparse.ArgumentParser(description="Retry missing/failed downloads from discovered_urls.json")
    parser.add_argument("--workers", type=int, default=12, help="Parallel workers (default: 12)")
    parser.add_argument("--timeout", type=int, default=20, help="Per-request timeout seconds (default: 20)")
    parser.add_argument("--retries", type=int, default=2, help="Retries per URL (default: 2)")
    parser.add_argument("--offset", type=int, default=0, help="Start index in pending list (default: 0)")
    parser.add_argument("--limit", type=int, default=0, help="How many pending URLs to retry (0 = all)")
    args = parser.parse_args()

    if not os.path.exists(DISCOVERED_PATH):
        raise FileNotFoundError(f"Missing input: {DISCOVERED_PATH}")

    items = load_discovered_items(DISCOVERED_PATH)
    downloaded, pending = split_items(items)

    print("=" * 60)
    print("FAILED DOWNLOAD RETRY")
    print("=" * 60)
    print(f"Total discovered: {len(items)}")
    print(f"Already downloaded: {len(downloaded)}")
    print(f"Pending before retry: {len(pending)}")

    if args.offset < 0:
        raise ValueError("--offset must be >= 0")
    if args.limit < 0:
        raise ValueError("--limit must be >= 0")

    if args.offset > 0 or args.limit > 0:
        end = None if args.limit == 0 else args.offset + args.limit
        pending = pending[args.offset:end]
        print(f"Pending selected for this run: {len(pending)} (offset={args.offset}, limit={args.limit or 'all'})")

    if not pending:
        print("Nothing to retry.")
        return

    ok, failed = retry_pending(
        pending,
        workers=args.workers,
        timeout=args.timeout,
        retries=args.retries,
    )

    report = {
        "total_discovered": len(items),
        "already_downloaded_before_retry": len(downloaded),
        "pending_before_retry": len(pending),
        "offset": args.offset,
        "limit": args.limit,
        "retried_success": len(ok),
        "still_failed": len(failed),
        "success_items": ok,
        "failed_items": failed,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 60)
    print(f"Retried success: {len(ok)}")
    print(f"Still failed: {len(failed)}")
    print(f"Report saved: {REPORT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
