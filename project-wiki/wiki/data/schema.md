# DB 스키마 (Schema)

**상태**: active
**마지막 업데이트**: 2026-04-22
**관련 페이지**: [spec.md](spec.md), [decisions.md](../architecture/decisions.md), [endpoints.md](../api/endpoints.md)

---

## 개요

이 프로젝트는 세 개의 저장소를 병렬로 사용한다.

| 저장소 | 용도 | 위치/엔드포인트 | 운영 |
|--------|------|----------------|------|
| **PostgreSQL 16** | 문서 메타데이터 + 대화 히스토리 | `postgres://raguser@localhost:5432/ragdb` | Docker (`docker-compose.yml`) |
| **Qdrant** | 청크 임베딩 벡터 + 메타데이터 payload | `http://localhost:6333` | Docker (`docker-compose.yml`) |
| **파일시스템** | 업로드 원본 + Docling 파싱 결과 | `data/uploads/`, `data/markdown/` | 로컬 디스크 (재인덱싱용, ADR-010) |

**불변식**:
- `documents.doc_id`는 **모든 저장소의 조인 키**. PostgreSQL PK, Qdrant payload `metadata.doc_id`, 파일시스템 `{doc_id}.{ext}`.
- Qdrant는 인덱스(검색용), PostgreSQL은 진실(source of truth). 재인덱싱으로 Qdrant는 언제든 재구축.

---

## PostgreSQL

SQLAlchemy 모델은 [packages/db/models.py](../../../packages/db/models.py). `Base.metadata.create_all()`가 서버 시작 시 [apps/main.py](../../../apps/main.py) lifespan에서 실행되어 없는 테이블만 생성. 기존 테이블에 컬럼 추가는 `ALTER TABLE IF NOT EXISTS` 수동 마이그레이션 사용(현재는 `content_hash` 추가가 유일).

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
| `status` | `VARCHAR(32)` | default `"done"` | `done`/`failed` (현재는 `done`만 사용) |

**인덱스**
- `documents_pkey` — PK(`doc_id`) btree
- `ix_documents_content_hash` — UNIQUE(`content_hash`) btree. NULL 중복 허용

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

---

## Qdrant

컬렉션은 임베딩 차원에 따라 동적 생성된다([packages/vectorstore/qdrant_store.py](../../../packages/vectorstore/qdrant_store.py)). 차원 불일치 시 `CollectionDimensionMismatch` 예외로 재인덱싱을 강제(ADR-016).

### 컬렉션 `documents` (기본명, `.env`의 `QDRANT_COLLECTION`로 변경 가능)

| 속성 | 값 | 비고 |
|------|-----|------|
| 거리 | `Cosine` | 정규화된 임베딩에서 내적과 동일 |
| 차원 | **1536** (현재, OpenAI `text-embedding-3-small`) | BGE-M3 토글 시 1024로 자동 전환 (ADR-016) |
| 포인트 수 (2026-04-22) | 4037 | 문서 6개 × 평균 673 청크 |
| 상태 | green | |

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
      "indexed_at":    "2026-04-22T...",
      "language":      "auto",
      "content_type":  "text" | "table" | "image",
      "dl_meta": {                    # Docling 원본 메타 (doc_items, headings, prov, origin, schema_name)
          "headings":  [...],
          "doc_items": [ {"label": "text|code|list_item|table|...", "prov": [{"page_no": ..., "bbox": ...}]}, ... ],
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

---

## 파일시스템

| 경로 | 내용 | 수명 |
|------|------|------|
| `data/uploads/{doc_id}{.pdf|.txt|.md|.docx}` | 업로드 원본. ADR-010 이후 영구 보관 | DELETE 시 미정리 (고아 가능) |
| `data/markdown/{doc_id}.md` | Docling MARKDOWN export 결과 (정규화 후) | 재인덱싱 fallback용 |
| `data/qdrant_storage/` | Qdrant 볼륨 (Docker) | `.gitignore` |
| `data/pg_data/` | PostgreSQL 볼륨 (Docker) | `.gitignore` |
| `data/eval_runs/{retrieval|answers}_<ts>.json` | 벤치 실행 결과 (TASK-004) | `.gitignore` |

**주의**: DELETE 엔드포인트가 현재 Qdrant와 PostgreSQL에서만 레코드를 지우고 원본·마크다운 파일은 그대로 둔다 ([overview.md](../../overview.md) 기술 부채 섹션 참조).

---

## 엔티티 관계도 (ERD, 논리)

```
┌──────────────────┐
│   documents      │
│  (PostgreSQL)    │           ┌────────────────────────┐
│  doc_id (PK) ────┼──────────►│   Qdrant points        │
│  title           │           │   metadata.doc_id (ix) │
│  content_hash(U) │           │   vector (1536 또는 1024)│
│  ...             │           └────────────────────────┘
└──────────────────┘                    ▲
                                        │ rebuild_index.py
                                        │
┌──────────────────┐                    │
│  data/uploads/   │ ◄──────────────────┘ (재인덱싱 입력)
│  data/markdown/  │
└──────────────────┘

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
- `documents.doc_id` ↔ Qdrant `metadata.doc_id`  ↔ `data/uploads/{doc_id}.*` ↔ `data/markdown/{doc_id}.md`
- `conversations.session_id` ↔ `messages.session_id` (CASCADE)

---

## 마이그레이션 이력

SQLAlchemy `create_all()`은 멱등이고 컬럼 추가에는 안전하지 않다. 컬럼 추가는 수동 `ALTER TABLE` 사용.

| 날짜 | 변경 | SQL |
|------|------|-----|
| 2026-04-21 | `documents.content_hash` 추가 + UNIQUE INDEX (ADR-005) | `ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64); CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_content_hash ON documents (content_hash);` |
| 2026-04-21 | `conversations`, `messages` 테이블 신규 생성 (ADR-006) | `Base.metadata.create_all()` 자동 |

**정식 마이그레이션 도구(Alembic 등) 미도입**. 테이블·컬럼 변경이 누적되면 도입 검토 ([roadmap.md](../../roadmap.md) 중기).

---

## 알려진 이슈 / 기술 부채

- DELETE 엔드포인트가 `data/uploads/`·`data/markdown/` 원본 파일을 정리하지 않아 고아 파일 누적 가능 (overview 기술 부채)
- `content_hash=NULL`인 레거시 문서는 L1 중복 감지 대상 외 (ADR-005)
- `documents.status`는 실질적으로 `done`만 사용 — 실패 상태 기록 미구현
- Alembic 같은 정식 마이그레이션 없음 — 스키마 변경 시 수동 SQL 필요
