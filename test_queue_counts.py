"""Test queue counts after fix"""
import json
import sys

# Force reimport
if 'ingestion.ingest_pipeline' in sys.modules:
    del sys.modules['ingestion.ingest_pipeline']
if 'ingestion' in sys.modules:
    del sys.modules['ingestion']

import ingestion.ingest_pipeline as p

def show_plan(items):
    print()
    print('=== INGESTION PLAN (AFTER FIX) ===')
    xlsx_cnt = len(items.get('xlsx', []))
    html_cnt = len(items.get('html', []))
    pdf_cnt = len(items.get('pdf', []))
    img_cnt = len(items.get('image', []))
    
    print(f'XLSX:   {xlsx_cnt:>5}  (should be ~16)')
    print(f'HTML:   {html_cnt:>5}  (should be ~360)')
    print(f'PDF:    {pdf_cnt:>5}  (should be ~2466)')
    print(f'Image:  {img_cnt:>5}  (should be 0)')
    print()
    
    if pdf_cnt < 3500:
        print('✅ PDF count is FIXED - no longer force-appending all local PDFs')
    else:
        print('❌ PDF count still wrong - force-append still happening')
    
    return True

p.ingest_items_ordered = show_plan

with open('data/discovered_urls.json','r',encoding='utf-8-sig') as f:
    urls = json.load(f)

# Filter out image URLs
text_urls = []
for u in urls:
    if isinstance(u,dict):
        url = u.get('url','').lower()
        if not any(url.endswith(ext) for ext in ['.png','.jpg','.jpeg','.gif','.webp']):
            text_urls.append(u)
    else:
        text_urls.append(u)

p.ingest_items(text_urls)
