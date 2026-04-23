#!/usr/bin/env python3
"""
PostgreSQL의 문서 목록을 기반으로 Qdrant 컬렉션을 재구축한다.

우선순위:
  1. data/uploads/{doc_id}.{ext} 원본이 있으면 그것으로 재인덱싱
  2. 없으면 data/markdown/{doc_id}.md (Docling 파싱 결과)로 재인덱싱 — HybridChunker 이점은 일부 제한됨

사용법: python pipeline/rebuild_index.py
       python pipeline/rebuild_index.py ./data/uploads
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from apps.config import get_settings
from packages.db.connection import init_db, get_engine
from packages.db.repository import list_documents
from packages.db.models import Base
from packages.llm.embeddings import build_embeddings
from packages.llm.chat import build_chat
from packages.vectorstore.qdrant_store import QdrantDocumentStore
from packages.rag.pipeline import RAGPipeline
from packages.rag.reranker import get_reranker
from packages.rag.sparse import SparseEmbedder
from sqlalchemy.orm import sessionmaker


def _resolve_source_file(doc_id: str, upload_dir: Path, markdown_dir: Path) -> Path | None:
    """원본 파일 > 마크다운 순으로 재인덱싱용 입력을 결정."""
    originals = list(upload_dir.glob(f"{doc_id}.*"))
    if originals:
        return originals[0]
    md = markdown_dir / f"{doc_id}.md"
    if md.exists():
        return md
    return None


def main():
    settings = get_settings()
    upload_dir = Path(sys.argv[1] if len(sys.argv) > 1 else settings.upload_dir)
    markdown_dir = Path(settings.markdown_dir)

    init_db(settings.postgres_url)
    Base.metadata.create_all(bind=get_engine())

    embeddings = build_embeddings(settings)

    # 기존 컬렉션 삭제 후 재생성
    from qdrant_client import QdrantClient
    client = QdrantClient(url=settings.qdrant_url)
    if settings.qdrant_collection in [c.name for c in client.get_collections().collections]:
        client.delete_collection(settings.qdrant_collection)
        print(f"기존 컬렉션 삭제: {settings.qdrant_collection}")

    sparse = (
        SparseEmbedder(model_name=settings.sparse_model_name)
        if settings.search_mode == "hybrid"
        else None
    )
    store = QdrantDocumentStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embeddings=embeddings,
        search_mode=settings.search_mode,
        sparse_embedder=sparse,
    )
    print(f"search_mode: {settings.search_mode}")
    llm = build_chat(settings)
    reranker = get_reranker(backend=settings.reranker_backend)
    pipeline = RAGPipeline(store=store, llm=llm, reranker=reranker, settings=settings)

    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        records = list_documents(db)

    print(f"재구축 대상: {len(records)}개 문서")
    print(f"입력 탐색 경로: {upload_dir} → {markdown_dir} (fallback)\n")

    ok = skip = 0
    for record in records:
        src = _resolve_source_file(record.doc_id, upload_dir, markdown_dir)
        if src is None:
            print(f"  ⚠ 원본/마크다운 모두 없음, 스킵: {record.doc_id} {record.title!r}")
            skip += 1
            continue

        fallback = " (markdown fallback)" if src.suffix.lower() == ".md" and src.parent == markdown_dir else ""
        print(f"  → {record.title!r} ← {src.name}{fallback}")
        new_record = pipeline.ingest(
            file_path=str(src),
            title=record.title,
            source=record.source or "",
            doc_id=record.doc_id,
            content_hash=record.content_hash,
        )
        # chunk_count 등 최신화 (DB 기존 레코드는 삭제하지 않고 update는 별도 함수가 필요하므로
        # 재색인 스크립트는 벡터 인덱스 재생성에만 집중한다. DB row는 기존 값을 유지.)
        print(f"     청크 수: {new_record.chunk_count} (테이블: {new_record.has_tables}, "
              f"이미지: {new_record.has_images})")
        ok += 1

    print(f"\n인덱스 재구축 완료: 성공 {ok}건, 스킵 {skip}건")


if __name__ == "__main__":
    main()
