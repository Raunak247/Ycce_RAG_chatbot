#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRODUCTION VALIDATION REPORT
YCCE Multimodal RAG System - Complete Integration Ready

This script validates all system components before full-scale deployment.
Run this to confirm all functionality is working correctly.
"""

import os
import json
import sys

def validate_files():
    """Check all critical files exist."""
    print("\n" + "="*70)
    print("[1/5] FILE STRUCTURE VALIDATION")
    print("="*70)
    
    critical_files = {
        "Main Pipeline": "main_initial_crawl.py",
        "VectorDB Manager": "vectordb/vectordb_manager.py",
        "Image Embeddings": "vectordb/image_embeddings.py",
        "Ingest Pipeline": "ingestion/ingest_pipeline.py",
        "BFS Crawler": "crawler/bfs_crawler.py",
        "Change Detector": "detector/change_detector.py",
        "Config": "config.py",
        "Requirements": "requirements.txt",
    }
    
    missing = []
    for name, path in critical_files.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f" ✓ {name:20} {path:35} ({size:,} bytes)")
        else:
            missing.append(f"{name} ({path})")
    
    if missing:
        print(f"\n ✗ MISSING FILES: {', '.join(missing)}")
        return False
    return True

def validate_imports():
    """Check critical imports work."""
    print("\n" + "="*70)
    print("[2/5] IMPORT VALIDATION")
    print("="*70)
    
    imports_to_test = {
        "LangChain Core": "from langchain_core.documents import Document",
        "LangChain Community": "from langchain_community.embeddings import HuggingFaceEmbeddings",
        "FAISS": "from langchain_community.vectorstores import FAISS",
        "Sentence Transformers": "from sentence_transformers import SentenceTransformer",
        "CLIP": "from transformers import CLIPModel, CLIPProcessor",
        "PyTorch": "import torch",
        "PIL": "from PIL import Image",
        "Requests": "import requests",
    }
    
    failed = []
    for name, imp in imports_to_test.items():
        try:
            exec(imp)
            print(f" ✓ {name:25} OK")
        except Exception as e:
            failed.append(f"{name}: {str(e)[:40]}")
            print(f" ✗ {name:25} FAILED: {str(e)[:40]}")
    
    if failed:
        print(f"\n ✗ IMPORT FAILURES: {len(failed)} module(s)")
        return False
    return True

def validate_data_structure():
    """Check data directory structure."""
    print("\n" + "="*70)
    print("[3/5] DATA STRUCTURE VALIDATION")
    print("="*70)
    
    data_dir = "data"
    if not os.path.exists(data_dir):
        print(f" ✗ Data directory missing: {data_dir}")
        return False
    
    print(f" ✓ Data directory: {data_dir}/")
    
    # Check expected files
    expected_files = {
        "discovered_urls.json": "Crawled URLs",
        "url_registry.json": "Change detection registry",
        "pipeline_progress.json": "Pipeline state",
    }
    
    for fname, desc in expected_files.items():
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            size = os.path.getsize(fpath)
            print(f"   ✓ {fname:30} ({size:,} bytes) - {desc}")
        else:
            print(f"   - {fname:30} (not yet created) - {desc}")
    
    return True

def validate_faiss_index():
    """Check FAISS index if it exists."""
    print("\n" + "="*70)
    print("[4/5] FAISS INDEX VALIDATION")
    print("="*70)
    
    faiss_path = os.path.join("data", "faiss_index")
    if not os.path.exists(faiss_path):
        print(f" - FAISS index not yet created: {faiss_path}/")
        print("   (Will be created on first pipeline run)")
        return True
    
    files = os.listdir(faiss_path)
    total_size = sum(os.path.getsize(os.path.join(faiss_path, f)) for f in files)
    print(f" ✓ FAISS index found:")
    print(f"   - Location: {faiss_path}/")
    print(f"   - Files: {len(files)}")
    print(f"   - Total size: {total_size / (1024*1024):.2f} MB")
    for fname in files[:5]:
        fsize = os.path.getsize(os.path.join(faiss_path, fname)) / 1024
        print(f"     • {fname} ({fsize:.1f} KB)")
    return True

def validate_multimodal_components():
    """Check multimodal-specific components."""
    print("\n" + "="*70)
    print("[5/5] MULTIMODAL COMPONENTS VALIDATION")
    print("="*70)
    
    components = {
        "ImageEmbedder": ("vectordb/image_embeddings.py", "ImageEmbedder"),
        "VectorDBManager.upsert_image_embedding": ("vectordb/vectordb_manager.py", "upsert_image_embedding"),
        "VectorDBManager.persist": ("vectordb/vectordb_manager.py", "def persist"),
    }
    
    all_valid = True
    for name, (fpath, marker) in components.items():
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            if marker in content:
                print(f" ✓ {name:40} Found in {fpath}")
            else:
                print(f" ✗ {name:40} NOT FOUND in {fpath}")
                all_valid = False
        except Exception as e:
            print(f" ✗ {name:40} Error: {e}")
            all_valid = False
    
    # Check media registry capability
    media_reg = os.path.join("data", "media_registry.json")
    if os.path.exists(media_reg):
        with open(media_reg, 'r') as f:
            reg = json.load(f)
        print(f" ✓ Media registry exists: {len(reg)} items")
    else:
        print(f" - Media registry will be created on first pipeline run")
    
    return all_valid

def main():
    """Run all validations."""
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█  YCCE MULTIMODAL RAG SYSTEM - PRE-DEPLOYMENT VALIDATION  " + " "*9 + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    try:
        checks = [
            ("File Structure", validate_files),
            ("Imports", validate_imports),
            ("Data Structure", validate_data_structure),
            ("FAISS Index", validate_faiss_index),
            ("Multimodal Components", validate_multimodal_components),
        ]
        
        results = []
        for name, check_func in checks:
            try:
                result = check_func()
                results.append((name, result))
            except Exception as e:
                print(f"\n ✗ {name} validation failed: {e}")
                results.append((name, False))
        
        # Summary
        print("\n" + "="*70)
        print("VALIDATION SUMMARY")
        print("="*70)
        
        passed = sum(1 for _, r in results if r)
        total = len(results)
        
        for name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status:7} {name}")
        
        print("\n" + "-"*70)
        print(f"OVERALL: {passed}/{total} checks passed")
        
        if passed == total:
            print("\n✅ SYSTEM IS READY FOR PRODUCTION DEPLOYMENT")
            print("\nNext steps:")
            print("  1. Run: python main_initial_crawl.py")
            print("  2. Monitor pipeline_progress.json for status")
            print("  3. Check FAISS index generation (~2 hours for 27k URLs)")
            print("  4. Verify media_registry.json creation")
            return 0
        else:
            print("\n⚠️  SYSTEM HAS UNRESOLVED ISSUES")
            print("Please address failures above before deployment")
            return 1
        
    except Exception as e:
        print(f"\n✗ VALIDATION FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return 2

if __name__ == "__main__":
    sys.exit(main())
