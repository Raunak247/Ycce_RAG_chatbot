import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit
from collections import deque
from config import BASE_URL, DOMAIN, MAX_DEPTH, RATE_LIMIT, DISCOVERED_URLS


def is_internal(url):
    return DOMAIN in urlparse(url).netloc


def detect_type(url):
    url = url.lower()
    if url.endswith(".pdf"):
        return "pdf"
    if url.endswith((".xlsx", ".xls")):
        return "xlsx"
    if url.endswith(".csv"):
        return "csv"
    if url.endswith(".txt"):
        return "txt"
    return "html"


def bfs_crawl(start_url=BASE_URL):
    print("🕷️ BFS crawling started...")

    visited = set()
    def normalize_url(u):
        parts = urlsplit(u)
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parts.path.rstrip('/')
        return urlunsplit((scheme, netloc, path, '', ''))

    queue = deque([(normalize_url(start_url), 0)])
    results = []

    while queue:
        url, depth = queue.popleft()
        if depth > MAX_DEPTH:
            continue

        # always work with a normalized URL to avoid duplicates caused by
        # fragments, query variations, trailing slashes or www prefix
        norm_url = normalize_url(url)
        if norm_url in visited:
            continue

        try:
            print(f"🔎 Crawling: {norm_url} (depth={depth})")
            response = requests.get(norm_url, timeout=10)
            visited.add(norm_url)

            file_type = detect_type(norm_url)

            results.append({
                "url": norm_url,
                "type": file_type,
                "depth": depth
            })

            if "text/html" not in response.headers.get("Content-Type", ""):
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            for a in soup.find_all("a", href=True):
                joined = urljoin(norm_url, a["href"])
                next_norm = normalize_url(joined)
                if is_internal(next_norm) and next_norm not in visited:
                    queue.append((next_norm, depth + 1))

            time.sleep(RATE_LIMIT)

        except Exception as e:
            print(f"❌ Crawler error at {url}: {e}")

    with open(DISCOVERED_URLS, "w") as f:
        json.dump(results, f, indent=2)

    print("✅ BFS crawling completed")
    return results