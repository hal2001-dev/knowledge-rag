# 프로젝트 구조 (Project Structure)

**상태**: active
**마지막 업데이트**: 2026-04-23
**관련 페이지**: [decisions.md](decisions.md), [spec.md](../data/spec.md), [schema.md](../data/schema.md), [admin_ui.md](../features/admin_ui.md)

프로젝트 루트: `/Users/hal2001/workspace/projects/personal/knowledge-rag`

---

## 한눈 요약

```
knowledge-rag/
├── apps/             FastAPI 서버 (API 엔드포인트)
├── packages/         비즈니스 로직 (RAG · DB · 벡터저장소 · LLM · 로더)
├── ui/               Streamlit 멀티탭 UI
├── pipeline/         운영 스크립트 (재인덱싱)
├── scripts/          벤치·스모크 스크립트 (평가·수동 테스트)
├── tests/            pytest (unit + integration + eval dataset)
├── data/             런타임 데이터 (gitignore: uploads·markdown·DB 볼륨)
├── project-wiki/     설계·결정·이슈·로그 문서 (24 md 파일)
├── .claude/          Claude Code 로컬 설정 (gitignore)
├── .streamlit/       Streamlit 서버 설정
├── docker-compose.yml  Qdrant + PostgreSQL
├── requirements.txt    파이썬 의존성 (FastAPI·LangChain·Docling 등)
├── setup.sh            venv + docker 초기 셋업
└── pytest.ini          테스트 설정
```

---

## 전체 트리 (핵심 파일만, `.venv`·`__pycache__`·DB 볼륨 생략)

```
knowledge-rag/
├── apps/                              # FastAPI 애플리케이션
│   ├── __init__.py
│   ├── main.py                        # lifespan: LangSmith·Reranker warm-up·DB init
│   ├── config.py                      # Pydantic Settings (5개 백엔드 토글 포함)
│   ├── dependencies.py                # get_db · get_pipeline (reranker 주입)
│   ├── routers/
│   │   ├── ingest.py                  # POST /ingest (SHA-256 중복 감지 → 파이프라인)
│   │   ├── query.py                   # POST /query (세션·history·LangSmith 태깅)
│   │   ├── documents.py               # GET /documents · GET /index/overview · GET /documents/{id}/chunks · DELETE
│   │   └── conversations.py           # CRUD /conversations
│   └── schemas/
│       ├── ingest.py                  # IngestResponse (+ duplicate 플래그)
│       ├── query.py                   # QueryRequest · QueryResponse (suggestions 포함)
│       ├── documents.py               # DocumentItem · ChunkPreview · IndexOverviewResponse
│       └── conversations.py           # Conversation·Message 스키마
│
├── packages/                          # 재사용 비즈니스 모듈
│   ├── code/
│   │   ├── models.py                  # Document · DocRecord · ScoredChunk 데이터클래스
│   │   └── logger.py                  # get_logger (표준 포매터)
│   ├── db/                            # PostgreSQL (ADR-005, ADR-006)
│   │   ├── connection.py              # init_db · get_session
│   │   ├── models.py                  # documents / conversations / messages SQLAlchemy ORM
│   │   ├── repository.py              # document CRUD + hash 조회
│   │   ├── conversation_repository.py # 대화 CRUD + 최근 N턴 로드
│   │   └── migrations/init.sql        # 참고용 초기 스키마
│   ├── llm/
│   │   ├── chat.py                    # build_chat — LLM 백엔드 토글 (ADR-014)
│   │   └── embeddings.py              # build_embeddings — openai / bge-m3 (ADR-016)
│   ├── loaders/
│   │   ├── base.py                    # BaseLoader 추상 클래스
│   │   ├── docling_loader.py          # HybridChunker + OCR 자동 + 정규화 (ADR-004/008/009/021)
│   │   └── factory.py                 # 확장자로 로더 선택
│   ├── rag/                           # RAG 파이프라인 핵심
│   │   ├── pipeline.py                # RAGPipeline.ingest · query (@traceable, 단계별 타이머)
│   │   ├── chunker.py                 # 2차 방어 청커 (RecursiveCharacterTextSplitter)
│   │   ├── retriever.py               # Qdrant top-K + reranker 주입
│   │   ├── reranker.py                # FlashRank · BGE-M3 토글 (ADR-012)
│   │   └── generator.py               # 답변 + suggestions JSON 생성 (ADR-019)
│   └── vectorstore/
│       └── qdrant_store.py            # Qdrant 추상화 (차원 자동 감지, scroll_by_doc_id)
│
├── ui/
│   └── app.py                         # Streamlit 5탭: 채팅 · 문서 · 대화 · 시스템 · 평가 (ADR-017, ADR-020)
│
├── pipeline/
│   └── rebuild_index.py               # 기존 DB 문서 기반 Qdrant 재인덱싱 (원본→마크다운 fallback)
│
├── scripts/                           # 운영·실험 스크립트
│   ├── bench_retrieval.py             # Hit@K · Precision · Recall · MRR (ADR-015)
│   ├── bench_answers.py               # Ragas faithfulness·answer_relevancy·context_* (ADR-015)
│   ├── ingest_sample.py               # 수동 업로드 테스트
│   └── test_query.py                  # 수동 질의 테스트
│
├── tests/
│   ├── conftest.py                    # sample_pdf·mock_llm·mock_embeddings fixtures
│   ├── eval/dataset.jsonl             # 12개 질의 + expected_doc_ids (평가 기준)
│   ├── unit/
│   │   ├── test_chunker.py
│   │   ├── test_docling_loader.py
│   │   └── test_generator.py
│   └── integration/
│       └── test_ingest_api.py
│
├── data/                              # 런타임 데이터
│   ├── uploads/                       # 업로드 원본 (gitignore, ADR-010)
│   ├── markdown/                      # Docling MARKDOWN export (gitignore)
│   ├── qdrant_storage/                # Qdrant 볼륨 (gitignore)
│   ├── pg_data/                       # PostgreSQL 볼륨 (gitignore)
│   └── eval_runs/                     # 벤치 결과 JSON (commit 대상)
│
├── project-wiki/                      # 프로젝트 위키 (24개 md)
│   ├── CLAUDE.md                      # 위키 스키마·운영 규칙
│   ├── index.md                       # 전체 페이지 카탈로그
│   ├── log.md                         # append-only 작업 이력
│   ├── overview.md                    # 프로젝트 현황·다음 할 일
│   ├── roadmap.md                     # 실행 큐·장기 검토·완료 항목
│   ├── changelog.md                   # semver 버전 이력 (0.1.0 ~ 0.14.3)
│   ├── glossary.md                    # 용어 사전
│   ├── references.md                  # 참고 자료
│   ├── security.md                    # API 키 관리·민감 데이터 처리
│   └── wiki/
│       ├── architecture/
│       │   ├── decisions.md           # ADR-001 ~ ADR-021 (018 결번)
│       │   └── structure.md           # (본 문서)
│       ├── api/endpoints.md           # REST 엔드포인트 스펙
│       ├── data/
│       │   ├── spec.md                # 입력 형식·PDF 처리 프로세스
│       │   └── schema.md              # PostgreSQL·Qdrant·파일시스템 구조
│       ├── features/
│       │   ├── admin_ui.md            # 5탭 UI 명세
│       │   └── evaluation.md          # 벤치 방법·기반선 수치
│       ├── onboarding/setup.md        # 개발 환경 셋업
│       ├── deployment/runbook.md      # 배포 절차 (draft)
│       ├── testing/strategy.md        # 테스트 전략
│       ├── requirements/features.md   # 기능 요구사항
│       ├── troubleshooting/common.md  # 자주 발생하는 에러·해결
│       ├── reviews/patterns.md        # 리뷰 컨벤션·커밋 체크리스트
│       ├── security.md                # (루트 security.md와 중복 — 정리 후보)
│       └── issues/open/
│           ├── ISSUE-001-...md        # 모바일 파일 업로더 무반응
│           └── ISSUE-002-...md        # 후속 질문 배지 두 번째 클릭 무반응
│
├── .claude/                           # gitignore (개인 환경)
│   ├── settings.local.json            # Claude Code 권한 허용 목록
│   └── skills/                        # 로컬 스킬 카탈로그 (wiki/reviews/patterns.md 참조)
│       ├── rag-commit.md              # 커밋 전 체크리스트 + 메시지 템플릿 + push 분리
│       ├── rag-task-start.md          # 새 TASK 등록 (번호 산출·큐 갱신·log queue)
│       └── rag-lint.md                # 위키 정합성 단독 점검 (커밋 없이)
│
├── .streamlit/
│   └── config.toml                    # maxUploadSize 200MB · XSRF/CORS off (개발)
│
├── docker-compose.yml                 # Qdrant:6333 + PostgreSQL:5432
├── requirements.txt                   # 의존성 (FastAPI·LangChain·Docling·Ragas·BGE-rerank·HF transformers)
├── setup.sh                           # venv + docker 초기 셋업
├── pytest.ini                         # 테스트 설정
├── .env                               # 실제 키 (gitignore)
├── .env.example                       # 템플릿 (커밋 대상)
└── .gitignore
```

---

## 논리적 계층 (위 → 아래 호출)

```
┌─────────────────────────────────────────────────┐
│  Client                                          │
│   · Streamlit UI (ui/app.py) — 브라우저          │
│   · curl / 외부 MCP 클라이언트                    │
└────────────────┬────────────────────────────────┘
                 │ HTTP
                 ▼
┌─────────────────────────────────────────────────┐
│  FastAPI 서버 (apps/)                            │
│   · main.py                                      │
│   · routers/ (ingest, query, documents, ...)     │
│   · schemas/ (Pydantic I/O)                      │
│   · dependencies.py (DI: get_db, get_pipeline)   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  비즈니스 로직 (packages/rag/)                    │
│   · RAGPipeline (@traceable)                     │
│       ingest → loader → chunker → store          │
│       query  → retrieve → rerank → generate      │
└──┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│loaders │ │llm     │ │rag     │ │vectorstore │
│Docling │ │chat    │ │chunker │ │Qdrant      │
│  +OCR  │ │embed   │ │retrieve│ │scroll·del  │
│        │ │(backend│ │rerank  │ │            │
│        │ │ toggle)│ │generate│ │            │
└────────┘ └───┬────┘ └────────┘ └─────┬──────┘
               │                        │
               ▼                        ▼
      ┌────────────────┐       ┌─────────────────┐
      │ OpenAI API     │       │ Qdrant (Docker) │
      │ / BGE-M3 local │       │ :6333           │
      └────────────────┘       └─────────────────┘

┌─────────────────────────────────────────────────┐
│  메타데이터·영속 (packages/db/)                  │
│   · documents (SHA-256 UNIQUE)                   │
│   · conversations · messages (CASCADE)           │
│        ▼                                          │
│  PostgreSQL (Docker) :5432                        │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  파일시스템 (data/)                              │
│   · uploads/{doc_id}.{ext}   원본 (재인덱싱용)    │
│   · markdown/{doc_id}.md     파싱 결과 (fallback)│
│   · qdrant_storage/ · pg_data/  Docker 볼륨       │
│   · eval_runs/*.json         벤치 결과 (commit)   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  관측 (LangSmith)                                 │
│   @traceable → rag.ingest / rag.query            │
│   tags: reranker · llm · suggestions · session   │
└─────────────────────────────────────────────────┘
```

---

## 디렉터리별 역할

### `apps/` — HTTP 경계
- REST 엔드포인트만 담당. 비즈니스 로직은 모두 `packages/`로 위임
- 스키마(Pydantic)와 라우터, 의존성 주입 구성
- `lifespan`에서 LangSmith env export, Reranker warm-up, DB 테이블 생성

### `packages/` — 비즈니스 로직 (프레임워크 독립)
하위 6개 모듈이 각자의 관심사만 책임:

| 모듈 | 역할 | 핵심 ADR |
|---|---|---|
| `code/` | 공통 데이터클래스·로거 | — |
| `db/` | PostgreSQL ORM + repository (documents·conversations·messages) | ADR-005, 006 |
| `llm/` | LLM·Embedding 백엔드 토글 | ADR-013, 014, 016 |
| `loaders/` | Docling 파싱 + OCR + 정규화 + HybridChunker | ADR-004, 008, 009, 021 |
| `rag/` | pipeline·retrieve·rerank·generate + 2차 청커 | ADR-002, 012, 019 |
| `vectorstore/` | Qdrant 추상화 (차원 자동 감지, scroll) | ADR-001, 016 |

의존 방향: `apps/` → `packages/*` → 외부 서비스(Qdrant·OpenAI 등). `packages/`는 FastAPI·Streamlit에 의존 안 함

### `ui/`
- Streamlit 멀티탭. API는 HTTP로만 호출
- `sys.path`에 프로젝트 루트를 주입해 `apps.config`를 직접 임포트(시스템 탭 설정 카드용). 그 외엔 API 경로 유지

### `pipeline/`
- 운영 배치 스크립트. `rebuild_index.py`는 원본 파일 우선 → 마크다운 fallback으로 Qdrant 재생성

### `scripts/`
- 평가·수동 테스트 도구. CI 밖에서 ad-hoc 실행
- `bench_retrieval.py`(Phase 1), `bench_answers.py`(Phase 2) — ADR-015

### `tests/`
- `unit/`: 로더·청커·생성기 단위 테스트
- `integration/`: `/ingest` API 통합 테스트
- `eval/dataset.jsonl`: 평가 기준 질의 12개 (benchmarks가 공유)

### `data/`
- 런타임 디렉터리. 대부분 gitignore. 유일한 예외는 `eval_runs/*.json` (벤치 결과 재현용)

### `project-wiki/`
- 설계 문서·의사결정·로그·이슈가 여기 집중. 코드와 1:1로 동기화 유지가 목적
- lint 규칙은 `/rag-commit` 스킬(로컬)이 자동 검증

---

## 실행 형상 (Runtime Topology)

로컬 개발 중 동시 구동되는 프로세스:

```
[Terminal 1]  uvicorn apps.main:app --reload
              ├─ LangSmith: @traceable로 rag.ingest/query 트레이스
              ├─ Reranker warm-up (BGE-M3, ~4초)
              └─ Listens: http://localhost:8000

[Terminal 2]  streamlit run ui/app.py --server.port 8501
              └─ Listens: http://localhost:8501

[Docker]      docker compose up -d  (docker-compose.yml)
              ├─ Qdrant :6333  (data/qdrant_storage/)
              └─ PostgreSQL :5432  (data/pg_data/)

[External]    OpenAI API (api.openai.com) — embedding·LLM
              HuggingFace Hub — BGE reranker·Docling 모델 다운로드 (최초 1회)
              LangSmith (smith.langchain.com) — 트레이스 업로드
```

---

## 변경 시 동반 갱신 원칙 (위키 정합성)

| 코드 변경 위치 | 동반 문서 |
|---|---|
| `apps/routers/*.py` (API) | `wiki/api/endpoints.md` |
| `packages/db/models.py` | `wiki/data/schema.md` + 수동 `ALTER TABLE` 마이그레이션 |
| `packages/loaders/*` | `wiki/data/spec.md` (PDF 처리 프로세스) |
| `packages/rag/*` | `wiki/architecture/decisions.md` (ADR) |
| `ui/app.py` | `wiki/features/admin_ui.md` |
| `.env`·`apps/config.py` 설정 | `wiki/onboarding/setup.md`, `security.md` |
| 모든 TASK 완료 | roadmap·overview·log·changelog·ADR 전부 갱신 (ADR-015 원칙) |

---

## 신규 기능 추가 시 권장 경로

1. `roadmap.md` 단기 섹션에 TASK-NNN 큐잉 (서브태스크·완료 기준·주의사항)
2. `packages/rag/` 또는 `packages/loaders/`에 구현
3. `apps/routers/`에 필요 시 엔드포인트 추가
4. `ui/app.py`에 UI 배선
5. ADR-NNN 작성 (배경·선택지·결정·결과)
6. `changelog.md [X.Y.Z]` 추가
7. `log.md`에 `impl` 항목 append
8. `/rag-commit` 스킬로 lint·커밋

---

## 알려진 정리 대상

- `wiki/security.md`와 루트 `security.md` **중복 존재** (24 md 중 1건) — 한쪽으로 통합 권장 (후순위 정리 항목)
- `packages/db/migrations/init.sql`은 참고용 정적 파일. 정식 마이그레이션 도구(Alembic 등) 미도입 상태
- `requirements/acceptance.md`·`config/environments.md`·`config/dependencies.md`·`deployment/monitoring.md` 등 미작성 placeholder 다수. `index.md` 상태 표에서 `-`로 표시됨
