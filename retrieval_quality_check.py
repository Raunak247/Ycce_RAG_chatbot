#!/usr/bin/env python
"""Run a strict retrieval quality check against index.faiss/index.pkl."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import List

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chatbot.rag_engine import SmartRAG

DEFAULT_QUERIES = [
    "Who is the HOD of AIDS department?",
    "Give me academic calendar link",
    "What is YCCE full form?",
    "Show faculty list of computer technology department",
    "Provide syllabus details for semester 4 AIDS",
]


def load_queries(path: str | None) -> List[str]:
    if not path:
        return DEFAULT_QUERIES

    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Queries file not found: {p}")

    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
        raise ValueError("JSON query file must contain an array of strings")

    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def run_check(queries: List[str], required_rate: float) -> int:
    rag = SmartRAG()

    if hasattr(rag.vectordb, "is_index_ready") and not rag.vectordb.is_index_ready():
        health = getattr(rag.vectordb, "index_health", {}) or {}
        print("[FAIL] Index is not healthy. Rebuild/repair index.faiss and index.pkl first.")
        print(
            "        "
            f"vectors={health.get('vector_count', 0)} "
            f"id_map={health.get('id_map_count', 0)} "
            f"docstore={health.get('docstore_count', 0)}"
        )
        return 2

    passed = 0
    print("=" * 90)
    print("RETRIEVAL QUALITY CHECK")
    print("=" * 90)

    for idx, query in enumerate(queries, start=1):
        context, docs = rag._retrieve_context(query, k=8)
        intent = rag._detect_query_intent(query)
        quality = rag._retrieval_quality_report(query, docs, intent=intent)

        status = "PASS" if quality["passed"] else "FAIL"
        if quality["passed"]:
            passed += 1

        print(f"[{idx:02d}] {status} | {query}")
        print(
            "     "
            f"docs={len(docs)} overlap={quality['best_overlap']:.2f} "
            f"semantic={quality['best_semantic']:.2f} "
            f"supported_docs={quality['supported_docs']}"
        )
        if not context:
            print("     reason=no context returned")
        elif not quality["passed"]:
            print(f"     reason={quality['reason']}")

    total = len(queries)
    pass_rate = (passed / total) if total else 0.0

    print("-" * 90)
    print(f"Result: {passed}/{total} passed ({pass_rate * 100:.1f}%)")
    print(f"Required pass rate: {required_rate * 100:.1f}%")

    if pass_rate >= required_rate:
        print("[OK] Retrieval quality check passed")
        return 0

    print("[FAIL] Retrieval quality check failed")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict retrieval quality check for YCCE FAISS index")
    parser.add_argument("--queries-file", help="Path to .txt or .json file containing test prompts")
    parser.add_argument(
        "--required-pass-rate",
        type=float,
        default=1.0,
        help="Required pass rate between 0 and 1 (default: 1.0)",
    )
    args = parser.parse_args()

    if args.required_pass_rate < 0 or args.required_pass_rate > 1:
        raise ValueError("--required-pass-rate must be between 0 and 1")

    queries = load_queries(args.queries_file)
    if not queries:
        raise ValueError("No queries found for quality check")

    return run_check(queries, args.required_pass_rate)


if __name__ == "__main__":
    raise SystemExit(main())
