# Wiki Log

이 파일은 append-only입니다. 항목을 수정하지 말고 새 항목을 위에 추가하세요.
`grep "^## \[" log.md | head -10` 으로 최근 항목을 빠르게 확인할 수 있습니다.

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
