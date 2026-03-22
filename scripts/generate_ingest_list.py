import json
from urllib.parse import urlsplit, urlunsplit
from collections import Counter
import os

DISCOVERED = os.path.join(os.path.dirname(__file__), '..', 'data', 'discovered_urls.json')
INGEST_OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'ingest_urls.json')


def normalize_keep_query(u):
    parts = urlsplit(u)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]
    path = parts.path.rstrip('/')
    # remove fragment but keep query
    return urlunsplit((scheme, netloc, path, parts.query, ''))


def generate():
    with open(DISCOVERED, 'r', encoding='utf-8') as f:
        data = json.load(f)

    dedup = {}
    types = Counter()
    for entry in data:
        raw = entry.get('url')
        if not raw:
            continue
        norm = normalize_keep_query(raw)
        if norm not in dedup:
            dedup[norm] = {
                'url': norm,
                'originals': [raw],
                'type': entry.get('type'),
                'depth': entry.get('depth', 0)
            }
        else:
            dedup[norm]['originals'].append(raw)

        types[entry.get('type')] += 1

    out = list(dedup.values())
    with open(INGEST_OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)

    print('discovered_total=', sum(types.values()))
    print('deduped_count=', len(out))
    print('types=', types)


if __name__ == '__main__':
    generate()
