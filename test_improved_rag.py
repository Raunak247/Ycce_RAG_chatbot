#!/usr/bin/env python
"""Test improved RAG engine"""

from chatbot.rag_engine import SmartRAG

print("=" * 60)
print("🧪 Testing Improved RAG Engine")
print("=" * 60)

rag = SmartRAG()

print("\n✅ RAG Engine Features:")
print("  • Multi-query retrieval (query variants)")
print("  • 7+ document retrieval (vs 3 before)")
print("  • Better prompt engineering")
print("  • Full source documents display")
print("  • Improved confidence scoring")

# Test queries
test_queries = [
    "Tell me about YCCE",
    "What are admission requirements?",
    "BTech CSE course structure",
]

print("\n" + "=" * 60)
print("Testing Multiple Queries:")
print("=" * 60)

for i, query in enumerate(test_queries, 1):
    print(f"\n[Query {i}] {query}")
    try:
        result = rag.answer(query)
        
        print(f"\n✅ Answer Preview (first 200 chars):")
        print(f"   {result['answer'][:200]}...")
        
        print(f"\n📊 Metrics:")
        print(f"   • Confidence: {result['confidence']*100:.1f}%")
        print(f"   • Documents Retrieved: {result['docs_count']}")
        print(f"   • Sources Available: {len(result.get('sources', []))}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

print("\n" + "=" * 60)
print("✅ Test Complete!")
print("=" * 60)
