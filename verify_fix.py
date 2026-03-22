#!/usr/bin/env python
"""Verify the fix was applied correctly"""

print("\n=== CHECKING IF PDF FORCE-APPEND CODE WAS REMOVED ===\n")

with open('ingestion/ingest_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Search for the old code patterns
patterns = [
    "for root, _, files in os.walk(pdf_root):",
    "added_local_pdf_count",
    "[pdf] +",
]

found = False
for pattern in patterns:
    if pattern in content:
        print(f"❌ Found old pattern: {pattern}")
        found = True

if not found:
    print("✅ Old PDF force-append code is REMOVED from source")
    print()
    print("Queue should now be:")
    print("  PDF: ~2,466 (100% from discovered_urls)")
    print("  NOT pdf: ~4,840 (which was discovered + all local files)")
else:
    print("\n⚠️ Code still contains old patterns - issue not fully fixed")		
