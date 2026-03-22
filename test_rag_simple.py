#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick RAG verification test"""

from chatbot.rag_engine import SmartRAG

def test_rag():
    print("\n[TEST] Initializing SmartRAG Engine...")
    try:
        rag = SmartRAG()
        print("[OK] SmartRAG loaded successfully\n")
        
        # Test a simple query
        query = "What is YCCE?"
        print(f"[QUERY] {query}")
        answer = rag.answer(query)
        print(f"[ANSWER] {answer}\n")
        return True
    except Exception as e:
        print(f"[ERROR] {e}\n")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_rag()
    exit(0 if success else 1)
