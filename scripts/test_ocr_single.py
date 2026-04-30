"""ISSUE-010 단권 OCR 테스트 — macOS Vision(ocrmac) + force_full_page_ocr.

DB·Qdrant·프로덕션 markdown 건드리지 않음. 결과는
`data/markdown_ocr_test/{doc_id}.md` 에만 저장.

사용법:
  .venv/bin/python scripts/test_ocr_single.py 365a35c9-6123-4ec0-8eee-dd55cfd72573
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    OcrMacOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


OUT_DIR = Path("data/markdown_ocr_test")
SRC_DIR = Path("data/uploads")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("doc_id")
    p.add_argument("--lang", default="ko-KR,en-US",
                   help="comma-separated BCP-47 codes (Vision)")
    args = p.parse_args()

    src = SRC_DIR / f"{args.doc_id}.pdf"
    if not src.exists():
        print(f"❌ 원본 PDF 없음: {src}", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.doc_id}.md"

    pdf_opts = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        ocr_options=OcrMacOptions(
            lang=[s.strip() for s in args.lang.split(",") if s.strip()],
            force_full_page_ocr=True,
        ),
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts)}
    )

    src_kb = src.stat().st_size / 1024
    print(f"▶ 변환 시작: {src.name} ({src_kb:.0f} KB)")
    print(f"  ocr=ocrmac (Vision) · lang={args.lang} · force_full_page_ocr=True")
    t0 = time.monotonic()

    result = converter.convert(str(src))
    md = result.document.export_to_markdown()
    out.write_text(md, encoding="utf-8")

    dt = time.monotonic() - t0
    out_kb = out.stat().st_size / 1024
    print(f"✓ 완료 — {dt:.1f}s")
    print(f"  결과: {out} ({out_kb:.1f} KB, {len(md):,} chars)")
    print()

    # 비교: 현 production markdown
    prod = Path("data/markdown") / f"{args.doc_id}.md"
    if prod.exists():
        prod_kb = prod.stat().st_size / 1024
        ratio = out_kb / prod_kb if prod_kb > 0 else float("inf")
        print(f"비교 — 기존 추출: {prod_kb:.1f} KB → OCR: {out_kb:.1f} KB ({ratio:.1f}x)")
    print()

    # 본문 샘플 — 처음/중간/끝
    lines = md.splitlines()
    n = len(lines)
    print(f"=== 첫 30줄 ===")
    for ln in lines[:30]:
        print(ln)
    if n > 100:
        print(f"\n=== 중간(L{n//2}~+25) ===")
        for ln in lines[n//2:n//2+25]:
            print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
