"""
Diagnose FAISS index health: check real docs vs legacy vectors, sample content.
"""
import faiss, pickle, os, random

idx = faiss.read_index('data/faiss_index/index.faiss')
print('Total vectors:', idx.ntotal)
print('Dimension:', idx.d)
print('Index type:', type(idx).__name__)

with open('data/faiss_index/index.pkl', 'rb') as f:
    docstore, id_map = pickle.load(f)

real_dict = docstore._dict if hasattr(docstore, '_dict') else {}
print('Docstore real docs:', len(real_dict))
print('ID map entries:', len(id_map))
print('Zombie vectors (no docstore entry):', len(id_map) - len(real_dict))

# Check how many id_map entries are actually in the docstore
found = 0
missing = 0
for k, uuid in id_map.items():
    if uuid in real_dict:
        found += 1
    else:
        missing += 1

print('ID map -> docstore found:', found)
print('ID map -> docstore missing (zombies):', missing)

# Sample 5 real docs from the docstore
print()
print('--- REAL DOC SAMPLES (from docstore) ---')
real_items = list(real_dict.items())
random.shuffle(real_items)
for uuid, doc in real_items[:5]:
    meta = getattr(doc, 'metadata', {})
    src = str(meta.get('source', meta.get('file_path', '?')))
    ft = str(meta.get('file_type', '?'))
    content = getattr(doc, 'page_content', str(doc))
    print('  uuid=%s' % uuid[:12])
    print('  source=%s' % src[:80])
    print('  file_type=%s' % ft)
    print('  content=%r' % content[:120])
    print()

# Test a quick similarity search
print('--- SIMILARITY SEARCH TEST ---')
try:
    os.environ.setdefault('HF_HUB_DISABLE_HTTPX', '1')
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', local_files_only=True)
    
    queries = [
        'YCCE establishment year',
        'Dr Anita Shekhawat faculty',
        'AIDS sem 4 timetable',
    ]
    
    for q in queries:
        vec = model.encode([q], convert_to_numpy=True)
        D, I = idx.search(vec, 20)
        real_count = 0
        zombie_count = 0
        best_score = None
        best_content = None
        for dist, int_idx in zip(D[0], I[0]):
            if int_idx == -1:
                continue
            uuid = id_map.get(int_idx)
            if uuid and uuid in real_dict:
                real_count += 1
                if best_score is None:
                    best_score = dist
                    doc = real_dict[uuid]
                    best_content = getattr(doc, 'page_content', '')[:150]
            else:
                zombie_count += 1
        print('Query: %r' % q)
        print('  Real docs in top-20: %d, Zombies: %d' % (real_count, zombie_count))
        if best_score is not None:
            print('  Best L2 score: %.4f' % best_score)
            print('  Best content: %r' % best_content[:120])
        print()
except Exception as e:
    print('Search test failed:', e)
    import traceback; traceback.print_exc()
