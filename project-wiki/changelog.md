# Changelog

버전별 변경 이력입니다. 새 항목은 위에 추가합니다.

---

## 형식

```markdown
## [버전] - YYYY-MM-DD
### Added
- 새로 추가된 기능
### Changed
- 변경된 기능
### Fixed
- 수정된 버그
### Removed
- 제거된 기능
### Deprecated
- 곧 제거될 기능
```

---

## [0.5.0] - 2026-04-21

### Added
- **HybridChunker 명시적 설정 + 전체 heading 경로 breadcrumb 주입**: 청크 content 앞에 `"Chapter > Section > Subsection"` prepend. `always_emit_headings=True`, `omit_header_on_overflow=False`. 중복 제거 로직 포함
- **페이지 번호 복구**: `dl_meta.doc_items[*].prov[0].page_no`에서 실제 페이지 추출 (기존엔 전부 0)
- **원본 파일 영구 보관**: `data/uploads/{doc_id}{ext}` 보존 — 재인덱싱 가능 구조
- **FlashRank 실제 활성화**: 그동안 정의만 있고 미사용이던 재순위를 `retrieve()`에서 실제 호출
- `pipeline/rebuild_index.py` 마크다운 fallback 지원 (`data/uploads/` 없으면 `data/markdown/{doc_id}.md`)

### Changed
- ROS PDF 기준 청크 수: **1619 → 800 (−51%)** — 섹션 경계 존중으로 의미 응집도↑
- 2차 청커 `RecursiveCharacterTextSplitter` 상한: 512자 → 2000자 (HybridChunker가 주 청킹, 보조 역할)
- `retrieve()`의 score 의미 변경: Qdrant 코사인 유사도 → FlashRank 점수(0~1)

### Known Issues
- FlashRank `ms-marco-MiniLM-L-12-v2`는 영어 학습 모델이라 **한국어 질의 + 영문 문서 크로스에 약함** — 다국어 재순위 모델 평가 필요
- 이번 재인덱싱은 원본 PDF가 소실되어 마크다운 fallback 사용 — PDF의 `prov.page_no`는 활용 못 함

---

## [0.4.0] - 2026-04-21

### Added
- **LangSmith 관측 통합**: `@traceable` 데코레이터로 `rag.ingest`/`rag.query` 트레이스, 세션 ID 메타데이터 태깅, 단계별 타이머(`파싱/청킹/저장 ms`)
- **파싱 후 정규화**: Docling 로더에 `_normalize` 유틸 — NFC, 단어 분리 하이픈 복구, 페이지 번호 제거, 비정상 공백/연속 공백 정리 (테이블 구조는 보존)
- `.streamlit/config.toml` 업로드 호환성 설정 (XSRF/CORS off, maxUploadSize=200)

### Changed
- 업로드 상한: **50MB → 200MB** (`.env`, `apps/config.py`, Streamlit 모두 동기화)
- UI 타임아웃: 600s → 1800s
- `default_score_threshold`: 0.7 → 0.3 (한↔영 임베딩 유사도 실제 분포에 맞춤)
- `ui/app.py`의 `file_uploader` `type` 화이트리스트 제거 → 모바일 파일 피커 호환

### Fixed
- 모바일/LAN IP 접근 시 파일 업로드가 차단되던 문제
- `/query`가 점수 임계치 초과로 "관련 문서를 찾지 못했습니다"를 반환하던 문제

---

## [0.3.0] - 2026-04-21

### Added
- **대화 히스토리 영속화**: `conversations`, `messages` 테이블 신설. `/query`에 `session_id` 옵션 추가, 최근 20개 턴을 LLM 컨텍스트로 주입
- **세션 관리 API**: `POST/GET /conversations`, `GET/DELETE /conversations/{session_id}`
- **파일 해시 기반 중복 업로드 감지 (L1)**: 업로드 바이트의 SHA-256 → 동일 해시 존재 시 `409 Conflict` (기존 `doc_id`/`title` 반환)
- `documents.content_hash` 컬럼 + UNIQUE INDEX
- `.streamlit/config.toml`: `maxUploadSize=200`, `runOnSave=true`

### Changed
- `packages/rag/generator.py`: `ChatPromptTemplate` → `SystemMessage` + `Human/AI` 메시지 시퀀스 (히스토리 주입용)
- UI(`ui/app.py`): `session_id`를 `st.session_state`에 유지, 409 응답을 `st.warning`으로 표시, 파일 선택 시 파일명·크기 명시

---

## [0.2.0] - 2026-04-19

### Added
- `setup.sh`: Python 3.12.2 venv 생성 및 의존성 설치 자동화
- `docker-compose.yml`: Qdrant + PostgreSQL 컨테이너 구성
- `packages/loaders/`: Docling 기반 문서 로더 (텍스트·테이블·이미지 파싱)
- `packages/rag/chunker.py`: RecursiveCharacterTextSplitter (512자, 50 오버랩)
- `packages/vectorstore/qdrant_store.py`: Qdrant 벡터스토어 래퍼 (add/search/delete)
- `packages/db/`: PostgreSQL ORM + Repository (SQLAlchemy)
- `packages/rag/retriever.py`: FlashRank reranking (top-20 → top-5)
- `packages/rag/generator.py`: gpt-4o-mini 프롬프트 체인
- `packages/rag/pipeline.py`: ingest / query 전체 파이프라인
- `apps/`: FastAPI REST API (4개 엔드포인트)
- `ui/app.py`: Streamlit UI (업로드·채팅·문서 관리)
- 문서 파싱 시 `data/markdown/{doc_id}.md` 자동 저장

### Changed
- 벡터 DB: FAISS → Qdrant (Docker 기반, 삭제 지원)
- 문서 파서: pdfplumber → Docling (테이블·이미지 파싱 포함)

---

## [0.1.0] - 2026-04-17

### Added
- 프로젝트 위키 초기 구조 설정
