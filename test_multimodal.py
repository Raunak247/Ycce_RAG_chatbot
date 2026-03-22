# -*- coding: utf-8 -*-
"""
Test script for multimodal FAISS functionality.
Tests: Text ingestion + Image embedding + FAISS storage
"""

import os
import json
from vectordb.vectordb_manager import VectorDBManager
from vectordb.image_embeddings import embed_image_from_url
from langchain_core.documents import Document

# Test config
TEST_FAISS_PATH = "data/faiss_index"
MEDIA_REGISTRY = "data/test_media_registry.json"

# Sample test URLs
TEST_URLS = {
    "text": [
        "https://ycce.edu/",
    ],
    "images": [
        "https://ycce.edu/wp-content/uploads/2024/02/Gallery.jpg",
        "https://ycce.edu/wp-content/uploads/2024/03/Classroom.jpeg",
    ]
}

def test_multimodal_ingestion():
    """Test multimodal FAISS: text + images."""
    
    print("\n" + "="*60)
    print("[TEST] Multimodal FAISS Integration")
    print("="*60)
    
    # Initialize FAISS
    db = VectorDBManager(persist_directory=TEST_FAISS_PATH)
    media_records = []
    
    # -------- TEST 1: Add sample documents (simulate text ingestion) --------
    print("\n[TEST 1] Adding text documents...")
    try:
        sample_docs = [
            Document(
                page_content="YCCE is a leading educational institution in India.",
                metadata={"source": "https://ycce.edu/", "type": "html"}
            ),
            Document(
                page_content="The college offers programs in engineering and management.",
                metadata={"source": "https://ycce.edu/programs", "type": "html"}
            ),
        ]
        db.add_documents(sample_docs)
        print(f"[OK] Added {len(sample_docs)} text documents")
    except Exception as e:
        print(f"[ERROR] Text ingestion failed: {e}")
        return False
    
    # -------- TEST 2: Embed test images --------
    print("\n[TEST 2] Embedding images with CLIP...")
    image_count = 0
    image_failed = 0
    
    for img_url in TEST_URLS["images"]:
        try:
            print(f"  [IMG] Processing: {img_url.split('/')[-1][:50]}...")
            embedding = embed_image_from_url(img_url)
            
            if embedding:
                # Store in FAISS
                metadata = {
                    "source_url": img_url,
                    "content_type": "image"
                }
                db.upsert_image_embedding(embedding, metadata)
                media_records.append(metadata)
                image_count += 1
                print(f"  [OK] Embedded: dim={len(embedding)}")
            else:
                image_failed += 1
                print(f"  [FAIL] Could not embed image")
                
        except Exception as e:
            image_failed += 1
            print(f"  [ERROR] {str(e)[:60]}")
    
    print(f"\n[RESULT] Images processed: {image_count} success, {image_failed} failed")
    
    # -------- TEST 3: Persist FAISS --------
    print("\n[TEST 3] Persisting FAISS to disk...")
    try:
        db.persist()
        if os.path.exists(TEST_FAISS_PATH):
            size_mb = sum(os.path.getsize(os.path.join(TEST_FAISS_PATH, f)) 
                          for f in os.listdir(TEST_FAISS_PATH)) / (1024*1024)
            print(f"[OK] FAISS persisted ({size_mb:.2f} MB)")
        else:
            print("[WARN] FAISS path not found after persist")
    except Exception as e:
        print(f"[ERROR] Persist failed: {e}")
        return False
    
    # -------- TEST 4: Create media registry --------
    print("\n[TEST 4] Creating media registry...")
    if media_records:
        with open(MEDIA_REGISTRY, "w", encoding="utf-8") as f:
            json.dump(media_records, f, indent=2)
        print(f"[OK] Saved {len(media_records)} image URLs to media_registry.json")
    
    # -------- TEST 5: Test similarity search --------
    print("\n[TEST 5] Testing FAISS search...")
    try:
        # Search for similar documents
        query = "educational programs"
        result = db.similarity_search(query)
        if result and result[0]:
            content, score = result
            print(f"[OK] Found result with score: {score}")
            print(f"     Content: {content[:60]}...")
            if "Image" in str(content):
                print(f"     [IMAGE] Document contains image reference")
        else:
            print(f"[WARN] No results found for query: '{query}'")
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        return False
    
    # -------- SUMMARY --------
    print("\n" + "="*60)
    print("[SUCCESS] Multimodal FAISS test completed!")
    print(f"  - FAISS path: {TEST_FAISS_PATH}")
    print(f"  - Media registry: {MEDIA_REGISTRY}")
    print(f"  - Text docs: {len(sample_docs)}")
    print(f"  - Images embedded: {image_count}")
    print("="*60)
    
    return True


if __name__ == "__main__":
    test_multimodal_ingestion()
