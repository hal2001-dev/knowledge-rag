#!/usr/bin/env python3
"""
샘플 파일을 직접 파이프라인으로 수집하는 CLI 스크립트.
사용법: python scripts/ingest_sample.py <파일경로> <제목>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from apps.config import get_settings
from packages.db.connection import init_db
from packages.db.models import Base
from packages.db.connection import get_engine
from packages.db.repository import create_document
from packages.llm.embeddings import build_embeddings
from packages.llm.chat import build_chat
from packages.vectorstore.qdrant_store import QdrantDocumentStore
from packages.rag.pipeline import RAGPipeline


def main():
    if len(sys.argv) < 3:
        print("사용법: python scripts/ingest_sample.py <파일경로> <제목>")
        sys.exit(1)

    file_path = sys.argv[1]
    title = sys.argv[2]

    settings = get_settings()
    init_db(settings.postgres_url)
    Base.metadata.create_all(bind=get_engine())

    embeddings = build_embeddings(settings)
    store = QdrantDocumentStore(settings.qdrant_url, settings.qdrant_collection, embeddings)
    llm = build_chat(settings)
    pipeline = RAGPipeline(store=store, llm=llm, settings=settings)

    print(f"수집 중: {file_path}")
    record = pipeline.ingest(file_path=file_path, title=title)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        create_document(db, record)

    print(f"완료: doc_id={record.doc_id}, 청크={record.chunk_count}, "
          f"테이블={record.has_tables}, 이미지={record.has_images}")


if __name__ == "__main__":
    main()
