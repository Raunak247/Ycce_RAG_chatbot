import os
import requests
import tempfile

# ✅ REDIRECT TEMPFILE TO E DRIVE (ensure no C drive usage)
os.environ['TEMP'] = r'E:\temp'
os.environ['TMP'] = r'E:\temp'
os.makedirs(r'E:\temp', exist_ok=True)
tempfile.tempdir = r'E:\temp'  # Force tempfile module to use E drive

from bs4 import BeautifulSoup
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredExcelLoader,
    CSVLoader,
    TextLoader,
)
from langchain_core.documents import Document


def _fallback_pdf_text(tmp_path, source_url):
    """Best-effort PDF extraction when PyPDFLoader fails on font encodings."""
    try:
        from pypdf import PdfReader
    except Exception:
        return []

    docs = []
    try:
        reader = PdfReader(tmp_path, strict=False)
        for i, page in enumerate(reader.pages):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                # Skip problematic pages but keep extracting others.
                continue

            if text:
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source_url": source_url,
                            "page": i,
                        },
                    )
                )
    except Exception:
        return []

    return docs

def _is_local_path(source):
    return isinstance(source, str) and os.path.exists(source)


def load_html(source):
    import re as _re
    if _is_local_path(source):
        with open(source, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        source_url = source
    else:
        r = requests.get(source, timeout=15)
        r.raise_for_status()
        html = r.text
        source_url = source

    soup = BeautifulSoup(html, "html.parser")

    # Remove boilerplate noise: navigation menus, scripts, footers, sidebars
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "noscript", "iframe", "form", "button"]):
        tag.decompose()

    # Also remove elements commonly used for menus/sidebars by class/id
    for tag in soup.find_all(True, {"class": lambda c: c and any(
            k in " ".join(c).lower() for k in ["nav", "menu", "sidebar", "breadcrumb", "widget", "banner"])}):
        tag.decompose()

    # Try to extract content from the most-meaningful element first
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="main-content")
        or soup.find(id="main")
        or soup.find(id="content")
        or soup.find(class_="entry-content")
        or soup.find(class_="page-content")
        or soup.find(class_="content-area")
        or soup.find(class_="post-content")
        or soup.body
        or soup
    )

    text = main_content.get_text(separator="\n", strip=True)
    # Collapse excessive blank lines into at most two
    text = _re.sub(r"\n{3,}", "\n\n", text).strip()

    return [Document(page_content=text, metadata={"source_url": source_url})]


def load_pdf(source):
    if _is_local_path(source):
        loader = PyPDFLoader(source)
        return loader.load()

    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(source, stream=True, timeout=15, allow_redirects=True, headers=headers)
    if r.status_code != 200:
        raise ValueError(f"HTTP {r.status_code}")

    content_type = r.headers.get("content-type", "")

    # Stream to tempfile and validate magic bytes + EOF marker
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        # read first bytes then stream remainder to avoid loading whole file into memory
        first = r.raw.read(8)
        tmp.write(first)
        while True:
            chunk = r.raw.read(8192)
            if not chunk:
                break
            tmp.write(chunk)
        tmp.flush()
        tmp_name = tmp.name

    # Quick validation: PDF magic header or content-type indicating PDF
    try:
        with open(tmp_name, "rb") as f:
            start = f.read(8)
            if b"%PDF" not in start and "pdf" not in content_type.lower():
                os.remove(tmp_name)
                raise ValueError(f"Not a PDF (content-type={content_type}, start={start!r})")

            # ensure EOF marker exists near end of file
            f.seek(0, os.SEEK_END)
            size = f.tell()
            tail_len = min(4096, size)
            f.seek(size - tail_len)
            tail = f.read()
            if b"%%EOF" not in tail:
                os.remove(tmp_name)
                raise ValueError("EOF marker not found or file truncated")

    except Exception:
        # propagate the exception after cleanup (if file remains)
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except Exception:
                pass
        raise

    loader = PyPDFLoader(tmp_name)
    try:
        return loader.load()
    except Exception as e:
        # Some PDFs fail in pypdf due to unsupported encodings like /SymbolSetEncoding.
        # Fall back to per-page best-effort extraction so ingestion can continue.
        print(f"[WARN] Primary PDF parser failed ({e}); trying fallback parser")
        docs = _fallback_pdf_text(tmp_name, source if not _is_local_path(source) else source)
        if docs:
            return docs
        raise


def load_xlsx(source):
    if _is_local_path(source):
        loader = UnstructuredExcelLoader(source)
        return loader.load()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(requests.get(source, timeout=15).content)
        loader = UnstructuredExcelLoader(tmp.name)
        return loader.load()


def load_csv(source):
    if _is_local_path(source):
        loader = CSVLoader(source)
        return loader.load()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(requests.get(source, timeout=15).content)
        loader = CSVLoader(tmp.name)
        return loader.load()


def load_txt(source):
    if _is_local_path(source):
        loader = TextLoader(source)
        return loader.load()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(requests.get(source, timeout=15).content)
        loader = TextLoader(tmp.name)
        return loader.load()


def route_loader(source, file_type):
    if file_type == "pdf":
        return load_pdf(source)
    if file_type in ("xlsx", "xls"):
        return load_xlsx(source)
    if file_type == "csv":
        return load_csv(source)
    if file_type == "txt":
        return load_txt(source)
    return load_html(source)