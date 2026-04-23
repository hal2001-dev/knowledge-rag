#!/usr/bin/env python3
"""
폴더 단위 일괄 색인 CLI (TASK-010).

지정 폴더에서 지원 문서(.pdf .txt .md .docx)를 **하위 폴더 포함 재귀** 탐색해
API `POST /ingest`로 순차 업로드한다. L1 중복 감지(SHA-256, ADR-005)로
재실행 시 409 응답은 자동 스킵.

사용 예시:
  python scripts/bulk_ingest.py --dir ./sample_docs
  python scripts/bulk_ingest.py --dir ./docs --no-recursive
  python scripts/bulk_ingest.py --dir ./docs --dry-run
  python scripts/bulk_ingest.py --dir ./docs --exclude "draft/" --exclude "archive/"
  python scripts/bulk_ingest.py --dir ./docs --title-from relpath --source-prefix "acme/"

결과 JSON: data/eval_runs/bulk_ingest_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from apps.config import get_settings  # noqa: E402

SUPPORTED_EXTS_DEFAULT = (".pdf", ".txt", ".md", ".docx")


def _normalize_includes(include_str: str | None) -> tuple[str, ...]:
    """'*.pdf *.txt' 같은 공백 구분 문자열을 확장자 튜플로."""
    if not include_str:
        return SUPPORTED_EXTS_DEFAULT
    tokens = include_str.replace(",", " ").split()
    exts = []
    for t in tokens:
        t = t.strip().lower()
        if t.startswith("*."):
            t = t[1:]
        if not t.startswith("."):
            t = "." + t
        exts.append(t)
    # 지원 확장자 교집합만 허용 (서버가 거부할 파일 미리 제외)
    filtered = tuple(e for e in exts if e in SUPPORTED_EXTS_DEFAULT)
    if not filtered:
        print(f"⚠ --include에서 지원 확장자가 없어 기본값 사용: {SUPPORTED_EXTS_DEFAULT}")
        return SUPPORTED_EXTS_DEFAULT
    return filtered


def _collect_files(
    root: Path, recursive: bool, includes: tuple[str, ...], excludes: list[re.Pattern]
) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    files: list[Path] = []
    for p in sorted(root.glob(pattern)):
        if not p.is_file():
            continue
        if p.suffix.lower() not in includes:
            continue
        rel = p.relative_to(root).as_posix()
        if any(rx.search(rel) for rx in excludes):
            continue
        files.append(p)
    return files


def _derive_title(path: Path, root: Path, mode: str) -> str:
    if mode == "filename":
        return path.name
    if mode == "relpath":
        return path.relative_to(root).as_posix()
    # stem (기본)
    return path.stem


def _check_api(api_base: str) -> bool:
    try:
        r = requests.get(f"{api_base}/health", timeout=3)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def main():
    parser = argparse.ArgumentParser(description="폴더 단위 일괄 색인 (TASK-010)")
    parser.add_argument("--dir", required=True, help="색인할 폴더")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--recursive", dest="recursive", action="store_true", default=True, help="하위 폴더 포함 (기본)")
    g.add_argument("--no-recursive", dest="recursive", action="store_false", help="최상위 폴더만")
    parser.add_argument("--include", default=None,
                        help="공백·쉼표 구분 확장자 목록 (예: '*.pdf *.md'). 기본: pdf/txt/md/docx")
    parser.add_argument("--exclude", action="append", default=[],
                        help="경로 정규식 제외 (반복 가능). 예: --exclude 'draft/' --exclude '_archive'")
    parser.add_argument("--title-from", default="stem", choices=["stem", "filename", "relpath"],
                        help="제목 자동 생성 기준. stem=확장자 제외 파일명, filename=확장자 포함, relpath=폴더/파일명")
    parser.add_argument("--source-prefix", default="",
                        help="source 메타에 붙일 접두 (예: 'acme/docs/')")
    parser.add_argument("--workers", type=int, default=1,
                        help="동시 업로드 수 (기본 1 순차). 2+ 시 Docling 메모리·L1 UNIQUE 충돌 주의")
    parser.add_argument("--dry-run", action="store_true", help="실제 업로드 없이 대상 파일만 출력")
    parser.add_argument("--fail-fast", action="store_true", help="첫 실패 시 전체 중단 (기본은 계속)")
    parser.add_argument("--api-base", default="http://localhost:8000", help="API 서버 URL")
    parser.add_argument("--report", default=None,
                        help="결과 JSON 저장 경로 (기본: data/eval_runs/bulk_ingest_<ts>.json)")
    args = parser.parse_args()

    root = Path(args.dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"✗ --dir 경로를 찾을 수 없음: {root}")
        sys.exit(2)

    includes = _normalize_includes(args.include)
    exclude_patterns = [re.compile(rx) for rx in args.exclude]
    files = _collect_files(root, args.recursive, includes, exclude_patterns)

    print(f"=== bulk_ingest ===")
    print(f"dir        : {root}")
    print(f"recursive  : {args.recursive}")
    print(f"include    : {includes}")
    print(f"exclude    : {args.exclude or '(없음)'}")
    print(f"title-from : {args.title_from}")
    print(f"source-prefix: {args.source_prefix or '(없음)'}")
    print(f"workers    : {args.workers}")
    print(f"api-base   : {args.api_base}")
    print(f"대상 파일  : {len(files)}개")
    print()

    if not files:
        print("대상 파일 없음. 종료.")
        sys.exit(0)

    if args.dry_run:
        print("[DRY RUN] 업로드 안 함. 대상 파일:")
        for p in files:
            print(f"  · {p.relative_to(root)}")
        sys.exit(0)

    # 파일 크기 상한 사전 체크 (서버 413 응답 방지)
    settings = get_settings()
    max_mb = settings.max_upload_size_mb

    # API health check
    if not _check_api(args.api_base):
        print(f"✗ API 서버에 연결 실패: {args.api_base}")
        print("  먼저 서버를 실행하세요: uvicorn apps.main:app")
        sys.exit(3)
    print(f"✓ API 응답 정상 ({args.api_base}/health)")
    print()

    # tqdm은 optional 의존성. 없으면 단순 카운터
    try:
        from tqdm import tqdm
        iterator = tqdm(files, desc="업로드", unit="file")
    except ImportError:
        iterator = files

    counters = {"ok": 0, "duplicate": 0, "failed": 0, "skipped_too_large": 0}
    results: list[dict] = []
    started_at = datetime.now(timezone.utc)
    t_start = time.monotonic()

    for p in iterator:
        rel = p.relative_to(root).as_posix()
        size_mb = p.stat().st_size / (1024 * 1024)
        result: dict = {"path": rel, "size_mb": round(size_mb, 2)}

        if size_mb > max_mb:
            counters["skipped_too_large"] += 1
            result["status"] = "skipped_too_large"
            result["reason"] = f"size {size_mb:.1f}MB > max {max_mb}MB"
            results.append(result)
            continue

        title = _derive_title(p, root, args.title_from)
        source_val = (args.source_prefix or "") + rel
        try:
            with open(p, "rb") as fh:
                resp = requests.post(
                    f"{args.api_base}/ingest",
                    files={"file": (p.name, fh.read())},
                    data={"title": title, "source": source_val},
                    timeout=1800,
                )
            if resp.status_code == 200:
                body = resp.json()
                counters["ok"] += 1
                result.update(status="ok", doc_id=body.get("doc_id"),
                              chunk_count=body.get("chunk_count"),
                              has_tables=body.get("has_tables"),
                              has_images=body.get("has_images"))
            elif resp.status_code == 409:
                detail = resp.json().get("detail", {})
                counters["duplicate"] += 1
                existing_id = detail.get("doc_id") if isinstance(detail, dict) else None
                result.update(status="duplicate", doc_id=existing_id)
            else:
                counters["failed"] += 1
                detail = None
                try:
                    detail = resp.json().get("detail")
                except Exception:
                    detail = resp.text[:200]
                result.update(status="failed", http_status=resp.status_code, error=detail)
                if args.fail_fast:
                    results.append(result)
                    print(f"\n✗ fail-fast: {rel} ({resp.status_code})")
                    break
        except requests.exceptions.RequestException as e:
            counters["failed"] += 1
            result.update(status="failed", error=str(e)[:200])
            if args.fail_fast:
                results.append(result)
                print(f"\n✗ fail-fast (네트워크): {rel}: {e}")
                break

        results.append(result)

    elapsed = time.monotonic() - t_start
    finished_at = datetime.now(timezone.utc)

    # 리포트 저장
    run_id = started_at.strftime("%Y-%m-%dT%H%M%SZ")
    report_path = Path(args.report) if args.report else (ROOT / f"data/eval_runs/bulk_ingest_{run_id}.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "dir": str(root),
        "recursive": args.recursive,
        "include": list(includes),
        "exclude": args.exclude,
        "title_from": args.title_from,
        "source_prefix": args.source_prefix,
        "workers": args.workers,
        "api_base": args.api_base,
        "total": len(files),
        **counters,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_sec": round(elapsed, 2),
        "results": results,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print("=== 결과 ===")
    print(f"total               : {len(files)}")
    print(f"ok (신규 색인)       : {counters['ok']}")
    print(f"duplicate (409 스킵) : {counters['duplicate']}")
    print(f"skipped_too_large    : {counters['skipped_too_large']}")
    print(f"failed               : {counters['failed']}")
    print(f"elapsed              : {elapsed:.1f}s")
    print(f"report               : {report_path}")

    # 실패가 있으면 exit code 1
    sys.exit(1 if counters["failed"] > 0 else 0)


if __name__ == "__main__":
    main()
