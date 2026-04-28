# Wiki Log

이 파일은 append-only입니다. 항목을 수정하지 말고 새 항목을 위에 추가하세요.
`grep "^## \[" log.md | head -10` 으로 최근 항목을 빠르게 확인할 수 있습니다.

---

## [2026-04-28] impl | TASK-020 후속 — NextJS 시리즈 카드·시리즈 스코프 배지 (0.26.1)

### 변경
- `web/types/api.ts` — openapi-typescript 재생성 (`pnpm gen:api`). SeriesItem/SeriesListResponse/SeriesMembersResponse/SeriesReviewItem + DocumentItem.series 5필드 + QueryRequest.series_filter 자동 반영
- `web/lib/api/types.ts` — series 4 type 별칭 추가
- `web/lib/api/keys.ts` — `keys.series.{all,list,detail,members}` 추가
- `web/lib/hooks/use-series.ts` 신설 — `useSeriesList()` + `useSeriesMembers(seriesId)`
- `web/components/library/series-card.tsx` 신설 — 시리즈 N권 응축 카드. 상단 amber 배경+테두리로 단일 doc 카드와 시각 구분. 펼치기 시 멤버 목록 (volume_number 순), 각 권 클릭 → `?doc_filter=`. [이 시리즈에 묻기] → `?series_filter=`. series_match_status 표시
- `web/components/library/doc-card.tsx` — 시리즈 멤버 doc에 "📚 Vol N" 배지 추가 (제목 옆). 비-시리즈 문서는 변화 없음
- `web/app/library/page.tsx` — 시리즈 그룹 섹션 (카테고리 그룹 위). 시리즈 멤버는 카테고리 그룹에서 제외 — 중복 표시 방지
- `web/components/chat/scope-banner.tsx` — `📚 시리즈 한정` 배지 모드 추가. amber 배경, 시리즈 제목+멤버 수 표시. 우선순위 doc > category > series 순으로 분기. clearAll에 `setSeriesFilter(null)` 포함
- `web/app/chat/page.tsx` — `series_filter` URL state 인자 + 활성 스코프 우선순위 정렬(`docFilter > category > seriesFilter`) + ChatInput placeholder 4분기

### 검증
- `pnpm exec tsc --noEmit` 0 에러
- `pnpm exec eslint` 0 경고 (변경 5파일)
- Playwright Phase 1 (`AUTH_ENABLED=false pnpm exec playwright test ui-flow`): 9 passed / 1 skipped (mobile drawer chromium-desktop 의도 skip 유지). UI 추가 회귀 0
- 백엔드 라이브: 시리즈 백필을 도서관에 즉시 노출하려면 `python scripts/suggest_series.py --apply`로 6 suggested 후보를 confirm 단계 거치거나, FastAPI `/documents/{id}/series_match/attach`로 수동 묶기. UI 자체는 series가 0건이어도 회귀 0 (시리즈 그룹 섹션 자동 숨김)

### Streamlit 동결 정합 유지
- 사용자 측 NextJS는 read-only — 카드·스코프·라우팅만 노출. 검수(confirm/reject/attach)는 ADR-029 결정대로 FastAPI 엔드포인트 + CLI로만 가능. NextJS admin 이전 시 검수 페이지 도입 (별건)

### 영향 페이지
- changelog 0.26.1
- overview 동일 행 0.26.1로 NextJS UI 추가 표기

---

## [2026-04-28] impl | TASK-020 — Series/묶음 문서 1급 시민 도입 완료 (ADR-029, 0.26.0)

### 데이터 모델
- 마이그레이션 `0005_add_series_tables.sql` 적용 — `series` 테이블 신설, `documents` 4컬럼 추가, FK ON DELETE SET NULL, CHECK constraint 2개 (series_type / series_match_status), 인덱스 2개
- ORM: `SeriesRecord` 신설, `DocumentRecord`에 series 4필드 + `documents_series_match_status_check`
- `DocRecord` 데이터클래스에도 series 4필드 — response 매핑 일관성

### 휴리스틱 (LLM 호출 0)
- 동일 source 폴더 + 공통 prefix ≥ 8자(권 번호 정규화 후) + 동일 doc_type + 숫자 시퀀스
- 신뢰도 high(4신호) → auto_attached / medium(3) → suggested / low → 처리 없음
- 권 번호 패턴 — Chapter N / Ch.N / Vol N / Volume N / N권 / 제 N권 / N편 / N장 / 끝 숫자 / `_NN.pdf` / Nst-th
- 4자리 연도(2024) 차단, 제목 중간 버전 번호("ROS 2.0.3") 차단

### 통합
- `apps/indexer_worker.py` — BackgroundTasks 체인 6단계로 `series_match` 추가, 실패 격리(예외 흡수, 인덱싱은 성공)
- `packages/vectorstore/qdrant_store.py:set_series_payload` — 청크 metadata 부분 갱신, payload index `metadata.series_id` keyword
- 검색 통합 — `QueryRequest.series_filter` + retriever/pipeline/qdrant_store 통과. 활성 스코프 우선순위 **doc > category > series** (한 번에 하나)
- LangSmith 트레이스 메타에 `series_filter` 추가

### API (10 엔드포인트, `apps/routers/series.py`)
- 사용자 read: `/series` 목록, `/series/{id}`, `/series/{id}/members`
- 관리자 write: POST `/series`, PATCH `/series/{id}`, DELETE `/series/{id}`
- 검수: GET `/series/_review/queue` (auto_attached + suggested 큐), POST `/documents/{id}/series_match/confirm|reject|attach`
- `app.include_router(series.router, ...)` 등록 검증 — 10 routes 노출 확인

### CLI 백필 (`scripts/suggest_series.py`)
- dry-run / `--apply` 분기. 결과 JSON 리포트 `data/eval_runs/suggest_series_<ISO>.json`
- 실 인덱스 107문서 dry-run 결과:
  - **suggested 6건** — UNIX Power Tools / 하루하루가 세상의 종말 / 디지털 포트리스 (각 2권씩, 폴더 분산이라 high 미달)
  - **low_confidence 18건** — Premier Press 출판사 prefix 같은 잘못된 매칭 가능성 후보, 검수 필요
  - **no_candidate 83건** — 단일 문서

### 검증
- `pytest tests/unit/test_series_matcher.py -v` → **26/26 passed (0.13s)**
- 통합 smoke (실 DB+Qdrant) — high 자동 묶기, 기존 시리즈 합류, skip 정책(rejected/auto_attached/confirmed 재바인딩 차단), volume_number 추출, cover_doc_id 자동 모두 정상
- 단위 회귀 영향 0건 (사전 부채 4건 동일)

### 검수 인터페이스 — Streamlit 동결 정책 정합
- 메모리 `feedback_streamlit_no_edit` 준수 — Streamlit 검수 페이지 미수행
- FastAPI 엔드포인트 + CLI 백필 두 경로로 1인 운영 cover. NextJS admin 이전(별건) 시 검수 페이지 도입

### 영향 페이지
- ADR-029 본문 신설 ([decisions.md](wiki/architecture/decisions.md))
- changelog 0.26.0
- overview 진행 표 — TASK-020 완료 행으로 이동
- roadmap.md 큐 — TASK-020 완료 표기

### 후속 (별건)
- TASK-019 NextJS UI에 시리즈 카드·시리즈 스코프 배지 추가
- LLM 보조 (medium 신뢰도가 too noisy 판명 시, 사용자 합의 후)
- 시리즈 단위 요약·태그 집계 표면화

---

## [2026-04-28] query | "검색 후 상위 섹션 펼쳐보기"는 미구현 — 도구는 갖춰짐, 별건 후속 후보

### 사용자 질의
- 청크 파싱 시 마크다운으로 변환 후 다시 청킹할 때 헤더 정보를 유지하는지 → 정정. 마크다운을 거치지 않음. Docling이 구조 트리에서 직접 청크 발행 + 각 청크 머리에 전체 heading 경로 breadcrumb prepend (`packages/loaders/docling_loader.py:57-114`). 마크다운(`data/markdown/{doc_id}.md`)은 별건의 사람용 사이드 산출물 (`_save_markdown` L141-160)
- 청킹 본문이 로컬 로그에 남는지 → 아니오. `logs/`에는 개수·타이밍·플래그(`테이블/이미지`)만 한 줄. 청크 본문은 Qdrant payload(검색용) + `data/markdown/{doc_id}.md`(사람용)에 영속화
- 검색에서 청크를 찾은 뒤 상위 섹션 검색 가능한지 → **현재 직접 지원 X. 도구는 거의 갖춰짐**

### 현재 상태 (2026-04-28 시점 코드 기준)
| 자원 | 상태 |
|---|---|
| `metadata.heading_path` (리스트, 상위→하위) | ✅ 모든 청크 영속화 (`docling_loader.py:123`) |
| breadcrumb 문자열 청크 본문 prepend | ✅ 임베딩에 자연 포함 |
| `metadata.heading_path` Qdrant payload index | ❌ `qdrant_store.py:152-157`은 `doc_id/doc_type/category/tags` 4개만 keyword index |
| `scroll_by_doc_id(doc_id)` | ✅ chunk_index 순 회수 (`qdrant_store.py:375-397`) |
| 검색 hit → 같은 헤딩 prefix 청크 묶음 확장 API/UI | ❌ 미구현 — retriever·pipeline·UI 어디에도 경로 없음 |
| 유일한 활용 | 랜딩 카드 `top_headings` 집계 (`apps/routers/documents.py:241-257`) |

### 후속 후보 (별건, 사용자 결정 대기)
- **(A) "이 섹션 전체 보기"** — 검색 hit가 속한 `heading_path[0..k]` prefix 공유 청크를 chunk_index 순으로 모아 반환. 산정 ~80~150줄 + 테스트, 1~2시간. NextJS SourceExpander 옆 "📖 이 섹션 전체 보기" 버튼으로 자연스러운 UX
- **(B) 헤딩 거시 검색** — `metadata.heading_path` keyword index 추가 + `GET /sections/search?q=` 엔드포인트, distinct 후보군. 산정 ~150~250줄 + 테스트
- 결론: **(A)가 답변 품질·UX 양쪽에 즉시 도움**. 사용자 "위키 정리만"이라 본 query 항목으로만 기록, 태스크 등록 보류

### 영향 페이지
- 본 항목 (log.md) — 후속 결정에 활용

---

## [2026-04-28] impl | TASK-019 Phase B (a) — Clerk JWT 실 검증 구현 (0.25.0)

### 변경
- `apps/middleware/auth.py:_verify_token` — stub 제거 + 실 구현. PyJWKClient로 JWKS 자동 fetch+캐시 → RS256 서명 검증 → `iss` 일치 확인 → `sub` claim을 user_id 반환. 실패 분류:
  - `PyJWKClientError` (네트워크·키 미존재) → `logger.warning` + `None`
  - `InvalidTokenError` 계열 (만료·서명 불일치·issuer 불일치·claim 누락) → `logger.info` + `None`
  - 기타 예외 → `logger.exception` + `None` (누설 차단)
- `audience` 검증은 비활성화(`verify_aud: False`). Clerk 토큰은 통상 `aud` claim 미포함, 서명·exp·iss로 강도 확보. 필수 claim은 `["exp", "iat", "sub", "iss"]`로 강제
- JWKS 클라이언트는 `__init__`에서 lazy(첫 검증 호출에서 1회 생성). 메모리 풋프린트 증가 0 (Phase 1 모드는 생성 자체 안 함)
- `requirements.txt` — `pyjwt[crypto]>=2.8` 추가 (TASK-019, ADR-030 Phase 2 주석)
- `tests/unit/test_middleware_auth.py` 신설 — 자체 RSA 키쌍으로 가짜 JWKS를 mock, 9개 케이스 회귀:
  1. 정상 토큰 → sub 반환
  2. 만료 토큰 → None
  3. 잘못된 issuer → None
  4. 잘못된 서명(다른 키) → None
  5. 필수 claim(sub) 누락 → None
  6. `clerk_jwks_url` 미설정 → None (시도 자체 안 함)
  7. `clerk_issuer` 미설정 → None
  8. JWKS 조회 실패(PyJWKClientError) → None
  9. sub claim 비문자열 → None

### 검증
- `pytest tests/unit/test_middleware_auth.py -v` → **9/9 passed (0.80s)**
- 전체 `pytest tests/unit/` → 본 작업 영향 0건 (기존 4건 실패는 base 동일 — generator 반환 타입 변경 사전 부채, 본 작업 무관)
- 의존성 설치: `pyjwt 2.12.1`, `cryptography 47.0.0` (cffi 2.0.0, pycparser 3.0 부수)
- `AUTH_ENABLED=false` 모드는 검증 호출 자체가 일어나지 않음 — 운영 동작 변화 0, 회귀 위험 0

### 의도적 제외
- `audience` 검증 — Clerk 토큰의 일반적 발급 형태 기준 비활성화. 향후 Clerk 설정에서 `aud` claim 추가 시 옵션 한 줄 변경
- 실 Clerk dev 환경 통합 검증 — 본 항목은 운영에서 `AUTH_ENABLED=true` 전환 단계로 분리

### Phase B 남은 항목 (최종)
- 운영에서 `AUTH_ENABLED=true` 전환 + 회귀 검증 (env 토글 한 줄 + 백엔드 재기동)

---

## [2026-04-28] impl | TASK-019 Phase B 잔여 정리 — chat 라이브 sources 머지 + Playwright Phase 1/2 실 실행 통과 (0.24.2)

### 변경
- `web/app/chat/page.tsx` — RAG mutation 응답의 `sources` 필드를 `liveSources` 상태로 보존 + 마지막 assistant 메시지에 머지. 이전엔 `suggestions`/`latency_ms`만 머지하고 `sources` 누락 → conversation refetch 도착 전까지 SourceExpander 미표시 결함. 백엔드 `MessageItem`은 `sources`를 영속화하지 않으므로 라이브 값을 fallback으로 유지(`sources: liveSources ?? arr[i].sources`). sessionId 변경 시 동기 리셋에 `setLiveSources(undefined)` 추가
- `web/tests/api-proxy.spec.ts` — 검증 경로를 `/api/health`(공개) → `/api/conversations`(보호)로 정정. proxy.ts `isPublicRoute`에 `/api/health`가 포함된 의도와 어긋나는 케이스를 수정. 보호된 `/api/*` 비인증 호출이 307 → `/sign-in` 인 것을 검증하는 본래 의도 회복. 헤더에 의도 명세 갱신

### 검증 (실 실행, 2026-04-28)
- `pnpm exec tsc --noEmit` 0 에러, `pnpm exec eslint app/chat/page.tsx` 0 경고
- **Phase 1** (`AUTH_ENABLED=false pnpm exec playwright test ui-flow`): 9 passed / 1 skipped (chromium-desktop의 모바일 drawer는 `test.skip(!isMobile)` 의도된 skip)
  - chromium-desktop / chromium-mobile 양 프로젝트
  - 케이스: `/chat` 헤더·입력창·보내기, `/library` 검색 placeholder, `/library?q=test` URL state, `/` → `/chat` 리다이렉트, 모바일 사이드바 drawer
- **Phase 2** (`AUTH_ENABLED=true pnpm exec playwright test auth-protected api-proxy`): 10 passed (8 auth-protected + 2 api-proxy)
  - sign-in 페이지 Clerk SignIn 렌더, `/`·`/chat`·`/library` 비로그인 시 `/sign-in` 리다이렉트(307)
  - `/api/conversations` 비인증 시 307 → `/sign-in` location 검증
- 첫 시도 시 .next dev 캐시가 Phase 1↔Phase 2 전환에서 `Cannot find module '@clerk/nextjs'` 발생 → `rm -rf .next` 후 재빌드로 해소 (의존성은 정상, 캐시 손상)

### 의도적 제외
- 인증된 흐름(로그인 후 페이지 동작) — `@clerk/testing` 도입 후 별건
- 백엔드 FastAPI 미가동 상태에서 실행 — Phase 1 ui-flow는 EmptyState fallback으로 페이지 로드 자체만 검증, Phase 2는 미들웨어 단계에서 차단되어 백엔드 도달 전 종료

### Phase B 남은 항목
- `apps/middleware/auth.py:_verify_token` Clerk JWT 실 검증 (현 stub)
- 운영 환경에서 `AUTH_ENABLED=true` 전환 + 회귀 검증

---

## [2026-04-28] impl | TASK-019 Phase B 진전 — proxy.ts AUTH 토글 + Playwright Phase 1/2 분리 (0.24.1)

### 발견 (Next 16 정정)
- Next 16에서 `middleware.ts` → `proxy.ts` 이름 변경 (함수명 `proxy`). 기존 `web/proxy.ts`는 Phase A에서 이미 작성돼 있었으나 AUTH_ENABLED 토글 미반영 상태. ADR-030 Phase 1(false 기본)에 정합하지 않음

### 변경
- `web/proxy.ts` — `AUTH_ENABLED` env 토글 추가. Phase 1(false): clerkMiddleware 통과만, 모든 라우트 무방호. Phase 2(true): `/`, `/chat`, `/library` 비로그인 시 `/sign-in` 리다이렉트(307). 공개 라우트 `/sign-in`, `/sign-up`, `/api/health` 추가
- `web/.env.local.example` — `AUTH_ENABLED=false` 기본값 + Phase 1/2 주석
- `web/tests/auth.spec.ts` → `auth-protected.spec.ts` rename + `test.skip(AUTH_ENABLED!=='true')` 가드 추가 (Phase 2 모드 회귀)
- `web/tests/api-proxy.spec.ts` — Phase 2 가드 추가 + 의도 명확화
- `web/tests/ui-flow.spec.ts` (신규) — Phase 1 사용자 흐름 5케이스: `/chat` 로드(헤더·입력창·보내기), `/library` 로드(검색 placeholder), URL state(`?q=test`), `/` → `/chat` 리다이렉트, 모바일 drawer(Pixel 5)
- `web/playwright.config.ts` — 두 모드 실행 가이드 코멘트

### 검증 (코드 차원)
- DB: `conversations.user_id text NOT NULL DEFAULT 'admin'` + `ix_conversations_user_id` 적용 확인 (information_schema 조회)
- `category_filter` Qdrant 필터 절 — `pipeline.py:101-143` → `retriever.py:17-31` → `qdrant_store.py:239-244 must.append(FieldCondition(key="metadata.category"))` 추적. vector(L246-251 `filter=`) + hybrid(L262-277 `query_filter=`) 양 경로 적용. 0.23.1 hotfix(nested key) 정합 보존됨

### 의도적 제외
- 실제 `pnpm exec playwright test` 실행 — 본 커밋 후 사용자 환경에서 별건
- Clerk JWT 실 검증(`apps/middleware/auth.py:_verify_token` stub) — Phase 2 진입 시
- `components/chat/scope-banner.tsx`, `suggestions.tsx` Stub 채우기 — 별건 후속

### Phase B 남은 항목
- JWT 실 검증, scope-banner/suggestions 채우기, Playwright 실 실행, AUTH_ENABLED=true 전환

---

## [2026-04-28] impl | TASK-021 — 정기 모니터링 + 워커 RSS 가드 도입 완료 (0.24.0)

### 배포물
- `scripts/krag_snapshot.py` — 5분 주기 launchd fork, knowledge-rag 프로세스 + 시스템 top10 + 포트 dump, 매 줄 fsync, 7일 gzip 회전
- `scripts/krag_guard.py` — 30초 주기, `apps.indexer_worker` 한정 RSS ≥ 14GB SIGTERM + macOS 알림 + 사후 dump, `--observe-only`/`KRAG_GUARD_RSS_GB` 토글
- LaunchAgents 2개: `~/Library/LaunchAgents/com.knowledge-rag.{snapshot,guard}.plist` (RunAtLoad=true)
- ADR-031 본문 신설 ([decisions.md](wiki/architecture/decisions.md))
- 위키 신설: [wiki/deployment/monitoring.md](wiki/deployment/monitoring.md)
- 위키 갱신: [ISSUE-005](wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md) 후속 운영 인프라 섹션, [ISSUE-004](wiki/issues/open/ISSUE-004-docling-parse-longtail.md) 자동 차단 안전망 섹션, [index.md](index.md) Deployment 표 monitoring.md active 표기 + 페이지 수 30→31, [overview.md](overview.md) 다음 할 일 표

### 검증 (2026-04-28 19:51 KST)
- `launchctl list | grep knowledge-rag` → snapshot pid=74285 / guard pid=74287, 양쪽 exit=0
- 첫 스냅샷 dump 정상: 시스템 used 9.3% / 프로젝트 프로세스 9건 / top10 / 포트 3000=0 8000=0 8501=0
- 첫 가드 no-op: `worker not running (threshold=14.0GB)` 1줄 로그
- 모의 SIGTERM: decoy(`exec -a "python -m apps.indexer_worker --decoy" sleep 300`)에 `KRAG_GUARD_RSS_GB=0` 강제 트리거 → `OBSERVE`(--observe-only) 후 `KILL pid=NNN SIGTERM sent, dump=guard_kill_*.log`(82KB) → decoy DEAD 확인
- 자기 PID 제외 로직 정상

### 후속 (별건)
- ISSUE-005 본격 해결: 시스템 used% 가드를 RSS top + 화이트리스트 기반으로 재설계
- ISSUE-004 5번 `INDEXER_MAX_JOBS` 자가 종료 — 본 가드와 보완 관계
- 임계 14GB → 16GB 또는 "2회 연속 트리거" 컷 (운영 데이터 2~4주 축적 후)
- TASK-019 Phase B 재개

---

## [2026-04-28] queue | TASK-021 — 프로젝트 프로세스 정기 모니터링 + 워커 RSS 가드 큐잉

- 배경: ISSUE-005 누명 사건(2026-04-27) 후 강화 모니터(`/tmp/krag_monitor.py`)가 워커 lifecycle에 묶여 사라짐. 04-28 10:10 워커 SIGTERM 후 모니터 부재 — 다음 사건 사후 추적 도구 0. 또한 ISSUE-004 idle RSS 13.18GB 평탄(누수/fragmentation 가설 보강)에 대한 자동 차단 장치 없음.
- 범위: `scripts/krag_snapshot.py`(5분 정기 관찰) + `scripts/krag_guard.py`(30초 워커 한정 RSS 가드) + LaunchAgents 2개 + `wiki/deployment/monitoring.md` 신설 + ADR-031.
- 의도적 제외: 시스템 used% 가드(ISSUE-005 누명 결함 그대로), 워커 외 프로세스 가드(NextJS dev/Streamlit/Uvicorn 자동 kill 금지), 자동 재기동, `INDEXER_MAX_JOBS`(별건), 외부 알림(Slack/이메일 — 비용·키 합의 규칙), 메트릭 시각화.
- 사용자 합의 사양 (2026-04-28): 대상 워커 한정(`apps.indexer_worker`) · RSS ≥ **14GB**(ISSUE-004 idle 13.18GB + 1GB 여유) · SIGTERM only · 자동 재기동 없음 · macOS 알림 켬 · 단일 페이즈.
- 완료 기준: 두 스크립트 1회 실행 정상 → launchd 등록 후 첫 스냅샷·가드 발생 확인 → 모의 테스트(임계 일시 인하)로 SIGTERM + 알림 + 사후 dump 확인 → 일자 회전·7일 gzip 검증 → ADR-031 본문 + monitoring.md 신설 + ISSUE-005/004 cross-link.
- 실행 큐: ✅ TASK-001~018 → ⏸️ TASK-019(Phase A 완료·Phase B 일시 중단) → **🎯 TASK-021 (현재)** → 🕐 TASK-012/013/020 (후순위) → 🛑 인증·공개배포 묶음 잔여 4개
- 절차 예외: rag-task-start 0단계 "in-progress 있으면 중단" 원칙에 대한 사용자 승인 예외 — TASK-021은 NextJS 개발 환경 안정성 직결 운영 인프라이므로 끼워넣기. TASK-019은 ⏸️로 표기, Phase A 코드는 그대로 보존.
- 반영: roadmap(실행 큐 라인 갱신 + TASK-021 상세 섹션 추가), overview(다음 할 일 표 TASK-019 ⏸️ + TASK-021 🎯 행 추가)

---

## [2026-04-28] ops | 워커 15h 가동 결과 + #189 reset + ISSUE-004/005 갱신

### 가동 결과 (4/27 19:08 → 4/28 10:10, 15h 02m)
- worker pid 79071 단일 가동, 강화 모니터(pid 79207, 5s fsync) + 알림 watcher(pid 81234) 동시 가동
- 처리: 잡 45건 (#176~#220) — 정상 done **44** + 영구 failed **1**(#189 Game Coding Complete, retry=4 도달)
- 큐 종료 상태: done **219** / failed 1 / pending·in_progress 0 — 4/28 00:48 watcher가 잡 완료 알림 발사 후 자가 종료
- **임계 60% snapshot 발생 0건** — ISSUE-005 누명 시나리오 재발 없음. 이번 환경(NextJS dev 미가동)에서 가드는 안전 영역만 관찰
- worker SIGTERM → 7초 graceful shutdown 정상, 사후 snapshot 자동 dump: `data/diag/snapshot_worker_dead_20260428T101037.log` (17KB)

### 누수 추세 추가 데이터
- 종료 시점 worker RSS **13167MB**, 종료 직전 9h 22m(00:48~10:10) idle 상태에서도 RSS 13.18GB 평탄 유지
- 잡 처리 중 7~13GB 피크 후 회수 부분적, 다음 잡까지 13GB 보존 — 누수보다 fragmentation + ONNX/Docling 모델 잔여 텐서 가설이 더 정합
- ISSUE-004 후속 안 5번 `INDEXER_MAX_JOBS` 자가 종료가 본 패턴 직접 차단함을 측정으로 뒷받침

### 운영 조치
- failed #189 reset: `status='pending', retry_count=0, started_at=NULL, finished_at=NULL, error=NULL` (다음 워커 재기동 시 자동 claim)
- 다른 잡 변경 없음

### 문서화
- 갱신: [wiki/issues/open/ISSUE-004-docling-parse-longtail.md](wiki/issues/open/ISSUE-004-docling-parse-longtail.md) — "추가 측정 (2026-04-27 → 04-28)" 섹션 + 보강 가설 + 해결 방향 5번 우선순위 강화
- 갱신: [wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md](wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md) — "가동 15시간 결과" 섹션, 이번 가동 내 누명 재발 없음 명시

---

## [2026-04-27] diagnose+ops | 메모리 가드 worker 누명 사건 + ISSUE-005 신설

### 트리거
사용자 보고 — "또 worker 실행 중 CPU·메모리 풀 났다, 메모리 올라와서 worker 죽었다고 보고받음". 색인 작업 중이었다고 알고 있음.

### 진단
- 현재 워커 프로세스 0건. `logs/indexer_worker.log` 4/26 19:13:49 이후 갱신 0 — 오늘 두 차례 떴던 워커 모두 **새 잡 처리 흔적 없이 idle 상태로 죽음**
- `data/diag/auto_kill_mem_guard_20260427T103519.log` + `auto_kill_guard_20260426T194024.log` — 시스템 used% > 50% 임계로 가드가 SIGTERM 발사 (10:21 PID 2755 / 10:35 PID 65063)
- `worker_rss_20260426T194024.log` 마지막 30초 결정적: 워커 RSS 7055MB → 평탄 또는 감소. **시스템 free%만 92→41%로 50pt 추락**. 폭주 주체는 다른 프로세스
- DB: `ingest_jobs` done 175 / pending·failed 0, `documents` done 63 — 인덱싱 폭주 가설 기각
- 진짜 범인 후보(미확인): 좀비 docling 자식, NextJS dev(TASK-019 Phase B), Streamlit/Uvicorn — 사후 점검 시 모두 종료 상태라 단서 부족

### 운영 조치
- worker 재기동: pid 79071, RSS 667MB로 폴링 시작 (19:08:32)
- 강화 모니터 가동: `/tmp/krag_monitor.py` (pid 79207)
  - 5초 간격, **매 줄 `flush + os.fsync`** — freeze 직전 마지막 상태 보존
  - used% ≥ 60% 임계 시 `ps aux`(RSS top 30) + `vm_stat` 전체 → `data/diag/snapshot_warn_used<NN>_<ts>.log` 즉시 fsync
  - **자동 SIGTERM 미적용** — 누명 방지, 관찰 전용
- 19:46 시점 38분 안정: RSS 667MB 평탄, used 9%, 임계 snapshot 미발생

### 문서화
- 신설: [wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md](wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md)
- 갱신: [index.md](index.md) Issues 표

### 후속 (코드, 미합의)
- 가드 로직 개선: 시스템 used% 임계 시 worker 고정 SIGTERM이 아니라 RSS top 식별
- pid 트리(자식 포함) SIGTERM
- 다음 발생 시 모니터 snapshot으로 범인 식별 후 본격 대응

---

## [2026-04-26] diagnose+docs | bulk 175잡 freeze 진단 + ISSUE-004 신설

### 트리거
사용자 보고 — 0.23.3 fix(EMBED_BATCH=64) 이후에도 bulk 색인 중 시스템 freeze 재발. 처음 몇 건은 정상이다 갑자기 멈춤.

### 진단 (라이브 측정)
워커 PID·RSS·CPU·threads + DB 잡 카운트를 5~15초 폴러로 추적하면서 실제 freeze 트리거를 식별.

- **freeze 진짜 원인**: 워커 동시 기동. 단일 잡이 RSS 5~12GB 사용하므로 워커 2개면 합산 14~16GB → swap 폭주
- **단일 워커 검증**: 2755 PID로 175잡 100% 처리 (실제 47잡 파싱 + hash 중복 87 + 이전 누적 24, sys_free 90~97% 유지)
- **Docling 파싱이 단일 잡 비용의 90~96%** 차지 — 청크 수 무관, 페이지·테이블 그래프 비용
- **stale `in_progress` 누수**: SIGKILL로 끊긴 잡(39, 40)이 영원히 잠김 — `FOR UPDATE SKIP LOCKED`로 다른 워커도 안 잡음
- **`_save_markdown` 이중 파싱 결함** 식별 — `markdown_dir` 켜져 있으면 같은 PDF Docling 두 번 호출

### 문서화
- 신설: [wiki/issues/open/ISSUE-004-docling-parse-longtail.md](wiki/issues/open/ISSUE-004-docling-parse-longtail.md) — Docling 파싱 long-tail 후순위
- 갱신: [wiki/issues/resolved/ISSUE-003](wiki/issues/resolved/ISSUE-003-ingest-memory-spike-system-freeze.md) "후속 발견" 섹션 — 워커 동시 기동, 이중 파싱, stale 누수 4건 식별
- 갱신: [wiki/features/ingestion.md](wiki/features/ingestion.md) — "워커 1개 권장" 섹션 + 단일 잡 메모리 측정값 표 + 트러블슈팅 표 갱신
- 갱신: [wiki/troubleshooting/common.md](wiki/troubleshooting/common.md) — "bulk 인덱싱 중 macOS freeze (워커 동시 기동)" + "stale `in_progress` 잡 수동 reset" 레시피 2개

### 후속 (코드, 미합의)
- P0: 워커 동시 기동 가드(pidfile/Postgres advisory lock) + stale in_progress 자동 reset
- P1: `_save_markdown` 이중 파싱 제거
- P2: `INDEXER_MAX_JOBS` env 도입 (누적형 안전망)
- P3: ISSUE-004 (별도 검토)

### 운영 조치
- failed 15 + stale 2 = 17건 모두 `pending`으로 reset → 워커 자동 재처리 (대부분 hash 중복으로 즉시 done 예상)

---

## [2026-04-26] impl+ops | 잡 탭 상태 필터 + stale 잡 #26 reset (0.23.4)

### 작업
- **Streamlit 잡 탭 상태 필터 추가** ([ui/app.py](../ui/app.py) `TAB_JOBS`):
  - `st.multiselect("상태 필터", …)` — pending/in_progress/done/failed/cancelled 다중 선택
  - 라벨에 카운트 표시(`⚙️ 진행중 (2)`), 기본값은 큐에 1건이라도 있는 상태만(전부 0이면 전체 폴백)
  - 표 캡션 `필터 매칭 N / 전체 M` 추가
  - `STATUS_BADGE` dict를 표 루프 내부 → 잡 탭 상단으로 hoist해 필터·표가 공유
  - **Streamlit 동결 정책의 1건 한정 해제** — 메모리 `feedback_streamlit_no_edit`의 "사용자 명시 지시" 조건 충족(이번 1건만, 정책 자체는 유지)
- **stale 잡 #26 reset** (`도메인_주도_설계_구현과_핵심_개념_익히기`, 109MB PDF):
  - 발견 경위: 사용자가 잡 목록에서 1시간 넘게 in_progress인 항목 지적
  - 진단: started_at = 2026-04-26 17:36:04 KST = 현재 워커(18:39 시작)보다 1시간 전. 직전 워커가 claim 후 사망 → status만 in_progress로 잔존. 워커는 `SKIP LOCKED` + `status='pending'` 필터라 자동 회수 불가
  - 사망 정황: ISSUE-003 freeze 시간대와 일치(EMBED_BATCH 미적용 코드로 109MB+이미지 PDF 시도 중 메모리 폭발 가능성)
  - 처리: Qdrant 청크 0건·Postgres documents 행 0건 확인 → `UPDATE ingest_jobs SET status='pending', started_at=NULL, finished_at=NULL, error=NULL WHERE id=26`. 잔재 청소 불필요(부분 색인 전 사망)
  - 후속 처리: 0.23.3 EMBED_BATCH=64 적용된 현 워커가 jobs 36 종료 후 enqueued_at ASC 최선두인 #26을 자동 claim 예정

### 영향받은 페이지
- changelog.md (0.23.4)
- ui/app.py — Streamlit 잡 탭 (이번 1건 한정 동결 해제)

### 큐 상태 (after reset)
- pending 99 / in_progress 1 / done 19 / failed 15

### 후속 (착수 안 함)
- 워커 stale-recovery 자동화: `heartbeat_at` 컬럼 + 워커 진입 시 `started_at < NOW() - INTERVAL '30 min'` 자동 reset. 현재 수동 SQL 의존이라 같은 incident 시 또 손이 가야 함

---

## [2026-04-26] fix | ISSUE-003 — 인덱싱 메모리 폭발로 시스템 freeze (0.23.3)

### 작업
- 사용자 보고: bulk 인덱싱 중 시스템 멈춤. 원인 추적
- 원인: [packages/vectorstore/qdrant_store.py](../packages/vectorstore/qdrant_store.py) `QdrantDocumentStore.add_documents` (hybrid 분기)가 모든 청크의 텍스트/dense/sparse/PointStruct를 **단일 호출에서 메모리에 동시 보유**. upsert만 256배치, embed/PointStruct는 미배치. 수천 청크 문서에서 GB 단위 RSS 폭증 → 스왑 폭주 → freeze
- 수정: `EMBED_BATCH_SIZE = 64` 도입, `add_documents` hybrid 분기를 64청크 단위 `for` 루프로 재구성 — texts/dense_vecs/sparse_vecs/points 모두 루프 종료 시 GC. 한 시점 메모리 ≈ 64 × (벡터 + 텍스트)로 캡
- 위키: ISSUE-003(resolved) 신규, [features/ingestion.md](features/ingestion.md) 트러블슈팅 행 + "메모리 안전성 노트" 섹션 추가, 출처에 qdrant_store.py / ISSUE-003 추가

### 영향받은 페이지
- wiki/issues/resolved/ISSUE-003-ingest-memory-spike-system-freeze.md (신규)
- wiki/features/ingestion.md
- index.md
- changelog.md (0.23.3)

### 후속 (착수 안 함)
- `scripts/bulk_ingest.py` 의 `read_bytes()` 큰 파일 통째 로드, `apps/routers/ingest.py` 의 `await file.read()` — 같은 메모리 패턴이지만 이번 freeze의 원인은 아님. 추후 streaming hash/upload로 개선 후보

---

## [2026-04-26] doc | features/ingestion.md 신설 — bulk_ingest.py 사용법

### 작업
- `wiki/features/ingestion.md` 신규 작성 — `scripts/bulk_ingest.py` 옵션·모드(HTTP / `--via-queue`)·결과 카운터·트러블슈팅 정리
- `index.md`: Features 섹션 ingestion.md 항목을 미작성 → active 로 갱신, 총 페이지 수 26 → 27
- 부수: `packages/jobs/queue.py` 의 `error[:2000]` → `error[:4000]` (ingest_jobs.error 상한 확장) — ingestion.md 트러블슈팅에서 참조

### 영향받은 페이지
- wiki/features/ingestion.md (신규)
- index.md

---

## [2026-04-26] impl | TASK-019 Phase A — NextJS 사용자 UI 셋업 + Phase 1 라이브 검증 (0.23.2)

### 작업
- **Phase 1 라이브 검증** (0.23.0 + 0.23.1 + 마이그레이션 후속):
  - 워커 재기동(PID 65094, 새 코드) → init에서 hybrid collection 자동 재생성 (이전 fresh start 후속)
  - 7권 도서 nested 분류 적용 (3890 청크) — `category_filter` 5개(ai/ml, web/frontend, software/architecture, programming/systems, other) 모두 라이브 매칭 확인
  - 추가 2권(`더_이상한_수학책` 219s, `상대적이며_절대적인_지식의_백과사전` 168s) bulk_ingest → 신규 코드(0.23.1+)로 자동 nested 저장 검증

- **Phase A — NextJS web/ 셋업**:
  - `pnpm create next-app web` (Next 16.2.4, React 19.2, TypeScript 5.9 strict, Tailwind 4 + Turbopack, App Router, no-src-dir, import-alias `@/*`)
  - Note: stack.md 합의(Next 15 + Tailwind 3.4)와 다름 — latest로 진행. Next 16은 `middleware.ts` deprecated → `proxy.ts` 컨벤션
  - `pnpm dlx shadcn@latest init -d --force` 후 14개 컴포넌트 일괄 추가
  - 패키지 추가:
    - 런타임: `@clerk/nextjs@7.2`, `@tanstack/react-query@5.100`, `nuqs@2`, `react-markdown@10` + `remark-gfm@4` + `rehype-highlight@7`, `date-fns@4`
    - dev: `openapi-typescript@7`, `openapi-fetch`
  - 파일:
    - `app/layout.tsx` — `<ClerkProvider>` + `<Providers>`(QueryClient + TooltipProvider + Toaster) 래핑, lang="ko"
    - `app/providers.tsx` — TanStack Query (`staleTime=30s`, `refetchOnFocus=false`, `retry=1`) + shadcn TooltipProvider + sonner Toaster
    - `app/page.tsx` — Phase A placeholder (UserButton만)
    - `app/sign-in/[[...rest]]/page.tsx`, `app/sign-up/[[...rest]]/page.tsx` — Clerk catch-all
    - `proxy.ts` — Clerk `clerkMiddleware` + `createRouteMatcher`, `/sign-in(.*)`/`/sign-up(.*)`만 공개
    - `lib/api/client.ts` — `useApiClient()` hook이 Clerk `getToken()` → `Authorization: Bearer ...` 자동 첨부 (FastAPI `AuthMiddleware`와 짝). openapi-fetch 위에 interceptor
    - `.env.local.example` (commit) — Clerk 키 3종 + `NEXT_PUBLIC_API_BASE_URL` 안내
    - `.env.local` (gitignored) — 사용자가 직접 키 입력
    - `.gitignore` — `!.env*.example` 예외 추가

### 검증
- `pnpm tsc --noEmit` clean
- `pnpm dev` → 195~249ms ready (Next 16 Turbopack)
- `/sign-in` HTTP 200 (24KB SignIn 컴포넌트 렌더)
- `/` HTTP 307 → `/sign-in?redirect_url=...` (Clerk 보호 자동 리다이렉트)
- `Environments: .env.local` 로드 확인
- 사용자가 Clerk publishable+secret key 입력 → dev 서버 재기동 후 Clerk SignIn UI 정상 노출

### Phase B 작업 (대기)
- AppShell — 상단 카테고리 칩 + 좌측 사이드바(＋새 대화·자기 user_id 대화 목록·하단 📚 도서관) + 메인(활성 스코프 배지 + 본문)
- `/chat` — 메시지 히스토리 + 소스 expander + 후속 질문 배지 + empty state(요약·카테고리 분포·주제 칩·예시·최근 문서) + doc/category filter
- `/library` — 검색·형식·카테고리 필터 + 카드 그리드 + 그룹핑(기타 마지막) + 카드 상세 토글
- 사이드바 대화 목록 — `GET /conversations` (자기 user_id만), 세션 클릭 라우팅, hover 삭제
- 활성 스코프 배지 — 우선순위 series > category > doc, 한 번에 하나
- URL state 라우팅 (nuqs) — 도서관 ↔ 채팅 자동 이동
- Playwright 회귀 검증 + 모바일 viewport
- `AUTH_ENABLED=true` 백엔드 전환 + `CLERK_JWKS_URL` 채움
- changelog 0.24.0 + 위키 8개 페이지 갱신 + ADR-030 보강 + 메모리 stack.md 동기화

### 위키
- `changelog.md` 0.23.2 항목
- `wiki/architecture/stack.md` 갱신 — 실제 설치 버전 반영 (Next 16, Tailwind 4, Clerk 7, middleware → proxy)

---

## [2026-04-26] ops+fix | 0.23.1 마이그레이션 후속 — flat cleanup 비활성 (Qdrant API 한계) + 7건 nested 적용 검증

### 작업
- 0.23.0 코드(워커 PID 45535)가 5건 인덱싱 중인 상태 — flat key로 분류 저장 → 워커 재기동 후 마이그레이션 진행
- 워커 재기동 (새 PID 65094) → init에서 새 코드 로드
- `scripts/migrate_classification_payload_to_nested.py --dry-run` → 7 doc, 3890 청크 영향 확인
- `--cleanup-flat` 실행 → set_payload(nested) + delete_payload(flat) 둘 다 success 보고, 그러나 결과 검증 시 nested 0건 ?!

### 진단 — Qdrant API 한계 발견
- `delete_payload(keys=["metadata.category"])` 가 dot-notation을 **nested 경로로 해석**해 `payload.metadata.category` 삭제. flat top-level literal key는 안 지워짐
- 결과: 마이그레이션이 nested 추가 → 즉시 nested 삭제 → 0 nested, flat 잔존 (역효과)
- 직접 set_payload(key='metadata') 호출만 하면 nested 정상 추가됨 (검증)
- flat top-level literal key 'metadata.category' 안전 삭제는 collection drop + 재인덱싱 또는 청크별 overwrite_payload만 가능 (Qdrant API 자체 한계)

### 수정 — `migrate_classification_payload_to_nested.py`
- `--cleanup-flat` 옵션 동작 비활성: 호출되어도 경고 로그만 출력하고 no-op
- nested 추가만 수행 (flat은 cruft로 잔존, 디스크 낭비 작음, Filter는 nested 기준이라 검색 동작 정상)
- 함수 docstring에 한계 명시 + 안전한 flat 정리 방법 안내 (collection drop or overwrite_payload)

### 적용 결과
- nested 7/7 적용 완료 (3890 청크 모두 nested+flat 둘 다 가짐)
- `category_filter` 라이브 검증: 5개 카테고리(ai/ml, web/frontend, software/architecture, programming/systems, other) 모두 정확히 매칭
- TASK-019 Phase 2 NextJS 카테고리 칩 전제조건 충족

### 후속
- 정리가 정말 필요하면 collection drop + 재인덱싱 (~20분, 7권). 현재는 flat cruft 잔존 결정 (크기 작고 영향 없음)
- Qdrant API에 dot-literal key 명시 삭제 기능 요청 별건

---

## [2026-04-26] fix | 0.23.1 — `set_classification_payload` flat key → nested (ADR-025 잠재 버그)

### 진단
- TASK-019 Phase 1 라이브 검증 시 `category_filter='ai/ml'` 검색이 0건 매칭 발견
- doc_filter는 정상 → category 필터 자체의 데이터 모델 문제로 좁혀짐
- Qdrant scroll로 raw payload 확인:
  ```
  payload keys: ['page_content', 'metadata', 'metadata.doc_type', 'metadata.category', 'metadata.tags']
  metadata.category (nested 안): None
  payload['metadata.category'] (flat top-level): 'ai/ml'
  ```
- ADR-025 `set_classification_payload`가 `set_payload(payload={"metadata.category": "ai/ml"}, ...)` 형태로 호출 → Qdrant는 dict 키를 그대로 top-level 추가. dot-notation을 nested로 해석하지 않음. 반면 Filter `key="metadata.category"` 는 nested 경로 해석 → mismatch
- ADR-025 도입(2026-04-25) 후 카테고리 한정 검색이 실제로 사용되지 않아 표면화 안 됐던 잠재 버그

### 수정
- `packages/vectorstore/qdrant_store.py` `set_classification_payload`:
  - `set_payload(payload={"category":...}, key="metadata", ...)` 형태 — Qdrant가 nested merge로 처리
  - dict 키 `"metadata.category"` → `"category"` 등으로 단순화
- `scripts/migrate_classification_payload_to_nested.py` 신규:
  - 영향: ADR-025부터 작성된 모든 분류 payload
  - PostgreSQL `documents` 테이블의 doc_type/category/tags를 진실 원천으로 잡아 영향받은 doc_id 청크에 nested set_payload 재적용
  - `--dry-run`: 영향 범위만 출력
  - `--cleanup-flat`: 기존 flat key를 delete_payload로 정리 (기본 false — nested 추가만)
  - flat key 분포·영향 doc 수·적용 카운트 보고

### 적용 절차
1. 워커 재기동 (현재 가동 중인 워커는 OLD code의 set_classification_payload 그대로 사용 — 새 잡도 flat key 만듦)
2. `scripts/migrate_classification_payload_to_nested.py --dry-run` 영향 범위 확인
3. `scripts/migrate_classification_payload_to_nested.py --cleanup-flat` 실행 (nested 추가 + flat 정리)
4. category_filter 라이브 검증

### TASK-019 Phase 2 영향
Phase 2 NextJS의 상단 카테고리 칩·도서관 카테고리 필터·`category_filter` URL 라우팅이 이 fix 없이는 항상 0건. Phase 2 진입 전제조건 충족.

### 위키
- `changelog.md` 0.23.1 항목

---

## [2026-04-26] ops | fresh start 정리 후 워커 collection 캐시 mismatch — 워커 재기동 + stale 잡 reset

### 작업
- 사용자 지시로 인덱싱 데이터 전부 초기화 (TRUNCATE documents/ingest_jobs/conversations/messages CASCADE + Qdrant collection drop + data/uploads/markdown/eval_runs 정리)
- `bulk_ingest --dir /Volumes/shared/ingaged --via-queue` 재실행 (PDF 2건 enqueue: 가상_면접·읽기_좋은_코드)
- 워커가 매 retry마다 같은 위치에서 실패 — `404 Not Found: Collection 'documents' doesn't exist!`
- 진단: 워커(PID 45535, 20시간 가동)가 부팅 시점의 `_ensure_collection()` 결과를 캐시. 외부 collection drop 후 모든 upsert가 404. retry 0→1→2→3 모두 같은 원인
- 복구:
  1. 워커 재기동 (새 PID 63036) → init에서 collection 재생성 (hybrid, points=0)
  2. retry 3으로 stuck `in_progress`였던 잡 #1을 SQL로 reset (`status='pending', retry_count=0, started_at=NULL`)
  3. 새 워커가 polling cycle에서 #2 처리 → 끝난 후 #1 처리

### 결과
| 잡 | 책 | 처리 시간 |
|---|---|---|
| #2 | 읽기_좋은_코드가_좋은_코드다 | 178초 (~3분) |
| #1 | 가상_면접_사례로_배우는_대규모_시스템_설계_기초 | finished_at 01:53:15 (started_at은 reset로 NULL되어 duration 측정 불가) |

총 2건 done, 0 failed.

### 부수 데이터 이상
- 잡 #1의 `started_at`이 NULL — 수동 reset SQL이 컬럼을 NULL로 되돌렸고, 새 워커는 claim 시 started_at을 다시 set하지만 `mark_done`에서 finished_at만 update. 결과적으로 duration 산정 불가 (운영 영향 없음, 단순 메트릭 누락)
- 다음에 동일 reset 시 `started_at`은 NULL로 두지 말고 워커가 다시 set하도록 두는 게 깔끔

### 별건 / 후속
- ADR-028 알려진 한계 "stale `in_progress` 자동 회수 미구현"의 본 케이스 manifestation. housekeeping 잡(`started_at < NOW() - 1h` → pending 복귀) 도입하면 이 종류 수동 SQL 불필요
- `error[:2000]` 슬라이스 버그도 동일 패턴 노출 — traceback 끝 잘려 진단 첫 사이클에 정확한 원인(404)이 안 보임. `error[-2000:]` 또는 컬럼 한도 확대 필요
- **운영 절차 표준화** — `wiki/troubleshooting/common.md`에 "Qdrant collection drop 후 잡이 매 retry마다 404로 실패" 신규 섹션 추가. 정리 절차 6단계(enqueue 중지·TRUNCATE·collection drop·파일 정리·**워커 재기동**·uvicorn 재기동)를 명시

### Streamlit 잡 탭 — 한정 동결 해제 (사용자 명시)
- 사용자가 "enqueued만 보이고 종료일자가 없다"는 UX 마찰 지적 → ui/app.py의 잡 탭 표 한정으로 동결 해제
- 컬럼 6 → 9: `ID │ 상태 │ 제목 │ retry │ enqueued │ started │ finished │ duration │ doc_id`
- duration 동작: in_progress → 라이브 경과(`now - started`), done/failed → `finished - started`, 그 외 → "—"
- 60초 미만 `Ns`, 1시간 미만 `MmSSs`, 그 이상 `HhMMm`
- 잡 탭 외 다른 Streamlit 영역은 동결 정책 그대로 (메모리 `feedback_streamlit_no_edit` 유지)

### 위키 갱신
- `wiki/troubleshooting/common.md` — "Qdrant collection drop 후 잡이 매 retry마다 404로 실패" 섹션 신규 (원인·해결·재발 방지 절차·관련 ADR 링크)
- `wiki/troubleshooting/common.md` 헤더 마지막 업데이트 2026-04-22 → 2026-04-26

---

## [2026-04-26] impl | TASK-019 Phase 1 — 백엔드 토대 (ADR-030, 0.23.0)

### 코드 변경
- `apps/middleware/auth.py` (신규) — Origin 분기 인증 미들웨어. `_is_lan_host()` (RFC1918 + loopback + IPv6) + `AuthMiddleware.dispatch()` (JWT 헤더 / LAN origin / 외부 origin 3분기). EXEMPT_PATHS = `/health`, `/docs`, `/redoc`, `/openapi.json`. `AUTH_ENABLED=false`(기본) 시 모든 요청 admin 통과
- `apps/middleware/__init__.py` (신규) — 패키지 마커
- `apps/main.py` — CORSMiddleware (`localhost:3000` + `127.0.0.1:3000`) + AuthMiddleware 등록
- `apps/config.py` — `auth_enabled`(false), `clerk_jwks_url`, `clerk_issuer`, `cors_origins` 4개 신설
- `apps/schemas/query.py` — `QueryRequest.category_filter: Optional[str]`
- `apps/routers/query.py` — `Request` 의존성으로 `user_id` 추출, `category_filter` 파이프라인 통과, LangSmith 메타·태그(`session:`, `user:`)
- `apps/routers/conversations.py` — 4개 엔드포인트 모두 `Request` 의존성 + `user_id` 통과 + owner 검증 (다른 user 세션 GET/DELETE 시 404)
- `packages/rag/pipeline.py` — `category_filter` 인자 + 우선순위 분기(`doc_filter` 우선, 동시 지정 시 `category_filter` 무시) + LangSmith 태그(`category_filter:<value>`) 메타(`category_filter`)
- `packages/rag/retriever.py` — `category` 인자 통과
- `packages/vectorstore/qdrant_store.py` — `similarity_search_with_score(category=...)` + `payload.metadata.category` Filter 절. doc_id와 동시 지정 시 둘 다 must
- `packages/db/models.py` — `ConversationRecord.user_id String NOT NULL index=True`. 모델 default 미지정 (DB DEFAULT 'admin'은 마이그레이션 백필 전용)
- `packages/db/conversation_repository.py` — 6개 함수 모두 `user_id` 인자 추가. `get_conversation`/`get_or_create_conversation`/`list_conversations`/`delete_conversation`은 owner 필터, `create_conversation`은 INSERT 시 명시 주입
- `packages/db/connection.py` — sentinel `0004_add_conversations_user_id.sql`: `("column", "conversations", "user_id")` 추가. **부수 fix: LOCK_ID 9바이트 → 8바이트** (`b"knowledg"` = 0x6B6E6F776C656467, signed bigint 적합)
- `packages/db/migrations/0004_add_conversations_user_id.sql` (신규) — `ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'admin'` + 인덱스

### 마이그레이션 적용 결과 (스모크)
- 0004 적용 — `conversations.user_id` 컬럼 추가, `ix_conversations_user_id` 생성
- 기존 29개 행 모두 `user_id='admin'` 자동 백필 (DEFAULT 정책)
- LOCK_ID 패치로 advisory lock 정상 획득 (이전엔 9바이트 ASCII가 `pg_advisory_xact_lock(bigint)` 한도 초과)

### 격리 검증 (직접 SQLAlchemy 세션)
| 케이스 | 기대 | 결과 |
|---|---|---|
| admin 새 세션 생성 | user_id='admin' | ✅ |
| clerk_user_abc 새 세션 생성 | user_id='clerk_user_abc' | ✅ |
| admin이 자기 세션 조회 | 성공 | ✅ |
| admin이 clerk 세션 조회 | None (격리) | ✅ |
| admin 목록 카운트 | admin user_id만 (29 + 1 임시 = 30) | ✅ |
| clerk 목록 카운트 | 1 | ✅ |
| admin이 clerk 세션 삭제 시도 | False (차단) | ✅ |
| 정리 후 admin 카운트 | 29 (원상복구) | ✅ |

### 부팅 검증
- `from apps.main import app` OK
- 미들웨어 체인: CORSMiddleware → AuthMiddleware (등록 순)
- LAN host 분기 단위 테스트: 127.0.0.1·localhost·192.168.x·10.x·172.16.x·::1 모두 LAN, 8.8.8.8·example.com 외부 인식

### 부수 발견 (운영 노트)
- 현재 실행 중인 uvicorn(PID 45489)은 옛 코드 — 새 미들웨어/repository 미적용. DB DEFAULT 'admin' 정책 덕분에 옛 코드도 INSERT 누락 시 자동 백필돼 운영 호환성 유지. 재시작 시점은 사용자 결정
- 인덱서 워커(PID 45535)는 conversations 미접근이라 재시작 불필요. bulk 인덱싱 진행에 영향 0

### 위키
- `wiki/architecture/decisions.md` ADR-030 추가 (사용자/관리자 UI 분리, Clerk 채택 + 인증 공급자 비교, Origin 분기 전략)
- `changelog.md` 0.23.0 항목

### Phase 2 진입 조건
- `.env`에 `AUTH_ENABLED=true`, `CLERK_JWKS_URL`, `CLERK_ISSUER` 추가
- `web/.env.local`에 `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` 추가
- uvicorn 재시작
- NextJS 프로젝트 신설(`web/`) → shadcn/ui + TanStack Query + Clerk + AppShell + 페이지 구현

---

## [2026-04-25] doc | TASK-019 착수 전 기술 스펙 확정 — `wiki/architecture/stack.md` 신설

### 합의된 NextJS 기술 스펙
- 프레임워크: Next.js 15.x (App Router) + React 19 + TypeScript 5 strict, pnpm 9
- UI: shadcn/ui (Radix + Tailwind 3.4) + lucide-react + sonner + tailwindcss-animate
- 라우팅·상태: App Router native + nuqs(URL state) + TanStack Query v5 + Zustand v4(필요 시)
- API·인증: openapi-typescript + openapi-fetch + @clerk/nextjs v5 (이메일 OTP, 비번/소셜 X)
- 콘텐츠: react-markdown + remark-gfm + rehype-highlight
- 개발: ESLint + Prettier 3 (+ tailwindcss plugin) + Playwright 1.48+
- 의도적 제외 (Phase 1): 답변 스트리밍, 다크모드, 다국어, PWA, Sentry, Analytics, 리치 에디터, Vitest, Storybook
- 호환 이슈 발견 시 Next 14.2 + React 18로 다운그레이드 가능 (비파괴적 결정)

### 갱신
- `wiki/architecture/stack.md` 신설 (백엔드 + NextJS + Streamlit + 인증 정책 통합)
- `wiki/index.md` — Architecture 섹션의 stack.md 등록(미작성 → active), 마지막 업데이트 갱신, 페이지 수 25→26
- `wiki/overview.md` — 상단 관련 페이지에서 `stack.md _(미작성)_` 마커 제거

### 다음 단계
- Phase 1 진입 — ADR-030 작성 → category_filter 백엔드 추가 → conversations.user_id 마이그레이션 → 인증 미들웨어 → CORS → 스모크 테스트

---

## [2026-04-25] queue | TASK-019 — 사용자 UI NextJS 분리 + Clerk 인증 (최우선)

### 합의 사항
- 사용자 인지된 문제: Streamlit `st.tabs`가 프로그램적 탭 전환 미지원 → 도서관·랜딩의 자동 이동 4 트리거가 토스트 안내만 남기고 멈춤. 모바일 UX 한계(ISSUE-001/002). 사용자/관리자 화면이 한 앱에 섞여 외부 공개·인증 도입 모두 어려움. 인증 없음 → 사용자별 데이터 격리 불가
- 해결 방향: 사용자 측(채팅·도서관·대화)을 NextJS thin client로 분리, Clerk 인증 도입. 관리자 측(문서·잡·시스템·평가)은 Streamlit 잔류·동결. LLM·RAG는 모두 FastAPI 단일 진실
- 우선순위: **최우선** — TASK-018 다음 자리, 다른 후순위 큐(TASK-012/013/020)보다 먼저 진행
- ADR: 다음 가용 ADR-030 예약 (착수 시 작성)

### 핵심 결정
- **분리 정책**: 사용자 = NextJS / 관리자 = Streamlit. 동일 FastAPI 백엔드 공유. 포트 분리(8501 admin / 3000 user / 8000 API)
- **인증**: NextJS만 Clerk(`@clerk/nextjs` 미들웨어). 이메일 OTP만(비번 X, 소셜 X). Free 플랜
- **인증 분리 전략 (Origin 분기)**:
  - JWT 헤더 있음 → Clerk 검증 → `user_id = clerk.user_id`
  - 헤더 없음 + LAN/localhost origin → `user_id = 'admin'` 자동 (Streamlit + 로컬 스크립트 호환)
  - 헤더 없음 + 외부 origin → 401
- **데이터 격리**: `conversations.user_id TEXT NOT NULL`, sentinel idempotent 마이그레이션. 기존 행 `'admin'` 백필. 사용자 A → B 세션 GET 시 404
- **역할 분리 없음**: 모든 로그인 사용자 동등. Clerk Organizations·publicMetadata role 미사용
- **익명 사용 불허**: 로그인 필수
- **Streamlit 측 모든 수정 동결**: 사용자 명시 지시까지. NextJS 분리 작업에서 ui/app.py·관련 자산 일체 미수정 (메모리 `feedback_streamlit_no_edit`)

### 보류 묶음 영향 (부분 해제)
2026-04-22 보류된 5개 항목 묶음 중 **#4 "앱 내 인증"만 부분 해제** (Clerk 도입). 나머지 4개는 보류 유지:
- ISSUE-001 (모바일 업로드)
- 관리자 UI 2단계
- HTTPS 배포
- 관리자 전용 UI 버튼

### 레이아웃·페이지
- AppShell: 상단 카테고리 칩(라벨만, NULL→"기타") + 좌측 사이드바(데스크톱 펼침·모바일 drawer 닫힘, ＋새 대화·자기 user_id 대화 목록·하단 📚 도서관) + 메인(활성 스코프 배지 + 본문)
- 페이지: `/chat`, `/library` (대화는 사이드바로 흡수, `/conversations` 라우트 없음)
- 활성 스코프 우선순위: series > category > doc, 한 번에 하나
- 세션 제목: 첫 질문 일부 자동 사용 (현 정책 유지)

### 외부 의존·키 (사전 합의 사항)
- Clerk 계정 (사용자 직접 생성) — Free 플랜 10k MAU/월 무료
- API 키 2~3개 (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, 선택 `CLERK_WEBHOOK_SECRET`)
- 신규 패키지: `@clerk/nextjs`, NextJS 14/15, shadcn/ui, TanStack Query, openapi-typescript

### 의도적 제외
- Streamlit 측 모든 수정 (동결 정책)
- HTTPS 배포·도메인 (TASK-012과 묶이는 별건)
- 관리자 UI 2단계, ISSUE-001, 관리자 UI 버튼 (보류 묶음 잔류)
- 사용자/관리자 역할 분리 (Organizations, role metadata)
- 비밀번호 로그인, 소셜 로그인 (Phase 1)
- 'admin' 사용자에 NextJS UI 접근 (Streamlit 대화는 Streamlit에서만)
- 답변 스트리밍 SSE, PWA, 다국어 (별건 후속)
- 시리즈 카드·시리즈 스코프 (TASK-020 완료 시 NextJS에 추가)
- 익명 사용, B2B/SSO/SAML

### 산정
**7~9일 (집중, 중앙값 7~8일)** — Clerk 통합 + Origin 분기 미들웨어 + user_id 마이그레이션 + 보호 라우트 +1.5~2일 합산

### 회귀 전략
- Streamlit 8501 그대로 운영 — NextJS 빌드 실패 시 즉시 회귀
- `category_filter` default `None` → 후방호환 100%
- 인증 미들웨어 `AUTH_ENABLED=false` 토글로 도입 시점 분리
- conversations down 마이그레이션 별도 SQL

### 반영
- `roadmap.md`: 실행 큐 TASK-018 다음에 `🆕 TASK-019 (최우선)` 삽입, 진행표·하단 상세 섹션(배경·아키텍처·범위·의도적 제외·완료 기준·회귀 전략·리스크·외부 의존)
- `overview.md`: "다음 (예정)" 표 최상단에 TASK-019, 보류 묶음 표를 "부분 해제 후 잔여 4개"로 업데이트, "Streamlit 측 모든 수정" 동결 행 추가
- `log.md`: 이 엔트리
- 메모리 `feedback_streamlit_no_edit.md` 신설 + `MEMORY.md` 인덱스 추가

### 다음 단계
- 별도 사용자 "착수" 지시 시 구현 진입 (메모리 `feedback_task_start` 규칙: 등록까지만, 구현은 별도 턴)
- 착수 시 ADR-030 작성 → Clerk 발급 가이드 → `web/` 신설 → FastAPI 미들웨어 → 마이그레이션 → 페이지 구현 → Playwright 검증

---

## [2026-04-25] queue | TASK-020 — Series/묶음 문서 (Option D, 후순위)

### 합의 사항
- 사용자 인지된 문제: 같은 책이 30챕터처럼 여러 파일로 쪼개져 인덱싱되면 도서관 카드가 흩어지고 "이 책에 대해 묻기"가 1챕터에만 한정됨
- 해결 방향: Series/묶음을 1급 시민으로 도입(Option A 스키마) + 색인 시점 자동 묶기(휴리스틱, 신뢰도 임계값으로 분기) + 관리자 사후 검수(Confirm/Detach)
- 우선순위: 후순위 큐잉. TASK-012/013과 동일 패턴, 사용자 명시적 "착수" 지시 시 진행
- ADR: 다음 가용 ADR-029 예약 (착수 시 작성)

### 핵심 결정
- **Option D 채택** — A(스키마)+B(태그)+C(휴리스틱) 비교 후, A 스키마 + 자동 묶기 + 검수 하이브리드가 사용자 부담 0 + 1급 시민 + 정정 가능을 모두 만족
- **자동 묶기 시점**: 색인 후처리 (indexer_worker BackgroundTasks 체인의 summary→classify→**series_match**)
- **신뢰도 임계값**:
  - High (동일 source 폴더 + 공통 prefix ≥ 8자 + 동일 doc_type + 숫자 시퀀스) → `auto_attached`로 자동 묶기
  - Medium → `suggested`로 검수 큐만 등록 (`series_id NULL` 유지)
  - Low → 처리 없음
- **재바인딩 회피**: `series_match_status=rejected` 마킹된 문서는 동일 휴리스틱이 다시 자동 묶기 시도 안 함 (관리자 의사 존중)
- **사용자 측 시리즈 편집은 admin 전용** — NextJS 사용자 UI는 read-only

### 데이터 모델 (착수 시 ADR-029로 확정)
- `series` 테이블 신설(`series_id`, `title`, `description`, `cover_doc_id`, `series_type`, `created_at`)
- `documents`에 4컬럼 추가: `series_id`(FK), `volume_number`, `volume_title`, `series_match_status`(none/auto_attached/suggested/confirmed/rejected)
- Qdrant payload에 `series_id`, `series_title` 추가 (재인덱싱 회피, 부분 업데이트 + keyword index)

### 의도적 제외
- 자동 제안 LLM 보조 (휴리스틱이 부족하면 별건 합의)
- 시리즈와 카테고리·doc 동시 스코프 활성 (단순화: series > category > doc 우선순위, 한 번에 하나)
- 시리즈 자체에 별도 카테고리·태그·요약 (멤버 데이터 집계 표면화만)
- 무한 재바인딩 (rejected 기억으로 차단)

### 완료 기준
- 마이그레이션 idempotent(advisory lock + sentinel) 통과
- 새 문서 인덱싱 시 series_match 자동 실행 (실패 격리 — 인덱싱은 성공)
- High 신뢰도면 `auto_attached`로 자동 채워진 채 done
- `/query.series_filter` 적용 시 시리즈 멤버만 검색됨 (vector·hybrid 양 경로)
- Streamlit 검수 페이지: auto_attached + suggested 두 큐 + Confirm/Detach
- detach된 문서는 동일 휴리스틱이 재바인딩 시도하지 않음

### 회귀 전략
- `series_id IS NULL` 기존 동작 100% 보존
- `SERIES_ENABLED=true|false` 토글로 도입 시점 분리
- down 마이그레이션으로 rollback 가능

### 반영
- `roadmap.md`: 실행 큐 마지막에 `🕐 TASK-020`, 진행표 후순위 행 추가, 하단 상세 섹션(배경·아키텍처·범위·의도적 제외·완료 기준·회귀 전략·리스크) 작성
- `overview.md`: 다음 할 일 표에 TASK-020 행 추가
- `log.md`: 이 엔트리

### 다음 단계
- 별도 사용자 지시 시까지 자동 진행 금지 (TASK-012/013과 동일 큐 정책)
- TASK-019 (NextJS 사용자 UI 전환)는 별도 진행. NextJS의 시리즈 카드·시리즈 스코프 배지는 TASK-020 완료 시점에 NextJS에 추가하는 흐름 (NextJS는 series_id NULL 가정으로 우선 동작 가능)

---

## [2026-04-25] ops | 32MiB 한도 패치 후속 — 고아 청크 정리 + failed 잡 15건 reset

### 작업
- Qdrant 고아 청크 정리 — 검증용 단건 동기 ingest(`scripts/debug_single_ingest.py`)가 documents/ingest_jobs DB row 없이 Qdrant에만 직접 넣은 doc_id `e61dce3f-39cc-4a70-9706-523d326c26cb` 1,034 청크를 `points/delete` filter로 제거. 검증 카운트 0
- 영구 실패 잡 일괄 reset — 32MiB 한도 패치 직전에 retry 3회 모두 같은 페이로드 한도에 막혀 `failed/retry_count=4`로 누적된 15건의 대형 도서 잡을 `pending/retry_count=0/error=NULL`로 되돌림. 모든 잡 traceback 머리가 indexer_worker.py:181 동일 위치라 단일 원인으로 판단

### SQL
```sql
UPDATE ingest_jobs
SET status='pending', retry_count=0, error=NULL,
    started_at=NULL, finished_at=NULL
WHERE status='failed' AND retry_count >= 3;
-- UPDATE 15
```

### 검증
- 워커 PID 45535 정상 가동(2:07PM 기동, 폴링 3→15s backoff)
- reset 직후 폴링 사이클에서 즉시 claim 시작

### 영향 범위
- 처리 대기 큐가 일시에 15건 추가 — 평균 5분/건(80MB PDF 기준) 가정 시 75분 대기, 워커 직렬 처리. 다른 ingest 요청은 그 뒤로 밀림
- 처리 중 같은 32MiB 한도 외 다른 원인(예: Docling OOM)으로 실패하는 잡이 있으면 다시 retry 3회 소진 후 `failed`. 그 경우 별건으로 분석

### 후속 — bulk_ingest 재실행
- `scripts/bulk_ingest.py --dir /Volumes/shared/ingaged --via-queue` 재실행 — 34파일 중 19 duplicate / **15 신규 enqueue** / 0 failed / 15.7s. 리포트 `data/eval_runs/bulk_ingest_2026-04-25T133408Z.json`
- reset 15건 + 신규 15건 합산해 워커 처리 대기 ≈ 2.5시간

---

## [2026-04-25] fix | Qdrant 32MiB upsert 한도 + UI 시스템 탭 hybrid 표시

### 코드
- `packages/vectorstore/qdrant_store.py` — `UPSERT_BATCH_SIZE = 256` 상수 도입. hybrid 경로 `add_documents`의 단일 `client.upsert()` 호출을 256건 단위 루프로 분할. dense+sparse+payload 합산 ~8MB 수준(한도의 1/4)로 안전 마진 확보. vector 경로는 `langchain_qdrant` 내부 `batch_size=64` 자동 분할이라 미변경
- `ui/app.py` 시스템 탭 — `info.config.params.vectors`가 hybrid 모드에서 dict(`{"dense": VectorParams}`)로 반환되는데 UI가 단일 객체 가정으로 `.size`를 직접 접근해 `AttributeError`. dict/객체 분기 + dense 차원·distance + sparse 키 노출. `qdrant_store.DENSE_NAME` 재사용

### 증상 / 영향
- 1k+ 청크 PDF(예: 80MB / 1,034 청크)가 hybrid 모드에서 일관되게 400으로 영구 실패 — 워커가 retry 3회까지 모두 같은 페이로드 한도에서 막혀 12건의 대형 도서 잡이 `failed/retry_count=4` 누적
- `ingest_jobs.error`의 `error[:2000]` 상한이 정확히 traceback 끝(`Payload error: JSON payload ...`)을 잘라버려 1차 진단이 어려웠음. 단건 동기 재현(`scripts/debug_single_ingest.py`)으로 끝까지 출력해 회수

### 검증
- 동일 PDF로 재실행: `1034개 하이브리드 벡터(dense+sparse) 저장 완료 (batch=256)`, 저장 7.6초, 총 5분 12초(파싱 5분이 대부분)
- 시스템 탭: `mode: hybrid · dense(dense) dim=1536 distance=Distance.COSINE · sparse=[sparse]` 정상 표시

### 부수 발견 (별건)
- `packages/jobs/queue.py:100`의 `error[:2000]` 슬라이스가 traceback 머리만 남기고 끝부분(예외 메시지)을 잘라 진단 어려움. `error[-2000:]` 또는 컬럼 상한 확대 검토 후속 TASK 후보
- 12건 누적된 영구 실패 잡 처리(상태 reset → 재처리)는 별건

### 위키 갱신
- `schema.md` 통째 재작성 — `ingest_jobs` 테이블 + documents의 summary/분류 7컬럼 + 마이그레이션 이력 + UPSERT_BATCH_SIZE 표기
- `endpoints.md` 통째 재작성 — `/jobs` 2개 + summary/regenerate + PATCH /documents/{id} + chunks + index/overview + /query doc_filter + /ingest queue 모드 응답
- `decisions.md` 마지막 업데이트 날짜 갱신
- `changelog.md` 0.22.1 항목 추가

---

## [2026-04-25] impl | TASK-018 완료 — 색인 워커 분리 (ADR-028)

### 코드
- `packages/db/migrations/0003_add_ingest_jobs.sql` 신설 — `ingest_jobs` 테이블, sentinel은 `("table", "ingest_jobs")`
- `packages/db/connection.py` — sentinel 시스템을 column/table 양쪽 지원, `pg_advisory_xact_lock`으로 동시 기동 race 해소(uvicorn + worker 동시 시작 시 `pg_type` UNIQUE 충돌 방지)
- `packages/db/models.py` `IngestJobRecord` 신설 (status CHECK, retry_count, error)
- `packages/jobs/__init__.py`, `packages/jobs/queue.py` — `enqueue_job`, `claim_next_job(SKIP LOCKED)`, `mark_done`, `mark_failed`, `get_job`, `list_jobs`
- `apps/indexer_worker.py` 신설 — `python -m apps.indexer_worker`, 폴링(3→15s backoff), claim → pipeline.ingest → summary/classify 인라인 → mark_done. SIGTERM graceful, retry 3
- `apps/config.py` `ingest_mode: "queue"|"sync"` (기본 queue)
- `apps/routers/ingest.py` — queue/sync 분기. queue 모드는 enqueue + 202 + `{job_id}` 응답
- `apps/routers/jobs.py` 신설 — read-only 조회 API
- `apps/main.py` — jobs 라우터 등록
- `apps/schemas/ingest.py` — `IngestResponse.job_id` 옵션 필드
- `scripts/bulk_ingest.py` — `--via-queue` 옵션 (HTTP 거치지 않고 직접 enqueue), `enqueued` 카운터
- `docker-compose.yml` — uvicorn + worker 운영 절차 주석

### 검증 (스모크)
- 작은 파일 1건 (327B txt): enqueue → claim(0s) → 인덱싱(4s) → summary(4s) → classify(1s) → done. 총 9초
- 잡 상태: `pending → in_progress → done` 추적 정상, retry_count=0
- 자동 분류 LLM fallback: `note / software/architecture / 0.3`
- 큐 모드 전환 후 `/query`·`/health` 응답성 영향 없음

### 운영 인시던트 (이 turn에서 발견·해소)
- uvicorn + worker 동시 기동 시 `0003_add_ingest_jobs.sql` 마이그레이션을 두 프로세스가 동시 실행 → `pg_type_typname_nsp_index` UNIQUE 위반. 워커가 즉시 죽음
- 해소: `pg_advisory_xact_lock(<project_id>)`로 트랜잭션 단위 직렬화 + 모든 sentinel 통과 시 빠른 경로(lock 없이 종료) + lock 획득 후 sentinel 재확인. 운영 중 추가 마이그레이션 시 동일 패턴 적용

### 모델 결정 — Postgres 큐 (의존성 0)
- 후보: Redis+RQ/Celery (인프라 +1) / 파일시스템 inbox (race) / uvicorn workers≥2 (자원 경합 잔존)
- 선택: Postgres 기존 인프라 재사용. SKIP LOCKED로 멀티 워커 안전. 잡 상태·retry·에러 가시성 확보

### 의도적 제외
- stale `in_progress` 자동 회수 — 후속 housekeeping 잡 별건
- 워커 N개 동시 운영 검증 (`INDEXER_CONCURRENCY` env 노출) — 별건
- 잡 진행 UI — admin 인증 도입 후
- 앱 컨테이너 Dockerfile + docker-compose `indexer` 서비스 — 별건
- 큐 메트릭(처리량·lag·실패율) Prometheus — 별건

### 관련 페이지
- architecture/decisions.md ADR-028 신규
- changelog.md [0.22.0]
- roadmap.md 실행 큐 ✅ TASK-018 추가, 후순위 TASK-012/013만 잔존
- overview.md 진행표·최근 결정 갱신

### 실행 큐 최종 (이번 라운드)
```
✅ TASK-001~011 → ✅ TASK-014 → ✅ TASK-015 → ✅ TASK-016 → ✅ TASK-017 → ✅ TASK-018
→ 🕐 TASK-012 (Cloudflare Tunnel, 후순위)
→ 🕐 TASK-013 (MkDocs, 후순위)
→ 🛑 인증·공개배포 묶음 (보류)
```

---

## [2026-04-25] impl | TASK-017 완료 — 랜딩 카드 v2 (ADR-027)

### 코드
- `apps/schemas/documents.py` — `RecentDocItem` 신설, `IndexOverviewResponse`에 `top_tags`/`categories`/`recent_docs` 추가
- `apps/routers/documents.py` `index_overview` 끝에 분포 계산 + categories.yaml label 매칭 + 최근 6개 미니 카드 데이터 생성
- `ui/app.py` 빈 채팅 카드 — 카테고리 분포 한 줄, 주제 칩(library_search 사전 채우기), 최근 문서 3-grid 카드(active_doc_filter 라우팅), 전체 문서 expander

### 검증
- 추가 LLM 호출 0 (모든 데이터 파생)
- 응답 페이로드 ~1.5KB → ~3KB (현 20문서)
- 캐시 무효화 흐름 변화 없음

### 의도적 제외
- 칩 IDF·blacklist 정제 — 별건
- 카드 상세 modal — Streamlit 1.36+ st.dialog 검증 후 별건
- 최근 문서 정렬 옵션 — 별건

### 관련 페이지
- architecture/decisions.md ADR-027 신규
- changelog.md [0.21.0]
- roadmap.md 실행 큐 ✅ TASK-017 추가, 다음은 TASK-018(색인 워커 분리)
- overview.md 진행표·최근 결정 갱신

### 실행 큐
```
✅ TASK-001~011 → ✅ TASK-014 → ✅ TASK-015 → ✅ TASK-016 → ✅ TASK-017
→ 🆕 TASK-018 (큐잉, 색인 워커 분리)
→ 🕐 TASK-012/013 (후순위)
```

---

## [2026-04-25] impl | TASK-016 완료 — 사용자 도서관 탭 (ADR-026)

### 코드
- `ui/app.py` — `TAB_LIBRARY` 신설(채팅 직후·문서 직전), 검색/형식/카테고리 필터, 카테고리 그룹 카드 그리드(3 col), 카드 상세 토글(abstract/sample_questions/meta), confidence < 0.4 ⚠️ 배지
- 채팅 탭 상단 — 활성 doc_filter 배지 + [전체 검색] 해제 버튼, `/query` POST에 doc_filter 필드 동봉
- `apps/schemas/query.py` `QueryRequest.doc_filter` 추가
- `packages/rag/retriever.py` — `retrieve(... doc_id=)` 인자 추가
- `packages/rag/pipeline.py` — `query(... doc_filter=)` 추가, LangSmith 태그·메타에 `doc_filter` 표기
- `apps/routers/query.py` — request 통과
- 신규 API 없음 — 기존 `GET /documents` 응답에 K014/K015 4필드가 이미 들어 있어 그대로 재사용

### 검증
- 현 20문서: 카테고리 8개 + (미분류) 0. 카드 그리드·필터·doc_filter 라우팅 정상
- vector·hybrid 양쪽 모두 doc_id 인자 이미 지원해서 backend 변경 최소
- doc_filter 활성 시 검색 latency 추가 비용 미미 (Qdrant filter 절)

### 의도적 제외
- 카드 상세 modal 전환 (Streamlit 1.36+ `st.dialog`) — 의존성 검증 후 별건
- 다중 문서 한정·카테고리 패싯 한정 — 별건
- 사용자 PATCH (카테고리 잘못 분류 즉석 수정) — admin 인증 도입 후

### 관련 페이지
- architecture/decisions.md ADR-026 신규
- changelog.md [0.20.0]
- roadmap.md 실행 큐 ✅ TASK-016 추가, TASK-017 in-progress 표시
- overview.md 진행표·최근 결정 갱신

### 실행 큐
```
✅ TASK-001~011 → ✅ TASK-014 → ✅ TASK-015 → ✅ TASK-016
→ 🆕 TASK-017 (착수 예정, 랜딩 카드 확장) → 🆕 TASK-018 (큐잉, 색인 워커 분리)
→ 🕐 TASK-012/013 (후순위)
```

---

## [2026-04-25] impl | TASK-015 완료 — 카테고리 메타데이터 + 자동 분류 (ADR-025)

### 코드
- `packages/db/migrations/0002_add_classification_columns.sql` 신설 — `doc_type`/`category`/`category_confidence`/`tags`, CHECK enum, 인덱스. sentinel 컬럼(`doc_type`)으로 idempotent
- `packages/db/{models,repository}.py` 동기화 — `update_document_classification`, `list_documents_without_category`
- `packages/code/models.py` `DocRecord` 분류 4필드 추가
- `config/categories.yaml` — 초기 9 카테고리(보유 20문서 기반)
- `packages/classifier/` 신설 — `CategoryClassifier.classify(title, file_type, source, summary)` 룰 매칭 → LLM fallback. doc_type은 file_type/source 휴리스틱
- `packages/vectorstore/qdrant_store.py` — `_ensure_payload_indexes` (4 keyword index), `set_classification_payload` (`set_payload(points=Filter(...))` 부분 업데이트)
- `apps/routers/documents.py` — `PATCH /documents/{id}` 신규, `classify_and_summarize_for_doc` 백그라운드 헬퍼 (summary→classify 순차), `_generate_summary_inner` 분리
- `apps/routers/ingest.py` — `doc_type/category/tags` 옵션 폼, 사용자 명시값 우선 분기
- `apps/schemas/documents.py` — `DocumentItem` 4필드, `DocumentPatchRequest`
- `scripts/classify_documents.py` 신설

### 검증 (파일럿 20문서)
- rule 16건 + LLM fallback 4건, 총 5.7초, 비용 ≈ $0.001
- 정확도 수동 검수 20/20 (웹/딥러닝/시스템 설계/로보틱스/프로그래밍/모바일/기타 모두 의도 일치)
- doc_type 휴리스틱 정확(pdf=book, txt/md=note, docx=report)
- LLM low-confidence 사례 정직 표면화 — 폴리머클레이/헌법재판소/더미 문서가 `other` + 0.3

### 모델 결정 — gpt-4o-mini (ADR-024 토글 인프라 재사용)
- 별도 키 추가 없이 LLM fallback에서 동일 모델 사용. 비용은 룰 매칭 우선이라 매우 작음
- 향후 categories.yaml 확장 시 룰 매칭 비율이 더 높아짐 (LLM 호출 비율 감소)

### Qdrant payload 운영 메모
- `client.set_payload(...)`는 `points=` 키워드 인자가 Filter/FilterSelector/IDs 모두 받음 (qdrant-client 1.17.1). 처음 `points_selector=`로 호출했다가 TypeError → 수정
- 4 keyword 인덱스(`metadata.doc_id|doc_type|category|tags`) 추가 — 향후 검색 시 필터 비용 0~수ms 예상

### 의도적 제외
- 검색 시 메타데이터 필터·부스팅 (별건, payload index만 깔아 둠)
- 패싯 사이드바·다중 라벨 분류 (TASK-016에서 일부, 본격은 별건)
- categories.yaml GUI 편집 (수기 편집 유지)
- 신뢰도 임계 미만 시 NULL 강제 — 정보 보존 우선으로 confidence를 표면 노출

### 관련 페이지
- architecture/decisions.md ADR-025 신규
- changelog.md [0.19.0]
- roadmap.md 실행 큐 ✅ TASK-015 추가, TASK-016 in-progress 표시
- overview.md 진행표·최근 결정 갱신

### 실행 큐
```
✅ TASK-001~011 → ✅ TASK-014 → ✅ TASK-015 → 🆕 TASK-016 (착수 예정, 도서관 탭)
→ 🆕 TASK-017 (큐잉) → 🆕 TASK-018 (큐잉, 색인 워커 분리)
→ 🕐 TASK-012/013 (후순위)
```

---

## [2026-04-25] impl | TASK-014 완료 — 문서 자동 요약 (ADR-024)

### 코드
- `packages/db/migrations/0001_add_summary_columns.sql` 신설 — `summary JSONB`, `summary_model`, `summary_generated_at`
- `packages/db/connection.py` — sentinel 컬럼 존재 검사 후 ALTER 회피 (idempotent, AccessExclusiveLock 충돌 방지)
- `packages/db/models.py` `DocumentRecord` 3컬럼 추가, `init.sql`에 content_hash 누락분 동시 보정
- `packages/db/repository.py` — `update_document_summary`, `list_documents_without_summary`
- `packages/code/models.py` `DocRecord` 동기화
- `packages/summarizer/` 신설 — `document_summarizer.summarize_document()` (1회 LLM 호출, JSON mode 강제, 첫 8청크·청크당 1500자) + `prompts.py` (system + few-shot 2건)
- `apps/config.py` — `summary_enabled: bool = True`
- `apps/routers/documents.py` — `GET/POST /documents/{id}/summary[/regenerate]` 2개 + `generate_summary_for_doc()` 백그라운드 헬퍼
- `apps/schemas/documents.py` — `SummaryResponse`, `DocumentItem` 확장
- `apps/routers/ingest.py` — `BackgroundTasks` 훅으로 인덱싱 후 비동기 요약 생성
- **핫픽스**: `apps/routers/ingest.py`의 async 라우트 안에서 sync `pipeline.ingest`를 `asyncio.to_thread`로 위임 — bulk_ingest 중에도 `/query`·`/health` 응답 가능. (TASK-018 색인 워커 분리 전 임시 완화)
- `scripts/generate_summaries.py` 신설 — `--dry-run`/`--regenerate`/`--limit`/`--doc-id`/`--report`

### 검증 (파일럿 16문서)
- 시범 1건 + 일괄 15건 모두 ok, 평균 3.7s/문서, 총 56초, 비용 ≈ $0.08
- 환각 0건 (한국어 시스템 설계 / 영문 ROS / 짧은 더미 무작위 검수)
- 영문 원본 → 한국어 요약, 기술 용어("ROS", "USB 카메라 드라이버") 원어 유지
- 정보 부족 문서는 `target_audience=""`, `sample_questions=[]`로 정직하게 빈값

### 모델 결정 — gpt-4o-mini
- 사용자 합의: 신규 `ANTHROPIC_API_KEY` 부담 회피, 기존 `LLM_BACKEND=openai` 인프라(ADR-014) 재활용
- 한국어 자연스러움·환각 억제는 Anthropic Haiku 4.5 우위 가능성 있으나, 파일럿 결과 카탈로그·랜딩 용도로 충분
- 향후 정량 비교 필요해지면 토글로 1시간 내 전환 가능 — 회귀 조건 ADR-024에 명시

### 의도적 제외
- Hierarchical summary (긴 책 앞부분 편향 보강) — 후속 별건
- 요약 검색 필터·부스팅 — TASK-015 자동 분류와 함께 별건
- admin 인증 — 인증·공개배포 묶음 해제까지 `regenerate` API는 로컬 LAN 전용

### 운영 인시던트 (이 turn에서 발견·해소)
- 사용자 환경에서 4시간째 진행 중이던 `bulk_ingest` PID 39830이 `documents` 테이블에 `AccessShareLock` 보유 → 신규 ALTER 마이그레이션이 `AccessExclusiveLock` 대기로 dead-wait → uvicorn workers 5분 startup hang의 직접 원인
- 해소: bulk_ingest 종료 + sentinel 컬럼 사전 검사 패치(IF NOT EXISTS이지만 ALTER 시도 자체가 lock 잡음) + uvicorn 재기동
- 별도 발견: `async def ingest` 안에서 sync `pipeline.ingest`(Docling 파싱) 직접 호출이 event loop를 블록 → bulk 동시 진행 시 `/query`·`/health` 응답 불능. `asyncio.to_thread`로 핫픽스
- 근본 해결은 색인 프로세스 분리(TASK-018) — 별도 큐잉 예정

### 관련 페이지
- architecture/decisions.md ADR-024 신규
- changelog.md [0.18.0]
- roadmap.md 실행 큐 ✅ TASK-014 추가, TASK-018 큐잉
- overview.md 진행표·최근 결정 갱신

### 실행 큐
```
✅ TASK-001~011 → ✅ TASK-014 → 🆕 TASK-018 큐잉 예정 (색인 워커 분리)
→ 🆕 TASK-015~017 (큐잉, K014 입력 데이터 확보 완료)
→ 🕐 TASK-012/013 (후순위)
```

---

## [2026-04-25] queue | TASK-014~017 — "지식 도서관(Knowledge Library)" 묶음 큐잉

- 배경: 사용자 요구는 "검색 품질"이 아니라 **"이 RAG에 어떤 정보가 있는지 사용자가 탐색 가능하게"**. admin 문서 목록(TASK-005)은 운영자용이라 사용자 탐색에 부적합. 채팅 진입 시 "뭐 물어볼지 모르겠다" cold-start 문제 해소 + 인덱싱된 전체 문서를 카테고리별로 일람·요약 즉시 확인 가능해야 함
- 대화 경로: 메타데이터 활용 검토 → 카테고리 관리 부재 확인 → 카테고리 추출 방법 검토 → 컬렉션 분리 vs 단일+payload 결정 → 사용자가 의도를 "corpus 가시화"로 재정의 → 요약 + 전체 문서 카탈로그 + 카테고리 그룹 요구로 정리
- 4개 TASK 분할:
  - **TASK-014 문서 요약** — Claude Haiku 4.5, JSONB 영구 캐시, 한 줄/개요/주제/예시 질문 5필드, 일회성 ~$0.1 (47문서)
  - **TASK-015 자동 분류** — doc_type/category/tags, TASK-014 topics를 tags로 채택, categories.yaml 매칭 + LLM fallback, 단일 Qdrant 컬렉션 유지
  - **TASK-016 도서관 탭** — 카테고리 그룹·요약 모달·"이 책에 대해 묻기" 액션, doc_filter 검색 한정 라우팅
  - **TASK-017 랜딩 확장** — TASK-008(완료, ADR-020) 카드를 주제 칩·최근 문서·전체 도서관 진입로로 확장
- 의존: K014 → K015 (요약의 topics 활용) → K016 (둘 다 필요) → K017 (K016 컴포넌트 재사용)
- 단일 컬렉션 유지 결정: 컬렉션 분리는 "임베딩 모델을 유형별로 달리 써야 할 때"까지 보류, ADR에 회귀 조건 명시 예정
- 자동 분류 우선: 사용자 입력 부담 제거가 핵심, 신뢰도 낮으면 NULL + admin 검토 배지
- 의도적 제외: 검색 시 메타데이터 필터·부스팅(별건 후속), 카테고리 트리 GUI 편집(YAML 수기), 원문 미리보기, 사용자별 개인화
- 실행 큐: TASK-001~011 ✅ → 🕐 TASK-012/013 (후순위) → **🆕 TASK-014~017 (큐잉)**
- 반영: roadmap(실행 큐·진행표·4개 상세 정의), log(이 엔트리)
- ADR: 착수 시 신규 번호 부여 — TASK-014(요약 모델·스키마), TASK-015(단일 컬렉션 + 자동 분류), TASK-016(탭 통합 + doc_filter)

---

## [2026-04-23] queue | TASK-013 — MkDocs Material + GitHub Pages 문서 사이트 큐잉 (후순위)

- 배경: project-wiki/는 5단계 중첩 구조가 정보 조직의 핵심. GitHub Wiki는 flat 전제라 네비게이션 손실 큼. 외부 공개·검색 가능한 경로 필요하지만 현 구조 재작성 없이
- 결론: **MkDocs Material + GitHub Pages** — `project-wiki/`를 `docs_dir`로 그대로 사용, GitHub Actions로 push 시 자동 빌드·배포
- 대안 검토: GitHub Wiki(flat 강제·구조 손실·링크 재작성 대량), GitBook/Docusaurus(외부 의존·오버킬) — MkDocs 압승
- 범위 분리: 에이전트 작업(mkdocs.yml·workflow·링크 호환 점검·rag-lint에 `mkdocs build --strict` 추가·runbook) vs 사용자 작업(GitHub Settings → Pages → Source `gh-pages` branch 활성화, 선택적 커스텀 도메인)
- 내부 링크: 현재 상대 경로 대부분 MkDocs에서 그대로 동작. `--strict` 빌드로 소수 404 정정
- 의도적 제외: 위키 구조 flatten, 다국어, Algolia 등 외부 검색, Docusaurus
- 회귀 전략: mkdocs.yml·workflow 제거 + gh-pages 브랜치 삭제로 3분 내 완전 롤백
- 실행 큐: TASK-001~011 ✅ → 🕐 TASK-012 (도메인 Cloudflare 이전 후) → **🕐 TASK-013 (후순위)**
- 반영: roadmap(실행 큐·상세 정의), overview(다음 할 일), log(이 엔트리)
- ADR: 착수 시 신규 번호 부여

---

## [2026-04-23] tool | `/rag-commit` · `/rag-lint` PII 스캔 확장

- 배경: 2026-04-23 security 작업에서 위키 3곳 실 이메일 노출 발견. 기존 스킬은 API 키만 검출하고 PII는 수동 grep 의존
- `/rag-commit` 2단계 민감정보 스캔 분리: (2a) API 키 / (2b) **PII(개인 이메일 도메인)** / (2c) `.env` stage
- `/rag-lint` 체크 8 신설: 위키 전체 .md에서 개인 이메일 도메인(gmail/naver/daum/kakao/hanmail/yahoo/outlook/hotmail/icloud) 패턴 스캔
- placeholder `HAL2001`, `<admin-email>`, `@users.noreply.github.com`는 정규식 매칭 제외
- 매치 시 경고(commit)·FAIL(lint) → `security.md` PII 공개 범위 정책에 따라 치환 후 재시도
- 반영: `.claude/skills/rag-commit.md`, `.claude/skills/rag-lint.md` (저장소 외 로컬)

---

## [2026-04-23] security | 위키 PII 제거 + security.md 공개 범위 정책 신설

- 스캔 결과: 위키에 실 이메일 3곳 평문 노출(로그 1, 로드맵 2). 전화번호·실명·사설 IP는 없음
- 조치: 이메일을 `HAL2001` 플레이스홀더로 치환. append-only 예외 — PII 삭제는 log 이전 엔트리 인라인 수정 허용
- security.md 신설 섹션 "개인정보(PII) 공개 범위 정책" — 금지 위치·허용 위치·플레이스홀더·사고 대응·정기 grep 명령
- git Author 설정: 앞으로의 커밋부터 `HAL2001` 명의, 이메일은 로컬 저장소 한정 설정(--global 미변경). 구체 이메일 값은 `git config user.email`로만 확인, 위키에 평문 기록 금지
- 과거 커밋의 실명/로컬 hostname은 그대로 — 재작성은 파괴적이라 사용자 명시 지시 없이는 보류
- 반영: security.md, roadmap.md(TASK-012 섹션 2곳), log.md(TASK-012 queue 엔트리 1곳)

---

## [2026-04-23] queue | TASK-012 — Cloudflare Tunnel + Access 외부 노출 게이트웨이 큐잉 (후순위)

- 배경: 외부(모바일·지인 장비)에서 RAG 접속·테스트 필요. 현 상태는 Streamlit 8501·FastAPI 8000 모두 localhost·인증 없음. 인증·공개배포 묶음 전체 보류(2026-04-22) 중이라 앱 내 인증 불가
- 결론: **앱 코드 0줄** + **Cloudflare Tunnel + Access(이메일 OTP)** 조합으로 "외부 테스트 접근 게이트" 최소 조각만 꺼냄. 묶음 전체 해제 아님
- 대안 검토: Clerk(150~250줄, React 의존·Streamlit 어색), 자체 bcrypt 게이트(80줄, 이메일 OTP 직접 구현 필요), **Cloudflare Access(0줄·엣지 인증·Tunnel과 같은 대시보드·Free 50 MAU)** — 현 요구에 Access 압승
- 범위 분리: 사용자 작업(계정·도메인 네임서버 이전·대시보드 셋업·외부 기기 테스트) vs 에이전트 작업(runbook·신규 ADR·changelog·overview·log·선택적 UI 헤더 표기)
- 노출 포트: **8501만** — Streamlit이 서버사이드로 8000 호출하므로 FastAPI 외부 노출 불필요
- 이메일 화이트리스트(초기): `HAL2001` (실 이메일은 `.env` 또는 Cloudflare 대시보드에만 저장, 위키·커밋 메시지·공개 문서에 평문 금지). One-time PIN, 세션 24h
- 전제조건: 사용자의 도메인을 Cloudflare 네임서버로 이전 (전파 10분~24h)
- 의도적 제외: 앱 내 패스워드/Clerk/Auth0, 다중 사용자·역할, FastAPI 외부 노출, ISSUE-001, 관리자 UI 2단계
- 회귀 전략: `cloudflared tunnel stop` 즉시 차단, Access Policy Allow→Block 즉시 차단, 앱 변경 없어 로컬 영향 0
- 실행 큐: TASK-001~011 ✅ → **🕐 TASK-012 (후순위, 사용자 도메인 이전·착수 지시 대기)**
- 반영: roadmap(실행 큐·상세 정의·사용자/에이전트 작업 분리), overview(다음 할 일)
- ADR: 착수 시 신규 번호 부여 (queue 단계에서는 번호 예약 없음 — `rag-task-start` 스킬 규칙)

---

## [2026-04-23] tool | `/rag-task-start`·`/rag-lint` 로컬 스킬 신설

- 위치: `.claude/skills/rag-task-start.md`, `.claude/skills/rag-lint.md` (로컬 전용, `.gitignore` 대상)
- **rag-task-start**: 새 TASK 등록 시 다음 TASK/ADR 번호 산출(018 결번 유지), roadmap 실행 큐·overview 다음 할 일·log `queue` 항목을 일관 절차로 동반 갱신. 범위·의도적 제외·완료 기준을 사용자와 합의한 뒤 등록까지만(구현 착수는 별도 턴)
- **rag-lint**: `/rag-commit` 4단계 lint 스크립트를 단독 호출. 7개 체크(위키링크 잔여·깨진 .md·ADR 정의vs참조·changelog 내림차순·index 페이지 수·index 날짜 정합·overview 날짜 정합) 실패 시 대응 표 안내, 파일 수정은 안 함
- 트리거: "태스크 등록"·"태스크 착수" / "lint 해줘"·"위키 점검"
- 반영: `wiki/reviews/patterns.md`에 "로컬 스킬 카탈로그" 섹션 신설 (세 스킬 역할·상호관계·추가 기준 명문화), `wiki/architecture/structure.md`에 skills 디렉터리 확장
- 배경: TASK-011 완료 시점에 `/rag-commit` 한 스킬만으로는 TASK 등록·중간 lint 절차가 매번 수동 반복되어 누락 여지. 3회 이상 반복 확인된 패턴만 스킬화 원칙(patterns.md에 명시)

---

## [2026-04-23] impl | TASK-011 완료 — 하이브리드 검색 (ADR-023)

### 코드
- `packages/rag/sparse.py` 신설 — FastEmbed `Qdrant/bm25` + Kiwi 한국어 전처리 (`SparseEmbedder`, `preprocess()`, 싱글턴 캐시)
- `packages/vectorstore/qdrant_store.py` 재작성 — `search_mode` 분기, named vectors(dense/sparse), `_ensure_collection` 구조 검증, hybrid 경로는 raw `PointStruct`·`SparseVector`·`client.query_points(prefetch=..., query=FusionQuery(fusion=RRF))`로 직접 호출
- `apps/config.py` — `search_mode`, `sparse_model_name` 설정 추가
- `apps/dependencies.py`, `pipeline/rebuild_index.py`, `scripts/bench_retrieval.py`, `scripts/bench_answers.py` — `SparseEmbedder` 주입
- `.env`, `.env.example`, `requirements.txt`(fastembed≥0.4, kiwipiepy≥0.17) 반영

### 검증
- Phase 1 벤치(vector vs hybrid, BGE-reranker, dataset 12건): **Hit@3=1.000 동률**, P@3=1.000, Recall@3=0.944, MRR=1.000
- latency: vector 579ms → hybrid 1008ms (+74%, 허용 범위)
- Phase 2 Ragas 벤치는 LLM/reranker 경로 미변경이라 생략 (긴 실행 시간 대비 이득 불확실)
- 한국어 질의 Kiwi 전처리 수기 확인: 명사·동사·외국어·숫자만 추출, 조사/어미 제거

### 의도적 제외
- Phase 2 Ragas 재측정 — 생성 경로 동일 (사용자 요청으로 조기 종료)
- hybrid 모드에서 `as_retriever()` LangChain 호환 — `NotImplementedError`로 명시, 현재 경로는 `retrieve()`만 사용
- 실시간 mode 전환 — 컬렉션 구조 차이(unnamed vs named vectors)로 **재인덱싱 필수**

### 관련 페이지
- architecture/decisions.md ADR-023 신규 (하이브리드 검색 도입, A/B 결과, follow-ups)
- changelog.md [0.16.0]
- roadmap.md 실행 큐 ✅ TASK-011 추가, 장기 리뷰에서 "하이브리드 검색" 제거
- overview.md 진행표·기술 스택(sparse embedding 추가)·최근 결정·완료 태스크·사용자 개선점

### 실행 큐 최종
```
✅ TASK-001~011 모두 완료
🛑 인증·공개배포 묶음 (사용자 지시 대기)
🔄 장기: Graph RAG, MCP 재개, 대화 요약 메모리 등
```

---

## [2026-04-23] impl | TASK-010 완료 — 폴더 일괄 색인 CLI (ADR-022)

### 코드
- `scripts/bulk_ingest.py` 신설 — `Path.rglob` 재귀 탐색, API `POST /ingest` HTTP 호출, L1 중복 감지 활용
- CLI 옵션: `--dir --recursive/--no-recursive --include --exclude(반복) --title-from --source-prefix --workers --dry-run --fail-fast --api-base --report`
- `MAX_UPLOAD_SIZE_MB` 초과 파일은 `skipped_too_large`로 분류 (실패 아님)
- 결과 JSON: `data/eval_runs/bulk_ingest_<ts>.json` — total/ok/duplicate/failed/skipped_too_large + per-file results
- `tests/integration/test_bulk_ingest.py` — dry-run 기반 6개 케이스 (재귀·no-recursive·exclude·include·없는 폴더·빈 폴더)

### 검증
- 스모크: 3파일 재귀 업로드 6.8초 / 재실행 전부 409 스킵 0.0초 (progress resume 대체)
- 통합 테스트 6/6 통과
- 업로드 후 `/documents` API에서 3건 등록 확인, 정리 후 원복

### 의도적 제외
- 관리자 UI 버튼·`POST /bulk_ingest` API — 인증 없는 현 단계에서 노출 금지 (인증·공개배포 묶음과 함께 미래 도입)
- S3/원격 스토리지 — 로컬 파일시스템만
- 대화형 websocket 진행 표시 — tqdm + LangSmith 트레이스로 충분

### 관련 페이지
- architecture/decisions.md ADR-022 신규
- changelog.md [0.15.0]
- roadmap.md TASK-010 완료 처리, 실행 큐 **전 예정 태스크 완료**
- overview.md 진행표·최근 결정·다음 할 일
- wiki/onboarding/setup.md "대량 문서 색인 (TASK-010)" 섹션 추가

### 실행 큐 최종
```
✅ TASK-001~010 모두 완료
🛑 인증·공개배포 묶음 (사용자 지시 대기)
🔄 장기: Graph RAG, MCP 재개, 하이브리드 검색 등
```

---

## [2026-04-23] queue | TASK-010 — 폴더 단위 일괄 색인 CLI 스크립트 큐잉

- 배경: 현재 문서 등록은 UI·API·`ingest_sample.py` 모두 1건씩. 폴더 전체 배치 수단 부재
- 범위: `scripts/bulk_ingest.py` 신설 — **하위 폴더 포함 재귀 탐색**, 확장자 필터, 정규식 exclude, `--dry-run`·`--fail-fast`·`--report` 등
- 재실행 안전성: L1 중복 감지(SHA-256)·원본 영구 보관·자동 OCR·토큰 상한(TASK-001~009)이 모두 준비되어 폴더 재실행해도 409로 스킵
- 의도적 제외: 관리자 UI 버튼·`POST /bulk_ingest` API — **인증 없는 현 단계에서 노출 금지**, 인증·공개배포 묶음과 함께 도입
- 결과 리포트 스키마: `{total, ok, duplicate, failed, results[]}`를 `data/eval_runs/bulk_ingest_<ts>.json`에 저장
- 주의: 스캔 PDF 섞이면 OCR로 파일당 수 분 소요. 동시 실행 금지(L1 UNIQUE 충돌 가능)
- 실행 큐: TASK-001~009 ✅ → **TASK-010 (다음)**
- 반영: roadmap(실행 큐·사용자 경로 표·TASK-010 상세 정의), overview(다음 할 일·사용자 개선점)

---

## [2026-04-23] docs | 전체 프로젝트 구조도 신설 — wiki/architecture/structure.md

- 디렉터리별 트리(apps/ packages/ ui/ pipeline/ scripts/ tests/ data/ project-wiki/ .claude/ .streamlit/) + 각 파일의 역할 주석
- 논리적 계층도: Client → FastAPI → RAGPipeline → loaders/llm/rag/vectorstore → 외부 서비스·DB·파일시스템
- 런타임 토폴로지: uvicorn + streamlit + docker(Qdrant+Postgres) + 외부(OpenAI·HF·LangSmith)
- 디렉터리별 역할·의존 방향 원칙 ("packages/는 FastAPI/Streamlit 비의존")
- 변경 시 동반 갱신 원칙 표 (코드 위치 → 갱신 대상 wiki)
- 신규 기능 추가 시 권장 경로 8단계 (roadmap → 구현 → ADR → changelog → log → /rag-commit)
- 알려진 정리 대상: wiki/security.md 중복, Alembic 미도입, placeholder md들
- index.md Architecture 섹션에 등재 (총 페이지 24 → 25)

---

## [2026-04-23] docs | PDF 처리 프로세스 정리 + 스캔 PDF OCR 기록 정정

### 배경
사용자 질의("OCR 미처리 PDF는 처리 안 되나?")를 통해 **위키 기록이 실제 코드와 어긋남을 확인**:
- `wiki/data/spec.md`: "스캔 PDF ⚠️ OCR 필요·추후 검토"
- `wiki/troubleshooting/common.md`: "OCR 전처리 필요 (현재 미지원)"
- 실제 확인: Docling `PdfPipelineOptions.do_ocr=True` 기본값 → 스캔 PDF 자동 OCR 처리 중 (EasyOCR 내장)

### 정정
- **spec.md**: 지원 형식 표에서 스캔 PDF 행 ✅ 처리로 변경, 파일 크기 상한 50MB → 200MB 정정. 최상단 상태를 draft → active로
- **spec.md 신규 섹션 "PDF 처리 프로세스 (End-to-End)"**: Stage 0~6 + 단계별 타이밍·장애 처리 상세 플로우 문서화
  - Stage 0: 업로드 수신 (중복 감지, 원본 영구 보관)
  - Stage 1: Docling 파싱 + 자동 OCR 분기 (digital/scanned/mixed)
  - Stage 2: 마크다운 저장 + 정규화 (재인덱싱 fallback용)
  - Stage 3: HybridChunker 청킹 (breadcrumb · page_no 복구)
  - Stage 4: 2차 방어 청킹 (RecursiveCharacterTextSplitter)
  - Stage 5: 임베딩·Qdrant 저장
  - Stage 6: PostgreSQL 메타데이터 기록 + 캐시 무효화
- **troubleshooting/common.md**: "PDF 파싱 결과가 빈 문자열" 항목 전면 재작성 — OCR 미지원 안내 제거, 실제 원인 5개(보안 PDF, 손상, 폰트 임베딩 없음, 흐린 스캔, 워터마크 오버레이) + 해결 단계 명시
- **ADR-004 결과**에 OCR 자동 처리 보강 + 정정 메모

### 교훈
위키 초기 기록(2026-04-17~19)이 추정 기반이었음. 코드 실제 동작을 정기적으로 재검증하는 lint 확장 검토 필요 (예: ADR의 "결과" 블록 내용이 코드와 일치하는지 자동 체크)

---

## [2026-04-23] tool | `/rag-commit` 로컬 스킬 신설

- 위치: `.claude/skills/rag-commit.md` (로컬 전용, `.gitignore` 대상)
- 범위: 커밋 전 체크(민감키 스캔·`.env` 방지·data/ ignore·위키 lint·동반 갱신) + 표준 메시지 템플릿 + 금지 동작 차단 (force push to main, --no-verify 등)
- 자동화된 wiki lint: 5개 항목 (위키링크·깨진 링크·미정의 ADR·changelog 순서·index 페이지 수)
- 메시지 템플릿 4종: feat(TASK) / fix / docs(wiki) / chore(보류·철회)
- 트리거: 사용자가 "/rag-commit" 또는 "커밋해줘"·"push해줘" 발화
- 위키 반영: `wiki/reviews/patterns.md`의 "커밋 체크리스트" 섹션에 체크 항목 요약 + 스킬 파일 포인터
- 배경: 2026-04-22에 API 키 채팅 평문 노출 2회·GitHub Push Protection 차단 1회 발생한 이력 때문에 사전 차단 장치 필요

---

## [2026-04-22] lint | 위키 전체 정합성 점검·정정

### 점검 범위 (스크립트로 자동화)
1. 남은 위키링크 `[[...]]`: **0건** ✅
2. 깨진 `.md` 상대 링크: **0건** ✅
3. TASK-001~009 상태 일관성 (roadmap/overview/log/changelog 간): ✅ 모두 `✅ 완료`로 일치. TASK-006만 `🚫 철회` 일관
4. ADR 정의 vs 참조: **ADR-018이 참조만 존재, 정의 없음** → 정정 (아래)
5. 등록 ISSUE 파일: ISSUE-001, ISSUE-002 ✅
6. changelog 버전 연속성: **0.11.0 누락** → 정정 (아래)
7. index.md 페이지 수 vs 실제: **선언 19 vs 실제 24** → 정정

### 정정 조치
- **ADR-018 참조** (3곳, 전부 TASK-006 철회 컨텍스트): `roadmap.md` 서브태스크·완료 기준, `log.md` queue 항목에 **"(TASK-006 철회로 미작성. 재개 시 다음 가용 번호로 재할당)"** 주석 추가. 정의 파일은 생성하지 않음
- **changelog [0.11.0] 건너뜀 표기**: `[0.12.0]` 위에 "0.11.0 — 건너뜀" 블록 추가하고 사유·참조 명시
- **index.md**: 마지막 업데이트를 "TASK-001~009 완료, ADR-012~021(018 결번), ISSUE-001·002 등록"으로 최신화. 페이지 수 19 → **24 (루트 9 + wiki/ 13 + issues/open/ 2)**

### 결과
위키 정합성 체크 전 항목 통과. 남은 "참조 없는 ADR/버전" 항목은 결번 표기로 명시되어 정의와 참조가 일치함

---

## [2026-04-22] issue | ISSUE-002 등록 — 후속 질문 배지 무반응 (3회 수정 시도 증상 지속)

- 증상: 예시 질문 클릭 후 답변 하단 배지 클릭 시 재질의 트리거 안 됨 (모바일 재현 확인)
- 3회 수정 시도 기록 ([0.14.1]·[0.14.2]·[0.14.3])는 모두 Streamlit 모범 사례에 부합하나 원인은 아니었음 → 유지
- 유력 가설: 모바일 Streamlit WebSocket 이벤트 누락 (ISSUE-001과 같은 계열). 데스크톱 검증 필요
- 보류: "인증·공개배포 묶음"에 편입 (ISSUE-001·관리자 UI 2단계·HTTPS 배포와 함께 재검증)
- 반영: `wiki/issues/open/ISSUE-002-*.md` 신설, troubleshooting·ADR-019 회고·overview·index에 상태 갱신

---

## [2026-04-22] fix v3 | 배지 무반응 — **진짜 근본 원인은 버튼 key 불일치** ([0.14.3])

- 0.14.1(st.rerun 제거)·0.14.2(st.chat_message 바깥 렌더) 둘 다 **추정 원인이 틀렸음** — 증상 지속
- **진짜 원인**: 라이브 렌더 `live_{len(messages)}_sug_*` key vs 다음 rerun 히스토리 렌더 `hist_{msg_idx}_sug_*` key 불일치. Streamlit widget state는 key 바인딩이라 사용자 클릭 이벤트가 분리된 위젯 사이에서 소실됨
- 수정: 두 경로의 key 접두사를 `msg_{msg_idx}`로 통일. 라이브는 append 직후 `len(messages) - 1` 사용 → 다음 rerun 히스토리의 `enumerate` 인덱스와 동일 값
- **재발 방지 원칙** (강하게 기록): Streamlit에서 같은 논리적 위젯이 여러 렌더 경로에 존재한다면 반드시 동일 key를 사용할 것
- 이전 v1/v2 수정은 Streamlit 모범 사례에 부합하므로 되돌리지 않음. 오진이었음을 changelog·ADR-019 회고·troubleshooting에 명시
- 반영: changelog [0.14.3], ADR-019 회고, troubleshooting/common.md UI 항목, 본 log

---

## [2026-04-22] fix v2 | 배지 무반응 — 진짜 원인은 chat_message 내부 버튼 ([0.14.2])

- 이전 0.14.1 수정(st.rerun 제거)은 부분 해결. "처음 예시 질문 후 아래 배지 선택 시 무반응" 증상 지속
- 진짜 원인: `_render_suggestions()`의 `st.button`이 `st.chat_message(...)` **컨테이너 내부**에서 호출 → 두 번째 이후 클릭에서 컨테이너 재생성 ↔ widget state 복원 경쟁으로 click 이벤트 소실
- 수정: 배지 렌더를 `with st.chat_message` 블록 **바깥**으로 이동 (히스토리 루프·라이브 렌더 양쪽)
- **재발 방지 원칙** 추가: Streamlit에서 `st.button`은 컨테이너 위젯(chat_message, expander, popover 등)의 컨텍스트 매니저 안에 두지 말 것 — ADR-019 회고 + troubleshooting/common.md에 기록
- 반영: changelog [0.14.2], ADR-019 회고, troubleshooting 항목 갱신

---

## [2026-04-22] fix | 후속 질문 배지 두 번째 이후 클릭 무반응 해결 ([0.14.1])

- 증상: 답변 아래 suggestions 배지 #1 클릭은 정상이나 같은 답변의 다른 배지를 이어 클릭하면 재질의 안 됨
- 원인: `_render_suggestions()`·empty state 배지 핸들러에서 `st.rerun()` 명시 호출이 Streamlit의 버튼 자동 rerun과 중복되어 state 플러시 타이밍 꼬임
- 해결: `ui/app.py`의 두 핸들러에서 `st.rerun()` 제거, `_pending_question` 세션 키 세팅만 남김. 자동 rerun이 바깥 `if question:` 블록을 재실행
- 반영: changelog [0.14.1], ADR-019 회고 섹션, troubleshooting/common.md UI 섹션 항목 신설

---

## [2026-04-22] decision | 인증·공개배포 전체 보류 (사용자 지시까지)

- 사유: 개인·내부 사용 시스템 단계, 인증·관리자 분리·HTTPS 배포 모두 현재 불필요
- 보류 묶음: ISSUE-001 · 관리자 UI 2단계 · HTTPS 리버스 프록시 · API 키/OAuth · 관리자 전용 UI 버튼
- 재개 조건: 사용자 명시적 지시
- 반영: roadmap 실행 큐/장기 목록, overview 다음 할 일/열린 이슈, ISSUE-001 헤더에 묶음 정보 명시
- 장기 목록의 "인증 (API Key/OAuth)" 항목도 동일 묶음에 편입

---

## [2026-04-22] impl | TASK-009 완료 — DELETE 파일 정리 + HybridChunker 토큰 상한 (ADR-021)

### 코드
- `apps/routers/documents.py` DELETE:
  - `Path(settings.upload_dir).glob(f"{doc_id}.*")` 순회 unlink
  - `Path(settings.markdown_dir) / f"{doc_id}.md"` 존재 시 unlink
  - 삭제 실패(권한 등)는 warning 로그 후 계속 진행 (DB·Qdrant 정리 성공은 무효화하지 않음)
- `packages/loaders/docling_loader.py`: `HuggingFaceTokenizer(tokenizer=AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2"), max_tokens=480)`으로 HybridChunker 구성. import/버전 오류 시 기본 chunker fallback + warning

### 검증
- **삭제 스모크**: 테스트 문서 업로드 → `/data/uploads/{id}.txt`·`/data/markdown/{id}.md` 생성 확인 → DELETE → 두 파일 모두 사라짐 확인
- **토큰 경고**: 새 API 기동 + 스모크 업로드 후 `grep -c "Token indices sequence length"` = **0** (이전 재인덱싱 경고 다수 대비)
- 기존 저장된 Qdrant 청크는 재인덱싱하지 않으면 유지 — 토큰 상한 효과는 새 업로드부터

### 관련 페이지
- architecture/decisions.md ADR-021 신규
- changelog.md [0.14.0]
- roadmap.md TASK-009 완료, 실행 큐 **전 예정 태스크 완료**
- overview.md 완료 표·최근 결정·다음 할 일 갱신

### 실행 큐 최종 상태
```
✅ TASK-001~009 모두 완료
🛑 ISSUE-001 + 관리자 UI 2단계 (사용자 지시 대기)
🔄 장기: Graph RAG, MCP 재개, 하이브리드 검색, 대화 요약, 인증, 스트리밍, L2 중복 감지
```

---

## [2026-04-22] impl | TASK-008 완료 — 빈 채팅 인덱스 요약 카드 (ADR-020)

### 코드
- `apps/schemas/documents.py`: `IndexOverviewResponse(doc_count, titles, top_headings, summary, suggested_questions)`
- `apps/routers/documents.py`:
  - `GET /index/overview` 신규 — Qdrant scroll로 문서당 상위 50청크 heading 집계 + LLM JSON 모드로 summary·예시 질문 5개 생성
  - 인메모리 캐시 `(doc_count, sorted doc_ids)` 키, `invalidate_index_overview_cache()` 헬퍼
- `apps/routers/ingest.py` + DELETE에서 캐시 무효화 호출
- `apps/config.py`·`.env(.example)`: `INDEX_OVERVIEW_ENABLED` 토글
- `ui/app.py`: 빈 채팅 empty state에 `st.container(border=True)` 카드 — summary·문서 리스트·예시 질문 5개 배지(클릭→`_pending_question`→자동 재질의). 업로드·삭제 시 `_index_overview` 캐시 무효화

### 검증
- 1차 호출: doc_count=6, titles 6개, top_headings 5개, 한국어 요약 2~3문장 + 예시 질문 5개 생성
  - "이 시스템은 딥러닝과 로봇 프로그래밍에 관한 지식을 제공합니다. 특히 ROS..."
- 2차 호출: **5ms 캐시 히트** (LLM 호출 0)
- 업로드·삭제 시 자동 무효화 (코드 경로 확인)

### 관찰·한계
- top_headings에 "또는 return np .sum(x**2)" 같은 노이즈가 섞이는 케이스 — heading 정제는 후속
- JSON 모드 미지원 공급자에선 fallback 문구 사용

### 관련 페이지
- architecture/decisions.md ADR-020 신규
- changelog.md [0.13.0]
- roadmap.md TASK-008 완료, 실행 큐 `TASK-009 (다음)`
- overview.md 완료 표·최근 결정·다음 할 일 갱신

### 다음
- **TASK-009**: DELETE 시 원본 파일 동반 삭제 + HybridChunker 토큰 상한 튜닝 (512 초과 경고 제거)

---

## [2026-04-22] impl | TASK-007 Phase 1 완료 — 후속 질문 제안 (ADR-019)

### 코드
- `packages/rag/generator.py` 재작성: plain/with_suggestions 두 system prompt, OpenAI JSON 모드(`response_format={"type":"json_object"}`), 파싱 실패 graceful degrade (answer는 원문, suggestions=[])
- `apps/config.py`·`.env(.example)`: `SUGGESTIONS_ENABLED` (기본 true), `SUGGESTIONS_COUNT` (기본 3)
- `apps/schemas/query.py`: `QueryResponse.suggestions: list[str] = []`
- `packages/rag/pipeline.py`:
  - `generate()` 반환 dict 변경에 맞춰 `suggestions` 전파
  - `tracing_context` 태그에 `suggestions:<bool>`, 메타에 `suggestions_enabled/count` 추가
  - query 로그에 `suggestions=N` 포함
- `apps/routers/query.py`: `QueryResponse`에 suggestions 전달
- `ui/app.py`: `_render_suggestions()` 헬퍼, 과거 메시지도 배지 재클릭 가능. `_pending_question` 세션 키로 자동 재질의

### 검증
- `SUGGESTIONS_ENABLED=true` + "ROS의 주요 구성요소는?" → 한국어 suggestions 3개 정상 생성, latency 4142ms
  - "ROS의 파일 시스템 레벨에 대해 더 알고 싶습니다."
  - "계산 그래프 레벨에서 어떤 개념들이 포함되나요?"
  - "ROS 커뮤니티 레벨의 자원에는 어떤 것들이 있나요?"
- `SUGGESTIONS_ENABLED=false` 회귀 테스트: suggestions=0, answer 동일 → **회귀 0**
- 답변이 불충분(예: "관련 문서를 찾지 못했습니다.")일 때 suggestions 강제 빈 리스트

### 주요 원칙 준수
- 추가 LLM 호출 0회 (토큰 +50~100 응답)
- JSON 파싱 실패에도 answer는 항상 반환
- LangSmith 태그로 suggestions 경유 여부 관측 가능

### 관련 페이지
- architecture/decisions.md ADR-019 신규
- changelog.md [0.12.0]
- roadmap.md TASK-007 완료 처리, 실행 큐 `TASK-008 (다음)`
- overview.md 완료 표·최근 결정 갱신

### 다음
- **TASK-008**: 빈 채팅 인덱스 요약 카드 + 예시 질문 (Phase 2). `GET /index/overview` 엔드포인트 + LLM 캐시

---

## [2026-04-22] docs | 태스크 재정리 + 사용자 개선점 명시

### 재정리 내용
- overview.md "다음 할 일"을 4개 블록(완료 ✅ / 다음 🎯 / 보류 🛑 / 철회·장기 🚫🔄)으로 재구성. 기존 번호 순서 꼬임 정리
- 신규 섹션 **"예정 태스크 완료 시 사용자 개선점"** 추가 — 각 태스크가 before/after로 사용자 체감 어떻게 바꾸는지 표로 정리
- roadmap.md 상단 실행 큐 블록 시각화 + "사용자 관점 개선 경로" 요약 표 추가
- 알려진 한계 섹션은 태스크 현황의 "기술 부채" 블록으로 통합해 중복 제거

### 신규 큐잉 (TASK-007 이후 실행 큐)
- **TASK-008**: 빈 채팅 인덱스 요약 카드 + 예시 질문 5개 (TASK-007 Phase 2 승격). `GET /index/overview` 엔드포인트 + LLM 캐시. ADR-020 예정
- **TASK-009**: 디스크 정리(DELETE 시 파일 동반 삭제) + HybridChunker 토큰 상한 튜닝(512 초과 경고 제거). ADR-021 예정

### 현재 큐
```
✅ TASK-001~005 → 🎯 TASK-007 (다음) → TASK-008 → TASK-009
→ 🛑 ISSUE-001 + 관리자 UI 2단계 (사용자 지시 대기)
→ 🔄 장기: Graph RAG, MCP 재개, 하이브리드 검색, 대화 요약, 인증, 스트리밍, 중복 감지 L2
```

---

## [2026-04-22] decision | TASK-006 (MCP 서버 익스포트) — 🚫 철회

- 사용자 판단: **현재 시스템에서 MCP 노출은 불필요** — 범위에서 제외
- 사유: 프로젝트 코어 품질(retrieval·답변 품질)에 기여 없음. Claude Code 통합은 외부 소비자 유스케이스가 구체화되기 전 과잉
- 조치:
  - 실행 큐에서 제거 (`TASK-005 ✅ → TASK-007 (다음)` 로 재편)
  - roadmap의 TASK-006 섹션은 `~~취소선~~` + "참고용" 표기로 보존 (재개 시 원본 서브태스크 재활용)
  - 장기 목록(재평가 섹션)에 "MCP 서버 익스포트 (철회 후 장기 검토)" 등재 + 재개 조건 명시
- 재개 조건: ① 외부 에이전트(Claude Code/Cursor 등)가 이 지식 베이스를 소비할 구체 유스케이스, ② HTTP/SSE 모드 필요성. 충족 시 신규 TASK-NNN으로 재정의

---

## [2026-04-22] decision | Graph RAG 도입 — 현재는 보류 (비용·복잡도 사유)

- 검토 결과 Graph RAG(Microsoft GraphRAG / LlamaIndex PropertyGraph 등)는 "적극적 질의"·"인덱스 가시성" 니즈와 부합은 하나, **현재 규모(문서 6개, 청크 4037, 로컬 Hit@3=1.0)에 비해 비용·복잡도가 과도**
- 추정 비용: 재인덱싱 시 LLM 호출 $30~120, Neo4j/AGE 등 저장소 추가 Docker 서비스 1개, incremental 업데이트 전략 필요
- 대안 경로: TASK-007(후속 질문) + Phase 2(인덱스 요약 카드) + 필요 시 경량 엔티티 추출로 같은 니즈의 80~90% 해결 가능
- **재평가 조건** (roadmap 장기 목록에 명시): ① 문서 100+, ② 질의 로그에서 multi-hop/cross-document 패턴 비중 ↑, ③ 경량 대안으로 해결 안 될 때
- 착수 시 의무: 별도 ADR 작성, TASK-004 프레임워크로 before/after 정량 비교

---

## [2026-04-22] queue | TASK-007 — 후속 질문 제안 + 인덱스 커버리지 가시성

- 배경: 사용자가 "이 RAG가 뭘 아는지" 예측 어려움. 답변 이후 탐색 방향 제시 없음 → 적극적 질의 UX 필요
- Phase 1 (이번 TASK 범위):
  - `generate()`를 JSON 모드로 확장해 `{"answer": ..., "suggestions": [...]}` 한 번에 생성 (추가 LLM 호출 0회)
  - `QueryResponse.suggestions` 스키마 추가, Streamlit 답변 하단 배지 3개 → 클릭 시 재질의
  - `.env` 토글 `SUGGESTIONS_ENABLED`, `SUGGESTIONS_COUNT`
  - LangSmith `suggestions_count` 메타
- Phase 2 (후속 분리): 빈 채팅 empty state에 "인덱스 요약 + 예시 질문 5개" 카드
- Phase 3 (더 후속): 형제 heading 기반 탐색 사이드 패널
- 실행 큐: TASK-006 → **TASK-007**

---

## [2026-04-22] queue | TASK-006 — RAG를 MCP 서버로 익스포트 (Claude Code 연계)

- 배경: 이 프로젝트의 RAG 인덱스를 Claude Code에서 `search_docs`/`list_docs` tool로 사용 가능하게 MCP 익스포트
- 범위: stdio MCP 서버 (`apps/mcp_server.py`) + 최소 tool 2개만. 관리 기능(업로드·삭제)은 기존 웹 UI에만
- 실행 큐: TASK-001~005 ✅ → **TASK-006 (다음)**
- 산출물: `apps/mcp_server.py`, `wiki/integrations/mcp.md` 또는 features/에 가이드, ADR-018, changelog [0.11.0]  *(※ TASK-006 철회로 ADR-018·버전 0.11.0은 미발행. 재개 시 다음 가용 번호로 재할당)*
- 주의: stdout 프로토콜 오염 방지 위해 logger를 stderr로 확인, FastAPI와 별도 프로세스(`python -m apps.mcp_server`)
- 의도적 제외: `ingest_doc`/`delete_doc`(보안), HTTP 모드(stdio 로컬 전용), 인증

---

## [2026-04-22] hold | ISSUE-001 + 관리자 UI 2단계 — 사용자 지시 대기

- ISSUE-001 페이지 상태를 "open · 🛑 보류 (사용자 지시 대기)"로 전환
- overview 열린 이슈·다음 할 일, roadmap 실행 큐 하단에 **자동 진행 금지** 명시
- 재개 조건: 사용자가 명시적으로 지시할 때까지 착수 금지
- 향후 착수 시 범위: 원인 확정(진단 로그 수집 또는 ngrok HTTPS 테스트) → HTTPS 리버스 프록시 배포 → 관리자 UI 2단계(`/admin` 분리 + `ADMIN_PASSWORD`) 묶어 처리

---

## [2026-04-22] impl | TASK-005 완료 — 관리자 UI 1단계 (ADR-017)

### 코드
- `ui/app.py` 전면 재작성: `st.tabs(["채팅","문서","대화","시스템","평가"])` 5개 탭 구조, 기존 사이드바 업로드·문서목록은 "문서" 탭으로 이전
- 세션 상태 명시화(`messages`, `session_id`, `documents_cache`, `conversations_cache`, `selected_doc_id`, `selected_session_id`) — 탭 전환 시 채팅 상태 유실 방지
- 신규 백엔드:
  - `QdrantDocumentStore.scroll_by_doc_id(doc_id, limit)` (payload filter scroll, chunk_index 정렬)
  - `GET /documents/{doc_id}/chunks?limit=N` 엔드포인트
  - `ChunkPreview`, `ChunkPreviewResponse` 스키마 (content 500자로 자름)
- 시스템 탭은 `apps.config.get_settings()` + `QdrantClient.get_collection()` 직접 호출로 실시간 반영

### 기능
- 채팅: 기존 유지 + session_id 뱃지
- 문서: 업로드/목록/삭제 + **청크 미리보기 (상위 10개)** — heading_path·page·content_type 포함
- 대화: `/conversations` 목록, 선택 시 메시지 뷰, 세션 삭제. 최근 업데이트순
- 시스템: Reranker/LLM/Embedding/Qdrant/Health/LangSmith 6개 카드 읽기 전용
- 평가: `data/eval_runs/*.json` 최신 Retrieval·Answer 지표 + 최근 10개 히스토리 테이블

### 검증
- API+UI 재시작 후 `/documents/{id}/chunks?limit=3` smoke 통과 (heading_path·chunk_index·content 정상)
- UI 8501 포트 LISTEN 확인

### 1단계에서 제외 (옵션 B로 승격)
- 설정 변경 UI, 재인덱싱/벤치 실행 버튼, 인증, 청크 검색 디버거, LangSmith 임베드

### 관련 페이지
- architecture/decisions.md ADR-017 신규
- changelog.md [0.10.0]
- roadmap.md TASK-005 완료 처리, 실행 큐 전부 완료 마킹
- overview.md 다음 할 일 갱신 (5번 완료, 6번 "ISSUE-001 + 관리자 2단계" 대기)
- features/admin_ui.md 상태 draft → active

### 다음 큐
**대기**: ISSUE-001 근본 해결 + 관리자 UI 2단계 (HTTPS 배포 + `/admin` 분리 + `ADMIN_PASSWORD`) — 운영 배포 시점에 착수

---

## [2026-04-22] docs | 관리자 UI 기능 명세 페이지 신규 + ISSUE-001 후속 처리 지정

- `wiki/features/admin_ui.md` 신설 — 1·2·3단계 로드맵, 각 탭의 필드·데이터 출처·세션 상태 설계·보안 주의·1단계 제외 항목·완료 기준까지 명세
- ISSUE-001 헤더에 "**TASK-005 이후 HTTPS 배포와 묶어 해결**" 명시 — 관리자 UI 2단계(옵션 B) 승격 시점과 동일 스프린트로 처리
- index.md Features 섹션에 admin_ui.md 추가 (총 페이지 18→19), overview 열린 이슈·다음 할 일 반영

---

## [2026-04-22] queue | TASK-005 — 관리자 UI 1단계(Streamlit 탭) 큐잉

- 1단계(옵션 A): 현 Streamlit 앱에 `채팅/문서/대화/시스템/평가` 5개 탭 추가. 인증·페이지 분리 없음. LAN 전용
- 범위: 문서 CRUD + 청크 미리보기, 대화 CRUD + 메시지 뷰, 시스템 설정값(reranker/llm/embedding/Qdrant) 읽기 전용 카드, 평가 지표 최신 결과 카드
- 산출물: `ui/app.py` 탭 구조 + `wiki/features/admin_ui.md` + ADR-017 + changelog [0.10.0]
- 완료 기준 5개 명시 ([roadmap.md](roadmap.md))
- 2단계(옵션 B: `/admin` 분리 + 패스워드)는 HTTPS 배포·ISSUE-001 해결 시점에 승격
- 실행 큐: TASK-001/002/003/004 ✅ → **TASK-005 (다음)**

---

## [2026-04-22] docs | DB 스키마 문서화 — wiki/data/schema.md 신규

- 대상 저장소 3종 전부 정리: PostgreSQL(`documents`/`conversations`/`messages`), Qdrant(컬렉션/payload), 파일시스템(`data/uploads`/`data/markdown`/`data/eval_runs`)
- 실제 DB에서 컬럼·인덱스·Qdrant 컬렉션 config 라이브로 추출해 문서화(현재 포인트 4037개, dim 1536)
- 조인 키(`documents.doc_id` ↔ Qdrant `metadata.doc_id` ↔ 파일시스템 `{doc_id}.*`) 및 논리 ERD 포함
- 마이그레이션 이력(content_hash 추가 등) 기록, 알려진 기술 부채 나열
- index.md·data/spec.md에 링크 추가, 총 페이지 수 17 → 18

---

## [2026-04-22] impl | TASK-002 완료 — Embedding 토글 + A/B (OpenAI 유지, BGE-M3 옵트인, ADR-016)

### 코드
- `apps/config.py`: `embedding_backend`, `embedding_model_name`, `embedding_warmup` 3개 필드
- `.env(.example)`: `EMBEDDING_BACKEND=openai|bge-m3`, `EMBEDDING_MODEL_NAME`, `EMBEDDING_WARMUP`
- `packages/llm/embeddings.py` 전면 재작성: `_EmbeddingWithDim` 래퍼가 `embedding_dim`·`backend`·`model` 속성 노출
- `packages/vectorstore/qdrant_store.py`:
  - `VECTOR_SIZE` 상수 제거 → `embeddings.embedding_dim`에서 읽음
  - 기존 컬렉션 차원과 현재 임베딩 차원이 다르면 `CollectionDimensionMismatch` 예외
- `pipeline/rebuild_index.py`: `RAGPipeline(reranker=...)` 생성자 맞춤 (차원 변경 재인덱싱 지원)
- `requirements.txt`: `langchain-huggingface` 추가

### 실험 (TASK-004 프레임워크로 A/B, 12 질의)
| 지표 | OpenAI | BGE-M3 | Δ |
|------|--------|--------|---|
| Hit@3 / Precision@3 / MRR | 1.000 | 1.000 | = |
| Recall@3 | 0.944 | 0.944 | = |
| Retrieval latency | 580ms | 423ms | −27% |
| faithfulness | 0.886 | 0.857 | −3% |
| answer_relevancy | 0.648 | 0.618 | −5% |
| context_precision | 0.986 | 0.924 | −6% |
| context_recall | 0.942 | 0.917 | −3% |

### 결정
**OpenAI 기본 유지 + BGE-M3 토글 확보** (ADR-016). 전환 이득 없음. dataset 성격이 크게 바뀌면 재평가.

### 실행 안정성
- 컬렉션 차원 1536→1024 전환 후 복원(1024→1536)까지 무장애 수행 — 자동 감지·재인덱싱 동작 검증

### 관련 페이지
- architecture/decisions.md ADR-016
- changelog.md [0.9.0]
- roadmap.md TASK-002 완료 처리, 실행 큐 전부 완료 마킹
- overview.md 기술 스택·최근 결정·다음 할 일
- features/evaluation.md 실험 2026-04-22-c 추가

### 다음
실행 큐의 모든 태스크(001~004) 완료. 추가 실험 후보:
- `answer_relevancy 0.648` 개선을 위한 프롬프트 간결화 (저비용, TASK-005 후보)
- reference(정답 답변 문자열) 라벨 추가로 context_recall 진짜 값 확보 (TASK-004 Phase 2 개선)

---

## [2026-04-22] impl | TASK-004 완료 — 평가 프레임워크 (Ragas + 자체 벤치) + 기반선 수립 (ADR-015)

### 코드
- `tests/eval/dataset.jsonl` 신설 — 12개 질의 + `expected_doc_ids` 라벨 (ko 7 / en 4 / mixed 2)
- `scripts/bench_retrieval.py` — Hit@K/Precision@K/Recall@K/MRR, reranker A/B 지원, JSON 저장
- `scripts/bench_answers.py` — Ragas 4종 지표(faithfulness, answer_relevancy, context_precision, context_recall) + LangSmith run 자동 기록
- `requirements.txt`에 `ragas>=0.2`, `datasets>=4.0` 추가

### 버그 수정 (초기 구현 중 발견)
- bench_retrieval: recall 공식이 청크 중복을 카운트해 1 초과 → unique-doc 기반으로 수정
- bench_answers: pipeline.query의 200자 excerpt를 Ragas에 넘겨 faithfulness 0.15 → retrieve() 직접 호출 + 전체 청크 전달로 0.886 복구

### 기반선 수치 (2026-04-22)
- Phase 1 A/B (12 질의):
  - FlashRank: Hit@3=0.917, P@3=0.847, R@3=0.861, MRR=0.833
  - **BGE-M3 : Hit@3=1.000, P@3=1.000, R@3=0.944, MRR=1.000** ← 기본
- Phase 2 (BGE-M3 + gpt-4o-mini):
  - faithfulness 0.886, answer_relevancy 0.648, context_precision 0.986, context_recall 0.942 (self-reference)

### 원칙 (강제)
이후 모든 품질 관련 ADR은 **before/after 수치 첨부**. reranker/LLM backend 교체 시 Phase 1+2 재실행 후 결정.

### 관련 페이지
- architecture/decisions.md ADR-015 신규
- changelog.md [0.8.0]
- roadmap.md TASK-004 완료 처리, 실행 큐 `TASK-001 ✅ → TASK-003 ✅ → TASK-004 ✅ → (필요 시) TASK-002`
- features/evaluation.md 전면 개편 (최신 지표 + 실행 방법 + 해석 가이드 + 취약점)
- overview.md 진행표·최근 결정·다음 할 일

### 다음
- TASK-002(BGE-M3 임베딩 교체)는 현재 지표로 필요성이 **강하지 않음** (Hit@3=1.0, faithfulness 0.886). 즉시 착수 권장 대상 아님
- 낮은 지표는 **answer_relevancy 0.648** → 프롬프트 간결화가 저비용 후속 실험 후보 (별도 태스크로 제안 가능)

---

## [2026-04-22] impl | TASK-003 완료 — LLM 백엔드 토글 인프라 (ADR-014)

### 코드
- `apps/config.py`: `llm_backend`, `llm_base_url`, `llm_api_key`, `llm_model`, `llm_temperature(str)` 5개 필드 추가. 기존 `openai_chat_*`는 legacy fallback으로 유지
- `.env(.example)`: `LLM_BACKEND`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE` 추가 (기본값 비움 → openai/gpt-4o-mini)
- `packages/llm/chat.py` 재작성:
  - `_BACKENDS` 맵(openai/glm/custom), `_resolve()`로 우선순위 해석
  - `ChatOpenAI(base_url=..., api_key=..., model=..., temperature=...)` 하나로 모든 OpenAI-호환 공급자 처리
- `packages/rag/pipeline.py`: `tracing_context` 태그·메타에 `llm:<backend>`, `llm_backend`, `llm_model` 추가. query 로그 포맷에 `llm=backend:model` 포함
- `llm_temperature`는 Pydantic 빈 문자열 → float 파싱 실패를 피하려 `str`로 받고 내부 파싱

### 검증
- 기본 `LLM_BACKEND=openai`로 `/query` 정상 응답 (gpt-4o-mini, 이전 동작 회귀 없음)
- 로그: `질의: '...' (reranker=bge-m3, llm=openai:gpt-4o-mini)`
- LangSmith: `llm:openai` 태그 + `llm_model=gpt-4o-mini` 메타 확인

### 관련 페이지
- architecture/decisions.md ADR-014 신규
- changelog.md [0.7.0], roadmap.md(TASK-003 완료 처리 + 실행 큐 진행), overview.md(기술 스택·다음 할 일·최근 결정)

### 다음
- 실행 큐: **TASK-003 ✅ → TASK-004 (다음)** — 품질 측정 프레임워크
- GLM 실전 전환은 TASK-004 수치로 근거 확보 후 별도 결정

---

## [2026-04-22] queue | TASK-004 — 품질 측정 프레임워크 큐잉 + 실행 순서 원칙 명시

- 실행 원칙: 태스크 순차 진행, 병렬 금지. 앞 태스크 종료(문서화 포함) 후 다음 착수
- 현재 큐: TASK-001 ✅ → TASK-003 (다음) → TASK-004 → (필요 시) TASK-002
- TASK-004 구성:
  - Phase 1: `bench_retrieval.py` — Precision@3 / Recall@3 / MRR (2~3시간)
  - Phase 2: `bench_answers.py` — Ragas(faithfulness, answer_relevance, context_precision/recall) + LangSmith Dataset 자동 업로드 (반나절)
  - 산출물: `features/evaluation.md` 전면 개편, ADR-015, changelog [0.8.0]
- 이후 모든 품질 실험의 정량 근거로 사용 (ADR에 before/after 수치 첨부 원칙)
- 재인덱싱 불필요, 저위험

---

## [2026-04-22] queue | TASK-003 — LLM 백엔드 토글 큐잉

- ADR-013의 연장선에서 교체 자체는 보류, **교체 가능성만 선제로 확보**하는 인프라 작업
- 서브태스크·완료 기준·주의사항 → roadmap.md 단기 섹션
- 기본값 `LLM_BACKEND=openai` 유지 (회귀 0 보장)
- 재인덱싱 불필요, 저위험

---

## [2026-04-22] decision | LLM 공급자 — gpt-4o-mini 유지 (ADR-013)

- GLM으로의 교체 검토: 한국어 품질·비용면에서 매력 있으나 컨텍스트 준수·안전 필터·생태 안정성에서 OpenAI 우위
- 코드 변경 없음. 추후 비용/데이터 주권 이슈 생기면 `.env` 토글 패턴으로 쉽게 교체 가능 (설계 메모 유지)

---

## [2026-04-22] issue | ISSUE-001 등록 — 모바일 파일 업로더 미동작

- 증상: 모바일 브라우저에서 Streamlit `file_uploader`가 선택한 파일을 표시/전송하지 못함
- 원인 가설: HTTP 평문 + WebSocket 업로드, 또는 Streamlit 1.56.0 모바일 회귀, 또는 MIME 정책
- 임시 회피: PC 업로드, 모바일은 `/query`만 사용
- 해결 방향: HTTPS 리버스 프록시 배포 후 재검증이 우선 조치
- 관련 페이지: `wiki/issues/open/ISSUE-001-...md`, `wiki/troubleshooting/common.md`, `overview.md` 열린 이슈

---

## [2026-04-22] impl | TASK-001 완료 — Reranker 다국어화 (BGE-reranker-v2-m3)

### 코드
- `packages/rag/reranker.py` 신설: `Reranker` 프로토콜 + `FlashRankReranker` + `BgeM3Reranker` + `get_reranker()` 팩토리 싱글톤
- `packages/rag/retriever.py` 재작성: reranker 주입형
- `packages/rag/pipeline.py`: `RAGPipeline(reranker=...)` 생성자에 추가, `query()`에 `tracing_context(tags=["reranker:<backend>"])` 태깅
- `apps/dependencies.py`: 설정값 기반 reranker 생성
- `apps/main.py`: `reranker_warmup=true`일 때 lifespan에서 더미 rerank로 모델 preload
- `apps/config.py` + `.env(.example)`: `RERANKER_BACKEND`, `RERANKER_MODEL_NAME`, `RERANKER_WARMUP` 3개 변수
- `requirements.txt`: `sentence-transformers>=3.0` 추가

### 검증
- 5개 질의 A/B 비교 완료 → [evaluation.md](wiki/features/evaluation.md)
- 완료 기준 충족: "ROS의 주요 구성요소는?" 질의가 BGE-M3에서 Learning ROS를 1위(0.588)로, 기존 FlashRank는 한국어 딥러닝 목차를 1위(0.998)로 오인하던 문제 해결
- E2E `/query` 답변 정확도 확인 ("파일 시스템 레벨 / 계산 그래프 레벨 / 커뮤니티 레벨")
- LangSmith 트레이스에 backend 태그 기록 확인

### 관련 페이지
- architecture/decisions.md ADR-012 신규, ADR-011 한계가 ADR-012에서 해결됨으로 연결
- changelog.md [0.6.0], overview.md 진행표·기술 부채 개정, roadmap.md TASK-001 완료 처리

### OpenAI/LangSmith 키
- 이전 세션에서 평문 노출된 키들 revoke·교체 완료. 새 OpenAI 키로 스모크 테스트 성공

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
