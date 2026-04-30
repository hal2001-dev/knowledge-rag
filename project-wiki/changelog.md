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

## [0.30.0] - 2026-04-30

### Added
- **Implicit doc_filter 자동 감지** (ADR-034) — 질문 본문에 책 제목이 명시되면 substring 매칭으로 자동 doc_filter 적용. 신규 모듈 `packages/rag/title_match.py`. explicit scope 미지정 시만 동작 (ADR-029 우선순위 일관)
- 매칭 알고리즘: 정규화(공백·언더스코어·하이픈·점 → 공백, 소문자) + 길이 ≥ 4 컷 + 가장 긴 매칭 1건 채택 + 동률 시 None
- 모듈 레벨 캐시 (TTL 60초) — 색인 후 최대 1분 내 자동 반영
- LangSmith 메타 `implicit_doc_title` — 트레이스에서 implicit 적용 여부 인지 가능

### Changed
- `packages/rag/pipeline.py:query` / `query_stream` — 진입 시점에 implicit detection 분기 (explicit scope 모두 None일 때만)

### Fixed
- 사용자 보고: 질문에 "2001 스페이스 오디세이" 명시했는데 다른 책 청크가 top-1로 잡히던 retrieval 문제. 검증 — top-1이 『인공생명』(각주) → 『2001_스페이스_오디세이』 p.145(원작 본문)로 교체 ✓

---

## [0.29.0] - 2026-04-30

### Added
- **자동 대화 제목** (`packages/db/conversation_repository.py`) — `add_message`가 첫 user 메시지 도착 시 conversation.title이 비어 있으면 60자 컷 + 말줄임표로 자동 채움 (`_summarize_to_title`). 기존 44건 SQL UPDATE로 일괄 백필
- **자동 스크롤** (`web/app/chat/page.tsx`) — `scrollRef`/`stickyRef`로 토큰 스트리밍 시 하단 자동 추적. 사용자가 위로 스크롤(120px 이상)하면 sticky 해제(읽기 방해 0). 새 질문 보낼 때 sticky 강제 활성화

### Changed
- **출처 인용 강화** (`packages/rag/generator.py`):
  - `_build_messages`: 컨텍스트 청크 헤더에 `출처: 『{title}』 p.{page}` 명시 prepend → LLM이 정확한 책 제목·페이지 참조 가능
  - `SYSTEM_PROMPT_PLAIN`: 인용 시 책 제목 본문 포함, 인용 직후 inline 페이지 표기 의무화, 답변 끝에 "참고 문서" 라인 추가
  - 효과: 검증 질의 "이아페투스의 눈은 어디에 언급?" → "『2001 스페이스 오디세이』의 p.274, p.290, p.292, p.305에서…" (이전: 책 제목 누락)
- 채팅 레이아웃 root height 정책 (`web/app/layout.tsx`): `<html>`/`<body>` 모두 `h-full overflow-hidden`로 통일 — 뷰포트에 정확히 묶임

### Fixed
- **ISSUE-012** — 채팅 입력창이 하단에 고정되지 않음 (스크롤 내려야 보임). `body min-h-full → h-full + overflow-hidden`으로 해결
- **ISSUE-013** — 사이드바 대화 목록 제목 오른쪽 overflow. flex item `min-w-0` + Radix ScrollArea → 일반 div 교체로 해결

### Removed
- `web/components/sidebar.tsx`에서 Radix ScrollArea import — 사이드바는 가로 truncate 우선이라 일반 overflow-y-auto가 더 적합

---

## [0.28.0] - 2026-04-30

### Added
- **`POST /query/stream` SSE 엔드포인트** (TASK-024, ADR-033) — 답변 토큰 스트리밍. 이벤트 시퀀스: `meta → sources → token* → suggestions → done`. 첫 토큰 ~500ms로 체감 latency 5~10x ↓
- **`packages/rag/generator.py`** — `generate_stream(...)` sync iterator (`llm.stream()` 감싸기) + `generate_suggestions(...)` 답변 종료 후 별도 LLM 호출. `INSUFFICIENT_MARKERS` 상수화
- **`packages/rag/pipeline.py:query_stream`** — `(event_type, data)` yield generator. `@traceable("rag.query_stream")` LangSmith 트레이스
- **`web/lib/hooks/use-rag-stream.ts`** (신규) — `fetch + ReadableStream + TextDecoderStream` SSE 파서. `AbortController` 중단 지원
- **채팅 중지 버튼** (`web/components/chat/chat-input.tsx`) — pending 시 send 자리에 빨간 X 버튼 (`AbortController.abort()`)

### Changed
- **`web/app/chat/page.tsx`** — `useRagQuery` mutation → `useRagStream` send 교체. `streamingAnswer` 상태로 토큰 누적 점진 렌더. `onDone` → `invalidateQueries(conversations.all)` → baseMessages 갱신 시 streamingAnswer 자동 클리어 (self-healing)
- 기존 `POST /query` 엔드포인트는 그대로 — 평가 스크립트·기타 호출자 후방호환 100%

### Architecture
- ADR-033 신규: 답변 스트리밍 SSE (TASK-024). 신규 엔드포인트 분리 + suggestions 별도 호출 분리

---

## [0.27.0] - 2026-04-30

### Added
- **`documents.extraction_quality` 컬럼** (마이그레이션 0006) — NULL/`ok`/`partial`/`scan_only`. CHECK 제약 + index. 텍스트 추출 품질 추적
- **macOS Vision OCR 토글** — `DoclingDocumentLoader(force_full_page_ocr=True, ocr_lang=("ko-KR","en-US"))`. 기본 False(후방호환), 스캔본 재색인 시점에만 ON. `ocrmac`은 Docling 2.90.0 의존성에 이미 포함 — 추가 설치 0
- **신규 스크립트 3종**:
  - `scripts/classify_extraction_quality.py` — 휴리스틱 백필 (markdown 크기 + chunk 평균 길이). `--dry-run`/`--only-empty` 지원
  - `scripts/test_ocr_single.py` — 단권 OCR 검증용 (production 데이터 비건드림, `data/markdown_ocr_test/` 별도 출력)
  - `scripts/reingest_scan_only.py` — `scan_only` 일괄 재색인 (OCR → markdown → Qdrant 청크 교체 → DB 갱신)
- **NextJS 도서관 카드 `📷 스캔` 빨간 배지** (`web/components/library/doc-card.tsx`) — `scan_only` / `partial` 시 자동 표시 + tooltip
- **NextJS 채팅 옵티미스틱 user 버블** (`web/app/chat/page.tsx`) — `pendingUserMessage` 상태로 mutation 발사 즉시 사용자 메시지 표시. refetch 후 자동 클리어 (self-healing)
- **`NEXT_PUBLIC_AUTH_ENABLED` 토글** (`web/lib/auth-flag.ts`) — Clerk 클라이언트 측 우회. HTTP LAN host에서 dev handshake 무한 루프 회피 (ISSUE-009)
- **TASK-024 (스트리밍 SSE)** roadmap 등록 — OCR 작업 직후 착수 예정

### Changed
- 스캔본 PDF 16건 본문 본격 색인됨 — markdown 평균 5KB → 200~500KB (~50~100배), 청크 70 → 800 (~10배)
- 16건 모두 `summary` 재생성 (gpt-4o-mini, 92초, 17/17 ok). 이제 도서관 카드 요약·topics가 실제 본문 기반
- DB extraction_quality 분포: ok 107/107 (전수)

### Fixed
- **ISSUE-009** — Clerk dev handshake 무한 루프 (HTTP LAN host에서 Secure 쿠키 미저장). `<ClerkProvider>` / `<UserButton>` / `useAuth()` 모두 토글 우회
- **ISSUE-010** — 스캔본 PDF 16건 본문 추출 0 (Docling `force_full_page_ocr=False` 기본값 한계). macOS Vision 재색인으로 해결. 검증 질의 통과 ("등장인물은?" 시 "정보 없음" → 실제 본문 인용)
- **ISSUE-011** — 채팅 사용자 메시지가 응답 도착 전까지 화면에 안 뜸 (옵티미스틱 렌더 누락)
- NextJS dev 서버 `allowedDevOrigins`에 `macstudio` hostname 추가

### Architecture
- ADR-030 후속: Phase 1 클라이언트 측 토글 분리 — `NEXT_PUBLIC_AUTH_ENABLED=false`로 ClerkProvider 마운트 자체 차단
- ADR-032 신규: 텍스트 추출 품질 추적 + 스캔본 PDF macOS Vision OCR 재색인

---

## [0.26.4] - 2026-04-29

### Improved — 답변 품질 보완 (사용자 보고 "답변이 조금 빈약")
- **`packages/rag/generator.py:SYSTEM_PROMPT_PLAIN`** — RESPONSE STRUCTURE(핵심 답변 → 근거·세부 → 유의사항 → 답변 가능 범위) + LENGTH GUIDANCE(단순/방법·절차/개념·비교) + INSUFFICIENT CONTEXT 명시 추가. 비용 0(프롬프트만)
- **`packages/rag/generator.py:SYSTEM_PROMPT_WITH_SUGGESTIONS`** — JSON 모드의 answer 필드 작성 규칙 추가: 위 STRUCTURE 그대로 따르기, `\n`·마크다운 적극 사용, 한 줄 압축 금지
- **`apps/config.py:default_top_k`** 3 → 5 (LLM 컨텍스트 풍부 + 인접 섹션 동반 효과)
- **`.env:DEFAULT_TOP_K`** 3 → 5 (env override가 우선이므로 함께 갱신)

### Verified
- 같은 시리즈 한정 query 비교 — 답변 122자 → **610자 (5x)**, 구조 단일 문단 → 핵심/근거 5단계/유의사항/답변 범위, sources 3 → 5, latency +3.6%(허용)
- 후속 질문 3개 정상 생성 (회귀 0)

### Notes — 후속 별건
- (C) heading prefix 동반 검색 — 같은 섹션 청크 자동 동반, ~80줄
- (D) self-critique 1회 추가 — 비용·latency 2x
- (E) `LLM_MODEL=gpt-4o` 토글 — 비용 ~10x 사전 합의 필요

---

## [0.26.3] - 2026-04-29

### Fixed
- **`packages/rag/pipeline.py:query`** — LangSmith 부모 `rag.query` run에서 `reranker_backend / llm_backend / llm_model / doc_filter / category_filter / series_filter / suggestions_*` 7필드와 4태그가 누락되던 결함. 원인: `@traceable`이 만든 부모 run은 함수 내부의 `tracing_context`로 덮어씌워지지 않음. `langsmith.run_helpers.get_current_run_tree().add_metadata/add_tags`로 부모 run에 직접 부여. 자식 run에는 기존 `tracing_context`가 그대로 상속해 동일 메타 유지

### Verified
- 같은 시리즈 한정 query 1건 재발송 → 누락 7필드 + 4태그 모두 부모 run metadata에 정상 노출. 기존 메타(session_id/user_id/history_turns 등) 회귀 0

---

## [0.26.2] - 2026-04-28

### Fixed
- **`scripts/suggest_series.py`** — `QdrantDocumentStore`를 직접 인스턴스화하던 분기에서 잘못된 키워드 인자(`collection_name=`, `embedding_dim=`) 사용으로 `--apply`가 실패하던 결함. `apps.dependencies.get_pipeline()._store`를 재사용하도록 변경 — store 시그니처 변동에 견고

### Operations — TASK-020 백필 1회 batch
- 6 suggested → 3 시리즈 confirmed:
  - `ser_1fcc33c3f57c` "디지털 포트리스" (2권)
  - `ser_f091b1e5242e` "하루하루가 세상의 종말" (2권)
  - `ser_63f37a2049b4` "unix power tools" (2권)
- Qdrant `metadata.series_id` payload 갱신 + `series_match_status='confirmed'` 마킹
- 검수 큐(pending_review) 0건으로 정리

### Verified — end-to-end
- `GET /series` 3 시리즈, member_count 정확
- `GET /series/{id}/members` 멤버 정보 + series 5필드 모두 채워짐
- `POST /query` with `series_filter` → 멤버 청크만 정확히 hit (`metadata.series_id` Filter 절 + payload index 정합 입증)
- NextJS UI는 GET 호출만으로 자동 노출 — `/library` 시리즈 그룹 섹션 + `/chat` ScopeBanner "📚 시리즈 한정"

---

## [0.26.1] - 2026-04-28

### Added — TASK-020 후속: NextJS 시리즈 UI
- **`web/types/api.ts` 재생성** + `lib/api/types.ts`/`keys.ts`에 series 4 type/key 추가
- **`web/lib/hooks/use-series.ts`**: `useSeriesList()` / `useSeriesMembers(seriesId)`
- **`web/components/library/series-card.tsx`**: 시리즈 N권 응축 카드 (amber 배경+테두리). 펼치기 시 volume_number 순 멤버 목록 + 권별 [이 권 한정 묻기]. 카드 헤더에 [이 시리즈에 묻기] (`?series_filter=`)
- **`web/components/library/doc-card.tsx`**: 시리즈 멤버 doc에 "📚 Vol N" 배지 (제목 옆). 비-시리즈는 변화 0
- **`web/app/library/page.tsx`**: 시리즈 그룹 섹션 (카테고리 그룹 위). 시리즈 멤버는 카테고리 그룹에서 제외 (중복 표시 방지)
- **`web/components/chat/scope-banner.tsx`**: `📚 시리즈 한정` 배지 모드 — amber 배경, 시리즈 제목 + 멤버 수. 우선순위 doc > category > series 분기 + clearAll에 setSeriesFilter(null) 포함
- **`web/app/chat/page.tsx`**: `series_filter` URL state + 활성 스코프 우선순위 정렬 + ChatInput placeholder 4분기

### Verified
- `pnpm exec tsc --noEmit` 0 에러 / `pnpm exec eslint` 0 경고
- Playwright Phase 1 `ui-flow` 9 passed / 1 skipped (의도된 mobile drawer skip 유지). 회귀 0

---

## [0.26.0] - 2026-04-28

### Added — TASK-020 Series/묶음 1급 시민 (ADR-029)
- **`series` 테이블 + `documents` 4컬럼**:
  - `series_id`(FK ON DELETE SET NULL), `volume_number`, `volume_title`, `series_match_status`(enum: none/auto_attached/suggested/confirmed/rejected)
  - 마이그레이션 `0005_add_series_tables.sql` — sentinel `("table","series")` + advisory lock 직렬화
- **`packages/series/matcher.py`** — 휴리스틱 매처 (LLM 호출 0):
  - 동일 source 폴더 + 공통 prefix ≥ 8자(권 번호 정규화 후) + 동일 doc_type + 숫자 시퀀스(Chapter/Vol/N권/N장/끝숫자/_NN/Nst-th)
  - 신뢰도 high(4신호) → auto_attached / medium(3) → suggested / low(그 외) → 처리 없음
  - 4자리 연도(2024) 차단, 제목 중간 버전 번호("ROS 2.0.3") 차단
- **`packages/series/match_runner.py:series_match_for_doc`** — DB·Qdrant payload 갱신 진입점. 신규 시리즈 자동 발급(`ser_<12hex>`) + cover_doc_id 자동 + 멤버 attach. 기존 시리즈 매칭 시 합류
- **`apps/indexer_worker.py`** — BackgroundTasks 체인 6단계로 `series_match` 추가 (실패 격리, summary 패턴 동일)
- **`packages/vectorstore/qdrant_store.py:set_series_payload`** — 청크 metadata에 series_id/series_title 부분 갱신. payload index `metadata.series_id` keyword 추가
- **검색 통합** — `QueryRequest.series_filter` + retriever/pipeline/qdrant_store 통과. 활성 스코프 우선순위 **doc > category > series** (단순화). LangSmith 트레이스 메타에 `series_filter` 추가
- **`apps/routers/series.py` 신규** — 10 엔드포인트:
  - GET `/series` (목록), GET `/series/{id}`, GET `/series/{id}/members`
  - POST `/series` (생성), PATCH `/series/{id}`, DELETE `/series/{id}`
  - GET `/series/_review/queue` (auto_attached + suggested 검수 큐)
  - POST `/documents/{id}/series_match/confirm|reject|attach`
- **`scripts/suggest_series.py`** — 백필 dry-run / `--apply`. 결과 JSON 리포트(`data/eval_runs/suggest_series_<ISO>.json`)
- **`tests/unit/test_series_matcher.py`** — 26 케이스 (volume 추출 14 + prefix 2 + 후보 산출 9 + skip 정책 1). 26/26 passed
- **`apps/schemas/documents.py`** — `DocumentItem`에 series 5필드 + `SeriesItem/SeriesCreateRequest/SeriesPatchRequest/SeriesListResponse/SeriesMembersResponse/SeriesReviewItem` 신설
- **`packages/code/models.py:DocRecord`** — series 4필드 추가 (response 매핑 일관성)

### Verified
- 실 인덱스 107문서 dry-run: suggested 6건(UNIX Power Tools / 하루하루가 세상의 종말 / 디지털 포트리스), low 18건, no_candidate 83건
- 통합 smoke (실 DB+Qdrant): high 자동 묶기 정상, 신규 시리즈 ID 발급, 멤버 attach, volume_number 추출, skip 정책(rejected/auto_attached/confirmed 재바인딩 차단) 모두 정상
- 단위 회귀 영향 0건 (사전 부채 4건 동일)

### Notes (Streamlit 동결 정책 정합)
- 시리즈 검수는 FastAPI 엔드포인트 + CLI 백필 두 경로로 제공. Streamlit 검수 페이지는 동결 정책에 따라 미수행. NextJS admin 이전 시 별건으로 검수 페이지 도입

---

## [0.25.0] - 2026-04-28

### Added
- **Clerk JWT 실 검증** ([apps/middleware/auth.py](../apps/middleware/auth.py)) — TASK-019 Phase B (a):
  - PyJWKClient로 JWKS 자동 fetch+캐시(기본 lifespan 300s, max_cached_keys 16)
  - RS256 서명 검증 + `iss` 일치 확인 + `sub` claim → user_id 매핑
  - 필수 claim 강제: `["exp", "iat", "sub", "iss"]`. `audience` 검증은 비활성화 (Clerk 토큰 형태 정합)
  - 실패 시 `None` 반환 → 미들웨어가 401 응답. 예외 분류로 운영 로그 잡음 최소화 (네트워크 장애는 warning, 클라이언트 토큰 거부는 info, 그 외 unexpected는 exception)
  - JWKS 클라이언트는 lazy 초기화 — `AUTH_ENABLED=false` 모드는 생성 자체 안 함, 메모리 풋프린트 증가 0
- **`requirements.txt`** — `pyjwt[crypto]>=2.8` 추가 (Clerk JWT RS256 + JWKS)
- **`tests/unit/test_middleware_auth.py`** 신설 — 자체 RSA 키쌍 + JWKS mock 9 케이스 (정상/만료/잘못된 issuer/잘못된 서명/필수 claim 누락/JWKS URL 미설정/issuer 미설정/JWKS 조회 실패/sub 비문자열). 9/9 passed (0.80s)

### Verified
- `pytest tests/unit/test_middleware_auth.py -v` → 9 passed
- 본 작업의 회귀 영향 0건 (base 사전 부채 4건은 generator 반환 타입 변경 분, 본 작업과 무관)
- Phase 1 (`AUTH_ENABLED=false`) 모드 — `_verify_token` 호출 자체가 안 일어나므로 운영 동작 변화 0

---

## [0.24.2] - 2026-04-28

### Fixed
- **`web/app/chat/page.tsx` 라이브 응답 머지 누락** — RAG mutation 응답의 `sources`가 `liveSources` 상태로 보존되지 않아 답변 직후 conversation refetch 도착 전까지 SourceExpander가 표시되지 않던 결함. `suggestions`/`latency_ms`와 동일하게 머지 + sessionId 변경 시 동기 리셋. 백엔드 `MessageItem`은 `sources`를 영속화하지 않으므로 라이브 값을 fallback으로 유지

### Changed
- **`web/tests/api-proxy.spec.ts` 검증 경로 정정** — `/api/health`(공개 라우트)에서 `/api/conversations`(보호 경로)로 변경. proxy.ts `isPublicRoute`(`/sign-in`, `/sign-up`, `/api/health`) 의도와 어긋나는 케이스를 수정해 보호 `/api/*`의 Clerk 게이트(307 → `/sign-in`) 회귀를 본래 의도대로 검증

### Verified
- **Playwright Phase 1** (`AUTH_ENABLED=false`, ui-flow): 9 passed / 1 skipped (mobile drawer는 `chromium-mobile` 한정 의도된 skip)
- **Playwright Phase 2** (`AUTH_ENABLED=true`, auth-protected + api-proxy): 10 passed
- `pnpm exec tsc --noEmit` 0 에러 / `pnpm exec eslint` 0 경고
- 운영 메모: 첫 모드 전환 시 `.next` dev 캐시가 `@clerk/nextjs` 모듈 미해결 발생 → `rm -rf .next` 1회로 해소 (의존성 정상, 캐시 손상)

---

## [0.24.1] - 2026-04-28

### Added
- **TASK-019 Phase B 진전 — `proxy.ts` AUTH_ENABLED 토글** ([web/proxy.ts](../web/proxy.ts)):
  - Next 16에서 `middleware.ts` → `proxy.ts` 이름 변경 사실 반영 (Phase A에서 이미 작성돼 있던 파일). AGENTS.md 권고대로 `node_modules/next/dist/docs/` 확인
  - Phase 1 (`AUTH_ENABLED=false`, 기본): `clerkMiddleware` 통과만, 모든 라우트 무방호 — FastAPI 미들웨어가 LAN/localhost는 `'admin'` 자동 부여 (ADR-030)
  - Phase 2 (`AUTH_ENABLED=true`): `/`, `/chat`, `/library` 비로그인 시 `/sign-in` 리다이렉트(307). 공개 라우트 `/sign-in`, `/sign-up`, `/api/health`
  - [web/.env.local.example](../web/.env.local.example) — `AUTH_ENABLED=false` 기본값 + Phase 1/2 주석
- **Playwright 두 모드 분리** ([web/tests/](../web/tests/)):
  - `auth.spec.ts` → `auth-protected.spec.ts` rename + `test.skip(AUTH_ENABLED!=='true')` 가드 — Phase 2 모드 회귀 4 케이스
  - `api-proxy.spec.ts` — Phase 2 가드 추가
  - `ui-flow.spec.ts` (신규) — Phase 1 사용자 흐름 5 케이스: `/chat` 로드(헤더·입력창·보내기 버튼), `/library` 로드(검색 placeholder), URL state 동기화(`?q=test`), 루트 `/` → `/chat` 리다이렉트, 모바일 drawer(Pixel 5 viewport)
  - `playwright.config.ts` — 두 모드 실행 가이드 코멘트 (`pnpm exec playwright test ui-flow` vs `AUTH_ENABLED=true ... auth-protected`)

### Verified
- **`category_filter` Qdrant 필터 절 적용** (코드 추적, 별도 코드 변경 없음): `pipeline.py:101-143` → `retriever.py:17-31` → `qdrant_store.py:239-244` `must.append(FieldCondition(key="metadata.category"))`. vector 경로(L246-251 `filter=`) + hybrid 경로(L262-277 `query_filter=`) 양쪽 적용. 0.23.1 hotfix(nested key `metadata.category`) 정합 보존
- **DB 마이그레이션 적용**: `information_schema` 조회로 `conversations.user_id text NOT NULL DEFAULT 'admin'` + `ix_conversations_user_id` 인덱스 확인

### Notes
- 실제 `pnpm exec playwright test` 실행은 본 커밋 후 사용자 환경에서 별건
- Phase B 남은 항목: Clerk JWT 실 검증(`apps/middleware/auth.py:_verify_token` stub → PyJWT+JWKS), `components/chat/scope-banner.tsx`/`suggestions.tsx` Stub 채우기, AUTH_ENABLED=true 전환
- 본 변경물은 ADR-030(Phase 1/2 분리)의 구현 진전이라 신규 ADR 없음

---

## [0.24.0] - 2026-04-28

### Added
- **운영 모니터링 인프라 (TASK-021, ADR-031)** — macOS launchd 기반 정기 스냅샷 + 워커 RSS 가드:
  - `scripts/krag_snapshot.py` — 5분 주기 단발 실행, knowledge-rag 관련 프로세스(cwd/cmdline 매칭) + 시스템 전체 RSS top 10 + 인기 포트(3000/8000/8501) LISTEN 카운트 + 시스템 used%/free%/load1/load5. 매 줄 fsync, `data/diag/snapshot/YYYYMMDD.log` 일자별 단일 파일, 7일 후 .log.gz 자동 압축
  - `scripts/krag_guard.py` — 30초 주기 단발 실행, **`apps.indexer_worker` 한정** RSS ≥ 14GB 시 그 PID에만 SIGTERM + macOS 알림(osascript) + 사후 dump(`guard_kill_pid<N>_<ts>.log` ps auxm + vm_stat). 자기 PID 제외 명시 로직. `--observe-only` 토글, `KRAG_GUARD_RSS_GB` 환경변수 임계 조정
  - LaunchAgents 2개: `~/Library/LaunchAgents/com.knowledge-rag.snapshot.plist` (StartInterval=300) + `com.knowledge-rag.guard.plist` (StartInterval=30, KRAG_GUARD_RSS_GB=14). RunAtLoad=true
  - [wiki/deployment/monitoring.md](wiki/deployment/monitoring.md) (신설) — 등록·해제·로그 위치·임계 조정·모의 테스트 절차

### Changed
- **ISSUE-005 후속 운영 조치** ([wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md](wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md)) — 강화 모니터(`/tmp/krag_monitor.py`)가 워커 lifecycle에 묶여 사라진 한계 보완. **launchd fork 모델로 PID 의존 0**, Claude Code/셸 lifecycle 무관. 워커 한정 SIGTERM으로 누명 결함 정반대로 뒤집음
- **ISSUE-004 자동 차단 안전망** ([wiki/issues/open/ISSUE-004-docling-parse-longtail.md](wiki/issues/open/ISSUE-004-docling-parse-longtail.md)) — idle RSS 13.18GB 평탄 패턴이 14GB 넘기 전 자동 컷. 해결 방향 5번(`INDEXER_MAX_JOBS` 자가 종료)을 일부만 충족, 자가 종료는 별건

### Verification (2026-04-28 19:51 KST)
- launchd 등록 직후 `RunAtLoad=true`로 즉시 1회 실행 확인 (`launchctl list | grep knowledge-rag` → snapshot/guard 양쪽 0 exit)
- 첫 스냅샷 dump 정상 (시스템 used 9.3% / 프로젝트 프로세스 9건 / top10 / 포트 3개)
- 첫 가드 no-op 정상 (`worker not running (threshold=14.0GB)`)
- 모의 SIGTERM 검증 통과 — decoy 프로세스(`exec -a "python -m apps.indexer_worker --decoy" sleep 300`) 띄운 뒤:
  - `KRAG_GUARD_RSS_GB=0 ... --observe-only`: decoy 감지하지만 kill 안 함 (`OBSERVE pid=NNN rss=NNNMB >= 0MB`)
  - `KRAG_GUARD_RSS_GB=0 ... `(real): SIGTERM 발사, decoy DEAD, 사후 dump 82KB 생성
- 자기 PID 제외 로직 정상 (가드 자체는 kill되지 않음)

### Notes
- 임계 14GB는 ISSUE-004 idle 13.18GB + 1GB 여유. 운영 데이터 2~4주 축적 후 16GB 또는 "2회 연속 트리거" 컷 보강 검토 (별건)
- 워커 외 프로세스 가드 없음 — NextJS dev / Streamlit / Uvicorn은 관찰만(TASK-019 진행 중 false positive kill 회피)
- 외부 알림(Slack/이메일) 미적용 — 비용·키 사전 합의 규칙(`feedback_cost_keys`)
- TASK-019(NextJS UI 분리) 일시 중단 후 끼워넣은 운영 인프라 — Phase A 완료 코드 보존, 본 TASK 완료 후 Phase B 재개

---

## [0.23.4] - 2026-04-26

### Added
- **Streamlit 잡 탭 상태 필터** ([ui/app.py](../ui/app.py) `TAB_JOBS`): `st.multiselect`로 pending / in_progress / done / failed / cancelled 다중 선택. 옵션 라벨에 카운트 노출(`⚙️ 진행중 (2)`), 기본값은 큐에 1건이라도 존재하는 상태만 선택, 비우면 전체 폴백. 표 캡션에 `필터 매칭 / 전체` 함께 표기. `STATUS_BADGE` dict는 표 루프 내부 → 잡 탭 상단으로 hoist해 필터 라벨과 표 셀이 공유. **Streamlit 동결 정책의 1건 한정 해제** (메모리 `feedback_streamlit_no_edit` 명시 지시 충족, 동결 정책 자체는 유지)

### Ops
- **stale 잡 #26 reset** (`도메인_주도_설계_구현과_핵심_개념_익히기`, 109MB PDF): 워커가 17:36:04 KST에 claim 후 `in_progress` 잔존, 1시간 19분 경과 시점 발견. 직전 워커 프로세스 사망(ISSUE-003 freeze 정황과 일치)이 원인. 워커는 `SELECT … FOR UPDATE SKIP LOCKED` + `status='pending'` 필터라 stale `in_progress`는 자동 회수 불가(heartbeat·timeout 미구현). Qdrant 청크 0건·Postgres documents 행 0건 확인 후 `UPDATE ingest_jobs SET status='pending', started_at=NULL, finished_at=NULL, error=NULL WHERE id=26` 단순 reset. 0.23.3 `EMBED_BATCH_SIZE=64` 적용된 워커가 다음 차례에 재처리 (`enqueued_at ASC` 정렬 상 큐 최선두)

### Notes
- 후속 후보(미착수): 워커 stale-recovery 자동화 — heartbeat 컬럼(`heartbeat_at`) + 워커 진입 시 `started_at < NOW() - INTERVAL '30 min' AND heartbeat 없음` 잡 자동 reset. 현재는 수동 SQL 의존

---

## [0.23.3] - 2026-04-26

### Fixed
- **ISSUE-003 — 인덱싱 중 메모리 폭발로 시스템 freeze**: `QdrantDocumentStore.add_documents` (hybrid 분기)가 한 호출의 **모든 청크 텍스트·dense·sparse·PointStruct를 동시에 메모리 보유**해, 수천 청크 PDF 1건만으로도 RSS가 GB 단위로 폭증 → 스왑 폭주 → 시스템 응답 불가. upsert는 256 배치였지만 embed/PointStruct 단계는 미배치였던 게 회귀 원인. `EMBED_BATCH_SIZE = 64` 도입 + `add_documents` hybrid 분기를 64청크 단위 루프로 재구성(`texts/dense_vecs/sparse_vecs/points` 모두 배치 종료 시 GC). 한 시점 메모리 ≈ 64청크 × (1536d 벡터 + 텍스트). vector 단일 모드는 langchain QdrantVectorStore에 위임되어 손대지 않음. 상세 — [ISSUE-003](../wiki/issues/resolved/ISSUE-003-ingest-memory-spike-system-freeze.md)

### Notes
- 후속 메모리 핫스팟 후보(미착수): `scripts/bulk_ingest.py` `read_bytes()` 큰 파일 통째 로드, `apps/routers/ingest.py` `await file.read()` 업로드 본문 통째 수신. 이번 freeze의 직접 원인 아니므로 별건으로 다룰 예정

---

## [0.23.2] - 2026-04-26

### Added
- **TASK-019 Phase A — NextJS 사용자 UI 셋업 (web/ 디렉터리 신설, ADR-030)**:
  - `web/` Next.js 16.2.4 + React 19.2 + TypeScript 5.9 strict + Tailwind 4 + Turbopack
  - shadcn/ui 14개 컴포넌트 (button/card/input/select/dialog/sheet/badge/scroll-area/sonner/tooltip/separator/skeleton/dropdown-menu/avatar)
  - `@clerk/nextjs` 7.2 — 이메일 OTP 보호 라우트(`proxy.ts`, Next 16 컨벤션 — `middleware.ts` deprecated), `<ClerkProvider>` + `<SignIn/>`/`<SignUp/>` catch-all 라우트
  - `@tanstack/react-query` 5 — `<Providers>`로 `QueryClient` + `<TooltipProvider>` + `<Toaster>` 합본
  - `nuqs` 2 (URL state, Phase B에서 활성), `react-markdown` 10 + `remark-gfm` 4 + `rehype-highlight` 7 (마크다운 렌더), `date-fns` 4
  - `openapi-typescript` + `openapi-fetch` (devDeps) — FastAPI 스키마에서 타입 자동 생성 + 타입 안전 fetch
  - `lib/api/client.ts` — `useApiClient()` hook이 Clerk `getToken()`으로 JWT를 Bearer 헤더에 자동 첨부 (FastAPI `AuthMiddleware`와 짝)
  - `app/page.tsx` Phase A placeholder (UserButton만), AppShell + 페이지 본격 구현은 Phase B
- **`.env.local.example` + `.env.local` 템플릿** — Clerk 키 3종(`publishable`/`secret`/[선택] `webhook secret`), `NEXT_PUBLIC_API_BASE_URL`, sign-in/up 라우트 안내. `.gitignore`는 `.env*` 차단 + `!.env*.example` 예외로 example만 commit

### Fixed
- **마이그레이션 스크립트 `--cleanup-flat` 비활성** — Qdrant `delete_payload(keys=["metadata.category"])` 가 dot-notation을 nested 경로로 해석해 방금 set_payload로 추가한 nested key를 삭제하는 역효과 발견. flat top-level literal key는 안 지워짐. 스크립트의 `--cleanup-flat` 옵션은 호출되어도 경고 로그만 출력하고 no-op으로 변경. nested 추가만 수행, flat은 cruft로 잔존하나 Filter는 nested 기준이라 검색 동작 정상. 안전한 flat 정리는 collection drop + 재인덱싱 또는 청크별 overwrite_payload만 가능 (Qdrant API 한계)

### Changed
- **stack.md 갱신** (실제 설치 버전 반영): Next.js 15 → 16, Tailwind CSS 3.4 → 4, `middleware.ts` → `proxy.ts` (Next 16 컨벤션), Clerk 5+ → 7.2

### Notes
- Phase A 검증 결과: `pnpm dev` → 195~249ms ready, `/sign-in` HTTP 200 (24KB SignIn 컴포넌트), `/` HTTP 307 → `/sign-in?redirect_url=...` (Clerk 보호 자동 리다이렉트)
- Phase B 작업: AppShell(상단 카테고리 칩 + 사이드바 + 메인 + 활성 스코프 배지) + `/chat` + `/library` + 사이드바 대화 목록 + Playwright 검증
- `AUTH_ENABLED=false` 백엔드 기본 유지 — Phase B 마무리 시점에 `true`로 전환 + `CLERK_JWKS_URL` 채움
- bulk 인덱싱: TASK-019 Phase 1 라이브 검증 후 7권 도서 nested 분류 적용 완료 (3890 청크 / ai-ml · web-frontend · software-architecture · programming-systems · other 5개 카테고리), 추가 2권(`더_이상한_수학책`, `상대적이며_절대적인_지식의_백과사전`) enqueue → 신규 코드(0.23.1+)로 자동 nested 저장

---

## [0.23.1] - 2026-04-26

### Fixed
- **`set_classification_payload` flat key → nested key** (ADR-025 잠재 버그, TASK-019 Phase 1 라이브 검증 시 표면화):
  - 증상: `category_filter='ai/ml'` 처럼 카테고리 한정 검색 시 매칭 0건. doc_filter는 정상.
  - 원인: Qdrant `set_payload`에 `key=` 파라미터를 안 줘서 `payload["metadata.category"]`(top-level flat key)로 저장됨. Filter `key="metadata.category"` 는 dot-notation = nested 경로(`payload.metadata.category`)로 해석 → mismatch
  - 수정: `set_classification_payload`에 `key="metadata"` 추가 + payload dict 키를 `"category"` 등으로 단순화. 결과: `payload["metadata"]["category"]` nested 저장
  - 데이터 마이그레이션: `scripts/migrate_classification_payload_to_nested.py` 신규. PostgreSQL `documents` 테이블을 진실 원천으로 영향받은 doc_id의 nested set_payload 재적용 + (선택) flat key delete_payload. `--dry-run`/`--cleanup-flat` 옵션
  - 영향 범위: ADR-025(2026-04-25)부터 도입된 모든 자동/수동 분류 호출. 기존 인덱스의 카테고리 필터가 동작 안 했지만 표면화 안 됐던 이유는 사용자가 카테고리 한정 검색을 실제로 호출하지 않았기 때문 (TASK-019 Phase 1 검증이 첫 호출)

### Notes
- 워커 재기동 후 신규 분류 호출은 nested로 저장. 기존 flat key는 위 마이그레이션 스크립트로 변환
- TASK-019 Phase 2 NextJS의 카테고리 칩·도서관 카테고리 필터·`category_filter` 라우팅이 이 fix 없이는 항상 0건 — Phase 2 진입 전제조건

---

## [0.23.0] - 2026-04-26

### Added
- **사용자 UI NextJS 분리 Phase 1 — 백엔드 토대** (TASK-019, ADR-030):
  - `apps/middleware/auth.py` (신규) — Origin 분기 인증 미들웨어. JWT 헤더 있으면 Clerk 검증(Phase 2 stub), 없으면 LAN/localhost origin은 `user_id='admin'` 자동 부여, 외부 origin은 401. `AUTH_ENABLED=false`(기본)일 땐 모든 요청 admin 통과 (Clerk 키 없이 백엔드 가동 가능).
  - `apps/middleware/__init__.py` (신규) — 미들웨어 패키지
  - 마이그레이션 `0004_add_conversations_user_id.sql` — `conversations.user_id TEXT NOT NULL DEFAULT 'admin'` + `ix_conversations_user_id`. sentinel `("column", "conversations", "user_id")`로 idempotent. 기존 29개 행은 DEFAULT 'admin'로 자동 백필.
  - `category_filter` end-to-end:
    - `apps/schemas/query.py` `QueryRequest.category_filter: Optional[str]` 추가
    - `packages/rag/{pipeline,retriever}.py` 인자 통과 + LangSmith 메타·태그
    - `packages/vectorstore/qdrant_store.py` `similarity_search_with_score(category=...)` + `payload.metadata.category` Filter 절. doc_id와 동시 지정 시 둘 다 must로 AND, pipeline 레이어가 우선순위(doc > category) 결정
    - `apps/routers/query.py` request 통과
  - `apps/main.py` — CORSMiddleware (NextJS dev `http://localhost:3000` 허용) + AuthMiddleware 등록
  - `apps/config.py` — `auth_enabled`(기본 false), `clerk_jwks_url`, `clerk_issuer`, `cors_origins` 4개 필드
- **conversations 사용자 격리** — 모든 repository 함수가 `user_id` 필수 인자
  - `create_conversation(user_id, ...)` — INSERT 시 명시 user_id 주입 (DB DEFAULT는 마이그레이션 백필 전용)
  - `get_conversation(session_id, user_id=...)` — owner 검증 시 user_id 일치 행만 반환
  - `get_or_create_conversation(session_id, user_id)` — 다른 user 세션 ID를 우연히 알아도 격리(새 세션 생성)
  - `list_conversations(user_id)` / `delete_conversation(session_id, user_id)` 자기 데이터만
  - 라우터 4개 모두 `Request.state.user_id` 의존성 통과 + 다른 user 세션 GET 시 404 (403 대신 정보 누출 회피)
- **위키**:
  - `wiki/architecture/decisions.md` ADR-030 — 사용자/관리자 UI 분리, Clerk 채택, Origin 분기 전략, 인증 공급자 비교
  - `wiki/architecture/stack.md` 신설 (백엔드 + NextJS + Streamlit + 인증 정책 통합)
  - `wiki/index.md` Architecture 섹션 갱신 (stack.md 등록)
  - `wiki/overview.md` 상단 관련 페이지에서 stack.md 미작성 마커 제거

### Fixed
- **마이그레이션 `pg_advisory_xact_lock` LOCK_ID 잠재 버그** ([packages/db/connection.py](../packages/db/connection.py)):
  - 9바이트 `0x6B6E6F776C65646765` (`'knowledge'` ASCII)가 PostgreSQL `bigint`(signed 64-bit, 최대 2^63-1) 한도 초과
  - TASK-018 도입 시 모든 sentinel 충족으로 빠른 경로만 타서 노출 안 됐고, TASK-019 신규 마이그레이션 0004로 표면화
  - 8바이트 `'knowledg'` (0x6B6E6F776C656467 ≈ 7.7e18 < 2^63-1)로 축약, 동일 lock id 의도 유지

### Notes
- `AUTH_ENABLED=false`가 기본 — Phase 2(NextJS + Clerk 통합) 진입 시 `.env`에 `AUTH_ENABLED=true` + Clerk 키 3종 추가 후 활성
- 현재 실행 중인 uvicorn은 옛 코드 — 재시작 후 새 미들웨어/repository 적용. 인덱서 워커는 conversations 미접근이라 재시작 불필요
- DEFAULT 'admin' 컬럼 정책 덕분에 옛 코드도 INSERT 시 user_id 누락해도 자동 백필되어 운영 호환성 유지

---

## [0.22.1] - 2026-04-25

### Fixed
- **Qdrant HTTP payload 32MiB 한도 초과로 대형 PDF 색인 실패** ([packages/vectorstore/qdrant_store.py](../packages/vectorstore/qdrant_store.py)):
  - 증상: 1k+ 청크 PDF(예: 80MB / 1,034 청크)가 hybrid 모드에서 단일 `client.upsert()` 호출 시 ~32MB 페이로드로 400 (`Payload error: JSON payload (33848096 bytes) is larger than allowed (limit: 33554432 bytes)`).
  - 영향: `ingest_jobs` 큐에서 동일 PDF가 retry 3회까지 모두 같은 지점에서 실패해 영구 `failed`. 12건의 대형 도서 잡이 누적.
  - 수정: 모듈 상수 `UPSERT_BATCH_SIZE = 256` 도입, hybrid 경로에서 `points`를 256건 단위로 분할 upsert. dense+sparse+payload 합산 ~8MB 수준으로 한도의 1/4. vector 경로는 `langchain_qdrant`가 내부 `batch_size=64`로 자동 분할하므로 미변경.
  - 검증: 동일 PDF로 단건 동기 재현(`scripts/debug_single_ingest.py`) 성공 — `1034개 하이브리드 벡터(dense+sparse) 저장 완료 (batch=256)`. 저장 7.6초.

- **UI 시스템 탭에서 hybrid 모드 시 `'dict' object has no attribute 'size'`** ([ui/app.py](../ui/app.py)):
  - 증상: `SEARCH_MODE=hybrid`로 named vectors 컬렉션이면 `info.config.params.vectors`가 `dict`(`{"dense": VectorParams(...)}`)로 반환되는데, UI가 단일 객체 가정으로 `.size` 접근.
  - 수정: dict/객체 분기 처리. dict면 dense 차원·distance + sparse 키 노출, 단일 객체면 기존 표시. `qdrant_store.DENSE_NAME` 상수 재사용.

### Notes
- `ingest_jobs.error` 컬럼이 `error[:2000]`로 잘려 traceback 끝(예외 메시지)이 사라지는 부수 이슈 발견. 별건으로 `error[-2000:]` 또는 컬럼 상한 확대 검토 예정.

### 운영 (data fix)
- 검증용 단건 ingest로 발생한 Qdrant 고아 청크 1건(doc_id `e61dce3f`) 1,034개 정리 (`points/delete` filter)
- 32MiB 한도 패치 직전 누적된 영구 실패 잡 15건(retry_count=4)을 `pending/retry_count=0/error=NULL`로 일괄 reset → 가동 중인 워커가 즉시 재처리 시작

---

## [0.22.0] - 2026-04-25

### Added
- **색인 워커 분리** (TASK-018, ADR-028): Postgres `ingest_jobs` 큐 + 독립 워커 프로세스. FastAPI는 enqueue+202만, indexer 워커가 SKIP LOCKED claim 후 인덱싱·요약·분류
- 마이그레이션 `0003_add_ingest_jobs.sql` — sentinel(`table`, `ingest_jobs`)
- `connection.py` sentinel 시스템 일반화 — column/table 양쪽 지원, `pg_advisory_xact_lock`으로 동시 기동 시 마이그레이션 race 해소
- `packages/db/models.py` `IngestJobRecord`
- `packages/jobs/queue.py` — `enqueue_job`, `claim_next_job`(SKIP LOCKED), `mark_done`, `mark_failed`, `get_job`, `list_jobs`
- `apps/indexer_worker.py` — entry point `python -m apps.indexer_worker`, 폴링 루프, SIGTERM 핸들러, retry 3회, 인라인 summary+classify 호출
- `apps/routers/jobs.py` — `GET /jobs/{id}`, `GET /jobs?status=&limit=`
- `apps/routers/ingest.py` — `INGEST_MODE=queue` 분기, 사용자 명시 doc_type/category/tags를 잡 레코드에 저장
- `IngestResponse.job_id: Optional[int]`
- `scripts/bulk_ingest.py` `--via-queue` — HTTP 거치지 않고 직접 enqueue (FastAPI 미기동 환경에서도 동작)
- docker-compose 주석 가이드 — uvicorn + worker 두 프로세스 표준 운영 절차

### Changed
- `apps/config.py` `ingest_mode: "queue" | "sync"` 추가 (기본 queue)
- `bulk_ingest` 결과 카운터에 `enqueued` 추가
- 마이그레이션 적용 흐름이 advisory lock으로 직렬화 — 동시 기동에도 안전

### 검증 (스모크)
- 작은 파일 1건: enqueue → claim → 인덱싱(4초) → 요약 → 분류(LLM fallback `note / software/architecture`) → done. 총 9초
- 잡 상태 머신: `pending → in_progress → done` 추적 정상
- 사용자 입력 분류 미지정 시 자동 분류 자연 동작
- `INGEST_MODE=sync`로 1줄 전환 시 기존 동작 복원 (회귀 0)

### 관련 ADR
- ADR-028 (Postgres 큐 결정·SKIP LOCKED·advisory lock·BackgroundTasks 마이그레이션 흐름)

---

## [0.21.0] - 2026-04-25

### Added
- **랜딩 카드 v2** (TASK-017, ADR-027): 빈 채팅 카드에 카테고리 분포 한 줄 + 주제 칩 6개 + 최근 문서 카드 3 grid + 전체 문서 expander
- `/index/overview` 응답 확장: `top_tags[]`, `categories[{id,label,count}]`, `recent_docs[{doc_id,title,one_liner,category}]`
- `apps/schemas/documents.py` `RecentDocItem` 신설, `IndexOverviewResponse` 3필드 추가(default 빈배열로 후방호환)
- 주제 칩 클릭 → `library_search` 사전 채우기, 최근 문서 카드의 [이 책에 대해 묻기] → `active_doc_filter` (TASK-016 라우팅 재사용)
- `categories.yaml` label 매핑 — 카테고리 id를 한국어 라벨로 표면화

### Changed
- 빈 채팅 empty state 레이아웃 재구성 — summary → 카테고리 분포 → 주제 칩 → 예시 질문 → 최근 문서 카드 → 전체 문서 expander 순

### 검증
- 추가 LLM 호출 0회 (모든 신규 필드는 DB 데이터로 파생)
- 응답 페이로드 ~1.5KB → ~3KB (현 20문서)
- 캐시 무효화 흐름 변화 없음 (기존 `_overview_cache` 그대로)

### 관련 ADR
- ADR-027 (응답 확장 vs 신규 엔드포인트 트레이드오프)

---

## [0.20.0] - 2026-04-25

### Added
- **사용자 도서관 탭** (TASK-016, ADR-026): 채팅 옆 신규 탭에 카테고리 그룹 카드 그리드 + 검색/형식/카테고리 필터 + "이 책에 대해 묻기" doc_filter 라우팅
- 카드 상세 토글 — abstract / sample_questions 버튼 / meta(source/file_type/indexed_at/confidence)
- 채팅 탭 상단 활성 배지 — 도서관에서 라우팅된 doc_filter 표시 + [전체 검색] 해제
- `apps/schemas/query.py` `QueryRequest.doc_filter: Optional[str]`
- `packages/rag/{pipeline.py,retriever.py}` — `doc_filter`/`doc_id` 인자 관통 (vector·hybrid 양쪽). LangSmith 태그·메타에 `doc_filter` 표기
- `apps/routers/query.py` — request → pipeline 통과
- `ui/app.py` `TAB_LIBRARY`, `active_doc_filter` 세션 상태, `library_expanded_doc` 카드 토글

### Changed
- `st.tabs` 순서: 채팅 → **도서관(신규)** → 문서 → 대화 → 시스템 → 평가 (사용자 우선 정렬)

### 검증
- 현 20문서: 카테고리 8개 + (미분류) 0건. 카드 그리드·필터·doc_filter 라우팅 정상
- doc_filter 추가 비용 미미 (Qdrant filter 절만 추가)
- 카드의 confidence < 0.4 ⚠️ 배지 — 점토 공예/헌법재판소/더미 문서가 admin 검수 대상으로 자동 표면화

### 관련 ADR
- ADR-026 (도서관 탭 통합 결정·doc_filter 라우팅·카드 그리드 vs 페이지 분리 트레이드오프)

---

## [0.19.0] - 2026-04-25

### Added
- **카테고리 메타데이터 + 자동 분류** (TASK-015, ADR-025): `documents`에 `doc_type`/`category`/`category_confidence`/`tags` 추가, 단일 Qdrant 컬렉션 + payload 동기화 + keyword index, 룰 매칭 우선·LLM fallback
- Postgres 마이그레이션 `0002_add_classification_columns.sql` — sentinel `doc_type`으로 idempotent 처리
- `config/categories.yaml` — 초기 카테고리 9개(ai/ml, software/architecture, programming/cpp|network|systems, web/frontend, mobile/android, robotics, other)
- `packages/classifier/` — `CategoryClassifier`, `infer_doc_type`, `load_categories`. 키워드 매칭 → LLM fallback (gpt-4o-mini, JSON mode)
- `packages/vectorstore/qdrant_store.py` — `_ensure_payload_indexes`, `set_classification_payload(doc_id, doc_type, category, tags)` (부분 업데이트, doc_id 필터)
- `packages/db/repository.py` — `update_document_classification`, `list_documents_without_category`
- `apps/routers/documents.py` — `PATCH /documents/{id}` (DocumentPatchRequest), `classify_and_summarize_for_doc` 백그라운드 헬퍼 (summary→classify 순차)
- `apps/routers/ingest.py` — `POST /ingest` 폼에 `doc_type`/`category`/`tags` 옵션 파라미터. 사용자 명시값 우선
- `apps/schemas/documents.py` — `DocumentItem`에 분류 4필드 추가, `DocumentPatchRequest`
- `scripts/classify_documents.py` — `--dry-run/--regenerate/--limit/--doc-id/--report` + method 통계(rule/llm/fallback_unknown)

### Changed
- `init.sql` — 분류 컬럼·인덱스·CHECK 제약 동시 추가(신규 환경)
- 기본 인덱싱 흐름: 사용자 분류 미지정 시 summary 생성 후 같은 백그라운드 turn에 자동 분류

### 검증
- 파일럿 20문서: rule 16건(LLM 0회) + LLM fallback 4건(≈$0.001), 총 5.7초, 정확도 20/20
- doc_type 휴리스틱 정확(pdf→book, txt→note, docx→report)
- LLM low-confidence (< 0.4) 사례 — 점토 공예/헌법재판소/더미 문서가 'other' + confidence 0.3으로 정직하게 표면화

### 관련 ADR
- ADR-025 (단일 컬렉션 결정·룰 매칭 우선·LLM fallback·회귀 조건)

---

## [0.18.0] - 2026-04-25

### Added
- **문서 자동 요약** (TASK-014, ADR-024): `summary` JSONB 영구 캐시 + 인덱싱 후 비동기 훅 + admin 강제 재생성 API
- `packages/summarizer/` — `document_summarizer.py`, `prompts.py` (system + few-shot 2건, 환각 차단 규칙)
- Postgres 마이그레이션 `0001_add_summary_columns.sql` — `summary JSONB`, `summary_model TEXT`, `summary_generated_at TIMESTAMPTZ`
- `packages/db/connection.py` — sentinel 컬럼 존재 검사 후 ALTER 회피 (idempotent, AccessExclusiveLock 충돌 방지)
- `packages/db/repository.py` — `update_document_summary`, `list_documents_without_summary`
- `apps/routers/documents.py` — `GET /documents/{id}/summary`, `POST /documents/{id}/summary/regenerate`, `generate_summary_for_doc(doc_id)` 백그라운드 헬퍼
- `apps/schemas/documents.py` — `SummaryResponse`, `DocumentItem`에 `summary`/`summary_model`/`summary_generated_at` 필드
- `scripts/generate_summaries.py` — `--dry-run`/`--regenerate`/`--limit`/`--doc-id`/`--report` 옵션, 결과 JSON 리포트
- `.env` 토글 `SUMMARY_ENABLED=true|false` (기본 true)

### Changed
- `apps/routers/ingest.py` — `pipeline.ingest`를 `asyncio.to_thread`로 위임. async 라우트의 event loop 차단 핫픽스(bulk_ingest 진행 중에도 `/query`·`/health` 응답 가능). 응답 후 `BackgroundTasks`로 `generate_summary_for_doc` 자동 호출
- `packages/db/models.py` `DocumentRecord` — summary 3개 컬럼 추가
- `packages/code/models.py` `DocRecord` — 동기화

### 검증
- 파일럿 16문서 모두 success (시범 1 + 일괄 15) — 평균 3.7s/문서, 총 56초, 비용 ≈ $0.08
- 한국어 / 영문 / 짧은 문서 무작위 검수 → 환각 0건, 정보 부족 시 빈 배열 정직 처리
- 영문 원본 → 한국어 요약 + 기술 용어 원어 유지

### 후속 / 결번
- TASK-015 자동 분류가 `summary.topics[]`를 `tags[]`로 채택하는 흐름이라 의존 정렬 유효
- ADR-018은 TASK-006(MCP) 철회로 결번. 다음 가용 ADR은 ADR-025

---

## [0.16.0] - 2026-04-23

### Added
- **하이브리드 검색** (TASK-011, ADR-023): Qdrant 네이티브 sparse vectors(BM25) + dense + RRF 병합
- `packages/rag/sparse.py` — `SparseEmbedder` + Kiwi 한국어 형태소 전처리 (명사·동사·외국어·숫자·한자·어근 추출)
- `packages/vectorstore/qdrant_store.py` 재작성 — `search_mode` 토글, named vectors 컬렉션, `query_points` + `FusionQuery.RRF`
- `.env` 토글: `SEARCH_MODE=vector|hybrid`, `SPARSE_MODEL_NAME=Qdrant/bm25`
- DI·rebuild·bench 스크립트 모두 hybrid 지원
- 의존성 `fastembed>=0.4`, `kiwipiepy>=0.17`

### Changed
- 기본값 `SEARCH_MODE=hybrid` — 회귀 0 확인 후 적용
- 재인덱싱 완료 (6 문서 → 1209 포인트, dense+sparse named vectors)

### 검증
- Phase 1 A/B (vector 2026-04-22 기반선 ↔ hybrid 2026-04-23):
  - Hit@3 1.000 ↔ 1.000, MRR 1.000 ↔ 1.000, Recall@3 0.944 ↔ 0.944 (동률, 이미 상한)
  - 평균 지연 580ms ↔ 1008ms (+74%, sparse 인코딩 + 병렬 검색 비용)
- 현 dataset(12 질의)은 벡터 단독으로 상한이라 hybrid 이득이 드러나지 않음. "정확 매칭" 질의 추가 시 이득 예상

---

## [0.15.0] - 2026-04-23

### Added
- **폴더 단위 일괄 색인 CLI** (TASK-010, ADR-022): `scripts/bulk_ingest.py` 신설
- 하위 폴더 포함 재귀 탐색 (`--recursive` 기본 True, `--no-recursive` 토글)
- 확장자 필터(`--include`), 정규식 제외(`--exclude`), 제목 자동 생성(`--title-from stem|filename|relpath`)
- `--dry-run`(대상만 미리보기), `--fail-fast`, `--source-prefix`, `--workers`, `--api-base`, `--report`
- L1 중복 감지(ADR-005) 활용 — 재실행 시 이미 등록된 파일 자동 409 스킵
- 결과 리포트 JSON → `data/eval_runs/bulk_ingest_<timestamp>.json`
- `MAX_UPLOAD_SIZE_MB` 초과 파일은 `skipped_too_large`로 집계 (실패 아님)
- 통합 테스트 `tests/integration/test_bulk_ingest.py` — 6개 케이스
- `wiki/onboarding/setup.md`에 "대량 문서 색인" 섹션 추가

### 검증
- 스모크: 재귀 3파일 업로드 6.8초 / 재실행 전부 409 스킵 0.0초
- 통합 테스트 6/6 통과
- 관리자 UI 버튼·`POST /bulk_ingest` API는 **인증·공개배포 묶음과 함께 보류** (무인증 노출 금지)

---

## [0.14.3] - 2026-04-22

### Fixed (0.14.1·0.14.2 수정이 추정 원인을 잘못 짚어 증상 지속 — 진짜 근본 원인 수정)
- **진짜 원인은 버튼 `key` 불일치**
  - 라이브 렌더: `live_{len(messages)}_sug_*`
  - 다음 rerun 히스토리 렌더: `hist_{msg_idx}_sug_*`
  - 사용자가 라이브에서 클릭했지만 rerun 시 같은 위치 버튼이 다른 key로 재렌더되어 Streamlit widget state가 이벤트 매칭 실패
- 수정: 두 경로의 key 접두사를 **메시지 인덱스 기반(`msg_{msg_idx}`)으로 통일**
- 라이브 렌더의 `key_prefix = f"msg_{len(messages) - 1}"` = assistant 메시지 append 직후 인덱스
- 히스토리 렌더의 `key_prefix = f"msg_{msg_idx}"` = enumerate 인덱스
- 두 값이 일치 → 라이브 클릭 이벤트가 다음 rerun 히스토리 렌더에서 정상 소비

### Note
- 0.14.1(st.rerun 제거)과 0.14.2(chat_message 바깥 렌더)는 부작용 방지로 유지되지만 **핵심 원인은 아니었음**. 추적 로그로 남김

---

## [0.14.2] - 2026-04-22

### Fixed (0.14.1 수정이 부분적이라 추가 수정)
- **배지 두 번째 이후 클릭 무반응 — `st.chat_message` 컨테이너 내부의 버튼으로 잘못 진단**
- `_render_suggestions()` 호출을 `with st.chat_message(...)` 블록 **바깥**으로 이동 (히스토리·라이브 양쪽)
- **결과적으로 이 변경만으로는 문제 미해결** — 진짜 원인은 0.14.3에서 발견·수정. 본 변경은 Streamlit 모범 사례에 부합하므로 되돌리지 않음

---

## [0.14.1] - 2026-04-22

### Fixed
- **후속 질문 배지 두 번째 이후 클릭이 무반응이던 문제** (`ui/app.py`): `_render_suggestions()`와 empty state 예시 질문 배지에서 버튼 클릭 후 **명시적 `st.rerun()` 호출을 제거**. `st.button` 클릭 자체가 rerun을 유발하므로 수동 호출은 중복이며, 두 번째 클릭부터 state 플러시 타이밍이 꼬여 재질의가 트리거되지 않았음
- **주의**: 이 수정만으로는 부분적 해결. 근본 원인은 0.14.2에서 별도 수정됨 (배지를 `st.chat_message` 바깥으로 이동)

---

## [0.14.0] - 2026-04-22

### Added
- **DELETE 시 고아 파일 동반 정리** (TASK-009, ADR-021): `data/uploads/{doc_id}.*`, `data/markdown/{doc_id}.md`를 DELETE 엔드포인트가 직접 삭제
- **HybridChunker 토큰 상한 명시**: `HuggingFaceTokenizer(max_tokens=480)` 지정 → 512토큰 초과 경고 0건. import 실패 시 기본 HybridChunker로 fallback

### Fixed
- ADR-010으로 원본 파일 영구 보관 후 DELETE가 디스크 정리를 안 해 고아 파일이 누적되던 기술 부채 해소
- "Token indices sequence length > 512" 경고로 인해 임베딩 경계에서 내용이 잘리던 문제 — 안전 마진 32토큰 포함 480으로 상한 명시

### Verified
- 업로드→두 파일 생성→DELETE→두 파일 모두 삭제 확인
- 토큰 경고: `grep -c "Token indices sequence length"` = **0**

---

## [0.13.0] - 2026-04-22

### Added
- **빈 채팅 인덱스 커버리지 카드** (TASK-008, ADR-020)
- 신규 엔드포인트 `GET /index/overview` — 문서 목록·상위 heading 집계·LLM 요약·예시 질문 5개를 한 번에 반환 + 인메모리 캐시
- `IndexOverviewResponse` 스키마, `invalidate_index_overview_cache()` 헬퍼
- 업로드(`/ingest`)·삭제(`/documents/{id}`) 시 캐시 자동 무효화
- `.env(.example)` 토글: `INDEX_OVERVIEW_ENABLED=true`
- Streamlit 채팅 탭 empty state에 "이 시스템이 아는 내용" 카드 + 인덱싱된 문서 리스트 + 예시 질문 5개 배지 (클릭 재질의)

### Verified
- 1차 호출: 한국어 요약 2~3문장 + 예시 질문 5개 정상 생성
- 2차 호출: **5ms 캐시 히트** (LLM 호출 0)
- 업로드/삭제 후 자동 무효화 동작

---

## [0.12.0] - 2026-04-22

### Added
- **후속 질문 제안** (TASK-007 Phase 1, ADR-019): 답변 후 LLM이 생성한 구체적 후속 질문 3개 배지로 표시, 클릭 시 즉시 재질의
- `packages/rag/generator.py`: 두 종류 system prompt + JSON 모드(`response_format={"type":"json_object"}`) + 파싱 실패 graceful degrade
- `apps/schemas/query.py`: `QueryResponse.suggestions: list[str] = []`
- `apps/config.py`·`.env(.example)`: `SUGGESTIONS_ENABLED`, `SUGGESTIONS_COUNT` 토글
- LangSmith 트레이스 태그 `suggestions:<bool>` + 메타 `suggestions_enabled/count`
- `ui/app.py`: `_render_suggestions()` 헬퍼, `_pending_question` 세션 키로 배지 클릭 재질의 플로우. 과거 메시지의 suggestions도 재클릭 가능

### Changed
- `generate()` 반환: `str` → `dict {"answer": str, "suggestions": list[str]}`
- `RAGPipeline.query` 반환 dict에 `suggestions` 키 추가
- 답변 토큰 +50~100 증가 (추가 LLM 호출 0회)

### Verified
- `SUGGESTIONS_ENABLED=true`: "ROS의 주요 구성요소는?" → 한국어 후속 질문 3개 정상 생성
- `SUGGESTIONS_ENABLED=false`: suggestions=0, answer 동일 → **회귀 0**
- 불충분 응답 시 suggestions 빈 리스트 강제

---

## [0.11.0] — 건너뜀

TASK-006 (RAG → MCP 서버 익스포트) 철회(2026-04-22)로 인해 0.11.0 버전은 발행되지 않음.
원본 큐잉 기록은 `roadmap.md`의 `~~TASK-006~~` 섹션과 `log.md` 2026-04-22 `queue` 항목에 보존.

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
