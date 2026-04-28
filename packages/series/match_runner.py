"""TASK-020 (ADR-029): series_match_for_doc 진입점.

매칭 결과를 DB에 반영(신규 시리즈 생성/기존 시리즈에 attach + status 마킹).
indexer_worker 의 BackgroundTasks 체인 마지막 단계에서 호출된다. 실패는 격리(인덱싱 자체는 성공).
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from packages.code.logger import get_logger
from packages.db import repository as repo
from packages.db.models import DocumentRecord
from packages.series.matcher import (
    Confidence,
    DocLite,
    find_candidates,
)

logger = get_logger(__name__)


def _to_lite(record: DocumentRecord) -> DocLite:
    return DocLite(
        doc_id=record.doc_id,
        title=record.title or "",
        source=record.source or "",
        doc_type=record.doc_type or "book",
        series_id=record.series_id,
        series_match_status=record.series_match_status or "none",
    )


def _new_series_id() -> str:
    return f"ser_{uuid.uuid4().hex[:12]}"


def _slugify_title(title: str, fallback: str) -> str:
    """공통 prefix가 너무 짧거나 비어있을 때 fallback 처리."""
    cleaned = re.sub(r"\s+", " ", (title or "").strip())
    if len(cleaned) < 3:
        return fallback
    return cleaned[:200]


def series_match_for_doc(
    db: Session,
    doc_id: str,
    *,
    qdrant_payload_setter=None,
) -> dict:
    """target 문서에 대해 시리즈 매칭을 시도하고 DB·payload를 갱신.

    qdrant_payload_setter: 시그니처 `(doc_ids: list[str], series_id: str, series_title: str) -> None`.
        None이면 payload 갱신을 건너뜀(테스트·드라이런용). 실패해도 DB 트랜잭션은 롤백 안 함.

    반환: 결과 요약 dict (logging·테스트 검증용). 매칭 미발생/스킵도 dict로 반환(예외 throw 안 함).
    """
    target = repo.get_document(db, doc_id)
    if target is None:
        return {"status": "skipped", "reason": "doc_not_found", "doc_id": doc_id}

    # rejected 또는 이미 묶인 문서는 재시도 안 함 (관리자 의사 존중)
    if (target.series_match_status or "none") in ("rejected", "auto_attached", "confirmed"):
        return {
            "status": "skipped",
            "reason": f"existing_status={target.series_match_status}",
            "doc_id": doc_id,
        }

    population_records = repo.list_documents(db)
    population = [_to_lite(r) for r in population_records]
    target_lite = _to_lite(target)

    candidate = find_candidates(target_lite, population)
    if candidate is None:
        # 매칭 없음 — none 유지
        return {"status": "no_candidate", "doc_id": doc_id}

    if candidate.confidence == Confidence.LOW:
        return {
            "status": "low_confidence",
            "doc_id": doc_id,
            "confidence": candidate.confidence.value,
        }

    if candidate.confidence == Confidence.MEDIUM:
        # 검수 큐에만 등록 — series_id NULL 유지
        repo.update_match_status(db, doc_id, "suggested")
        return {
            "status": "suggested",
            "doc_id": doc_id,
            "candidate_series_id": candidate.series_id,
            "candidate_title": candidate.series_title,
            "confidence": candidate.confidence.value,
        }

    # HIGH — 자동 묶기
    if candidate.series_id is None:
        # 신규 시리즈 생성 — peer doc도 같이 묶기
        new_id = _new_series_id()
        title = _slugify_title(candidate.series_title, target.title)
        repo.create_series(
            db,
            series_id=new_id,
            title=title,
            cover_doc_id=target.doc_id,
            series_type="book",
        )
        # 자기 attach
        repo.attach_to_series(
            db,
            target.doc_id,
            series_id=new_id,
            volume_number=candidate.volume_number,
            volume_title=target.title,
            match_status="auto_attached",
        )
        # peer attach (멤버에 자기 doc_id가 첫번째이므로 나머지 처리)
        affected_doc_ids = [target.doc_id]
        for peer_id in candidate.members:
            if peer_id == target.doc_id:
                continue
            peer = repo.get_document(db, peer_id)
            if peer is None:
                continue
            from packages.series.matcher import extract_volume_number
            peer_vol = extract_volume_number(peer.title) or extract_volume_number(peer.source)
            repo.attach_to_series(
                db,
                peer_id,
                series_id=new_id,
                volume_number=peer_vol,
                volume_title=peer.title,
                match_status="auto_attached",
            )
            affected_doc_ids.append(peer_id)
        series_id_used = new_id
    else:
        # 기존 시리즈에 자기만 추가
        repo.attach_to_series(
            db,
            target.doc_id,
            series_id=candidate.series_id,
            volume_number=candidate.volume_number,
            volume_title=target.title,
            match_status="auto_attached",
        )
        affected_doc_ids = [target.doc_id]
        series_id_used = candidate.series_id

    # Qdrant payload 동기화 (실패는 격리 — DB는 그대로 둠)
    if qdrant_payload_setter is not None:
        series_record = repo.get_series(db, series_id_used)
        try:
            qdrant_payload_setter(
                affected_doc_ids,
                series_id_used,
                series_record.title if series_record else candidate.series_title,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"series payload 동기화 실패 series_id={series_id_used} "
                f"docs={affected_doc_ids}: {exc}"
            )

    return {
        "status": "auto_attached",
        "doc_id": doc_id,
        "series_id": series_id_used,
        "members": affected_doc_ids,
        "confidence": candidate.confidence.value,
    }
