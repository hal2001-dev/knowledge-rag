# API 엔드포인트 명세

**상태**: draft
**마지막 업데이트**: 2026-04-21
**관련 페이지**: [[features/generation.md]], [[config/environments.md]]

---

## Base URL

| 환경 | URL |
|------|-----|
| dev | `http://localhost:8000` |
| prod | (미정) |

---

## 엔드포인트 목록

### POST /ingest
문서를 업로드하고 벡터 인덱스에 추가합니다. 업로드 바이트의 SHA-256이 기존 문서와 일치하면 409를 반환합니다 (중복 감지 L1).

**Request** (`multipart/form-data`)
- `file`: 업로드 파일 (pdf|txt|md|docx)
- `title`: 문서 제목 (form field)
- `source`: 출처 설명 (form field, optional)

**Response 200**
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
| 413 | 파일 크기 초과 (`max_upload_size_mb`, 기본 50MB) |
| 500 | 임베딩 실패 |

---

### POST /query
질문을 입력받아 답변을 반환합니다. `session_id`로 대화 히스토리를 이어갈 수 있습니다 — 없으면 새 세션이 생성되고, 있으면 해당 세션의 **최근 20개 턴**이 LLM 컨텍스트로 주입됩니다.

**Request**
```json
{
  "question": "질문 텍스트",
  "session_id": "uuid (optional)",
  "top_k": 3,
  "score_threshold": 0.7
}
```

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
  "latency_ms": 1240
}
```

---

### POST /conversations
새 대화 세션을 생성합니다. (클라이언트가 `/query`를 바로 호출해도 서버가 새 세션을 자동 발급하므로 선택적으로 사용)

**Request** — `{"title": "(optional)"}`
**Response** — `{"session_id", "title", "created_at", "updated_at"}`

### GET /conversations
모든 세션 목록 (최근 업데이트순).

**Response** — `{"conversations": [ConversationSummary...], "total": int}`

### GET /conversations/{session_id}
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

### DELETE /conversations/{session_id}
세션과 모든 메시지 삭제 (CASCADE).

**Response** — `{"deleted": "<session_id>"}` / 404

---

### GET /documents
인덱싱된 문서 목록을 반환합니다.

**Response**
```json
{
  "documents": [
    {
      "doc_id": "uuid",
      "title": "문서 제목",
      "chunk_count": 42,
      "indexed_at": "2026-04-17T10:00:00Z"
    }
  ]
}
```

---

### DELETE /documents/{doc_id}
특정 문서를 인덱스에서 제거합니다.

**Response**
```json
{
  "status": "deleted",
  "doc_id": "uuid"
}
```

---

## 인증

현재: 없음 (개발 환경)
향후: API Key 헤더 방식 검토 → [[security.md]]

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-04-21 | `/ingest` 409 응답(중복 감지 L1), `/query`에 `session_id` 추가, `/conversations` CRUD 신설 |
| 2026-04-17 | 초안 작성 |
