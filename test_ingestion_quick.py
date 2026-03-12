#!/usr/bin/env python
"""Quick test of ingestion logic"""
import json
import os
import sys

# Redirect paths to E drive
os.environ['HF_HOME'] = r'E:\.cache\huggingface'
os.environ['TORCH_HOME'] = r'E:\.cache\torch'

from ingestion.ingest_pipeline import ingest_items

print("[TEST] Loading discovered URLs...")
with open('data/discovered_urls.json', 'r', encoding='utf-8-sig') as f:
    items = json.load(f)

# Get first 10 items for quick test
test_items = items[:10]
print(f"[TEST] Testing with {len(test_items)} items")

for i, item in enumerate(test_items):
    item_type = type(item).__name__
    if isinstance(item, dict):
        url = item.get('url', str(item))[:60]
        item_type_field = item.get('type', 'unknown')
        print(f"  [{i+1}] dict: {item_type_field} | {url}")
    else:
        print(f"  [{i+1}] {item_type}: {str(item)[:60]}")

print("\n[TEST] Calling ingest_items()...")
try:
    result = ingest_items(test_items)
    print(f"[TEST] ✅ Result: {result}")
    
    # Check if anything was ingested
    if os.path.exists('data/ingested_urls.json'):
        with open('data/ingested_urls.json', 'r', encoding='utf-8-sig') as f:
            ingested = json.load(f)
        print(f"[TEST] Ingested URLs in file: {len(ingested)}")
        if ingested:
            print(f"[TEST] First ingested: {ingested[0]}")
    else:
        print("[TEST] ⚠️ ingested_urls.json not created")
        
except Exception as e:
    print(f"[TEST] ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
