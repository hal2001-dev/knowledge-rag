# 기술 스택

**상태**: active
**마지막 업데이트**: 2026-04-25
**관련 페이지**: [decisions.md](decisions.md), [structure.md](structure.md), [overview.md](../../overview.md), [roadmap.md](../../roadmap.md)

## 요약

Knowledge RAG는 두 개의 사용자 채널로 분리되어 운영됩니다(2026-04-25 결정, ADR-030 예약). **사용자 측은 NextJS 15 + Clerk thin client**, **관리자 측은 Streamlit (동결 정책)**, **백엔드는 단일 FastAPI**가 모든 LLM·RAG 처리를 담당합니다. 데이터 계층은 PostgreSQL(메타·세션·잡 큐) + Qdrant(벡터, named vectors hybrid).

---

## 1. 백엔드 (Python)

| 역할 | 선택 | 결정 이유 / 근거 ADR |
|------|------|---------|
| 언어 | Python 3.12.2 | venv 기반, 기존 ML/RAG 생태계 |
| API 서버 | **FastAPI** | async, OpenAPI 자동 생성(NextJS 클라이언트 자동화 활용), Pydantic 검증 |
| 문서 파싱 | **Docling 2.x** | 텍스트·테이블·이미지 통합 파싱 (ADR-004) |
| Chunking | HybridChunker (max_tokens=480) + 전체 heading breadcrumb 주입 | 의미 응집도 ↑, 토큰 경고 0 (ADR-009, ADR-021) |
| 임베딩 모델 | **OpenAI `text-embedding-3-small`** (기본) | `EMBEDDING_BACKEND` 토글로 BGE-M3 가능 (ADR-016) |
| Sparse Embedding | **FastEmbed `Qdrant/bm25`** + Kiwi 한국어 토크나이저 | 하이브리드 BM25 성분, 한국어 교착어 대응 (ADR-023) |
| 벡터 DB | **Qdrant** (Docker, named vectors: dense + sparse) | 하이브리드 검색 + RRF 융합 (ADR-001, ADR-023) |
| 메타데이터 DB | **PostgreSQL** (Docker) | SQLAlchemy ORM, advisory lock으로 마이그레이션 race 회피 (ADR-028) |
| 잡 큐 | **Postgres `ingest_jobs` (SKIP LOCKED)** | 별도 메시지 브로커 도입 회피, FastAPI는 enqueue+202만 (ADR-028) |
| 색인 워커 | `python -m apps.indexer_worker` (독립 프로세스) | API 응답성 보장, retry 3회, 실패 격리 (ADR-028) |
| Reranking | **BGE-reranker-v2-m3** (다국어, 로컬) | 한↔영 크로스 (ADR-012) |
| LLM | **gpt-4o-mini** (기본) | `LLM_BACKEND` 토글로 GLM/custom 가능 (ADR-013, ADR-014) |
| 프레임워크 | LangChain 0.3.x | 표준 RAG 컴포넌트 |
| 자동 분류 | 룰(`config/categories.yaml`) 우선 + LLM(gpt-4o-mini) fallback | 비용·정확도 균형 (ADR-025) |
| 자동 요약 | gpt-4o-mini + JSONB 영구 캐시 + BackgroundTasks 비동기 훅 | 환각 0건, 인덱싱 후 자동 (ADR-024) |
| 관측 | **LangSmith** (`@traceable`) | 트레이스·세션·단계별 타이머 (ADR-007) |
| 평가 | Ragas + 자체 Retrieval 벤치 | 기반선(Hit@3=1.0, faithfulness=0.886) (ADR-015) |

---

## 2. 사용자 UI — NextJS (TASK-019, ADR-030 예약)

**역할**: 사용자(채팅·도서관·대화) thin client. LLM·RAG 처리 0, FastAPI 호출만.

### 2.1 프레임워크 & 언어
| 항목 | 선택 | 결정 |
|---|---|---|
| 프레임워크 | **Next.js 15.x (App Router)** | 2026-04 안정. 호환 이슈 발견 시 14.2 다운그레이드 |
| 런타임 React | **React 19** | Next 15와 함께. Clerk/shadcn 19 호환 OK |
| 언어 | **TypeScript 5.x (strict)** | `"strict": true`, `"noUncheckedIndexedAccess": true` |
| Node | **20 LTS 이상** (가능 시 22 LTS) | |
| 패키지 매니저 | **pnpm 9.x** | 디스크 효율, 엄격한 peer-dep |

### 2.2 UI / 스타일
| 항목 | 선택 | 비고 |
|---|---|---|
| 디자인 시스템 | **shadcn/ui** (Radix + Tailwind) | copy-paste, NPM 의존 최소, 접근성 기본 |
| CSS | **Tailwind CSS 3.4+** | 유틸 우선, shadcn 호환 |
| 다크모드 | **light only (Phase 1)** + CSS 변수 인프라 | 후속 토글 가능하게 변수만 |
| 아이콘 | **lucide-react** | shadcn 기본, tree-shake |
| 토스트 | **sonner** | shadcn 권장 |
| 애니메이션 | **tailwindcss-animate** | shadcn 의존 |

shadcn 우선 설치: `button, card, input, select, dialog, sheet, badge, scroll-area, sonner, tooltip, separator, skeleton, dropdown-menu, avatar`

### 2.3 라우팅 & 상태
| 항목 | 선택 | 비고 |
|---|---|---|
| 라우팅 | **Next.js App Router (내장)** | 자동 페이지 이동 본질 해결 (Streamlit `st.tabs` 한계 극복) |
| URL state | **nuqs** (~3kb) | type-safe `useSearchParams`. `session_id`, `doc_filter`, `category`, `q`, `type` |
| 서버 상태 | **TanStack Query v5** | 캐싱, refetchOnFocus, mutation |
| 클라이언트 전역 상태 | **Zustand v4** (필요 시만) | 사이드바 토글 등. 작은 규모면 useState 충분 |

### 2.4 API & 인증
| 항목 | 선택 | 비고 |
|---|---|---|
| OpenAPI 타입 생성 | **openapi-typescript** | FastAPI 스키마 → TS 자동 생성 (CI 포함) |
| Fetch 래퍼 | **openapi-fetch** | 타입 안전 fetch + TanStack Query 조합 |
| 인증 | **@clerk/nextjs v5+** | 이메일 OTP 전용 (비번 X, 소셜 X) |
| 보호 라우트 | **middleware.ts** (Clerk) | 비로그인 → `/sign-in` 리다이렉트 |
| JWT 첨부 | TanStack Query default fetcher interceptor | Clerk `auth().getToken()` → `Authorization: Bearer ...` |

### 2.5 콘텐츠 / 폼 / 유틸
| 항목 | 선택 | 비고 |
|---|---|---|
| Markdown 렌더 | **react-markdown** + **remark-gfm** | 답변·요약·abstract |
| 코드 하이라이트 | **rehype-highlight** | 답변 내 코드 블록 |
| 폼 (필요 시) | **react-hook-form 7** + **zod** | Phase 1엔 거의 미사용 |
| 시간 포맷 | **date-fns v3** | 세션 목록 등 |
| 클래스 결합 | **clsx** + **tailwind-merge** | shadcn 자동 포함 (`cn()`) |

### 2.6 개발 도구
| 항목 | 선택 | 비고 |
|---|---|---|
| Lint | **ESLint** (Next 기본 + `@typescript-eslint`) + `eslint-config-prettier` | |
| 포맷 | **Prettier 3** + `prettier-plugin-tailwindcss` | 클래스 정렬 자동 |
| E2E 테스트 | **Playwright 1.48+** | Playwright MCP 환경 활용 |
| 단위 테스트 | **Vitest** | Phase 후속, 필요 시 도입 |

### 2.7 환경 변수 (`web/.env.local`, gitignored)
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<Clerk publishable>
CLERK_SECRET_KEY=<Clerk secret>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Knowledge RAG
# 선택 (webhook 도입 시)
# CLERK_WEBHOOK_SECRET=...
```
`web/.env.local.example`만 commit, 실제 키는 `.env.local`로 분리.

### 2.8 프로젝트 구조 (`web/` 신설)
```
web/
├── app/
│   ├── layout.tsx                  # ClerkProvider + QueryClientProvider + AppShell
│   ├── page.tsx                    # → /chat 리다이렉트
│   ├── chat/page.tsx               # 채팅 (URL: ?session_id&doc_filter&category)
│   ├── library/page.tsx            # 도서관 (URL: ?q&type&category)
│   ├── sign-in/[[...rest]]/page.tsx
│   └── sign-up/[[...rest]]/page.tsx
├── components/
│   ├── ui/                         # shadcn/ui 컴포넌트
│   ├── app-shell.tsx
│   ├── header-categories.tsx
│   ├── sidebar.tsx
│   ├── scope-badge.tsx
│   ├── chat/                       # message-list, source-expander, suggestions, empty-state
│   └── library/                    # filter-bar, doc-card, group-section
├── lib/
│   ├── api/                        # openapi-fetch client, query keys
│   ├── hooks/                      # useChat, useDocuments, useConversations, useScope
│   └── utils.ts                    # cn()
├── types/api.ts                    # openapi-typescript generated
├── middleware.ts                   # Clerk 보호 라우트
├── public/
├── .env.local.example              # commit
├── .env.local                      # gitignored
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.mjs
├── components.json                 # shadcn config
└── README.md
```

### 2.9 의도적 제외 (Phase 1, 후속 검토 가능)
- 답변 스트리밍 (SSE) — 백엔드 동반 작업 필요
- 다크모드 토글 (변수 인프라만 깔고 토글 후속)
- 다국어 (next-intl) — 한국어 단일
- PWA / Service Worker
- 에러 모니터링 (Sentry)
- Analytics
- 채팅 입력 리치 에디터 (Tiptap 등) — textarea 충분
- 사용자 프로필 편집 — Clerk `<UserButton>` 기본만
- React 단위 테스트 (Vitest) — Phase 후속
- Storybook — 도입 시점에 별건

---

## 3. 관리자 UI — Streamlit (잔류·동결)

**역할**: 관리자(문서 인덱싱·잡 큐 모니터·시스템 진단·평가) 화면. 사용자 측은 NextJS로 이전.

| 항목 | 선택 | 비고 |
|---|---|---|
| 프레임워크 | **Streamlit** (단일 `ui/app.py`) | 1단계 도입 (ADR-017). LAN 한정 |
| 인증 | 무인증 (LAN 한정) | Origin 분기로 FastAPI가 자동 `user_id='admin'` 부여 |
| 코드 동결 | **2026-04-25부터 모든 수정 동결** | 사용자 명시 지시까지. 메모리 `feedback_streamlit_no_edit` |

NextJS 측이 안정적으로 자리 잡은 후에도 관리자 도구로서 잔류 운영. 사용자 명시적 지시가 있을 때만 수정 가능.

---

## 4. 인증 / 인가

NextJS Clerk 도입(2026-04-25, TASK-019)으로 부분 해제됐고, 그 외 인증·공개배포 항목(HTTPS·관리자 UI 2단계·ISSUE-001·관리자 UI 버튼)은 보류 묶음 잔류.

| 채널 | 인증 | 미들웨어 동작 |
|---|---|---|
| NextJS (사용자) | **Clerk 이메일 OTP** | 비로그인 → `/sign-in` 강제. 로그인 후 JWT 헤더 첨부 |
| Streamlit (관리자) | 무인증 (LAN 한정) | FastAPI 측 Origin 분기로 무헤더+LAN origin → `user_id='admin'` |
| FastAPI 외부 호출 | JWT 강제 | 헤더 없는 외부 origin → 401 |

**역할 분리 없음** — 모든 로그인 사용자 동등. Clerk Organizations / publicMetadata role 미사용.

---

## 5. 데이터 계층 요약

| 저장소 | 역할 | 상세 |
|---|---|---|
| **PostgreSQL** | documents · conversations · messages · ingest_jobs · series(예정) | [schema.md](../data/schema.md) |
| **Qdrant** | 청크 벡터 (named vectors: dense + sparse) | hybrid 모드 RRF 융합 |
| 파일시스템 | `data/uploads/{doc_id}.{ext}` 원본 보관, `data/markdown/{doc_id}.md` 파싱 결과 | 재인덱싱 가능 (ADR-010) |

---

## 6. 의존 패키지 (요약)

자세한 버전·호환성은 `wiki/config/dependencies.md` (미작성, 도입 시 작성).

**Python (백엔드)**: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2`, `qdrant-client`, `langchain`, `langchain-qdrant`, `openai`, `docling`, `fastembed`, `kiwipiepy`, `sentence-transformers`, `flashrank`, `streamlit`, `ragas`, `langsmith`

**Node (NextJS, Phase 2 도입 예정)**: `next@15`, `react@19`, `typescript`, `@clerk/nextjs`, `@tanstack/react-query`, `tailwindcss`, `tailwindcss-animate`, `lucide-react`, `sonner`, `nuqs`, `openapi-typescript`, `openapi-fetch`, `react-markdown`, `remark-gfm`, `rehype-highlight`, `date-fns`, `clsx`, `tailwind-merge`, `react-hook-form`, `zod`

**개발 도구**: `eslint`, `prettier`, `prettier-plugin-tailwindcss`, `playwright`, (선택) `vitest`

---

## 7. 정책 호환

- 비용 0 (Clerk만 외부 + 사전 합의 완료, Free 플랜 10k MAU/월)
- 모든 OSS 패키지 MIT/Apache
- Streamlit 코드 동결 (메모리 `feedback_streamlit_no_edit`)
- `.env.local` gitignored (`.env.*` 룰)
- 인증·공개배포 묶음에서 "앱 내 인증" 항목만 부분 해제, 나머지 4개 보류 유지

---

## 8. 관련 결정

- ADR-001: Qdrant
- ADR-004: Docling
- ADR-007: LangSmith
- ADR-012: BGE-reranker-v2-m3
- ADR-013·ADR-014: gpt-4o-mini + LLM 백엔드 토글
- ADR-016: 임베딩 백엔드 토글
- ADR-017: 관리자 UI Streamlit 1단계
- ADR-023: 하이브리드 검색
- ADR-024: 자동 요약
- ADR-025: 자동 분류
- ADR-026/027: 도서관·랜딩 카드
- ADR-028: 색인 워커 분리
- ADR-029 (예약, TASK-020): Series/묶음
- ADR-030 (예약, TASK-019): NextJS 분리 + Clerk + Origin 분기
