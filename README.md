# YCCE Smart RAG Chatbot

This project is a FAISS-backed Retrieval-Augmented Generation system that answers YCCE questions from indexed chunks stored in `index.faiss` and `index.pkl`.

## What Is Implemented

The chatbot now uses a full, practical RAG pipeline instead of single-step similarity lookup.

1. Query understanding and correction
2. Multi-variant retrieval against FAISS
3. Hybrid reranking (lexical + semantic + source quality)
4. Evidence augmentation (sentence-level extraction)
5. Grounded answer generation with citations
6. Validation and fallback (extractive, no hallucination)
7. Response packaging with relevant links + evidence reasons
8. Quality scoring in percentage for retrieval and generation

## RAG Concepts Used

The code in `chatbot/rag_engine.py` applies the following RAG concepts end-to-end:

1. Chunk-based semantic retrieval from vector index (`index.faiss`)
2. Metadata-grounded retrieval using docstore (`index.pkl`)
3. Query rewriting and variant expansion for robust recall
4. Typo/semantic correction (normalization + fuzzy token correction)
5. Hybrid scoring (token overlap + embedding cosine similarity)
6. Intent-aware source balancing (`html`, `pdf`, `xlsx`, `csv`)
7. Low-signal/noise chunk suppression
8. Source deduplication and source diversity constraints
9. Sentence-level evidence mining and context compression
10. Citation-constrained generation (`[S1]`, `[S2]`, ...)
11. Grounding checks (answer-evidence overlap)
12. Citation coverage checks
13. Query-answer alignment checks
14. Deterministic fallback extraction when generation is weak
15. Confidence scoring + quality percentages

## Accuracy and Speed Strategy

No RAG system can guarantee absolute accuracy on all queries. This implementation is designed to maximize practical accuracy and robustness by:

1. Preferring authoritative chunks for role/factual questions
2. Rejecting weak evidence with safe response fallback
3. Returning evidence and links so answers are inspectable
4. Avoiding unsupported claims when context is missing
5. Using fast deterministic paths for some factual intents

## Quality Percentages (New Output)

Every answer now includes:

1. `retrieval_quality_percentage`
2. `generation_quality_percentage`

These are computed from retrieval support, semantic relevance, grounding, citation coverage, alignment, and confidence.

## API/Result Fields

A typical answer dictionary now contains:

1. `answer`
2. `sources`
3. `confidence`
4. `docs_count`
5. `avg_score`
6. `retrieval_quality` (when available)
7. `grounding_score` (path-dependent)
8. `citation_coverage` (path-dependent)
9. `alignment_score` (path-dependent)
10. `retrieval_quality_percentage`
11. `generation_quality_percentage`

## Data Dependencies

The chatbot answers from persisted vector artifacts:

1. `data/faiss_index/index.faiss`
2. `data/faiss_index/index.pkl`

If these are missing, stale, or noisy, answer quality will degrade.

## Run and Test

From the project root (`YCCE_Chatbot`):

```powershell
d:/ycce_chatbot/.venv/Scripts/python.exe -m py_compile chatbot/rag_engine.py
```

Quick smoke test:

```powershell
d:/ycce_chatbot/.venv/Scripts/python.exe -c "from chatbot.rag_engine import SmartRAG; r=SmartRAG(); print(r.answer('where is ycce located'))"
```

## Notes for Evaluation

1. Test with real user typos and shorthand (for example `calender`, `admisson`, `departmant`, `semster`).
2. Compare answers with official YCCE sources and evidence blocks.
3. Track percentage trends over multiple test prompts.

If you need stricter production behavior, set policy to return unknown whenever grounding or alignment drops below threshold.
