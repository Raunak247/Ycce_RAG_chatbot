import pickle
import faiss

idx = faiss.read_index('data/faiss_index/index.faiss')

def load_pickle_with_fallback(primary_path, backup_path):
    try:
        with open(primary_path, 'rb') as f:
            return pickle.load(f), primary_path
    except EOFError:
        with open(backup_path, 'rb') as f:
            return pickle.load(f), backup_path


d, used_path = load_pickle_with_fallback(
    'data/faiss_index/index.pkl',
    'data/faiss_index/index.pkl.bak'
)

if used_path.endswith('.bak'):
    print('[WARN] index.pkl is corrupted (EOF). Using index.pkl.bak for balance check.')

vectors = idx.ntotal

if isinstance(d, dict):
    id_map_obj = d.get('id_map', {})
    docstore_obj = d.get('docstore', {})
elif isinstance(d, tuple) and len(d) == 2:
    docstore_obj, id_map_obj = d
else:
    raise ValueError(f'Unsupported index.pkl format: {type(d)}')

id_map = len(id_map_obj)
docstore = len(getattr(docstore_obj, '_dict', docstore_obj))

print(f'index.faiss vectors:  {vectors:,}')
print(f'index.pkl id_map:     {id_map:,}')
print(f'index.pkl docstore:   {docstore:,}')
print()
if vectors == id_map == docstore:
    print('✅ PERFECTLY BALANCED - All counts match')
else:
    print('❌ IMBALANCE DETECTED')
    print(f'  Vectors vs ID Map:   {vectors - id_map:+,}')
    print(f'  Vectors vs Docstore: {vectors - docstore:+,}')
