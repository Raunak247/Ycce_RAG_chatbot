import json

with open('data/ingested_urls.json','r',encoding='utf-8') as f:
    items = json.load(f)

# Check PDF entries
pdf_ingested = [it for it in items if isinstance(it,dict) and it.get('status')=='ingested' and it.get('folder')=='pdf']
print(f'Total ingested PDFs: {len(pdf_ingested)}')
print()
print('Sample ingested PDF entries:')
for i, item in enumerate(pdf_ingested[:3]):
    url = item.get('url', 'N/A')
    if url and len(url) > 60:
        url = url[:60] + '...'
    print(f'{i+1}. URL: {url}')
    lp = item.get('local_path')
    print(f'   Local path: {lp if lp else "NOT SET"}')
    print()

# Check if any PDF entry has local_path set
pdf_with_paths = [it for it in pdf_ingested if it.get('local_path')]
print(f'\nPDFs with local_path set: {len(pdf_with_paths)} out of {len(pdf_ingested)}')
