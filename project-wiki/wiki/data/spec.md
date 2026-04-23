# 데이터 스펙 (Data Spec)

**상태**: active
**마지막 업데이트**: 2026-04-23
**관련 페이지**: `ingestion.md` _(미작성)_, `quality.md` _(미작성)_, [schema.md](schema.md) (DB 구조), [decisions.md](../architecture/decisions.md)

---

## 지원 입력 형식

| 형식 | 지원 여부 | 파서 | 비고 |
|------|-----------|------|------|
| PDF (디지털·텍스트 레이어) | ✅ | Docling 2.x | 텍스트·테이블·이미지 추출 |
| PDF (스캔·이미지 기반) | ✅ | Docling 2.x + **EasyOCR 자동** | 2026-04-23 확인. `do_ocr=True` 기본값으로 자동 처리 |
| DOCX | ✅ | Docling 2.x | 2026-04-19부터 지원 |
| TXT | ✅ | Docling 2.x | |
| Markdown | ✅ | Docling 2.x | |

---

## 입력 문서 제약

| 항목 | 제약 |
|------|------|
| 최대 파일 크기 | **200MB** (`MAX_UPLOAD_SIZE_MB`, `.streamlit/config.toml` 동기화) |
| 최대 페이지 수 | (미정) |
| 지원 언어 | 한국어, 영어 (OCR은 EasyOCR 기본 모델 지원 범위) |
| 인코딩 | UTF-8 |

---

## PDF 처리 프로세스 (End-to-End)

업로드된 PDF가 검색 가능한 벡터로 저장되기까지의 단계. 다른 형식(DOCX/TXT/MD)도 거의 동일하나 OCR 분기만 차이.

### Stage 0 — 업로드 수신
- `POST /ingest` ([apps/routers/ingest.py](../../../apps/routers/ingest.py))
- 파일 확장자 화이트리스트 검사 (`.pdf/.txt/.md/.docx`)
- 파일 크기 검사 (`MAX_UPLOAD_SIZE_MB`, 기본 200MB)
- **SHA-256 해시**로 중복 감지 (L1, ADR-005). 동일 해시 존재 시 `409 Conflict` 반환 (재파싱 생략)
- 원본 파일은 `data/uploads/{doc_id}{ext}`에 영구 보관 (ADR-010, 재인덱싱 가능)

### Stage 1 — Docling 파싱 (OCR 포함)
구현: [packages/loaders/docling_loader.py](../../../packages/loaders/docling_loader.py) · `DoclingDocumentLoader.load()`

**자동 OCR 동작** (페이지별로 Docling이 자동 분기):

| 페이지 유형 | 동작 | 속도 |
|---|---|---|
| 텍스트 레이어 존재 (digital PDF) | 텍스트 레이어 직접 추출 (OCR 건너뜀) | 빠름 (~수십 ms/페이지) |
| 스캔·이미지 기반 | EasyOCR로 페이지 이미지 → 텍스트 추출 | 느림 (~1~5초/페이지, 한국어·영어 기본 지원) |
| 혼합 | 페이지 단위로 자동 결정 | 중간 |

**첫 실행 시**: Docling이 내부 모델(TableFormer, EasyOCR 등)을 HuggingFace Hub에서 다운로드 (~1~2GB). 이후 캐시.

### Stage 2 — 마크다운 저장
- `ExportType.MARKDOWN`으로 **두 번째 Docling 변환** 실행 → 전체 문서의 마크다운 출력
- `_normalize_markdown()`으로 정규화 (NFC, 단어 분리 하이픈 복구, 페이지 번호 제거, NBSP/ZWSP 정리, 테이블 행 구조 보존)
- `data/markdown/{doc_id}.md`로 저장 — 나중에 원본 소실 시 **재인덱싱 fallback** 입력

### Stage 3 — HybridChunker 청킹 (ADR-009, ADR-021)
- `HuggingFaceTokenizer(model="sentence-transformers/all-MiniLM-L6-v2", max_tokens=480)`
- `HybridChunker(merge_peers=True, always_emit_headings=True, omit_header_on_overflow=False)`
- `langchain-docling`의 `DoclingLoader(export_type=DOC_CHUNKS, chunker=...)`로 호출

결과 청크:
- `content_type`: `text` | `table` | `image` (Docling `doc_items.label` 기반)
- `heading_path`: 전체 heading 계층 (예: `["Chapter 8","8.5","8.5.3 자율 주행"]`) — **breadcrumb로 본문 앞에 prepend**
- `page`: `dl_meta.doc_items[*].prov[0].page_no` (스캔 PDF도 페이지 번호 복구됨)
- 정규화: content는 `_normalize()` 적용 (테이블 청크는 제외하여 구조 보존)

### Stage 4 — 2차 방어 청킹
- [packages/rag/chunker.py](../../../packages/rag/chunker.py)의 `RecursiveCharacterTextSplitter(chunk_size=2000, overlap=100)`
- HybridChunker가 2000자 이상의 극단적 청크를 만든 경우에만 동작 (거의 발생 안 함)

### Stage 5 — 임베딩·Qdrant 저장
- [packages/llm/embeddings.py](../../../packages/llm/embeddings.py) — 기본 OpenAI `text-embedding-3-small` (1536-d). 토글로 BGE-M3(1024-d) 가능 (ADR-016)
- Qdrant 컬렉션은 임베딩 차원에 따라 자동 생성/검증
- payload에 `metadata` 전체(`doc_id`, `title`, `source`, `page`, `heading_path`, `content_type`, `dl_meta` 등) 저장

### Stage 6 — PostgreSQL 메타데이터 기록
- `documents` 테이블에 1행 insert: `doc_id`, `title`, `source`, `file_type`, `content_hash`, `chunk_count`, `has_tables`, `has_images`, `indexed_at`, `status`
- `invalidate_index_overview_cache()` 호출 → 빈 채팅 카드(ADR-020) 캐시 무효화

### 장애·예외 처리
- Stage 1~5 중 예외 발생 시 `data/uploads/{doc_id}{ext}`를 `unlink`하고 500 응답 (부분 상태 방지)
- 이미 등록된 content_hash이면 Stage 0에서 즉시 409 반환, Docling 실행 안 함
- OCR이 빈 결과를 낼 수 있는 케이스(보안 PDF, 손상된 파일, 비정상 인코딩 PDF 등)는 `chunk_count=0`이나 비정상적으로 작은 값으로 관측됨 → `troubleshooting/common.md` 참고

### 단계별 타이밍 (LangSmith + 서버 로그)
- `파싱 Xms · 청킹 Yms · 저장 Zms · 총 Wms` 포맷으로 ingest 로그에 기록 (ADR-007, ADR-014)
- LangSmith의 `rag.ingest` run에 단계 분해 가시성

---

## 청킹 설정 (현재 기준)

| 파라미터 | 값 | 비고 |
|----------|-----|------|
| 1차 청커 | **HybridChunker** (docling-core) | `merge_peers=True`, `always_emit_headings=True`, `omit_header_on_overflow=False` → ADR-009 |
| heading 경로 주입 | ✅ breadcrumb `"A > B > C"`를 content 앞에 prepend | 중복 제거 로직(`_strip_leading_headings`) 포함 |
| page 번호 복구 | ✅ `dl_meta.doc_items[*].prov[0].page_no`에서 추출 | 마크다운 입력 시에는 prov 없어서 `page=0` |
| 2차 청커 (방어용) | RecursiveCharacterTextSplitter | `chunk_size=2000`, `overlap=100`. HybridChunker가 주 청킹, 극단적 긴 청크만 안전망 |
| 테이블·이미지 청크 | 분할·normalize 모두 제외 | `content_type==table`는 파이프·대시 구조 보존 |
| 효과 (ROS PDF) | **1619 → 800 청크 (−51%)** | 섹션 경계 존중으로 응집도↑ |

### 파싱 후 정규화 (2026-04-21 추가)

Docling 파싱 결과를 청킹 전에 정규화한다 ([packages/loaders/docling_loader.py](../../packages/loaders/docling_loader.py)):

- NFC 유니코드 정규화
- 단어 분리 하이픈 복구 (`robot-\nics` → `robotics`)
- 숫자만 있는 줄(페이지 번호) 제거
- NBSP/ZWSP 등 비정상 공백 → 일반 공백
- 연속 공백·빈 줄 압축
- 테이블 청크·테이블 행은 구조 보존을 위해 정규화 제외

→ [decisions.md](../architecture/decisions.md) ADR-008

---

## 메타데이터 스키마

각 chunk에 저장되는 메타데이터:

```python
{
    "doc_id": str,                # 문서 고유 ID
    "title": str,                 # 문서 제목
    "source": str,                # 원본 파일 경로
    "page": int,                  # 페이지 번호 (PDF, prov.page_no 기반, 마크다운이면 0)
    "heading_path": list[str],    # 전체 heading 계층 (예: ["Chapter 8","8.5","8.5.3 자율 주행"])
    "chunk_index": int,           # 문서 내 청크 순서
    "indexed_at": str,            # ISO 8601 datetime
    "language": str,              # "auto"
    "content_type": str,          # "text" | "table" | "image"
    "dl_meta": dict,              # Docling 원본 메타 (doc_items, headings, prov 등)
}
```

---

## 중복 감지

업로드 시 파일 바이트 전체의 **SHA-256(64자 hex)** 을 계산해 `documents.content_hash`(UNIQUE) 에 저장합니다.
동일 해시가 이미 존재하면 `POST /ingest`가 `409 Conflict`와 기존 `doc_id`·`title`을 반환합니다 (idempotent).

- 감지 수준: **L1 (바이트 단위)** — 파일명/제목이 달라도 바이트가 동일하면 중복
- 한계: 포맷만 다른 동일 내용(예: 같은 PDF의 스캔본 vs 텍스트본), 리비전 차이가 있는 버전은 감지 불가 → L2/L3 도입 시 해결 (→ [decisions.md](../architecture/decisions.md) ADR-005)
- 기존 NULL 레코드: 도입 이전 문서는 `content_hash=NULL`로 감지 대상 외. 필요 시 백필 스크립트 별도 작성.

---

## 현재 사용 중인 데이터셋

| 이름 | 설명 | 문서 수 | 경로 |
|------|------|---------|------|
| (개발용 샘플) | | | raw/data/ |
