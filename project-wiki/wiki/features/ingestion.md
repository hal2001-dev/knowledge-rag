# 문서 수집 (Ingestion)

**상태**: active
**마지막 업데이트**: 2026-04-26
**관련 페이지**: [endpoints.md](../api/endpoints.md), [spec.md](../data/spec.md), [schema.md](../data/schema.md), [setup.md](../onboarding/setup.md)

## 요약

문서 색인 진입점은 두 가지입니다.
1) **HTTP** `POST /ingest` — 단건 업로드 (FastAPI 필요)
2) **CLI** `scripts/bulk_ingest.py` — 폴더 단위 일괄 색인 (단건 HTTP 반복 또는 큐 직접 enqueue)

L1 중복 감지(SHA-256, ADR-005)로 동일 내용 파일은 자동 스킵됩니다(409 또는 `duplicate`).
지원 확장자: `.pdf` `.txt` `.md` `.docx`.

---

## bulk_ingest.py — 폴더 단위 색인

### 사전 준비

| 모드 | 필요한 프로세스 |
|------|------------------|
| HTTP (기본) | `qdrant`, `postgres`, **uvicorn API** (워커는 `routing` 설정에 따라) |
| `--via-queue` | `qdrant`, `postgres`, **indexer 워커** (FastAPI 불필요) |

기동 절차는 [setup.md](../onboarding/setup.md) 참고. 워커는 다음으로 띄웁니다.

```bash
.venv/bin/python -m apps.indexer_worker
```

### 기본 사용

```bash
# 폴더 재귀 색인 (HTTP 모드, 기본)
.venv/bin/python scripts/bulk_ingest.py --dir ./sample_docs

# FastAPI 없이 큐로 직접 enqueue (워커 필요)
.venv/bin/python scripts/bulk_ingest.py --dir ./sample_docs --via-queue

# 최상위 폴더만, 미리보기
.venv/bin/python scripts/bulk_ingest.py --dir ./docs --no-recursive --dry-run
```

### 자주 쓰는 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--dir <path>` | (필수) | 색인할 폴더 |
| `--recursive` / `--no-recursive` | recursive | 하위 폴더 포함 여부 |
| `--include "*.pdf *.md"` | pdf/txt/md/docx | 공백·쉼표 구분 확장자. 지원 외 확장자는 무시 |
| `--exclude <regex>` | (없음) | 경로 정규식 제외, 반복 가능 (`--exclude draft/ --exclude _archive`) |
| `--title-from {stem,filename,relpath}` | `stem` | 제목 자동 생성 기준 |
| `--source-prefix "acme/"` | (없음) | `source` 메타에 붙일 접두 |
| `--dry-run` | off | 업로드 없이 대상만 출력 |
| `--fail-fast` | off | 첫 실패 시 전체 중단 |
| `--via-queue` | off | HTTP 거치지 않고 Postgres `ingest_jobs`에 직접 enqueue |
| `--api-base` | `http://localhost:8000` | HTTP 모드의 API URL |
| `--workers N` | 1 | 동시 업로드 수 (2+ 시 Docling 메모리 / L1 UNIQUE 충돌 주의) |
| `--report <path>` | `data/eval_runs/bulk_ingest_<ts>.json` | 결과 JSON 저장 경로 |

### 결과 카운터

콘솔과 리포트 JSON에 다음 카운터가 기록됩니다.

- `ok` — sync HTTP 모드에서 즉시 색인 완료
- `enqueued` — 큐 모드(또는 HTTP 큐 모드) 등록 완료. 실제 처리는 워커에서
- `duplicate` — content_hash 중복으로 스킵
- `skipped_too_large` — `MAX_UPLOAD_SIZE_MB` 초과로 스킵
- `failed` — 업로드/enqueue 실패

종료 코드: `failed > 0` 이면 1, 아니면 0.

### 결과 리포트

기본 경로: `data/eval_runs/bulk_ingest_<UTC타임스탬프>.json`

포함 필드:
- 실행 인자(`dir/recursive/include/exclude/title_from/source_prefix/workers/api_base`)
- 카운터(`total/ok/enqueued/duplicate/skipped_too_large/failed`)
- 시간(`started_at/finished_at/elapsed_sec`)
- `results[]` — 파일별 `{path, size_mb, status, doc_id?, job_id?, chunk_count?, error?}`

---

## 모드 선택 가이드

| 상황 | 권장 모드 |
|------|-----------|
| FastAPI를 항상 띄워 두고 즉시 처리 결과를 받고 싶다 | HTTP (기본) |
| 야간 대량 색인 / API 띄우기 부담 / 워커가 비동기로 처리해도 OK | `--via-queue` |
| 어떤 파일이 잡힐지 먼저 확인 | `--dry-run` |
| 한 건이라도 실패하면 즉시 멈추고 디버깅 | `--fail-fast` |

> 중복 처리는 L1(SHA-256) 단계에서 차단되므로, 같은 폴더를 재실행해도 안전합니다.
> 다만 `--via-queue`는 SHA 계산 후 즉시 `uploads/`로 복사하므로, 중복이면 복사 없이 스킵됩니다.

---

## 트러블슈팅

| 증상 | 원인 / 조치 |
|------|------------|
| `✗ API 서버에 연결 실패` | uvicorn 미기동. `--via-queue`로 우회하거나 API 기동 |
| `enqueued`만 늘고 `done`이 안 늘어남 | indexer 워커가 안 떠 있음. `python -m apps.indexer_worker` |
| `duplicate` 비율이 비정상으로 높음 | 같은 파일을 다른 경로로 복제 색인 중. `data/uploads/` 또는 Postgres `documents.content_hash` 확인 |
| `skipped_too_large` | `MAX_UPLOAD_SIZE_MB`(env)로 상한 조정 |
| 큐 모드에서 일부 job `failed` | `ingest_jobs.error` 컬럼 확인 (현재 4000자 상한) — 일시적 OpenAI 임베딩 connect 실패는 retry 후에도 소진되면 `failed`로 잠김. 재실행 권장 |
| 인덱싱 중 시스템 freeze / RSS 폭증 | 한 문서의 청크가 너무 많을 때 임베딩+PointStruct가 한 번에 메모리에 올라가 발생했던 회귀(ISSUE-003). 0.23.3에서 `qdrant_store.add_documents`(hybrid)에 `EMBED_BATCH_SIZE=64` 적용으로 캡. 여전히 OOM이 보이면 워커 수↓ 또는 `EMBED_BATCH_SIZE`↓를 같이 조정. 상세는 [ISSUE-003](../issues/resolved/ISSUE-003-ingest-memory-spike-system-freeze.md) |

## 메모리 안전성 노트 (2026-04-26 ~)

hybrid 모드 색인 시 메모리 점유는 다음 두 상수로 캡됩니다.

- `EMBED_BATCH_SIZE = 64` — 임베딩·PointStruct 구성 단위. 한 시점 RAM ≈ 64청크 × (dense 1536d + sparse + 텍스트 원문)
- `UPSERT_BATCH_SIZE = 256` — Qdrant HTTP payload 한도(32MiB) 회피용 네트워크 배치

embed_batch < upsert_batch 관계이므로 실제 upsert는 64 단위 1회로 끝납니다. 워커 동시성을 올리면 위 점유가 워커 수만큼 곱해지니 RAM 예산에 맞춰 조정하세요. vector 단일 모드(`search_mode=vector`)는 langchain QdrantVectorStore 내부 배치에 위임됩니다.

## 출처

- 코드: `scripts/bulk_ingest.py`
- 큐 enqueue: `packages/jobs/queue.py`
- 워커: `apps/indexer_worker.py`
- 벡터 저장: `packages/vectorstore/qdrant_store.py` (`add_documents`, `EMBED_BATCH_SIZE` / `UPSERT_BATCH_SIZE`)
- ADR-005 (L1 중복), ADR-018 (큐 모드), ADR-028 (워커 분리)
- ISSUE-003 (메모리 폭발 회귀 — 2026-04-26 해결)
