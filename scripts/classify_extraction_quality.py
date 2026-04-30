"""ISSUE-010: documents.extraction_quality 일괄 평가/백필.

휴리스틱:
- markdown 파일이 없으면          → 'partial' (보수적, 사람 검토 필요)
- markdown_size < 30KB             → 'scan_only' (TOC·판권만 추출된 스캔본 패턴)
- chunk_count > 0 이고
  size_per_chunk < 150 bytes        → 'scan_only' (페이지번호·OCR 노이즈 조각만)
- 그 외                             → 'ok'

`--dry-run` 으로 미리 보고, 미지정 시 UPDATE 적용.
`--only-empty` 로 NULL/미평가 행만 처리.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


SCAN_SIZE_THRESHOLD = 30_000        # markdown 30KB 미만 → 스캔본 추정
SCAN_AVG_CHUNK_THRESHOLD = 150      # chunk 평균 길이 150B 미만 → 노이즈 조각만


def classify(md_size: int, chunk_count: int, md_exists: bool) -> str:
    if not md_exists:
        return "partial"
    if md_size < SCAN_SIZE_THRESHOLD:
        return "scan_only"
    if chunk_count and (md_size / chunk_count) < SCAN_AVG_CHUNK_THRESHOLD:
        return "scan_only"
    return "ok"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="UPDATE 없이 출력만")
    p.add_argument("--only-empty", action="store_true", help="extraction_quality IS NULL 만 평가")
    p.add_argument(
        "--markdown-dir",
        default="data/markdown",
        help="마크다운 디렉토리(기본 data/markdown)",
    )
    args = p.parse_args()

    load_dotenv()
    md_dir = Path(args.markdown_dir)
    if not md_dir.exists():
        print(f"❌ markdown 디렉토리 없음: {md_dir}", file=sys.stderr)
        return 2

    e = create_engine(os.environ["POSTGRES_URL"])

    where = "WHERE extraction_quality IS NULL" if args.only_empty else ""
    with e.connect() as c:
        rows = c.execute(text(
            f"SELECT doc_id, title, chunk_count, extraction_quality FROM documents {where}"
        )).fetchall()

    transitions: dict[str, int] = {"ok": 0, "partial": 0, "scan_only": 0}
    changed: list[tuple[str, str, str, str, int, int]] = []  # (doc_id, title, prev, new, size, chunks)

    for r in rows:
        f = md_dir / f"{r.doc_id}.md"
        size = f.stat().st_size if f.exists() else 0
        new_q = classify(size, r.chunk_count or 0, f.exists())
        prev = r.extraction_quality
        if prev != new_q:
            changed.append((r.doc_id, r.title, prev or "(NULL)", new_q, size, r.chunk_count or 0))
        transitions[new_q] += 1

    print(f"평가 대상: {len(rows)}건")
    print(f"분류: ok={transitions['ok']}  partial={transitions['partial']}  scan_only={transitions['scan_only']}")
    print(f"변경 예정: {len(changed)}건")
    print()
    for did, title, prev, new, size, cc in sorted(changed, key=lambda x: (x[3], x[4])):
        print(f"  {prev:>9} → {new:<9}  size={size/1024:>6.1f}KB  chunks={cc:>3}  {title[:40]}  ({did[:8]}…)")

    if args.dry_run:
        print("\n(dry-run) UPDATE 미적용")
        return 0

    if not changed:
        print("\n변경 없음 — UPDATE 생략")
        return 0

    with e.begin() as c:
        for did, _, _, new, _, _ in changed:
            c.execute(
                text("UPDATE documents SET extraction_quality = :q WHERE doc_id = :d"),
                {"q": new, "d": did},
            )
    print(f"\n✅ {len(changed)}건 UPDATE 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
