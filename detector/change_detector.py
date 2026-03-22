import os
import json
import hashlib
import requests
from config import REGISTRY_PATH


def compute_hash(content):
    return hashlib.md5(content).hexdigest()


def load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return {}
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def save_registry(registry):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def detect_changes(crawled_items):
    print("🧠 Running change detection...")

    registry = load_registry()
    changed = []

    for item in crawled_items:
        url = item["url"]

        try:
            r = requests.get(url, timeout=10)
            content_hash = compute_hash(r.content)

            if url not in registry:
                print(f"🆕 NEW: {url}")
                registry[url] = {"hash": content_hash, "type": item["type"]}
                changed.append(item)

            elif registry[url]["hash"] != content_hash:
                print(f"♻️ UPDATED: {url}")
                registry[url]["hash"] = content_hash
                changed.append(item)

        except Exception as e:
            print(f"❌ Detector error at {url}: {e}")

    save_registry(registry)
    print(f"✅ Change detection done. {len(changed)} items changed.")
    return changed