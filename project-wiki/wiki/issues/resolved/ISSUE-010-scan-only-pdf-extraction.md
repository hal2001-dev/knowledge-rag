---
name: ISSUE-010 스캔본 PDF 텍스트 추출 누락 — 16권 본문 사실상 0, 검색·답변 불가
description: 텍스트 레이어가 없는 스캔 PDF 16건이 Docling 기본 모드에서 목차·판권만 추출되고 본문은 사실상 0인 상태로 색인됨. 시리즈 ser_f091b1e5242e + "등장인물은?" 질의에 답이 없는 것을 계기로 발견. extraction_quality 컬럼 도입 + 휴리스틱 백필 + 도서관 카드 배지 + macOS Vision OCR 재색인으로 해결.
type: issue
---

# ISSUE-010: 스캔본 PDF 텍스트 추출 누락 — 16권 본문 사실상 0

**상태**: resolved · 2026-04-30
**발생일**: 2026-04-30 (사용자 보고)
**해결일**: 2026-04-30
**관련 기능**: ingestion, retrieval — 모든 OCR 파이프라인 의존 작업
**관련 ADR**: [ADR-032](../../architecture/decisions.md) OCR 토글 + 스캔본 재색인 정책
**관련 코드**:
- [packages/db/migrations/0006_add_extraction_quality.sql](../../../../packages/db/migrations/0006_add_extraction_quality.sql) — `documents.extraction_quality` 컬럼 + CHECK + index
- [packages/db/models.py](../../../../packages/db/models.py), [packages/code/models.py](../../../../packages/code/models.py), [packages/db/repository.py](../../../../packages/db/repository.py), [apps/schemas/documents.py](../../../../apps/schemas/documents.py) — 모델·스키마·Repository 통과
- [packages/loaders/docling_loader.py](../../../../packages/loaders/docling_loader.py) — `force_full_page_ocr` flag + macOS Vision OCR converter
- [scripts/classify_extraction_quality.py](../../../../scripts/classify_extraction_quality.py) — 휴리스틱 백필 (markdown 크기·평균 chunk 길이)
- [scripts/test_ocr_single.py](../../../../scripts/test_ocr_single.py) — 단권 검증용
- [scripts/reingest_scan_only.py](../../../../scripts/reingest_scan_only.py) — `scan_only` 일괄 재색인
- [web/components/library/doc-card.tsx](../../../../web/components/library/doc-card.tsx) — `📷 스캔` 배지

---

## 증상

사용자가 시리즈 `ser_f091b1e5242e`(하루하루가 세상의 종말) + "등장인물은?" 질의 시 "정보가 포함되어 있지 않습니다" 응답. 검색 결과 sources의 excerpt가 `"102j2l"`, `"182 003"` 같은 OCR 노이즈·페이지 번호 조각만 노출.

진단 결과: 두 권의 markdown 파일 크기가 5~7KB (소설 한 권으로는 비정상적으로 작음). 스캔 후 본문이 사실상 추출되지 않은 상태로 색인됐음.

## 원인 분석

전체 107건 중 16건이 동일 패턴의 스캔본:
- 모두 소설 (디지털 포트리스, 스노우 크래쉬, 하루하루가 세상의 종말, 천사들의 제국, 성채, 종말일기 Z, 데드 아일랜드, 좀비 서바이벌 가이드, 양심의 문제, 우주바이러스 The Andromeda Strain)
- markdown 크기 < 30KB 또는 chunk 평균 길이 < 150B
- 추출된 청크는 목차·판권·페이지번호 조각뿐

근본 원인: **Docling 기본 OCR 설정 (`do_ocr=True`이지만 `force_full_page_ocr=False`)**. 레이아웃 모델이 페이지 전체를 단일 이미지로 인식하지 못해 OCR 영역 자체가 안 잡힘. `bitmap_area_threshold=0.05`도 작은 영역을 추가로 필터링.

기존 텍스트 레이어가 있는 디지털 PDF 91건은 정상 추출 — Docling의 텍스트 백엔드가 직접 처리해서 OCR 경로 무관.

## 해결 방법

### 1. 식별 — `extraction_quality` 컬럼

`documents.extraction_quality TEXT` 컬럼 추가 (NULL/`ok`/`partial`/`scan_only`). 휴리스틱(markdown 크기 + chunk 평균 길이)으로 16건을 `scan_only`로 백필.

### 2. UI 표시 — 도서관 카드 배지

`web/components/library/doc-card.tsx`에 `📷 스캔` 배지 + tooltip ("스캔본 — 검색·답변 불가") 추가. 사용자가 어떤 책이 영향받는지 즉시 인지.

### 3. 재색인 — macOS Vision OCR

ADR-032 합의 후 `DoclingDocumentLoader.force_full_page_ocr=True` 옵션 추가. macOS Vision (`ocrmac`, Docling 2.90.0 의존성에 이미 포함)으로 페이지 전체 OCR. EasyOCR/Tesseract 대비:
- 추가 의존성 0
- 한국어·영어 정확도 충분 (단권 테스트 검증)
- 권당 4~8분 (Docling 레이아웃 + 청킹 포함)

`scripts/reingest_scan_only.py` 일괄 실행:
- 권당: OCR → markdown 덮어쓰기 → Qdrant 청크 삭제 → 새 청크 add → category/series payload 재적용 → DB 갱신 (chunk_count, extraction_quality='ok', summary=NULL)
- 결과: **16/16 성공, 총 119.5분, 평균 8분/권, 메모리 RSS 피크 6.9GB (8GB 가드 안쪽)**, 에러 0

### 4. summary 재생성

OCR 후 `summary=NULL`로 무효화 → `scripts/generate_summaries.py` 자동 대상으로 재생성.

## 검증

### 데이터 측
- 마크다운 평균 크기: 5KB → 200~500KB (~50~100배 증가)
- 청크 수: 평균 70 → 800 (~10배)
- 모든 107건 `extraction_quality='ok'`

### 사용자 시나리오
- 시리즈 `ser_f091b1e5242e` + "등장인물은?" 재질의:
  - 이전: "정보가 포함되어 있지 않습니다." + sources excerpt "102j2l"
  - 현재: "놈들·해병들·중사·FBI 요원" 등 실제 본문 인용. excerpt = "8월 11일 22시 28분 한 언덕지대라면 놈들은 계곡 어디에나 숨어 있을 수 있다…"

답변이 여전히 "구체적 이름은 부족"이라 회신하는 건 좀비 소설 본문 특성(익명 캐릭터 위주)이지 OCR 실패가 아님.

## 재발 방지

### 신규 색인 시점
- TASK-018 indexer 워커가 새 PDF 색인할 때 `extraction_quality`를 자동 평가·기록하는 후처리 훅 도입 검토 (현재는 수동 백필 — `scripts/classify_extraction_quality.py --only-empty`)
- 신규 스캔본 자동 OCR 모드 진입은 보류 — 일반 PDF에 OCR을 켜면 시간만 폭증

### 운영
- `scripts/classify_extraction_quality.py --only-empty` 정기 실행 (launchd 큐에 합류 검토)
- 도서관 카드 `📷 스캔` 배지로 사용자가 직접 보고할 수 있음 — 운영자 모니터링 부담 ↓

**관련**: ADR-030(NextJS 사용자 UI), ADR-032(OCR 토글), TASK-024(스트리밍 SSE — 옆 묶음)
