#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Inspect FAISS index contents and statistics.
"""

import os
import json
from pathlib import Path

FAISS_PATH = "data/faiss_index"

def inspect_faiss_index():
    """Analyze FAISS index contents."""
    print("\n" + "="*80)
    print("FAISS INDEX INSPECTION")
    print("="*80)
    
    if not os.path.exists(FAISS_PATH):
        print(f"[ERROR] FAISS index not found at: {FAISS_PATH}")
        return False
    
    # List files in FAISS directory
    print(f"\n[1] FAISS Index Directory: {FAISS_PATH}")
    files = os.listdir(FAISS_PATH)
    total_size = 0
    print(f"    Files ({len(files)}):")
    for fname in files:
        fpath = os.path.join(FAISS_PATH, fname)
        fsize = os.path.getsize(fpath)
        total_size += fsize
        size_mb = fsize / (1024*1024)
        print(f"      - {fname}: {size_mb:.2f} MB")
    
    print(f"    Total size: {total_size / (1024*1024):.2f} MB")
    
    # Try to load FAISS and inspect vectors
    print(f"\n[2] Loading FAISS Index...")
    try:
        from vectordb.vectordb_manager import VectorDBManager
        db = VectorDBManager(persist_directory=FAISS_PATH)
        
        if db.db is None:
            print(f"    [WARN] FAISS DB is None")
            return False
        
        # Get index stats
        index = db.db.index
        if hasattr(index, 'ntotal'):
            num_vectors = index.ntotal
            print(f"    ✓ Total vectors in index: {num_vectors}")
        else:
            print(f"    [WARN] Cannot determine vector count")
            num_vectors = 0
        
        # Try to get documents
        print(f"\n[3] Document Metadata:")
        try:
            # FAISS stores document metadata
            if hasattr(db.db, 'docstore'):
                docstore = db.db.docstore
                num_docs = len(docstore._dict) if hasattr(docstore, '_dict') else 0
                print(f"    ✓ Total documents: {num_docs}")
                
                # Show sample documents
                if num_docs > 0:
                    print(f"    Sample documents (first 5):")
                    count = 0
                    for key, doc in (docstore._dict.items() if hasattr(docstore, '_dict') else []):
                        if count >= 5:
                            break
                        content = doc.page_content if hasattr(doc, 'page_content') else str(doc)[:80]
                        source = doc.metadata.get('source', 'N/A') if hasattr(doc, 'metadata') else 'N/A'
                        print(f"      [{count}] Source: {source}")
                        print(f"          Content: {content[:60]}...")
                        count += 1
            else:
                print(f"    [WARN] No docstore found")
        except Exception as e:
            print(f"    [ERROR] Cannot read docstore: {e}")
        
        # Check metadata file if exists
        print(f"\n[4] Metadata Files:")
        if os.path.exists(os.path.join(FAISS_PATH, "index.pkl")):
            print(f"    ✓ index.pkl found ({os.path.getsize(os.path.join(FAISS_PATH, 'index.pkl')) / 1024:.2f} KB)")
        if os.path.exists(os.path.join(FAISS_PATH, "index.faiss")):
            print(f"    ✓ index.faiss found ({os.path.getsize(os.path.join(FAISS_PATH, 'index.faiss')) / (1024*1024):.2f} MB)")
        
        print(f"\n[SUMMARY]")
        print(f"  Vectors stored: {num_vectors}")
        print(f"  Index size: {total_size / (1024*1024):.2f} MB")
        
        if num_vectors == 0:
            print(f"\n  ⚠️  WARNING: FAISS index is EMPTY!")
            print(f"  PDFs have NOT been ingested yet.")
            print(f"  Step 3 of main_initial_crawl.py needs to be executed.")
        else:
            print(f"\n  ✓ Index has {num_vectors} vectors")
        
        return num_vectors > 0
        
    except Exception as e:
        print(f"    [ERROR] Failed to load FAISS: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    inspect_faiss_index()
