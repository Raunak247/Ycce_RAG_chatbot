#!/usr/bin/env python
"""
Test the IMPROVED RAG engine with better branch-specific retrieval
"""

from chatbot.rag_engine import SmartRAG

print("=" * 80)
print("✅ Testing Improved RAG Engine with Enhanced Branch Matching")
print("=" * 80)

rag = SmartRAG()

# Test query that should now work better
test_query = "give me the syllabus of 4th sem of aids branch"

print(f"\n📝 Query: {test_query}")
print("\n🔍 Generating query variants...")

# Show the variants being tested
variants = rag._generate_query_variants(test_query)
for i, v in enumerate(variants, 1):
    print(f"   [{i}] {v}")

print("\n🔄 Retrieving from FAISS...")
result = rag.answer(test_query)

print(f"\n✅ Answer Generated:")
print(f"   {result['answer'][:400]}\n")

print(f"📊 Metrics:")
print(f"   • Confidence: {result['confidence']*100:.1f}%")
print(f"   • Documents Retrieved: {result['docs_count']}")
print(f"   • Average Score: {result.get('avg_score', 'N/A')}")

print("\n" + "=" * 80)
print("🔧 DIAGNOSIS:")
print("=" * 80)

if result['confidence'] < 0.5:
    print("""
⚠️ Low confidence - AIDS 4th semester syllabus likely NOT in database

SOLUTION: You mentioned you personally stored data in FAISS.
         The AIDS 4th semester syllabus needs to be added.

OPTIONS:

1️⃣  USE MANUAL INGESTION TOOL (Recommended):
   
   If you have the AIDS syllabus as a file:
   
   python manual_ingest.py "path/to/aids_4th_sem.txt" "AIDS" "4th"
   
   Or for PDF:
   
   python manual_ingest.py "path/to/aids_4th_sem.pdf" "AIDS" "4th"

2️⃣  RE-CRAWL WEBSITE:
   
   python main_initial_crawl.py
   
   (Ensures all branch syllabi are fetched from the website)

3️⃣  CHECK EXISTING DOCUMENTS:
   
   python diagnose_faiss.py
   
   (Shows what's currently in the database)

After ingesting the AIDS syllabus, the chatbot will immediately be able to:
✅ Answer questions about AIDS 4th semester syllabus
✅ Provide course details
✅ Give structure and examination scheme information
    """)
else:
    print("✅ Confidence is good! Content is likely in the database.")
