#!/usr/bin/env python
"""Diagnose FAISS index content and retrieval quality"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vectordb.vectordb_manager import VectorDBManager

def diagnose_faiss():
    print("=" * 80)
    print("🔍 FAISS Index Diagnostic Report")
    print("=" * 80)
    
    # Initialize FAISS
    vectordb = VectorDBManager()
    
    if not vectordb.db:
        print("❌ FAISS index not found!")
        return
    
    print(f"\n✅ FAISS index loaded successfully\n")
    
    # Test various keywords
    test_queries = {
        "AIDS Branch": [
            "artificial intelligence and data science",
            "aids",
            "ai data science",
            "4th semester aids syllabus",
        ],
        "CSE AIML": [
            "cse aiml",
            "computer science aiml",
            "ai machine learning",
        ],
        "Syllabus": [
            "syllabus",
            "curriculum",
            "course structure",
            "scheme of examination",
        ],
        "Semester": [
            "4th semester",
            "iv semester",
            "fourth semester",
        ]
    }
    
    print("\n" + "=" * 80)
    print("Testing Retrieval Quality by Keyword Category")
    print("=" * 80)
    
    results_summary = {}
    
    for category, queries in test_queries.items():
        print(f"\n📚 {category}")
        print("-" * 80)
        
        for query in queries:
            try:
                # Search
                docs = vectordb.db.similarity_search_with_score(query, k=3)
                
                if docs:
                    print(f"\n  Query: '{query}'")
                    print(f"  ✅ Found {len(docs)} documents")
                    
                    for i, (doc, score) in enumerate(docs, 1):
                        content_preview = doc.page_content[:150].replace("\n", " ")
                        print(f"    [{i}] Score: {score:.4f} | {content_preview}...")
                    
                    if category not in results_summary:
                        results_summary[category] = {"found": 0, "not_found": 0}
                    results_summary[category]["found"] += 1
                else:
                    print(f"  Query: '{query}'")
                    print(f"  ❌ No results found")
                    if category not in results_summary:
                        results_summary[category] = {"found": 0, "not_found": 0}
                    results_summary[category]["not_found"] += 1
                    
            except Exception as e:
                print(f"  Query: '{query}'")
                print(f"  ❌ Error: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Summary")
    print("=" * 80)
    
    for category, stats in results_summary.items():
        total = stats["found"] + stats["not_found"]
        success_rate = (stats["found"] / total) * 100 if total > 0 else 0
        print(f"\n{category}")
        print(f"  Found: {stats['found']}/{total} ({success_rate:.1f}%)")
        if stats["not_found"] > 0:
            print(f"  ⚠️  Not found: {stats['not_found']}")
    
    # Specific test for AIDS 4th semester
    print("\n" + "=" * 80)
    print("🎯 Specific Test: AIDS 4th Semester Syllabus")
    print("=" * 80)
    
    aids_queries = [
        "aids 4th semester syllabus",
        "artificial intelligence and data science semester 4",
        "Artificial Intelligence and Data Science 4th sem curriculum",
    ]
    
    for q in aids_queries:
        print(f"\nTesting: '{q}'")
        docs = vectordb.db.similarity_search_with_score(q, k=5)
        if docs:
            print(f"Results: {len(docs)} documents")
            for doc, score in docs:
                if "aids" in doc.page_content.lower() or "artificial intelligence" in doc.page_content.lower():
                    print(f"  ✅ MATCH! Score: {score:.4f}")
                    print(f"     {doc.page_content[:200]}")
                    break
            else:
                print(f"  ⚠️ No AIDS-specific content in top 5 results")
        else:
            print(f"  ❌ No results")
    
    print("\n" + "=" * 80)
    print("Recommendations:")
    print("=" * 80)
    print("""
1. If AIDS syllabus is not found:
   - Check if the document was properly ingested into FAISS
   - Verify that crawled data includes AIDS branch content
   
2. To improve retrieval:
   - Re-run: python main_initial_crawl.py
   - Then check: python FAISS_STATUS_REPORT.py
   - Ensure all branch syllabi are in crawled data
   
3. For better indexing:
   - Consider adding branch-specific metadata
   - Use keyword-boosting in retrieval
   
4. To force re-index:
   - Delete data/faiss_index folder
   - Re-run main_initial_crawl.py
    """)

if __name__ == "__main__":
    diagnose_faiss()
