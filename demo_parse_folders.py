import os
import traceback
from pathlib import Path

import pandas as pd
from PIL import Image

from loaders.loader_routers import route_loader

BASE_INPUT = Path("data/input")
FOLDERS = ["xlsx", "html", "pdf", "image"]
MAX_FILES_PER_FOLDER = 5
MAX_PREVIEW_CHARS = 700


def pick_files(folder_path: Path, max_count: int):
    if not folder_path.exists():
        return []
    files = [p for p in folder_path.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.name.lower())
    return files[:max_count]


def normalize_text(text: str, max_chars: int):
    compact = " ".join((text or "").split())
    return compact[:max_chars]


def parse_text_file(file_path: Path, folder_name: str):
    if folder_name == "html":
        docs = route_loader(str(file_path), "html")
    elif folder_name == "pdf":
        docs = route_loader(str(file_path), "pdf")
    elif folder_name == "xlsx":
        try:
            docs = route_loader(str(file_path), "xlsx")
        except Exception:
            # Fallback parser when optional unstructured deps are unavailable.
            df = pd.read_excel(file_path)
            docs = [
                type("SimpleDoc", (), {"page_content": df.to_string(index=False)})()
            ]
    else:
        return {"ok": False, "error": f"Unsupported text folder: {folder_name}"}

    if not docs:
        return {"ok": False, "error": "Loader returned no documents"}

    joined = "\n".join((d.page_content or "") for d in docs)
    return {
        "ok": True,
        "doc_count": len(docs),
        "preview": normalize_text(joined, MAX_PREVIEW_CHARS),
    }


def parse_image_file(file_path: Path):
    with Image.open(file_path) as img:
        width, height = img.size
        mode = img.mode
        fmt = img.format

    return {
        "ok": True,
        "doc_count": 1,
        "preview": (
            f"Image metadata only (no OCR in this demo): "
            f"format={fmt}, size={width}x{height}, mode={mode}"
        ),
    }


def process_folder(folder_name: str):
    folder_path = BASE_INPUT / folder_name
    files = pick_files(folder_path, MAX_FILES_PER_FOLDER)

    print("=" * 100)
    print(f"FOLDER: {folder_name} | sample files: {len(files)}")
    print("=" * 100)

    if not files:
        print("No files found in this folder.\n")
        return

    for idx, file_path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] File: {file_path.name}")
        try:
            if folder_name == "image":
                result = parse_image_file(file_path)
            else:
                result = parse_text_file(file_path, folder_name)

            if result.get("ok"):
                print(f"Status: OK | Parsed units: {result.get('doc_count', 0)}")
                print("Content Preview:")
                print(result.get("preview", ""))
            else:
                print(f"Status: FAILED | Reason: {result.get('error', 'Unknown error')}")

        except Exception as ex:
            print(f"Status: FAILED | Exception: {ex}")
            print(traceback.format_exc(limit=1).strip())

        print("-" * 100)

    print()


def main():
    print("DEMO: Parsing 5 files from each folder (xlsx, html, pdf, image)")
    print("This demo does NOT write FAISS and does NOT update ingested_urls.json")
    print()

    for folder in FOLDERS:
        process_folder(folder)

    print("Demo finished.")


if __name__ == "__main__":
    main()
