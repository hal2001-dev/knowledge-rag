"""TASK-020 (ADR-029): 시리즈 백필 스크립트.

기존 인덱스에 대해 휴리스틱을 일괄 실행한다. `--apply`가 없으면 dry-run (제안만 보고서로).

사용:
    # dry-run — 어떤 문서가 어떤 시리즈에 묶일지만 보기
    python scripts/suggest_series.py

    # 실 적용 — high 신뢰도는 자동, medium은 suggested로 큐잉
    python scripts/suggest_series.py --apply

결과:
    data/eval_runs/suggest_series_<ISO>.json — 처리 요약 + 케이스별 분류
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from apps.config import get_settings  # noqa: E402
from packages.code.logger import get_logger  # noqa: E402
from packages.db import repository as repo  # noqa: E402
from packages.db.connection import init_db  # noqa: E402
import packages.db.connection as dbc  # noqa: E402
from packages.series import series_match_for_doc  # noqa: E402
from packages.vectorstore.qdrant_store import QdrantDocumentStore  # noqa: E402

logger = get_logger(__name__)


def _build_setter(apply: bool, store: QdrantDocumentStore | None):
    if not apply or store is None:
        return None
    return store.set_series_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실 적용 (기본은 dry-run, DB·payload 변경 없음)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리 대상 문서 수 상한 (대형 인덱스 단계별 적용용)",
    )
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.postgres_url)

    store: QdrantDocumentStore | None = None
    if args.apply:
        store = QdrantDocumentStore(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            embedding_dim=1536,  # 프로덕션 OpenAI dim — backend별 dim는 store가 자체 검증
        )
    setter = _build_setter(args.apply, store)

    db = dbc._SessionLocal()
    try:
        all_docs = repo.list_documents(db)
        # 이미 attach/confirmed/rejected 인 건 매처 진입점이 알아서 skip — 단 dry-run에서도 같은 정책
        targets = [d for d in all_docs if (d.series_match_status or "none") == "none"]
        if args.limit:
            targets = targets[: args.limit]

        results: list[dict] = []
        counters = {"auto_attached": 0, "suggested": 0, "low_confidence": 0, "no_candidate": 0, "skipped": 0}
        for d in targets:
            if args.apply:
                r = series_match_for_doc(db, d.doc_id, qdrant_payload_setter=setter)
            else:
                # dry-run: 매처만 호출, DB 갱신 X
                from packages.series.matcher import find_candidates
                from packages.series.match_runner import _to_lite
                pop = [_to_lite(x) for x in all_docs]
                target_lite = _to_lite(d)
                cand = find_candidates(target_lite, pop)
                if cand is None:
                    r = {"status": "no_candidate", "doc_id": d.doc_id}
                elif cand.confidence.value == "low":
                    r = {"status": "low_confidence", "doc_id": d.doc_id, "candidate_title": cand.series_title}
                elif cand.confidence.value == "medium":
                    r = {
                        "status": "suggested",
                        "doc_id": d.doc_id,
                        "candidate_series_id": cand.series_id,
                        "candidate_title": cand.series_title,
                    }
                else:
                    r = {
                        "status": "auto_attached",
                        "doc_id": d.doc_id,
                        "members": cand.members,
                        "candidate_title": cand.series_title,
                    }
            results.append(r | {"title": d.title, "source": d.source})
            status = r.get("status", "skipped")
            counters[status] = counters.get(status, 0) + 1

        out_dir = ROOT / "data" / "eval_runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        out_path = out_dir / f"suggest_series_{ts}.json"
        out_path.write_text(
            json.dumps(
                {
                    "mode": "apply" if args.apply else "dry_run",
                    "total_targets": len(targets),
                    "counters": counters,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(f"== suggest_series ({'apply' if args.apply else 'dry-run'}) ==")
        print(f"  대상: {len(targets)}건")
        for k, v in counters.items():
            print(f"  - {k}: {v}")
        print(f"  리포트: {out_path}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
