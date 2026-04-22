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

## [0.10.0] - 2026-04-22

### Added
- **관리자 UI 1단계** (TASK-005, ADR-017): Streamlit `st.tabs`로 5개 탭 구조 — 채팅/문서/대화/시스템/평가
- 문서 탭: 업로드·목록·삭제 + **청크 미리보기** (상위 10개, heading_path·page·content_type 표시)
- 대화 탭: `/conversations` 목록 + 메시지 뷰 + 세션 삭제
- 시스템 탭: Reranker·LLM·Embedding·Qdrant·Health·LangSmith 6개 카드 (읽기 전용)
- 평가 탭: 최신 Retrieval/Answer 지표 + 최근 10개 히스토리
- 신규 API: `GET /documents/{doc_id}/chunks?limit=N`
- 신규 메서드: `QdrantDocumentStore.scroll_by_doc_id(doc_id, limit)`
- 스키마: `ChunkPreview`, `ChunkPreviewResponse`

### Changed
- `ui/app.py` 전면 재작성 (탭 구조)
- 사이드바의 업로드·문서 목록을 "문서" 탭으로 이전

### Notes
- 1단계는 **인증 없음, LAN 전용**. 2단계 승격 시 `ADMIN_PASSWORD`+HTTPS 리버스 프록시 + ISSUE-001 해결

---

## [0.9.0] - 2026-04-22

### Added
- **Embedding 백엔드 토글** (TASK-002, ADR-016): `EMBEDDING_BACKEND=openai|bge-m3`
- `apps/config.py`: `embedding_backend`, `embedding_model_name`, `embedding_warmup` 필드
- `packages/llm/embeddings.py` 전면 재작성: `_EmbeddingWithDim` 래퍼가 `embedding_dim` 속성 노출 (Qdrant 컬렉션 자동 차원 감지)
- `packages/vectorstore/qdrant_store.py`: 기존 컬렉션 차원 검증 + `CollectionDimensionMismatch` 예외
- `requirements.txt`: `langchain-huggingface` 추가
- `pipeline/rebuild_index.py`: reranker 주입 적용(차원 변경 시 재인덱싱 지원)

### Changed
- Qdrant 컬렉션 하드코딩된 `VECTOR_SIZE=1536` 제거 → 임베딩 객체의 `embedding_dim` 기반
- 기본값 `EMBEDDING_BACKEND=openai` 유지 (ADR-016, 회귀 0)

### A/B 실험 기록
BGE-M3 vs OpenAI(동일 reranker·LLM, dataset 12개):
- Retrieval 4종 지표 동률 (이미 상한)
- Retrieval latency: 580 → 423ms (−27%)
- faithfulness 0.886→0.857, answer_relevancy 0.648→0.618, context_precision 0.986→0.924, context_recall 0.942→0.917 (소폭 하락)
- **결정: OpenAI 기본 유지, BGE-M3 토글 확보** (ADR-016)

---

## [0.8.0] - 2026-04-22

### Added
- **평가 프레임워크** (TASK-004, ADR-015)
- `tests/eval/dataset.jsonl` — 12개 질의 + `expected_doc_ids` 라벨 (ko 7 / en 4 / mixed 2)
- `scripts/bench_retrieval.py` — Hit@K / Precision@K / Recall@K / MRR, reranker A/B 지원, JSON 저장
- `scripts/bench_answers.py` — Ragas 4종 지표 (faithfulness, answer_relevancy, context_precision, context_recall), LangSmith 자동 기록
- `requirements.txt`에 `ragas>=0.2`, `datasets>=4.0` 추가

### Fixed
- `bench_answers.py` 초기 버전이 `pipeline.query`의 200자 excerpt를 Ragas에 넘겨 faithfulness가 0.15로 급락하던 문제 → `retrieve()` 직접 호출로 전체 청크 전달 (0.886 복구)
- `bench_retrieval.py`의 recall 공식이 청크 중복을 카운트해 1을 초과하던 버그 → unique-document 기반으로 수정

### 기반선 수치 (2026-04-22)
- Retrieval (BGE-M3): Hit@3 = 1.000, Precision@3 = 1.000, MRR = 1.000, Recall@3 = 0.944
- Answer (gpt-4o-mini): faithfulness = 0.886, answer_relevancy = 0.648, context_precision = 0.986
- 이후 모든 품질 ADR은 before/after 수치 첨부 의무화

---

## [0.7.0] - 2026-04-22

### Added
- **LLM 백엔드 토글 인프라** (TASK-003, ADR-014): `.env`의 `LLM_BACKEND` 값(`openai|glm|custom`)만 바꿔 OpenAI ↔ GLM ↔ 기타 OpenAI-호환 공급자로 즉시 전환 가능
- `apps/config.py`: `llm_backend`, `llm_base_url`, `llm_api_key`, `llm_model`, `llm_temperature` 5개 필드 + 기존 `openai_chat_*` legacy fallback
- `packages/llm/chat.py`: `_BACKENDS` 기본값 맵(openai/glm/custom) + `_resolve()`로 `.env` 우선순위 해석
- LangSmith 트레이스에 `llm:<backend>` 태그 + `llm_backend`·`llm_model` 메타 (reranker 태깅과 동일 패턴)

### Changed
- `packages/rag/pipeline.py`의 query 로그 포맷에 LLM 정보 포함: `reranker=bge-m3, llm=openai:gpt-4o-mini`
- 기본값: `LLM_BACKEND=openai`, 실효 모델 `gpt-4o-mini` — ADR-013 결론 준수 (**회귀 0**)

### Notes
- 향후 공급자 교체는 `.env`의 `LLM_BACKEND`·`LLM_API_KEY`·(선택) `LLM_MODEL` 세 줄만 수정하면 완료
- 정량 비교는 TASK-004 평가 프레임워크 도입 후 수행

---

## [0.6.0] - 2026-04-22

### Added
- **BGE-reranker-v2-m3 도입** (다국어 cross-encoder): 한↔영 크로스 재순위 품질 해결
- `packages/rag/reranker.py`: `Reranker` 추상화 + `FlashRankReranker`·`BgeM3Reranker` 두 백엔드, `get_reranker()` 팩토리
- `.env`의 `RERANKER_BACKEND` 토글(`flashrank|bge-m3`), `RERANKER_MODEL_NAME`, `RERANKER_WARMUP` 변수
- lifespan preload(`reranker_warmup=true`)로 첫 질의 지연 제거
- LangSmith 트레이스에 `reranker:<backend>` 태그 + `reranker_backend` 메타 (쿼리별 필터링 가능)
- `sentence-transformers>=3.0` 의존성

### Changed
- `packages/rag/retriever.py`가 reranker 주입형으로 재작성, `RAGPipeline`이 `reranker`를 보유
- 기본 reranker 백엔드: `flashrank` → **`bge-m3`**

### Fixed
- ADR-011에서 관찰된 한국어 질의가 무관한 한국어 문서를 1위로 올리는 현상 해결 (완료 기준 충족)

### 평가
- [evaluation.md](wiki/features/evaluation.md) 에 5개 질의 A/B 비교 표 기록

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
