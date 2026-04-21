# Wiki Log

이 파일은 append-only입니다. 항목을 수정하지 말고 새 항목을 위에 추가하세요.
`grep "^## \[" log.md | head -10` 으로 최근 항목을 빠르게 확인할 수 있습니다.

---

## [2026-04-21] impl | 청킹·검색 품질 대폭 업그레이드 (재인덱싱 전제)

### HybridChunker + 전체 heading 경로 주입
- `packages/loaders/docling_loader.py`: 내부 기본 설정 대신 **명시적** `HybridChunker(merge_peers=True, always_emit_headings=True, omit_header_on_overflow=False)`로 교체
- `_extract_heading_path()`: 청크의 `dl_meta.headings` 전체 계층을 리스트로 추출
- `_strip_leading_headings()`: HybridChunker `contextualize()`가 본문 앞에 prepend하던 heading 라인을 정확히 정렬해 제거 → 중복 방지
- 최종 청크 콘텐츠 형태: `"Chapter 1 > Section 1.1\n\n<본문>"`
- 효과: ROS PDF가 **1619 → 800 청크 (−51%)**. 섹션 경계를 존중하며 응집도 높은 청크로 통합

### 페이지 번호 복구
- 기존 로더는 `raw_meta.get("page", raw_meta.get("dl_meta", {}).get("page", 0))`로 잘못된 키를 찾아 `page=0`만 저장
- `_extract_page_no()`: 청크의 `dl_meta.doc_items[*].prov[0].page_no`에서 실제 페이지 번호 추출
- 마크다운 fallback으로 재인덱싱 시에는 `page=0` 유지 (원본 PDF가 없어 `prov` 없음)

### 원본 파일 영구 보관 (재인덱싱 가능 구조)
- `apps/routers/ingest.py`: `finally: upload_path.unlink()` 제거 → 성공 시 `data/uploads/{doc_id}{ext}` 영구 보관, 인덱싱 실패 시에만 정리
- 향후 HybridChunker 옵션 튜닝·임베딩 모델 교체 시 재인덱싱이 즉시 가능

### FlashRank 실제 활성화 (미사용 → 사용)
- 기존 `retrieve()`는 정의만 있고 Qdrant 점수 정렬만 수행 (FlashRank 미경유)
- `packages/rag/retriever.py` 재작성: 프로세스 전역 `Ranker` 싱글톤, `RerankRequest`로 candidates 재순위, `score`를 FlashRank 점수(0~1)로 덮어씀
- 관찰된 부작용: `ms-marco-MiniLM-L-12-v2`가 영어 MARCO로 학습되어 **한국어 질의 + 영문 문서 크로스에 약함** → 후속 과제로 다국어 모델 평가 필요

### 2차 청커 완화
- `packages/rag/chunker.py`: HybridChunker가 토큰 예산으로 이미 관리하므로 `RecursiveCharacterTextSplitter` 상한을 512→2000자로 완화. 방어적 보조 역할로만 동작

### rebuild_index.py 강화
- `_resolve_source_file()`: `data/uploads/{doc_id}.*` 원본 우선, 없으면 `data/markdown/{doc_id}.md` fallback
- `content_hash`/`source` 전파로 재인덱싱 시 중복 감지 메타데이터 유지
- 이번 실행 결과: 성공 6건, 스킵 0건 (전부 마크다운 fallback — 원본 PDF는 소실됨)

### 관련 페이지
- architecture/decisions.md: ADR-009 (HybridChunker + breadcrumb), ADR-010 (원본 파일 보존), ADR-011 (FlashRank 실제 활성화)
- data/spec.md, overview.md, roadmap.md, changelog.md

---

## [2026-04-21] impl | LangSmith 관측 + 파싱 후 정규화 + 모바일 업로드 호환

### LangSmith 관측
- `.env`/`.env.example`/`apps/config.py`에 `LANGCHAIN_*` 4개 변수 추가
- `apps/main.py` lifespan에서 Pydantic 값을 `os.environ`으로 export (LangChain은 환경변수 직접 읽음)
- `RAGPipeline.ingest`/`query`에 `@traceable(run_type="chain", name="rag.ingest|rag.query")` 데코레이터 부착
- `ingest` 내부에 단계별 타이머 추가 → 로그에 `파싱 Xms · 청킹 Xms · 저장 Xms · 총 Xms`
- `apps/routers/query.py`에서 `tracing_context(tags=["session:<id>"], metadata={"session_id", "history_turns"})`로 대화별 필터링 가능
- 프로젝트명 `knowledge-rag`, 대시보드 확인 완료

### 파싱 후 정규화 (품질 개선 L1)
- `packages/loaders/docling_loader.py`에 `_normalize`/`_normalize_markdown` 추가
  - NFC 유니코드 정규화
  - 단어 중간 하이픈-줄바꿈 복구 (`robot-\nics` → `robotics`)
  - 숫자만 있는 줄(페이지 번호) 제거
  - NBSP/ZWSP 등 비정상 공백 → 일반 공백
  - 연속 공백·빈 줄 압축
- **테이블 행(`|...|`)은 구조 보존 위해 제외**, content_type==table 청크도 제외
- 효과 측정(1619청크 기존 PDF): -816자, -206줄
- 기존 인덱스 무영향 — 새 업로드부터 적용. 기존 문서 혜택은 재색인 필요

### 모바일 업로드 호환
- `.streamlit/config.toml`: `enableXsrfProtection=false`, `enableCORS=false` (개발망 한정)
- `ui/app.py`: `file_uploader`의 `type=[...]` 제약 제거 (모바일 파일 피커가 `.md`·`.docx` MIME 누락으로 선택 불가 문제) → 클라이언트측 확장자 검증으로 대체
- 업로드 상한 50MB → **200MB** 상향 (`.env` + `apps/config.py`), UI 타임아웃 600s → 1800s
- `default_score_threshold` 0.7 → 0.3 (한↔영 임베딩 유사도 현실값에 맞춤; 질의 결과 없음 문제 해결)

### 관련 페이지
- api/endpoints.md, data/spec.md, architecture/decisions.md (ADR-007 LangSmith, ADR-008 정규화), security.md, changelog.md, overview.md, roadmap.md

---

## [2026-04-21] impl | 파일 해시 기반 중복 업로드 방지 (L1)

- `documents` 테이블에 `content_hash VARCHAR(64)` 컬럼 + UNIQUE INDEX 추가 (`ALTER TABLE` 적용 완료)
- `apps/routers/ingest.py`: 업로드 바이트의 SHA-256 계산 → 동일 해시 존재 시 `409 Conflict` 응답 (기존 `doc_id`/`title` 반환, idempotent 동작)
- `packages/code/models.py`, `packages/db/repository.py`, `packages/rag/pipeline.py`: `content_hash` 필드 전파
- `ui/app.py`: 409 응답 시 `st.warning`으로 기존 문서 정보 표시
- 스모크 테스트: 동일 바이트 재업로드 시 409 + 기존 doc_id 반환 확인
- 관련 페이지: api/endpoints.md, data/spec.md, architecture/decisions.md (ADR-005)
- 기존에 인덱싱된 문서는 `content_hash=NULL`이므로 감지 대상 외 — 필요 시 백필 스크립트 별도 검토

---

## [2026-04-21] impl | 대화 히스토리 DB 저장 및 LLM 컨텍스트 주입

- 신규 테이블: `conversations`(세션), `messages`(턴, `(session_id, created_at)` 인덱스)
- `packages/db/conversation_repository.py` 신설 — `get_or_create_conversation`, `add_message`, `get_recent_messages(limit=20)`
- `packages/rag/generator.py`: `ChatPromptTemplate` 제거, `SystemMessage → [HumanMessage/AIMessage]* → HumanMessage(context+question)` 시퀀스로 히스토리 주입
- `apps/routers/query.py`: `session_id`(옵션) 수신, 없으면 새 세션 발급. 현재 턴 저장 **전** 최근 20개 메시지 스냅샷 로드 → LLM 컨텍스트로 전달 → 응답 후 user/assistant 메시지 저장
- `apps/schemas/query.py`: `QueryRequest.session_id`, `QueryResponse.session_id` 추가
- `apps/routers/conversations.py` 신설 — `POST/GET/GET{id}/DELETE{id}` CRUD
- `ui/app.py`: `st.session_state["session_id"]`로 세션 유지, "대화 초기화" 시 세션 리셋
- 형태소 분석은 임베딩+벡터 검색 경로에는 불필요하다고 결론 (M3 하이브리드 검색 도입 시 재검토)
- 관련 페이지: api/endpoints.md, architecture/decisions.md (ADR-006)

---

## [2026-04-19] impl | 전체 RAG 파이프라인 구현 완료

- Python 3.12.2 / venv 환경 구성 (`setup.sh`)
- Docker Compose로 Qdrant(:6333) + PostgreSQL(:5432) 기동
- **문서 파싱**: Docling 2.x — 텍스트·테이블·이미지 추출, 파싱 결과를 `data/markdown/{doc_id}.md`로 저장
- **청킹**: RecursiveCharacterTextSplitter (512자, 50 오버랩)
- **임베딩**: OpenAI text-embedding-3-small
- **벡터 DB**: Qdrant (`langchain-qdrant`) — doc_id 필터로 삭제 지원
- **메타데이터 DB**: PostgreSQL + SQLAlchemy ORM (`documents` 테이블)
- **Reranking**: FlashRank (`ms-marco-MiniLM-L-12-v2`) — Qdrant top-20 → FlashRank top-5
- **LLM**: gpt-4o-mini — 한국어/영어 자동 감지 응답
- **API 서버**: FastAPI (`POST /ingest`, `POST /query`, `GET /documents`, `DELETE /documents/{doc_id}`)
- **UI**: Streamlit (`ui/app.py`) — 업로드·채팅·문서관리 통합
- 비고: `langchain.text_splitter`, `langchain.retrievers` 경로 변경 대응 완료

---

## [2026-04-17] init | 위키 초기 생성
- 생성된 파일: CLAUDE.md, wiki/index.md, wiki/overview.md, wiki/log.md
- 비고: RAG 프로젝트 위키 초기 구조 설정
