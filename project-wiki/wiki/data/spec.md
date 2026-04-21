# 데이터 스펙 (Data Spec)

**상태**: draft
**마지막 업데이트**: 2026-04-21
**관련 페이지**: [[features/ingestion.md]], [[data/quality.md]]

---

## 지원 입력 형식

| 형식 | 지원 여부 | 파서 | 비고 |
|------|-----------|------|------|
| PDF | ✅ | Docling 2.x | 텍스트·테이블·이미지 추출 |
| 스캔 PDF (이미지) | ⚠️ | OCR 필요 | 추후 검토 |
| DOCX | ✅ | Docling 2.x | 2026-04-19부터 지원 |
| TXT | ✅ | Docling 2.x | |
| Markdown | ✅ | Docling 2.x | |

---

## 입력 문서 제약

| 항목 | 제약 |
|------|------|
| 최대 파일 크기 | 50MB |
| 최대 페이지 수 | (미정) |
| 지원 언어 | 한국어, 영어 |
| 인코딩 | UTF-8 |

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

→ [[architecture/decisions.md]] ADR-008

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
- 한계: 포맷만 다른 동일 내용(예: 같은 PDF의 스캔본 vs 텍스트본), 리비전 차이가 있는 버전은 감지 불가 → L2/L3 도입 시 해결 (→ [[architecture/decisions.md]] ADR-005)
- 기존 NULL 레코드: 도입 이전 문서는 `content_hash=NULL`로 감지 대상 외. 필요 시 백필 스크립트 별도 작성.

---

## 현재 사용 중인 데이터셋

| 이름 | 설명 | 문서 수 | 경로 |
|------|------|---------|------|
| (개발용 샘플) | | | raw/data/ |
