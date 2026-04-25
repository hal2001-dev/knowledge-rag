"""단건 동기 색인 — 큐/워커 우회. Qdrant upsert traceback 회수용 일회성 디버그 스크립트.

사용:
  python scripts/debug_single_ingest.py <pdf_path> [<title>]

특징:
  - apps.dependencies.get_pipeline()을 그대로 사용 → 운영과 동일 임베더·SEARCH_MODE.
  - documents/ingest_jobs DB row는 만들지 않음. 순수 Qdrant 경로만 검증.
  - 예외는 raise 그대로 — traceback 끝까지 출력.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from apps.dependencies import get_pipeline  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/debug_single_ingest.py <pdf_path> [title]")
        return 2

    pdf = Path(sys.argv[1]).expanduser().resolve()
    if not pdf.is_file():
        print(f"파일 없음: {pdf}")
        return 2
    title = sys.argv[2] if len(sys.argv) >= 3 else pdf.stem

    pipeline = get_pipeline()
    doc_id = str(uuid.uuid4())
    print(f"[debug] doc_id={doc_id} file={pdf} title={title}")
    record = pipeline.ingest(
        file_path=str(pdf),
        title=title,
        source=f"debug/{pdf.name}",
        doc_id=doc_id,
    )
    print(f"[debug] OK chunks={record.chunk_count} tables={record.has_tables} images={record.has_images}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
