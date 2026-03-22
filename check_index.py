import faiss, pickle, os

# Index stats
idx = faiss.read_index('data/faiss_index/index.faiss')
print('Total vectors:', idx.ntotal)
print('Dimension:', idx.d)
print('Index type:', type(idx).__name__)

with open('data/faiss_index/index.pkl', 'rb') as f:
    docstore, id_map = pickle.load(f)

d = docstore._dict if hasattr(docstore, '_dict') else {}
print('Docstore docs:', len(d))
print('ID map entries:', len(id_map))

# Sample 5 docs
print()
print('--- SAMPLE DOCS ---')
for i, (k, v) in enumerate(list(id_map.items())[:5]):
    doc = docstore.search(v) if hasattr(docstore, 'search') else d.get(v)
    content = getattr(doc, 'page_content', str(doc))[:150]
    meta = getattr(doc, 'metadata', {})
    src = str(meta.get('source', '?'))[:60]
    print('[%d] source=%s' % (i, src))
    print('     content=%r' % content[:100])

# Check embedding model used during ingestion
print()
print('--- CHECK SENTENCE TRANSFORMERS ---')
try:
    from sentence_transformers import SentenceTransformer
    print('sentence-transformers: INSTALLED')
    model_name = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    try:
        m = SentenceTransformer(model_name, local_files_only=True)
        v = m.encode(['test'])
        print('Model cached locally:', model_name)
        print('Embedding dim:', v.shape[1] if hasattr(v, 'shape') else len(v[0]))
    except Exception as e:
        print('Model NOT cached locally:', e)
        try:
            m = SentenceTransformer(model_name, local_files_only=False)
            v = m.encode(['test'])
            print('Model downloaded OK:', model_name, 'dim=', v.shape[1])
        except Exception as e2:
            print('Model download also failed:', e2)
            print('WILL USE HASH EMBEDDINGS - THIS IS THE PROBLEM!')
except ImportError as e:
    print('sentence-transformers NOT installed:', e)
    print('WILL USE HASH EMBEDDINGS - THIS IS THE PROBLEM!')
