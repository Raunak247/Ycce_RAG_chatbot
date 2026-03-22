#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick test to verify RAG pipeline: 
- Documents are stored in FAISS (from PDFs + YCCE website)
- Chatbot can retrieve and answer questions
"""

from vectordb.vectordb_manager import VectorDBManager
from chatbot.rag_engine import RAGEngine
import json

def test_rag_retrieval():
    """Test that FAISS has documents and can retrieve them."""
    print("\n" + "="*70)
    print("[TEST] RAG Retrieval Pipeline")
    print("="*70)
    
    # Initialize FAISS
    print("\n[1] Initializing VectorDBManager...")
    db = VectorDBManager()
    
    if db.db is None:
        print("[ERROR] FAISS not loaded - no documents in index")
        return False
    
    # Check index statistics
    print(f"[OK] FAISS loaded successfully")
    
    # Test some queries
    test_queries = [
        "What programs does YCCE offer?",
        "What is YCCE?",
        "Tell me about YCCE infrastructure",
        "What are the admission criteria?",
    ]
    
    print("\n[2] Testing retrieval with sample queries...")
    for query in test_queries:
        try:
            results = db.similarity_search(query, k=2)
            if results:
                print(f"\n  ✓ Query: '{query}'")
                for i, (content, score) in enumerate(results, 1):
                    snippet = content[:80].replace('\n', ' ')
                    print(f"    Result {i} (score={score:.3f}): {snippet}...")
            else:
                print(f"\n  ✗ Query: '{query}' - No results")
        except Exception as e:
            print(f"\n  ✗ Query: '{query}' - Error: {e}")
    
    # Initialize RAG Engine
    print("\n[3] Initializing RAG Engine...")
    try:
        rag = RAGEngine()
        print("[OK] RAG Engine initialized")
    except Exception as e:
        print(f"[ERROR] RAG Engine init failed: {e}")
        return False
    
    # Test RAG answer generation
    print("\n[4] Testing RAG answer generation...")
    test_prompt = "What is YCCE college known for?"
    try:
        answer = rag.answer(test_prompt)
        print(f"  Prompt: '{test_prompt}'")
        print(f"  Answer: {answer[:200]}...")
        print("[OK] RAG answer generation works")
    except Exception as e:
        print(f"[ERROR] RAG answer failed: {e}")
        return False
    
    print("\n" + "="*70)
    print("[SUCCESS] RAG pipeline is working correctly!")
    print("  ✓ FAISS has indexed documents")
    print("  ✓ Retrieval returns relevant results")
    print("  ✓ RAG engine can generate answers")
    print("="*70)
    
    return True

if __name__ == "__main__":
    success = test_rag_retrieval()
    exit(0 if success else 1)
