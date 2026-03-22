"""Quick diagnostic: file type distribution and HTML content sample in FAISS"""
import pickle
from collections import Counter

print("Loading FAISS pickle...")
with open('data/faiss_index/index.pkl', 'rb') as f:
    docstore, id_map = pickle.load(f)

d = docstore._dict if hasattr(docstore, '_dict') else {}
print(f"Total docs in docstore._dict: {len(d)}")
print(f"Total entries in id_map: {len(id_map)}")
print()

ft = Counter()
src_samples = {}
html_samples = []
legacy_count = 0

for doc in d.values():
    content = getattr(doc, 'page_content', '') or ''
    if '[Recovered legacy document]' in content or content.strip() == '':
        legacy_count += 1
        continue
    meta = getattr(doc, 'metadata', {}) or {}
    t = meta.get('file_type', 'MISSING')
    ft[t] += 1
    if t not in src_samples:
        src = meta.get('source_url') or meta.get('source', '?')
        src_samples[t] = str(src)[:100]
    if t == 'html' and len(html_samples) < 5:
        src = meta.get('source_url') or meta.get('source', '')
        html_samples.append((src, content[:200]))

print(f"Legacy/empty placeholder docs: {legacy_count}")
print()
print("Real content by file_type:")
for k, c in ft.most_common():
    print(f"  {k}: {c}  |  sample_src: {src_samples.get(k,'')}")

print()
print(f"HTML doc samples ({len(html_samples)} found):")
for src, content in html_samples:
    print(f"  src: {src[:80]}")
    print(f"  content: {content[:120]!r}")
    print()

# Check for AI/DS department-related HTML docs
print("Searching for 'faculty' or 'staff' HTML docs...")
faculty_html = []
for doc in d.values():
    content = getattr(doc, 'page_content', '') or ''
    meta = getattr(doc, 'metadata', {}) or {}
    ft_val = meta.get('file_type', '')
    if ft_val != 'html':
        continue
    cl = content.lower()
    if any(kw in cl for kw in ['faculty', 'hod', 'head of department', 'professor', 'dr.']):
        src = meta.get('source_url') or meta.get('source', '')
        faculty_html.append((src, content[:300]))
        if len(faculty_html) >= 10:
            break

print(f"Faculty-related HTML docs found: {len(faculty_html)}")
for src, content in faculty_html[:5]:
    print(f"  src: {src[:80]}")
    print(f"  preview: {content[:150]!r}")
    print()
