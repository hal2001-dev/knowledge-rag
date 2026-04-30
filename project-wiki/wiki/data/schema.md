# DB 스키마 (Schema)

**상태**: active
**마지막 업데이트**: 2026-04-25
**관련 페이지**: [spec.md](spec.md), [decisions.md](../architecture/decisions.md), [endpoints.md](../api/endpoints.md)

---

## 개요

이 프로젝트는 세 개의 저장소를 병렬로 사용한다.

| 저장소 | 용도 | 위치/엔드포인트 | 운영 |
|--------|------|----------------|------|
| **PostgreSQL 16** | 문서 메타데이터 + 요약/분류 + 대화 히스토리 + 색인 작업 큐 | `postgres://raguser@localhost:5432/ragdb` | Docker (`docker-compose.yml`) |
| **Qdrant** | 청크 임베딩 벡터 + 메타데이터 payload (vector 또는 hybrid 모드) | `http://localhost:6333` | Docker (`docker-compose.yml`) |
| **파일시스템** | 업로드 원본 + Docling 파싱 결과 | `data/uploads/`, `data/markdown/` | 로컬 디스크 (재인덱싱용, ADR-010) |

**불변식**:
- `documents.doc_id`는 **모든 저장소의 조인 키**. PostgreSQL PK, Qdrant payload `metadata.doc_id`, 파일시스템 `{doc_id}.{ext}`, `ingest_jobs.doc_id` 모두 동일.
- Qdrant는 인덱스(검색용), PostgreSQL은 진실(source of truth). 재인덱싱으로 Qdrant는 언제든 재구축.

---

## PostgreSQL

SQLAlchemy 모델은 [packages/db/models.py](../../../packages/db/models.py). `Base.metadata.create_all()`이 서버 시작 시 [apps/main.py](../../../apps/main.py) lifespan에서 실행되어 없는 테이블만 생성. 컬럼 추가는 `packages/db/migrations/*.sql` + [connection.py](../../../packages/db/connection.py)의 sentinel 시스템으로 idempotent 처리(ADR-028: column/table 양쪽 지원, `pg_advisory_xact_lock`으로 동시 기동 race 해소).

### 테이블 `documents`

문서 업로드 1건당 레코드 1개. Qdrant 벡터와 1:N 관계.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `doc_id` | `VARCHAR` | **PK** | UUID v4. 업로드 시 서버 발급 |
| `title` | `TEXT` | NOT NULL | 사용자 지정 제목 |
| `source` | `TEXT` | default `""` | 원본 파일명 또는 사용자 기재 출처 |
| `file_type` | `VARCHAR(16)` | default `"pdf"` | `pdf`/`txt`/`md`/`docx` |
| `content_hash` | `VARCHAR(64)` | **UNIQUE**, nullable | 업로드 바이트 SHA-256 (L1 중복 감지, ADR-005). 기존 레코드는 NULL |
| `chunk_count` | `INTEGER` | default 0 | 인덱싱된 청크 수 |
| `has_tables` | `BOOLEAN` | default false | Docling이 테이블 발견했는가 |
| `has_images` | `BOOLEAN` | default false | Docling이 이미지 발견했는가 |
| `indexed_at` | `TIMESTAMPTZ` | default `now()` | 인덱싱 시각 (UTC) |
| `status` | `VARCHAR(32)` | default `"done"` | `done`/`failed` (현재는 `done`만 사용 — 실패는 `ingest_jobs`에 기록) |
| `summary` | `JSONB` | nullable | TASK-014 (ADR-024) 자동 요약. `{one_liner, abstract, topics[], target_audience, sample_questions[]}` |
| `summary_model` | `TEXT` | nullable | 요약 생성 LLM 모델명 (예: `gpt-4o-mini`) |
| `summary_generated_at` | `TIMESTAMPTZ` | nullable | 요약 생성 시각 |
| `doc_type` | `VARCHAR(16)` | NOT NULL, default `"book"`, **CHECK** | TASK-015 (ADR-025). `book`/`article`/`paper`/`note`/`report`/`web`/`other` |
| `category` | `VARCHAR(64)` | nullable | 카테고리 ID (예: `software/architecture`). 라벨은 `config/categories.yaml` |
| `category_confidence` | `FLOAT` | nullable | 자동 분류 신뢰도 0~1. < 0.4면 검수 후보 |
| `tags` | `JSONB` | NOT NULL, default `[]` | 자동/수동 태그 배열. 보통 `summary.topics[]`에서 채택 |
| `series_id` | `VARCHAR` | nullable, **FK → series(series_id) ON DELETE SET NULL** | TASK-020 (ADR-029). 시리즈 멤버십. NULL이면 단일 문서 |
| `volume_number` | `INTEGER` | nullable | 권 번호 (1, 2, …). 휴리스틱·수동 입력 |
| `volume_title` | `TEXT` | nullable | "Chapter 1: Intro" 같은 권 제목 |
| `series_match_status` | `VARCHAR(16)` | NOT NULL, default `"none"`, **CHECK** | TASK-020. `none`/`auto_attached`/`suggested`/`confirmed`/`rejected` |

**인덱스**
- `documents_pkey` — PK(`doc_id`) btree
- `ix_documents_content_hash` — UNIQUE(`content_hash`) btree. NULL 중복 허용
- `ix_documents_series_id` — series_filter·도서관 그룹화용 (TASK-020)
- `ix_documents_match_status` — 검수 큐 조회용 (TASK-020)

**CHECK 제약**:
- `documents_doc_type_check` — 위 7종 외 거부
- `documents_series_match_status_check` — 위 5상태 외 거부

### 테이블 `conversations`

RAG 대화 세션 1건당 레코드 1개. `/query`가 `session_id` 없이 호출되면 자동 생성(ADR-006).

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `session_id` | `VARCHAR` | **PK** | UUID v4 |
| `title` | `TEXT` | default `""` | 사용자 지정(선택), 현재는 대부분 빈 값 |
| `created_at` | `TIMESTAMPTZ` | default `now()` | 생성 시각 |
| `updated_at` | `TIMESTAMPTZ` | default `now()`, `onupdate=now()` | 마지막 메시지 시각 자동 갱신 |

**인덱스**: `conversations_pkey`

### 테이블 `messages`

대화의 각 턴(user + assistant). `/query` 호출마다 2행 INSERT.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | `INTEGER` | **PK**, autoincrement | `nextval('messages_id_seq')` |
| `session_id` | `VARCHAR` | NOT NULL, **FK → conversations(session_id) ON DELETE CASCADE** | 대화 세션 |
| `role` | `VARCHAR(16)` | NOT NULL | `"user"` 또는 `"assistant"` |
| `content` | `TEXT` | NOT NULL | 메시지 본문 |
| `created_at` | `TIMESTAMPTZ` | default `now()` | 생성 시각 |

**인덱스**
- `messages_pkey` — PK(`id`)
- `ix_messages_session_created` — 복합 (`session_id`, `created_at`) btree. 최근 20개 메시지 조회 최적화(ADR-006)

**CASCADE**: 대화 삭제 시 메시지 자동 정리.

### 테이블 `series` (TASK-020, ADR-029)

저작 1건이 여러 파일로 쪼개진 묶음 단위. 멤버는 `documents.series_id == series.series_id`인 문서들.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `series_id` | `VARCHAR` | **PK** | `ser_<12hex>` 형식 (서버 발급 또는 사용자 지정) |
| `title` | `TEXT` | NOT NULL | 시리즈 제목. 휴리스틱 자동 생성 시 공통 prefix 사용 |
| `description` | `TEXT` | nullable | 시리즈 설명 (선택) |
| `cover_doc_id` | `VARCHAR` | nullable | 대표 문서 ID. 자동 생성 시 매처 호출 시점의 target doc_id |
| `series_type` | `VARCHAR(16)` | NOT NULL, default `"book"`, **CHECK** | `book`/`series`/`volume` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | 생성 시각 |

**인덱스**: `series_pkey` — PK(`series_id`)

**CHECK 제약**: `series_type_check`

**FK 정책**: `documents.series_id → series(series_id) ON DELETE SET NULL` — 시리즈 삭제 시 멤버 documents.series_id만 NULL로 분리되어 문서 데이터는 보존.

**관련 코드**:
- ORM: [packages/db/models.py:SeriesRecord](../../../packages/db/models.py)
- repository: [packages/db/repository.py](../../../packages/db/repository.py) `create_series` / `get_series` / `list_series` / `update_series` / `delete_series` / `list_series_members` / `attach_to_series` / `detach_from_series` / `update_match_status` / `list_pending_review`
- 매처: [packages/series/matcher.py](../../../packages/series/matcher.py), [packages/series/match_runner.py](../../../packages/series/match_runner.py)
- 라우터: [apps/routers/series.py](../../../apps/routers/series.py)
- 백필 CLI: [scripts/suggest_series.py](../../../scripts/suggest_series.py)

### 테이블 `ingest_jobs` (TASK-018, ADR-028)

색인 작업 큐. FastAPI는 enqueue만 하고, [apps/indexer_worker.py](../../../apps/indexer_worker.py)가 `SELECT … FOR UPDATE SKIP LOCKED`로 claim해 처리한다. uvicorn 응답성 보호 + 잡 가시성·retry·에러 영속화 목적.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | `BIGINT` | **PK**, autoincrement | `nextval('ingest_jobs_id_seq')` |
| `doc_id` | `TEXT` | indexed, nullable | 발급된 doc UUID. `documents.doc_id` 또는 향후 documents row와 매칭 |
| `file_path` | `TEXT` | NOT NULL | 워커가 읽을 절대 경로 (`data/uploads/{doc_id}.{ext}`) |
| `title` | `TEXT` | NOT NULL | 사용자 지정 제목 |
| `source` | `TEXT` | NOT NULL, default `""` | 출처 |
| `content_hash` | `VARCHAR(64)` | nullable | 업로드 바이트 SHA-256 (L1 중복 감지) |
| `user_doc_type` | `VARCHAR(16)` | nullable | 사용자 명시 doc_type. 있으면 자동 분류 skip |
| `user_category` | `VARCHAR(64)` | nullable | 사용자 명시 카테고리 |
| `user_tags` | `JSONB` | nullable | 사용자 명시 태그 배열 |
| `status` | `VARCHAR(16)` | NOT NULL, default `"pending"`, **CHECK** | `pending`/`in_progress`/`done`/`failed`/`cancelled` |
| `retry_count` | `INTEGER` | NOT NULL, default 0 | 영구 실패 임계값은 워커 상수 `MAX_RETRIES=3` |
| `error` | `TEXT` | nullable | 마지막 실패 traceback. **현재 `error[:2000]` 상한이 적용돼 끝부분이 잘릴 수 있음** ([queue.py:100](../../../packages/jobs/queue.py#L100)) |
| `enqueued_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | 큐 적재 시각 |
| `started_at` | `TIMESTAMPTZ` | nullable | 마지막 claim 시각 (재시도 시 갱신) |
| `finished_at` | `TIMESTAMPTZ` | nullable | done/failed 확정 시각 |

**인덱스**
- `ingest_jobs_pkey` — PK(`id`)
- `ix_ingest_jobs_doc_id` — btree(`doc_id`)
- `ix_ingest_jobs_status_enqueued` — 복합 (`status`, `enqueued_at`). 워커 폴링 쿼리(`status='pending' ORDER BY enqueued_at`)에 사용

**CHECK 제약**: `ingest_jobs_status_check` — 위 5종 외 거부

**상태 전이**:
```
pending ──claim──▶ in_progress ──ok──▶ done
                       │
                       └──exception──▶ pending(retry < 3) 또는 failed(retry ≥ 3)
```

**관련 코드**:
- 워커: [apps/indexer_worker.py](../../../apps/indexer_worker.py) — 폴링 3→15s backoff, SIGTERM graceful
- 큐 함수: [packages/jobs/queue.py](../../../packages/jobs/queue.py) — `enqueue_job` / `claim_next_job(SKIP LOCKED)` / `mark_done` / `mark_failed`
- 조회 API: [apps/routers/jobs.py](../../../apps/routers/jobs.py) — `GET /jobs`, `GET /jobs/{id}`

---

## Qdrant

컬렉션은 임베딩 차원에 따라 동적 생성된다([packages/vectorstore/qdrant_store.py](../../../packages/vectorstore/qdrant_store.py)). 차원 불일치 시 `CollectionDimensionMismatch` 예외로 재인덱싱을 강제(ADR-016). `.env`의 `SEARCH_MODE`로 두 가지 컬렉션 구조를 토글한다(ADR-023).

### 컬렉션 `documents` (기본명, `.env`의 `QDRANT_COLLECTION`로 변경 가능)

#### vector 모드 (`SEARCH_MODE=vector`)

| 속성 | 값 | 비고 |
|------|-----|------|
| 벡터 구조 | unnamed (단일 dense) | langchain_qdrant 기본 |
| 거리 | `Cosine` | 정규화된 임베딩에서 내적과 동일 |
| 차원 | **1536** (OpenAI `text-embedding-3-small`) | BGE-M3 토글 시 1024 (ADR-016) |
| 업로드 경로 | `langchain_qdrant.QdrantVectorStore.add_documents` (내부 `batch_size=64` 자동 분할) | |

#### hybrid 모드 (`SEARCH_MODE=hybrid`, ADR-023)

| 속성 | 값 | 비고 |
|------|-----|------|
| 벡터 구조 | named vectors `{ "dense": ..., "sparse": ... }` | dense + Qdrant 네이티브 sparse |
| dense | `Cosine`, 1536/1024 차원 | 위와 동일 |
| sparse | `SparseVectorParams()` 기본값 | Qdrant/bm25 + Kiwi 한국어 형태소 전처리 |
| 검색 | `query_points` + `FusionQuery(Fusion.RRF)` 병합 | dense top-2k ∪ sparse top-2k → RRF |
| 업로드 경로 | raw `client.upsert` | **`UPSERT_BATCH_SIZE=256` 단위 분할** ([qdrant_store.py](../../../packages/vectorstore/qdrant_store.py)). Qdrant HTTP payload 32MiB 한도 회피용 |

### Payload 인덱스 (TASK-015 + TASK-020, 두 모드 공통)

`_ensure_payload_indexes()`가 컬렉션 생성·기동 시 idempotent 적용(KEYWORD):

| 필드 | 용도 |
|------|------|
| `metadata.doc_id` | 문서 단위 조회/삭제(이미 사용 중) |
| `metadata.doc_type` | enum 필터 (book/article/...) |
| `metadata.category` | 카테고리 단일 문자열 필터 |
| `metadata.tags` | 태그 배열 (Qdrant keyword 인덱스가 array 자동 지원) |
| `metadata.series_id` | TASK-020 series_filter + 도서관 그룹화 |
| `metadata.heading_path` | TASK-022 (ADR-035) heading prefix 동반 검색 — array 원소 단위 매칭으로 prefix AND 필터링 |

### Payload 스키마 (각 포인트)

```python
{
  "page_content": "Chapter 1 > Section 1.1\n\n<본문>",  # LangChain 기본 필드
  "metadata": {
      "doc_id":        "uuid",       # documents.doc_id와 동일 (조인 키)
      "title":         "문서 제목",
      "source":        "원본 파일 경로 또는 식별자",
      "page":          42,            # dl_meta.doc_items[*].prov[0].page_no 기반 (ADR-009)
      "heading_path":  ["Chapter 8","8.5","8.5.3 자율 주행"],  # HybridChunker 전체 경로
      "chunk_index":   17,            # 문서 내 순서
      "indexed_at":    "2026-04-25T...",
      "language":      "auto",
      "content_type":  "text" | "table" | "image",

      # TASK-015: 분류 메타 (set_classification_payload로 일괄 set_payload)
      "doc_type":      "book",
      "category":      "software/architecture",
      "tags":          ["pandas","seaborn","데이터 시각화"],

      "dl_meta": {                    # Docling 원본 메타
          "headings":  [...],
          "doc_items": [ {"label": "...", "prov": [{"page_no": ..., "bbox": ...}]}, ... ],
          "origin":    {...},
          "schema_name": "DoclingDocument",
          "version":   "..."
      }
  }
}
```

**문서 단위 조작**: `metadata.doc_id`를 필터로 사용해 삭제/검색.
- 삭제: `QdrantDocumentStore.delete_by_doc_id(doc_id)` → `FieldCondition(key="metadata.doc_id", match=doc_id)`
- 필터 검색: `similarity_search_with_score(..., doc_id=...)`
- 분류 일괄 갱신: `set_classification_payload(doc_id, doc_type, category, tags)` — `set_payload`로 부분 업데이트, 다른 metadata 키 보존

---

## 파일시스템

| 경로 | 내용 | 수명 |
|------|------|------|
| `data/uploads/{doc_id}{.pdf|.txt|.md|.docx}` | 업로드 원본. ADR-010 이후 영구 보관 | DELETE 시 ADR-021로 동반 정리 |
| `data/markdown/{doc_id}.md` | Docling MARKDOWN export 결과 (정규화 후) | 재인덱싱 fallback용. DELETE 시 동반 정리 |
| `data/qdrant_storage/` | Qdrant 볼륨 (Docker) | `.gitignore` |
| `data/pg_data/` | PostgreSQL 볼륨 (Docker) | `.gitignore` |
| `data/eval_runs/{retrieval|answers|bulk_ingest|classification|summaries}_<ts>.json` | 벤치/색인/분류/요약 실행 결과 | `.gitignore` |

**참고**: ADR-021 이후 DELETE 엔드포인트가 두 파일을 동반 삭제한다. 단, 큐 모드에서 enqueue 후 워커 영구 실패한 잡(`status=failed`)의 업로드 파일은 자동 정리되지 않으므로 운영자가 별도 청소 필요.

---

## 엔티티 관계도 (ERD, 논리)

```
┌──────────────────┐
│   documents      │
│  (PostgreSQL)    │           ┌────────────────────────┐
│  doc_id (PK) ────┼──────────►│   Qdrant points        │
│  title           │           │   metadata.doc_id (ix) │
│  content_hash(U) │           │   dense (1536/1024)    │
│  summary (JSONB) │           │   sparse (hybrid 모드) │
│  doc_type/cat    │           │   payload indexes      │
│  tags (JSONB)    │           │     metadata.doc_id    │
│  ...             │           │     metadata.doc_type  │
└──────────────────┘           │     metadata.category  │
        ▲                      │     metadata.tags      │
        │ doc_id               └────────────────────────┘
        │                                ▲
┌──────────────────┐                     │ rebuild_index.py
│  ingest_jobs     │                     │
│  id (PK)         │                     │
│  doc_id (ix)     │                     │
│  status          │                     │
│  retry_count     │                     │
│  error           │      ┌──────────────────┐
│  enqueued_at     │      │  data/uploads/   │ ◄─── (재인덱싱 입력)
│  (status,        │      │  data/markdown/  │
│   enqueued_at)ix │      └──────────────────┘
└──────────────────┘
        │
        │ 워커: SKIP LOCKED claim
        ▼
  apps/indexer_worker.py
  → pipeline.ingest → summary → classify

┌──────────────────┐      CASCADE    ┌──────────────────┐
│ conversations    │───────────────► │   messages       │
│ session_id (PK)  │  1 → N          │  id (PK)         │
│ created_at       │                 │  session_id (FK) │
│ updated_at       │                 │  role, content   │
└──────────────────┘                 │  (session_id,    │
                                     │   created_at) ix │
                                     └──────────────────┘
```

**조인 키**:
- `documents.doc_id` ↔ Qdrant `metadata.doc_id` ↔ `data/uploads/{doc_id}.*` ↔ `data/markdown/{doc_id}.md` ↔ `ingest_jobs.doc_id`
- `conversations.session_id` ↔ `messages.session_id` (CASCADE)

---

## 마이그레이션 이력

`packages/db/migrations/*.sql` 파일을 [packages/db/connection.py](../../../packages/db/connection.py)의 sentinel 시스템이 idempotent 적용한다(ADR-028: 컬럼/테이블 양쪽 sentinel 지원, `pg_advisory_xact_lock`으로 동시 기동 race 방지).

| 파일 | 날짜 | 변경 | sentinel |
|------|------|------|----------|
| (사전) | 2026-04-21 | `documents.content_hash` + UNIQUE INDEX (ADR-005) | `("column", "documents", "content_hash")` |
| (사전) | 2026-04-21 | `conversations`, `messages` 테이블 생성 (ADR-006) | `Base.metadata.create_all()` 자동 |
| `0001_add_summary_columns.sql` | 2026-04-25 | `documents.summary/summary_model/summary_generated_at` (TASK-014, ADR-024) | `("column", "documents", "summary")` |
| `0002_add_classification_columns.sql` | 2026-04-25 | `documents.doc_type/category/category_confidence/tags` + CHECK (TASK-015, ADR-025) | `("column", "documents", "doc_type")` |
| `0003_add_ingest_jobs.sql` | 2026-04-25 | `ingest_jobs` 테이블 + 인덱스 + CHECK (TASK-018, ADR-028) | `("table", "ingest_jobs")` |
| `0004_add_conversations_user_id.sql` | 2026-04-26 | `conversations.user_id` (TASK-019, ADR-030) | `("column", "conversations", "user_id")` |
| `0005_add_series_tables.sql` | 2026-04-28 | `series` 테이블 + `documents` 4컬럼(series_id/volume_number/volume_title/series_match_status) + FK ON DELETE SET NULL + CHECK 2개 + 인덱스 2개 (TASK-020, ADR-029) | `("table", "series")` |

신규 환경(빈 DB)에서는 [init.sql](../../../init.sql)이 모든 컬럼/CHECK/인덱스를 한 번에 생성하므로 마이그레이션을 건너뛴다. 기존 환경(컬럼 일부만 있는 상태)에서는 sentinel이 부재하면 ALTER 적용.

**Alembic 같은 정식 마이그레이션 도구 미도입** — 누적되면 도입 검토 ([roadmap.md](../../roadmap.md) 중기).

---

## 알려진 이슈 / 기술 부채

- 큐 모드에서 영구 실패한 `ingest_jobs`의 `data/uploads/{doc_id}.*` 파일이 자동 정리되지 않음 — 운영자가 수동 청소 필요
- `ingest_jobs.error` 컬럼이 `error[:2000]`로 잘려 traceback 끝(예외 메시지)이 사라지는 사례 발생 — `error[-2000:]` 또는 컬럼 상한 확대 검토 별건
- `content_hash=NULL`인 레거시 문서는 L1 중복 감지 대상 외 (ADR-005)
- `documents.status`는 실질적으로 `done`만 사용 — 실패 상태는 `ingest_jobs.status=failed`로 표면화
- Alembic 같은 정식 마이그레이션 도구 없음 — 스키마 변경 시 `migrations/*.sql` + sentinel 패턴 수동 작성
