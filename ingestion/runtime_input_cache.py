import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse

import requests


INPUT_ROOT = os.path.join("data", "input")
MANIFEST_PATH = os.path.join(INPUT_ROOT, "download_manifest.json")
PENDING_DOWNLOADS_PATH = os.path.join(INPUT_ROOT, "pending_downloads_full.json")
DEFAULT_WORKERS = 12
DEFAULT_TIMEOUT = 20

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def _canonical_url(url: str) -> str:
    parsed = urlparse(url or "")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))


def _load_known_failed_urls() -> set[str]:
    failed_urls = set()

    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            for item in manifest.get("failed_items", []):
                url = item.get("url") if isinstance(item, dict) else None
                if url:
                    failed_urls.add(_canonical_url(url))
        except Exception:
            pass

    if os.path.exists(PENDING_DOWNLOADS_PATH):
        try:
            with open(PENDING_DOWNLOADS_PATH, "r", encoding="utf-8") as f:
                pending_items = json.load(f)
            for item in pending_items:
                url = item.get("url") if isinstance(item, dict) else None
                if url:
                    failed_urls.add(_canonical_url(url))
        except Exception:
            pass

    return failed_urls


def _safe_ext_from_url(url: str, fallback: str) -> str:
    path = urlparse(_canonical_url(url)).path.lower()
    _, ext = os.path.splitext(path)
    if ext:
        return ext
    return fallback


def _target_subdir_and_ext(item: dict) -> tuple[str, str]:
    url = item.get("url", "")
    item_type = (item.get("type") or "html").lower()

    if url.lower().endswith(IMAGE_EXTENSIONS):
        return "image", _safe_ext_from_url(url, ".jpg")
    if item_type == "pdf":
        return "pdf", ".pdf"
    if item_type in ("xlsx", "xls"):
        ext = ".xlsx" if item_type == "xlsx" else ".xls"
        return item_type, ext
    if item_type == "csv":
        return "csv", ".csv"
    if item_type == "txt":
        return "txt", ".txt"
    return "html", ".html"


def _local_path_for_item(item: dict) -> str:
    url = item.get("url", "")
    normalized_url = _canonical_url(url)
    subdir, ext = _target_subdir_and_ext(item)
    os.makedirs(os.path.join(INPUT_ROOT, subdir), exist_ok=True)

    base_name = os.path.basename(urlparse(normalized_url).path) or "index"
    base_name = "".join(ch for ch in base_name if ch.isalnum() or ch in ("-", "_", "."))
    if not base_name:
        base_name = "file"
    url_hash = hashlib.md5(normalized_url.encode("utf-8")).hexdigest()[:10]
    filename = f"{base_name}_{url_hash}{ext}"
    return os.path.join(INPUT_ROOT, subdir, filename)


def _download_item(item: dict, timeout: int = DEFAULT_TIMEOUT, retries: int = 2) -> dict:
    url = item.get("url")
    if not url:
        return {"ok": False, "item": item, "error": "missing url"}

    local_path = _local_path_for_item(item)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return {"ok": True, "item": item, "local_path": local_path, "cached": True}

    last_error = None
    for _ in range(retries + 1):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()

            with open(local_path, "wb") as f:
                f.write(response.content)

            return {"ok": True, "item": item, "local_path": local_path, "cached": False}
        except Exception as e:
            last_error = str(e)

    return {"ok": False, "item": item, "error": last_error or "download failed"}


def prepare_runtime_input_cache(items: list[dict], workers: int = DEFAULT_WORKERS) -> list[dict]:
    """
    Download changed/discovered URLs into data/input/{pdf,xlsx,csv,txt,html,image}.
    Returns enriched items with local_path where download succeeded.
    """
    os.makedirs(INPUT_ROOT, exist_ok=True)

    if not items:
        return []

    enriched_items = []
    failed = []
    cached_count = 0
    known_failed_urls = _load_known_failed_urls()
    pending_items = []
    skipped_known_failures = 0

    print(f"[INPUT] Preparing runtime input cache for {len(items)} items...")
    print(f"[INPUT] Target folder: {INPUT_ROOT}")
    print(f"[INPUT] Parallel downloads: {workers}")

    for original in items:
        item = dict(original)
        canonical_url = _canonical_url(item.get("url", ""))
        local_path = _local_path_for_item(item)

        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            item["local_path"] = local_path
            enriched_items.append(item)
            cached_count += 1
            continue

        if canonical_url in known_failed_urls:
            item["download_failed"] = True
            item["error"] = "known previous download failure"
            enriched_items.append(item)
            failed.append({"url": item.get("url", ""), "error": item["error"]})
            skipped_known_failures += 1
            continue

        pending_items.append(item)

    print(
        f"[INPUT] Local ready: {cached_count} | known failed skipped: {skipped_known_failures} | queued: {len(pending_items)}"
    )

    if pending_items:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            future_map = {executor.submit(_download_item, item): item for item in pending_items}
            for index, future in enumerate(as_completed(future_map), start=1):
                result = future.result()
                item = dict(result.get("item", {}))
                if result.get("ok"):
                    item["local_path"] = result.get("local_path")
                    enriched_items.append(item)
                    if result.get("cached"):
                        cached_count += 1
                else:
                    item["download_failed"] = True
                    item["error"] = result.get("error", "unknown")
                    enriched_items.append(item)
                    failed.append({"url": item.get("url", ""), "error": item["error"]})

                if index % 250 == 0 or index == len(pending_items):
                    print(f"[INPUT] Progress: {index}/{len(pending_items)} queued items processed")

    # Keep relative lightweight manifest for debugging and resumability visibility.
    manifest = {
        "total_requested": len(items),
        "downloaded_or_cached": len([item for item in enriched_items if not item.get("download_failed")]),
        "cached": cached_count,
        "failed": len(failed),
        "failed_items": failed[:200],
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"[INPUT] Cache ready. success={len(enriched_items)} cached={cached_count} failed={len(failed)}"
    )
    print(f"[INPUT] Manifest: {MANIFEST_PATH}")

    return enriched_items
