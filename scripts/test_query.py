#!/usr/bin/env python3
"""
질문을 입력받아 RAG 파이프라인으로 답변을 출력하는 CLI 스크립트.
사용법: python scripts/test_query.py "질문 내용"
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from apps.config import get_settings
from packages.llm.embeddings import build_embeddings
from packages.llm.chat import build_chat
from packages.vectorstore.qdrant_store import QdrantDocumentStore
from packages.rag.pipeline import RAGPipeline


def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/test_query.py \"질문\"")
        sys.exit(1)

    question = sys.argv[1]
    settings = get_settings()

    embeddings = build_embeddings(settings)
    store = QdrantDocumentStore(settings.qdrant_url, settings.qdrant_collection, embeddings)
    llm = build_chat(settings)
    pipeline = RAGPipeline(store=store, llm=llm, settings=settings)

    result = pipeline.query(question)

    print(f"\n질문: {question}")
    print(f"\n답변:\n{result['answer']}")
    print(f"\n소스 ({len(result['sources'])}개, {result['latency_ms']}ms):")
    for s in result["sources"]:
        print(f"  [{s['content_type']}] {s['title']} p.{s['page']} score={s['score']:.4f}")
        print(f"    {s['excerpt'][:100]}...")


if __name__ == "__main__":
    main()
