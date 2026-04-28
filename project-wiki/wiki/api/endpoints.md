# API 엔드포인트 명세

**상태**: active
**마지막 업데이트**: 2026-04-25
**관련 페이지**: [schema.md](../data/schema.md), [decisions.md](../architecture/decisions.md)

---

## Base URL

| 환경 | URL |
|------|-----|
| dev | `http://localhost:8000` |
| prod | (미정) |

---

## 인증

현재: 없음 (개발 환경, LAN 전용).
공개 노출 시 Cloudflare Tunnel + Access 게이트웨이 검토 — TASK-012(보류) / [security.md](../../security.md).

---

## 카테고리별 엔드포인트

### 색인 (Ingest)

#### POST /ingest

문서를 업로드하고 벡터 인덱스에 추가합니다. 운영 모드는 `.env`의 `INGEST_MODE`로 분기:

- **`INGEST_MODE=queue`** (기본, TASK-018/ADR-028): `ingest_jobs`에 enqueue만 하고 즉시 응답. 워커가 비동기 처리.
- **`INGEST_MODE=sync`**: 응답 시점까지 동기 인덱싱(회귀용).

업로드 바이트 SHA-256이 기존 문서와 일치하면 409 (L1 중복 감지, ADR-005).

**Request** (`multipart/form-data`)
- `file`: 업로드 파일 (pdf|txt|md|docx)
- `title`: 문서 제목 (form field, 필수)
- `source`: 출처 설명 (form field, optional)
- `doc_type`: `book`/`article`/`paper`/`note`/`report`/`web`/`other` (optional). 명시 시 자동 분류 skip
- `category`: 카테고리 ID (optional, 예: `software/architecture`)
- `tags`: 쉼표 구분 태그 문자열 (optional)

**Response 200 (queue 모드)**
```json
{
  "doc_id": "uuid",
  "title": "문서 제목",
  "status": "pending",
  "chunk_count": 0,
  "has_tables": false,
  "has_images": false,
  "duplicate": false,
  "job_id": 42
}
```
워커가 처리 진행을 `GET /jobs/{job_id}`에서 추적.

**Response 200 (sync 모드)**
```json
{
  "doc_id": "uuid",
  "title": "문서 제목",
  "status": "done",
  "chunk_count": 42,
  "has_tables": false,
  "has_images": false,
  "duplicate": false
}
```
요약·분류는 응답 직후 BackgroundTasks로 진행.

**Response 409 (중복)**
```json
{
  "detail": {
    "message": "이미 등록된 문서입니다.",
    "doc_id": "<기존 doc_id>",
    "title": "<기존 title>",
    "content_hash": "<sha256>"
  }
}
```

**에러 코드**
| 코드 | 의미 |
|------|------|
| 400 | 지원하지 않는 파일 형식 |
| 409 | 동일 바이트의 문서가 이미 등록됨 (L1 중복 감지) |
| 413 | 파일 크기 초과 (`MAX_UPLOAD_SIZE_MB`, 기본 200MB) |
| 500 | 임베딩/upsert 실패 (sync 모드만. queue 모드는 워커 traceback이 `ingest_jobs.error`에) |

---

### 색인 작업 큐 (Jobs, TASK-018)

#### GET /jobs

`ingest_jobs` 큐 목록을 최신순으로 반환합니다. UI "잡" 탭이 사용.

**Query**
- `status`: `pending`/`in_progress`/`done`/`failed`/`cancelled` (optional, 미지정 시 전체)
- `limit`: 1~500 (기본 50)

**Response**
```json
{
  "jobs": [
    {
      "id": 19,
      "doc_id": "uuid",
      "title": "문서 제목",
      "source": "원본 파일명",
      "status": "failed",
      "retry_count": 4,
      "error": "Traceback (most recent call last): ... (최대 2000자, 끝부분 잘릴 수 있음)",
      "enqueued_at": "2026-04-25T05:13:58.730259+00:00",
      "started_at": "2026-04-25T12:20:53.358026+00:00",
      "finished_at": "2026-04-25T12:25:53.098728+00:00"
    }
  ],
  "total": 1
}
```

#### GET /jobs/{job_id}

단건 잡 조회. 응답 형식은 `GET /jobs`의 jobs 배열 원소와 동일.

**Response 404** — 잡 없음

---

### 질의 (Query)

#### POST /query

질문을 입력받아 답변을 반환합니다. `session_id`로 대화 히스토리를 이어갈 수 있습니다 — 없으면 새 세션이 생성되고, 있으면 해당 세션의 **최근 20개 턴**이 LLM 컨텍스트로 주입됩니다(ADR-006).

**Request**
```json
{
  "question": "질문 텍스트",
  "session_id": "uuid (optional)",
  "top_k": 3,
  "initial_k": 20,
  "score_threshold": 0.7,
  "doc_filter": "uuid (optional, TASK-016)",
  "category_filter": "software/architecture (optional, TASK-019)",
  "series_filter": "ser_xxx (optional, TASK-020/ADR-029)"
}
```
- `doc_filter`: 특정 문서 한정 검색 (Qdrant `metadata.doc_id` 필터). 도서관 탭의 "이 책에 대해 묻기"가 사용.
- `category_filter`: 특정 카테고리 한정 검색 (`metadata.category`). 상단 카테고리 칩.
- `series_filter`: 특정 시리즈 한정 검색 (`metadata.series_id`). 도서관 시리즈 카드 [이 시리즈에 묻기].
- **활성 스코프 우선순위**: `doc_filter > category_filter > series_filter` (한 번에 하나, ADR-029). 상위 우선순위가 들어오면 하위는 무시.

**Response**
```json
{
  "session_id": "uuid",
  "answer": "생성된 답변",
  "sources": [
    {
      "doc_id": "uuid",
      "title": "문서 제목",
      "page": 3,
      "content_type": "text",
      "score": 0.92,
      "excerpt": "관련 청크 앞 200자"
    }
  ],
  "latency_ms": 1240,
  "suggestions": [
    "후속 질문 1",
    "후속 질문 2",
    "후속 질문 3"
  ]
}
```
`suggestions`는 `.env`의 `SUGGESTIONS_ENABLED=false`면 빈 배열 (TASK-007/ADR-019).

---

### 대화 (Conversations)

#### POST /conversations

새 대화 세션을 생성합니다. (클라이언트가 `/query`를 바로 호출해도 서버가 새 세션을 자동 발급하므로 선택적으로 사용)

**Request** — `{"title": "(optional)"}`
**Response** — `{"session_id", "title", "created_at", "updated_at"}`

#### GET /conversations

모든 세션 목록 (최근 업데이트순).

**Response** — `{"conversations": [ConversationSummary...], "total": int}`

#### GET /conversations/{session_id}

특정 세션의 메타데이터 + 전체 메시지 히스토리.

**Response 200**
```json
{
  "session_id": "uuid",
  "title": "",
  "created_at": "...",
  "updated_at": "...",
  "messages": [
    {"role": "user", "content": "...", "created_at": "..."},
    {"role": "assistant", "content": "...", "created_at": "..."}
  ]
}
```

**Response 404** — 세션 없음

#### DELETE /conversations/{session_id}

세션과 모든 메시지 삭제 (CASCADE).

**Response** — `{"deleted": "<session_id>"}` / 404

---

### 문서 (Documents)

#### GET /documents

인덱싱된 문서 목록을 반환합니다(최신 indexed_at 내림차순). UI "도서관" 탭이 사용.

**Response**
```json
{
  "documents": [
    {
      "doc_id": "uuid",
      "title": "문서 제목",
      "source": "원본 파일명",
      "file_type": "pdf",
      "chunk_count": 42,
      "has_tables": true,
      "has_images": false,
      "indexed_at": "2026-04-25T...",
      "status": "done",
      "summary": {
        "one_liner": "한 줄 요약",
        "abstract": "2~3문장 요약",
        "topics": ["주제1", "주제2"],
        "target_audience": "대상 독자",
        "sample_questions": ["이 문서에서 답할 수 있는 질문 3개"]
      },
      "summary_model": "gpt-4o-mini",
      "summary_generated_at": "2026-04-25T...",
      "doc_type": "book",
      "category": "software/architecture",
      "category_confidence": 0.92,
      "tags": ["pandas","seaborn"]
    }
  ],
  "total": 25
}
```
요약·분류 미생성이면 해당 필드 `null`.

#### PATCH /documents/{doc_id}

문서 분류 메타(`doc_type`/`category`/`tags`)를 업데이트하고 Qdrant payload도 동기화합니다 (TASK-015/ADR-025).

**Request**
```json
{
  "doc_type": "book",
  "category": "software/architecture",
  "tags": ["pandas","seaborn"]
}
```
모든 필드 optional. 빠진 필드는 변경하지 않음.

**Response** — 갱신된 `DocumentItem` (위 GET /documents의 단건과 동일 형식)

#### DELETE /documents/{doc_id}

특정 문서를 인덱스에서 제거합니다. Qdrant 청크 + PostgreSQL row + `data/uploads/{doc_id}.*` + `data/markdown/{doc_id}.md`를 동반 삭제 (ADR-021).

**Response**
```json
{
  "status": "deleted",
  "doc_id": "uuid"
}
```

#### GET /documents/{doc_id}/summary

문서 요약 조회 (TASK-014/ADR-024). 미생성이면 `summary=null`.

**Response**
```json
{
  "doc_id": "uuid",
  "summary": { "...": "위 GET /documents의 summary와 동일 구조" },
  "summary_model": "gpt-4o-mini",
  "summary_generated_at": "2026-04-25T..."
}
```

#### POST /documents/{doc_id}/summary/regenerate

요약 강제 재생성. 기존 summary가 있어도 새로 만들어 덮어씁니다.

**Response** — 위 GET /documents/{doc_id}/summary와 동일

#### GET /documents/{doc_id}/chunks

특정 문서의 청크를 `chunk_index` 순으로 미리보기 (관리자 UI용).

**Query**
- `limit`: 기본 10 (1~?)

**Response**
```json
{
  "chunks": [
    {
      "chunk_index": "0",
      "page": 1,
      "content_type": "text",
      "heading_path": ["Chapter 1","1.1"],
      "preview": "청크 본문 앞 ~300자"
    }
  ]
}
```

---

### 시리즈 / 묶음 (Series, TASK-020 — ADR-029)

`apps/routers/series.py`. 여러 파일로 쪼개진 한 저작을 묶는 1급 시민. 색인 시점 휴리스틱이 자동 묶기를 수행하고, 검수 큐에서 confirm/reject로 정정.

#### GET /series

전체 시리즈 목록 + 멤버 수.

**Response 200**
```json
{
  "series": [
    {
      "series_id": "ser_a1b2c3d4e5f6",
      "title": "심연 위의 불길",
      "description": null,
      "cover_doc_id": "uuid",
      "series_type": "book",
      "member_count": 3,
      "created_at": "2026-04-28T..."
    }
  ],
  "total": 1
}
```

#### GET /series/{series_id}

단일 시리즈 정보 + 멤버 수. 404 시 `{"detail":"시리즈를 찾을 수 없음: ..."}`.

#### GET /series/{series_id}/members

시리즈 멤버 문서 목록. `volume_number ASC NULLS LAST`, 그 다음 `indexed_at ASC` 정렬.

**Response 200**
```json
{"series_id": "ser_xxx", "members": [DocumentItem, ...]}
```

DocumentItem에는 series 필드(series_id/series_title/volume_number/volume_title/series_match_status)가 포함됨.

#### POST /series

수동 시리즈 생성 (관리자).

**Request**
```json
{
  "series_id": null,                  // null이면 서버 발급
  "title": "심연 위의 불길",
  "description": null,
  "cover_doc_id": null,
  "series_type": "book"               // book | series | volume
}
```

**Response 201**: SeriesItem. **409** if `series_id` 중복.

#### PATCH /series/{series_id}

부분 갱신. 필드 4개(title/description/cover_doc_id/series_type) 모두 optional.

#### DELETE /series/{series_id}

시리즈 삭제. FK `ON DELETE SET NULL`로 멤버 documents.series_id는 NULL로 분리, 문서 데이터 보존.

**Response 200**: `{"series_id": "ser_xxx", "deleted": true}`

---

#### GET /series/_review/queue

검수 큐 — `series_match_status IN ('auto_attached','suggested')` 문서 목록.

**Response 200**: `[SeriesReviewItem, ...]`
```json
[
  {
    "doc_id": "uuid",
    "title": "심연 위의 불길 1",
    "series_id": "ser_xxx",
    "series_title": "심연 위의 불길",
    "volume_number": 1,
    "series_match_status": "auto_attached"
  }
]
```

#### POST /documents/{doc_id}/series_match/confirm

`auto_attached → confirmed`. 관리자가 자동 묶기를 확정.

**Response 200**: 갱신된 DocumentItem. **400** if `series_id`가 비어있음.

#### POST /documents/{doc_id}/series_match/reject

분리 + `series_match_status = rejected`. 동일 휴리스틱이 다시 자동 묶기 시도하지 않음 (관리자 의사 영구 존중).

**Response 200**: 갱신된 DocumentItem.

#### POST /documents/{doc_id}/series_match/attach

수동 묶기 — 관리자가 시리즈를 직접 지정. status=confirmed.

**Query**: `series_id` (필수), `volume_number` (선택).

**Response 200**: 갱신된 DocumentItem. 404 if 문서 또는 시리즈 미존재.

---

### 시스템 / 인덱스 메타

#### GET /index/overview

인덱싱된 전체 컬렉션의 한 줄 요약 카드(채팅 빈 상태/도서관 진입 안내). TASK-008/ADR-020 + TASK-017/ADR-027 확장.

**Query**
- `limit`: 기본 6 (recent_docs 카드 개수에만 영향)

**Response**
```json
{
  "doc_count": 25,
  "titles": ["문서1","문서2","..."],
  "top_headings": ["Chapter X","..."],
  "summary": "이 시스템이 아는 내용 한국어 2~3문장",
  "suggested_questions": ["예시 질문 5개"],
  "top_tags": [{"tag":"pandas","count":7}, ...],
  "categories": [{"id":"software/architecture","label":"소프트웨어 아키텍처","count":4}, ...],
  "recent_docs": [
    {"doc_id":"uuid","title":"...","one_liner":"한 줄 요약","category":"..."}
  ]
}
```
응답은 인메모리 캐시. `/ingest`·`DELETE /documents/{id}`·`PATCH /documents/{id}` 시 자동 무효화.

#### GET /health

기본 헬스체크. Streamlit "시스템" 탭 카드와 bulk_ingest CLI의 사전 체크에 사용.

**Response 200** — `{"status": "ok"}`

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-04-28 | TASK-020: `/series` CRUD + `/series/{id}/members` + 검수 큐 + match confirm/reject/attach (10개), `/query.series_filter` 추가 + 활성 스코프 우선순위 doc>category>series |
| 2026-04-25 | 큐 모드(`/ingest` 응답에 `job_id`, queue/sync 분기) + `/jobs` 2개 + `/documents/{id}/summary` GET·regenerate + `PATCH /documents/{id}` + `/documents/{id}/chunks` + `/index/overview` 확장 + `/query`에 `doc_filter` |
| 2026-04-21 | `/ingest` 409 응답(중복 감지 L1), `/query`에 `session_id` 추가, `/conversations` CRUD 신설 |
| 2026-04-17 | 초안 작성 |
