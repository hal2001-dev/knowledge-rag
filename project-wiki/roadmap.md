# 로드맵

**상태**: active
**마지막 업데이트**: 2026-04-28
**관련 페이지**: [overview.md](overview.md), [features.md](wiki/requirements/features.md)

---

## 마일스톤

| 마일스톤 | 목표일 | 상태 | 내용 |
|----------|--------|------|------|
| M1: 기반 구축 | 2026-04-19 | `done` | Docling 파싱, Qdrant 인덱싱, PostgreSQL 메타데이터 |
| M2: 검색 동작 | 2026-04-19 | `done` | 쿼리 → Qdrant → FlashRank reranking → gpt-4o-mini E2E |
| M3: 품질 개선 | - | `todo` | 청킹 최적화, 임베딩 모델 실험, 평가 지표 도입 |
| M4: API 제공 | 2026-04-19 | `done` | FastAPI REST API 4개 엔드포인트, Streamlit UI |
| M5: 배포 | - | `todo` | 운영 환경 배포, 모니터링 |

---

## 단기 (이번 스프린트)

### 실행 순서 원칙
**태스크를 병렬로 진행하지 않는다.** 앞 태스크(문서화·ADR·위키 반영 포함)가 완전히 종료된 뒤 다음 태스크를 시작한다.

#### 실행 큐 (확정)
```
✅ TASK-001 → ✅ TASK-003 → ✅ TASK-004 → ✅ TASK-002 → ✅ TASK-005
→ ✅ TASK-007 → ✅ TASK-008 → ✅ TASK-009 → ✅ TASK-010 → ✅ TASK-011
→ ✅ TASK-014 (2026-04-25 완료, ADR-024) — 문서 자동 요약 (gpt-4o-mini, JSONB 캐시, BackgroundTasks 훅)
→ ✅ TASK-015 (2026-04-25 완료, ADR-025) — 카테고리 메타데이터 + 자동 분류 (룰 매칭 + LLM fallback, 단일 컬렉션 + payload 인덱스)
→ ✅ TASK-016 (2026-04-25 완료, ADR-026) — 도서관 탭 + doc_filter 라우팅 (카테고리 그룹 카드 그리드, "이 책에 대해 묻기")
→ ✅ TASK-017 (2026-04-25 완료, ADR-027) — 랜딩 카드 v2 (카테고리 분포·주제 칩·최근 문서 카드)
→ ✅ TASK-018 (2026-04-25 완료, ADR-028) — 색인 워커 분리 (Postgres `ingest_jobs` 큐 + indexer 프로세스, SKIP LOCKED claim, advisory lock 마이그레이션 race 해소)
→ ✅ TASK-021 (2026-04-28 완료, ADR-031) — 프로젝트 프로세스 정기 모니터링 + 워커 RSS 가드 (launchd 5분 스냅샷 + 30초 가드, ISSUE-005 누명 사건 후속, 모의 SIGTERM 테스트 통과)
→ ⚙️ TASK-019 (Phase A 완료·Phase B 재개 차례, 2026-04-28) — 사용자 UI NextJS 분리 + Clerk 인증. ADR-030
→ 🕐 TASK-012 (후순위, 2026-04-23 큐잉) — Cloudflare Tunnel + Access 외부 노출 게이트웨이 (코드 0줄, 운영 문서 중심)
→ 🕐 TASK-013 (후순위, 2026-04-23 큐잉) — MkDocs Material + GitHub Pages 문서 사이트 (현재 project-wiki/ 구조 유지, CI 자동 배포)
→ ✅ TASK-020 (2026-04-28 완료) — Series/묶음 문서 1급 시민 (ADR-029, changelog 0.26.0)
→ 🛑 인증·공개배포 전체 묶음 (사용자 지시까지 전부 보류, 2026-04-22)
     · ISSUE-001 (모바일 업로드) · 관리자 UI 2단계 · HTTPS 배포 · 앱 내 API 키/OAuth · 관리자 전용 UI 버튼
→ 🔄 장기 검토: Graph RAG, MCP 재개, 대화 요약, 스트리밍, L2 중복 감지
```

**TASK-012 주의**: 후순위. 사용자가 도메인을 Cloudflare에 이전하고 착수 지시할 때 진행. 이 작업은 **인증·공개배포 묶음 전체 해제가 아님** — "외부 테스트 접근 게이트" 최소 조각만 꺼낸 것. ISSUE-001·관리자 UI 2단계·앱 내 인증은 계속 보류.

#### 사용자 관점 개선 경로 (요약)
| 단계 | 완료 시 체감 변화 |
|---|---|
| TASK-007 | 답변 아래에 "이어서 물을 질문 3개" 자동 배지 — 클릭으로 탐색 연쇄 |
| TASK-008 | 빈 채팅에 "이 시스템이 아는 내용" 요약 + 예시 질문 5개 |
| TASK-009 | 문서 삭제 시 디스크까지 완전 정리 + 긴 청크 누락 제거 |
| **TASK-010** | **폴더 단위 일괄 색인 CLI** — 한 명령으로 수십~수백 개 문서 자동 등록, 중복 건 스킵, 실패 리포트** |
| TASK-011 | 하이브리드 검색(BM25 + dense + RRF, Kiwi 한국어 전처리) — 정확 용어·숫자 매칭 여력 확보 |
| (후순위) TASK-012 | Cloudflare Tunnel + Access 외부 노출 게이트웨이 — 이메일 OTP 하나로 외부 테스트 가능, 앱 코드 수정 0 |
| (후순위) TASK-013 | MkDocs Material + GitHub Pages — 현재 위키 구조를 손대지 않고 정적 사이트·검색·사이드바 확보 |
| **TASK-019** | **사용자 UI NextJS 분리 + Clerk 인증 — 관리자 UI(문서·잡·시스템·평가)는 Streamlit 잔류·동결. 사용자(채팅·도서관·대화)는 NextJS thin client. 인증·공개배포 묶음에서 "앱 내 인증" 항목만 부분 해제** |
| (후순위) TASK-020 | Series/묶음 문서 — 30챕터로 쪼개진 책을 한 시리즈로 묶어 검색·도서관·스코프 통합. 색인 시점 자동 묶기 + 관리자 사후 검수 |
| **TASK-014** | **문서별 자동 요약(한 줄 + 개요 + 주제 + 예시 질문) 영구 캐시 — 카탈로그·랜딩·소스 카드 공용 데이터** |
| **TASK-015** | **doc_type/category/tags 자동 채움 — 사용자 입력 부담 없이 카탈로그 그룹핑·검색 필터 활성화 가능** |
| **TASK-016** | **"도서관" 탭 — 인덱싱된 전체 문서를 카테고리별로 일람, 요약 클릭 한 번에 해당 문서로 질문 시작** |
| **TASK-017** | **랜딩 카드 확장 — 빈 채팅에서 주제 칩·최근 추가 문서·"이 시스템이 아는 것" 즉시 노출** |
| (보류) 인증·공개배포 묶음 | 모바일 업로드, 앱 내 인증, 관리자/사용자 경로 분리, 재인덱싱/벤치 버튼 — 사용자 지시까지 전부 보류 |

상세 개선점은 [overview.md](overview.md)의 "예정 태스크 완료 시 사용자 개선점" 섹션 참고.

---

철회: ~~TASK-006 (RAG → MCP 서버)~~ — 사용자 판단으로 현재 시스템 범위에서 제외 (장기 검토 목록으로 이동)

### ~~TASK-001: BGE-reranker-v2-m3 도입 (재순위 다국어화)~~ — ✅ 완료 (2026-04-22)
→ ADR-012, changelog [0.6.0], [evaluation.md](wiki/features/evaluation.md) 참고

**우선순위**: 최우선
**배경**: 현재 FlashRank `ms-marco-MiniLM-L-12-v2`는 영어 학습 cross-encoder라 한국어 질의 + 영문 문서 크로스에서 오작동. "ROS의 주요 구성요소는?" 질의가 한국어 딥러닝 문서의 "CONTENTS" 섹션을 0.988점, 실제 ROS 청크를 0.059점으로 평가한 사례 확인 (ADR-011)
**목표**: 한↔영 크로스 retrieval 품질을 가시적으로 개선
**범위**: 재순위 단계만. 임베딩(`text-embedding-3-small`)·Qdrant 컬렉션은 유지 → **재인덱싱 불필요**

**서브태스크**:
- [ ] 의존성 추가 — `FlagEmbedding` 또는 `sentence-transformers` 중 채택 결정 (FlagEmbedding이 BGE 공식)
- [ ] `.env`에 `RERANKER_BACKEND=flashrank|bge-m3` 토글 변수 + `RERANKER_MODEL_NAME` 추가
- [ ] `apps/config.py`에 동일 필드 추가
- [ ] `packages/rag/retriever.py` 재작성:
  - 추상화: `class Reranker(Protocol): def rerank(query, candidates, top_n) -> list[ScoredChunk]`
  - 구현 2종: `FlashRankReranker`, `BgeM3Reranker` (`BAAI/bge-reranker-v2-m3`)
  - 모델 로드는 프로세스 전역 싱글톤 + 첫 호출 시 lazy init
- [ ] 첫 로드 시간(~30~60초)을 `apps/main.py` lifespan에서 미리 warm-up할지 결정
- [ ] 동일 질의 5건으로 A/B 비교 표 작성, [features/evaluation.md](wiki/features/evaluation.md)에 기록:
  - "ROS의 주요 구성요소는?" / "Robotics Programming 방법은?" / "자율 주행" 등 한↔영 혼합
  - 측정: top-3 소스의 doc_id, 점수, 관련 여부 (수동 라벨)
- [ ] LangSmith 트레이스에 `reranker.backend` 메타데이터 태그 추가
- [ ] 기본값 결정: A/B 결과에 따라 `RERANKER_BACKEND=bge-m3`을 기본으로 할지, flashrank 유지하고 옵트인할지
- [ ] ADR-011 업데이트 또는 ADR-012 신규 작성 (결과 + 결정)
- [ ] changelog.md `[0.6.0]` 항목 추가

**완료 기준**: 동일 한국어 질의에서 ROS 영문 청크가 top-3에 진입, 무관한 한국어 딥러닝 문서가 1위로 올라가는 사례가 사라짐

**주의사항**:
- `bge-reranker-v2-m3` 모델은 ~570MB 다운로드 (HuggingFace Hub)
- GPU 없으면 청크당 100~300ms 추가 latency — `initial_k=20`이면 +2~6초. `initial_k`를 10으로 낮추는 옵션도 같이 고려
- 메모리 ~2GB 추가 점유

### ~~TASK-002: BGE-M3 임베딩 도입~~ — ✅ 완료 (2026-04-22)
→ ADR-016, changelog [0.9.0]
결과: A/B 비교 후 **OpenAI 기본 유지 + BGE-M3 토글 확보**. Retrieval 지표 동률, Answer 소폭 하락, 기본 전환은 보류. 토글 인프라는 구축됨.

### ~~TASK-003: LLM 백엔드 토글 (OpenAI ↔ GLM 등 OpenAI-호환 엔드포인트)~~ — ✅ 완료 (2026-04-22)
→ ADR-014, changelog [0.7.0]

**우선순위**: 중 (ADR-013에 이어 인프라만 선제 구축)
**배경**: ADR-013에서 gpt-4o-mini 유지로 결론 — 단, 향후 비용/데이터 주권/A-B 실험 필요 시 1시간 내 교체 가능한 **토글 인프라**를 지금 만들어 두면 결정만 `.env` 한 줄로 바뀜. 이미 Reranker에서 성공적으로 쓴 패턴(ADR-012)을 LLM에도 동일하게 적용.
**목표**: `.env`의 `LLM_BACKEND` 값만 바꿔 OpenAI / GLM / DeepSeek / Qwen 등 OpenAI-호환 엔드포인트로 즉시 전환 가능
**범위**: LLM 호출 경로만. 임베딩·Qdrant·Reranker 건드리지 않음 → **재인덱싱 불필요**, 품질 저하 위험 최소

**서브태스크**:
- [ ] `.env(.example)`에 추가:
  - `LLM_BACKEND=openai`  # `openai|glm|custom` (OpenAI-호환 전용)
  - `LLM_BASE_URL=`       # 빈 값이면 backend별 기본값
  - `LLM_API_KEY=`        # 빈 값이면 `OPENAI_API_KEY` fallback (OpenAI 호환용)
  - `LLM_MODEL=`          # 빈 값이면 backend별 기본값
  - `LLM_TEMPERATURE=0.0`
- [ ] `apps/config.py`에 동일 필드 추가. 기존 `openai_chat_model`/`openai_chat_temperature`는 **legacy**로 남기고 `build_chat`가 신규 필드 우선, 비어있으면 legacy로 fallback
- [ ] `packages/llm/chat.py` 재작성:
  - backend별 기본값 맵 (예: `openai → https://api.openai.com/v1, gpt-4o-mini`; `glm → https://open.bigmodel.cn/api/paas/v4/, glm-4-flash`)
  - `ChatOpenAI(model=..., openai_api_base=..., openai_api_key=..., temperature=...)` 하나로 통일 (GLM·DeepSeek·Qwen 모두 OpenAI-호환이라 타입 힌트·의존성 유지)
- [ ] 타입 힌트 확인 — [packages/rag/pipeline.py](../packages/rag/pipeline.py), [packages/rag/generator.py](../packages/rag/generator.py)의 `ChatOpenAI` 힌트는 유지 가능 (반환형이 동일)
- [ ] LangSmith 태깅 — `RAGPipeline.query`의 `tracing_context`에 `llm_backend`·`llm_model` 메타 추가 (ADR-012의 reranker 태깅과 동일 패턴)
- [ ] 기본값: **`LLM_BACKEND=openai`, 모델 `gpt-4o-mini` 유지** (ADR-013 결론)
- [ ] 스모크 테스트: `LLM_BACKEND=openai`에서 기존 동작 회귀 없음 확인. GLM 키가 있다면 `LLM_BACKEND=glm`으로 동일 질의 1건 테스트
- [ ] (선택) A/B 비교 — TASK-001과 동일 5개 질의로 `features/evaluation.md`에 추가 (GLM 키 없으면 skip)
- [ ] ADR-014 신규 작성 (토글 인프라 결정 + 기본값 유지 논리 + 확장 경로)
- [ ] changelog.md `[0.7.0]` 항목 추가
- [ ] `tests/conftest.py`의 `patch("langchain_openai.ChatOpenAI")` 확인 — 경로 불변이라 수정 불필요할 것 (재검증만)

**완료 기준**:
1. `.env`의 `LLM_BACKEND=openai`로 기존과 동일 동작 (회귀 없음)
2. `LLM_BACKEND=glm` + GLM 키로 `/query` 정상 응답 (스모크만)
3. LangSmith 트레이스에 `llm_backend=openai|glm` 메타 가시성
4. ADR-014·changelog 반영

**주의사항**:
- GLM 프롬프트에서 `temperature=0.0`일 때 출력 매우 짧아지는 경향 보고 — GLM 선택 시 0.3~0.5 권장. 토글 시 `LLM_TEMPERATURE` 기본값 분기 고려
- GLM은 안전 필터가 강해 특정 주제(정치·역사·일부 기술)가 응답 거부될 수 있음 — 문서 전반에 해당 주제가 있다면 기본값 유지가 맞음
- 공식 OpenAI-호환이 아닌 공급자는 `n`, `logprobs`, `tool_choice` 등 일부 파라미터 미지원 — `ChatOpenAI`가 보내는 기본 파라미터만 쓰는지 확인
- API 키는 절대 채팅·커밋에 평문 공유 금지 ([security.md](security.md))

### ~~TASK-004: 품질 측정 프레임워크 — Retrieval 지표 + LLM-judge (Ragas + LangSmith)~~ — ✅ 완료 (2026-04-22)
→ ADR-015, changelog [0.8.0], [evaluation.md](wiki/features/evaluation.md)

**우선순위**: 중 (TASK-003 완료 후 착수)
**전제**: TASK-003이 완전히 끝난 상태여야 함. 그래야 LLM 백엔드별 품질 차이를 동일 측정 도구로 A/B 가능.
**배경**: 지금까지의 개선(HybridChunker, FlashRank→BGE-m3, heading breadcrumb, 정규화)이 체감은 좋아졌지만 **정량 근거가 없음**. 앞으로의 실험(임베딩 교체, 하이브리드 검색, 프롬프트 튜닝)도 수치 없이는 판단이 어렵다.
**목표**: 단일 명령으로 Precision@3 / MRR / Faithfulness / Answer Relevance / Context Precision 을 산출, LangSmith에 축적
**범위**: 측정 인프라만. 품질 개선 시도는 별도 태스크

**Phase 1 — 레벨 1 (Retrieval 정량 기반선, 2~3시간)**:
- [ ] `tests/eval/dataset.jsonl` 신설 — 질의 10~20개 + 각 질의의 정답 `doc_id` 리스트
  - 현재 인덱싱된 문서군(ROS 영문 / 한국어 딥러닝) 기준으로 TASK-001 5개 질의를 베이스로 확장
  - 필드: `{"question": ..., "expected_doc_ids": [...], "language": "ko|en|mixed", "note": ...}`
- [ ] `scripts/bench_retrieval.py` 작성:
  - dataset을 읽고 각 질의를 `retrieve()`로 실행 → top-3 doc_id 수집
  - Precision@3, Recall@3, MRR 계산
  - reranker backend별로 표 출력 (flashrank vs bge-m3 회귀 감시용)
  - 결과를 `data/eval_runs/{YYYY-MM-DD_HHmmss}.json`에 저장
- [ ] `features/evaluation.md`의 "현재 최신 지표" 표를 실제 수치로 갱신
- [ ] 완료 기준: 동일 명령(`python scripts/bench_retrieval.py`) 재실행 시 수치 재현 가능

**Phase 2 — 레벨 2 (답변 품질, Ragas + LangSmith, 반나절)**:
- [ ] 의존성 추가 — `ragas` + `datasets` (requirements.txt)
- [ ] `scripts/bench_answers.py` 작성:
  - 동일 dataset 사용, `/query` 호출 결과의 `{question, answer, sources}`를 Ragas 입력 포맷으로 변환
  - Ragas metric: `faithfulness`, `answer_relevance`, `context_precision` (정답 doc_id 있으므로 `context_recall`도)
  - judge LLM은 `gpt-4o-mini` 기본 (비용·일관성)
  - LangSmith Dataset에 자동 업로드 (`client.create_examples`, `client.evaluate`)
- [ ] LangSmith UI에서 실행 이력 확인 — 같은 Dataset에 대한 reranker/LLM backend별 실험이 누적
- [ ] `features/evaluation.md`에 Phase 2 지표 섹션 추가
- [ ] 완료 기준: 한 번의 명령으로 5종 지표 + LangSmith run 업로드까지 자동 수행

**공통 — 문서화**:
- [ ] ADR-015 신규 — "측정 프레임워크 채택: Ragas + LangSmith Evaluators"
- [ ] changelog.md `[0.8.0]` 항목
- [ ] `features/evaluation.md` 전면 개편 (레벨 1·2 실행 방법 + 최신 지표 + 해석 가이드)
- [ ] roadmap.md TASK-004 완료 처리

**완료 기준(전체)**:
1. `bench_retrieval.py` 1회 실행으로 Precision@3·Recall@3·MRR 산출 재현
2. `bench_answers.py` 1회 실행으로 Ragas 5종 지표 산출 + LangSmith Dataset에 기록
3. 이후 TASK 실행 시 before/after 수치 비교가 표준 관행이 됨 (후속 모든 ADR에 수치 첨부 원칙)

**주의사항**:
- Ragas 지표 계산 자체가 LLM 호출을 다수 유발 — 10개 질의 × 5개 metric ≈ 50+ API call. 비용 모니터링
- judge LLM이 gpt-4o-mini면 편향·자기평가 경향 주의 — 가능하면 judge는 gpt-4o 또는 별도 모델로 고정
- dataset은 과적합 위험 — 튜닝에 사용한 질의가 그대로 평가 세트면 수치는 좋아 보여도 현실 성능은 아님. 평가 전용 질의 5~10개는 실험에서 제외
- 라벨 수작업 비용이 병목 — 초기 10~20개부터 시작하고 점진 확대

### ~~TASK-005: 관리자 UI (1단계, Streamlit 탭 기반)~~ — ✅ 완료 (2026-04-22)
→ ADR-017, changelog [0.10.0], [admin_ui.md](wiki/features/admin_ui.md)

**우선순위**: 중 (ISSUE-001/운영 배포와 연계되나 단독으로도 이득 큼)
**배경**: 문서·대화·설정·벤치 결과가 분산되어 (`.env`, Qdrant 대시보드, `data/eval_runs/*`, LangSmith) 운영 가시성 낮음. 대화 세션은 CRUD API만 있고 UI가 없어 누적만 된다. 설정 백엔드(Reranker/LLM/Embedding 토글)가 현재 어떤 값인지 UI에서 확인 불가.
**범위**: 1단계(옵션 A) — **현 Streamlit 앱에 탭 추가만**, 별도 페이지·인증·React 없음. 2단계(B, `/admin` 분리 + 패스워드)는 HTTPS 배포/ISSUE-001 해결 시점에 승격

**서브태스크**:
- [ ] `ui/app.py` 레이아웃 개편 — `st.tabs(["채팅", "문서", "대화", "시스템", "평가"])` 구조로 전환. 기존 사이드바 업로드는 유지
- [ ] 탭 **문서**: `/documents` 목록 + 삭제 + 업로드(현 기능 이전) + **청크 미리보기** (Qdrant scroll API로 해당 doc_id의 청크 5~10개 표시, heading_path·page·content_type·score 컬럼)
- [ ] 탭 **대화**: `/conversations` 목록 (최근 업데이트 순) + 선택 시 `/conversations/{id}` 메시지 뷰 + 삭제 버튼. 빈 세션·오래된 세션 일괄 정리 도우미
- [ ] 탭 **시스템**: 현재 설정 카드 출력
  - Reranker(`reranker_backend`), LLM(`llm_backend:llm_model`), Embedding(`embedding_backend`·`embedding_dim`) 3개
  - Qdrant 컬렉션 이름·dim·포인트 수·상태 (`QdrantClient.get_collection`)
  - `/health` 상태
  - LangSmith 프로젝트 링크 버튼 (`langchain_project`)
  - **변경 UI는 포함하지 않음** — `.env` 편집 후 서버 재시작 안내만 (읽기 전용)
- [ ] 탭 **평가**: `data/eval_runs/` 최신 `retrieval_*.json` / `answers_*.json` 파싱 → 최신 지표 카드 + 최근 5회 히스토리 표. "지금 실행" 버튼은 1단계에서 제외(블로킹 이슈)
- [ ] 읽기 API 보완 확인 — 청크 미리보기에 필요한 `QdrantDocumentStore.scroll_by_doc_id(doc_id, limit)` 메서드 있는지 점검, 없으면 추가
- [ ] 세션 상태 설계 — `st.session_state["active_tab"]`, `st.session_state["selected_session_id"]`, 탭 전환 시 상태 유실 방지
- [ ] UI 스모크: 문서·대화 CRUD 전체 플로우 1회 클릭 시나리오 통과
- [ ] 스크린샷 2~3장 → `wiki/features/admin_ui.md` 신규 (간단한 사용법 가이드)
- [ ] ADR-017 신규 — "관리자 UI 단계적 도입: 1단계=탭, 2단계=/admin 분리+인증, 3단계=전용 대시보드"
- [ ] changelog `[0.10.0]` 항목
- [ ] roadmap TASK-005 완료 처리, overview·log 반영

**완료 기준**:
1. Streamlit 좌측 탭 5개가 정상 전환되고 각 탭이 기능 동작
2. 문서 탭에서 업로드/삭제/청크 미리보기까지 막힘 없음
3. 대화 탭에서 세션 목록·메시지 뷰·삭제 동작
4. 시스템 탭이 현재 설정값을 올바르게 반영 (reranker/llm/embedding/Qdrant 4개 카드)
5. 평가 탭이 `data/eval_runs/`의 최신 결과를 표시

**주의사항**:
- 1단계는 **인증 없음** — LAN 내부에서만 접속해야 함 (HTTPS/인증은 옵션 B로 미루기)
- Qdrant `scroll`은 `metadata.doc_id` 필터로 호출해야 함 (ADR-005 참고)
- `data/eval_runs/*.json`은 계속 커지므로 최근 N개만 표시 (오래된 것 자동 삭제는 별도 태스크)
- UI 개편이 세션 상태에 영향 — 기존 채팅 `messages`·`session_id`는 **채팅 탭 안에서** 유지되어야 함. 탭 전환으로 유실되면 안 됨
- 배포 단계로 가면 옵션 B(/admin 분리 + 패스워드)로 승격 필요 — 1단계를 운영에 그대로 노출 금지

**후속(옵션 B로 승격될 때 추가될 것)**:
- `ui/pages/admin.py`로 분리, `ADMIN_PASSWORD` 환경변수 게이트
- 재인덱싱·벤치 실행 비동기 버튼
- 설정 토글(수정 후 서버 재시작 예약)

### ~~TASK-006: RAG를 MCP 서버로 노출~~ — 🚫 철회 (2026-04-22)
**상태**: 현재 시스템 범위에서 제외. 아래 원본 정의는 참고용으로 보존. 재개 시 장기 목록에서 선택해 신규 태스크(TASK-NNN)로 재등록할 것.
**사유**: 사용자 판단 — 현재 시스템에서 MCP 서버 노출은 불필요. Claude Code 통합은 장기 검토 목록으로 이동

**원본 정의 (참고용, 코드 작업 금지)**:
**우선순위**: 중 (프로젝트 코어 품질 영향 0. 본인 개발 흐름 개선)
**배경**: 이 프로젝트의 인덱스가 쌓여가는데 Claude Code로 다른 일을 할 때 이 지식을 불러 쓸 방법이 없음. MCP로 익스포트하면 Claude Code(및 Cursor 등 MCP 클라이언트)에서 `search_docs`, `list_docs` 같은 tool로 붙일 수 있어 "내 개인 RAG"가 자연스럽게 도구화됨.
**목표**: stdio MCP 서버를 추가해 Claude Code `.mcp.json` 또는 `.claude/settings.local.json`에서 붙이면 즉시 질의 가능
**범위**: **최소 2개 tool만**. 관리 기능(업로드·삭제·벤치)은 기존 웹 UI에 남김

**서브태스크**:
- [ ] 의존성 추가 — `mcp` (MCP Python SDK, `pip install mcp`)
- [ ] `apps/mcp_server.py` 신설 — stdio 서버
  - 기존 `RAGPipeline`·`QdrantDocumentStore`·`get_reranker()` 재사용 (코드 중복 금지)
  - tool `search_docs(query: str, top_k: int = 3) -> list[{title, doc_id, page, heading_path, excerpt, score}]`
    · 내부적으로 `RAGPipeline.query`를 호출하되 LLM 답변 생성은 생략(retrieve+rerank 결과만 반환)
    · **또는** `retrieve()` 직접 호출로 토큰 비용 0
  - tool `list_docs() -> list[{doc_id, title, file_type, chunk_count, indexed_at}]`
    · PostgreSQL `list_documents(db)` 결과 반환
- [ ] 진입점: `python -m apps.mcp_server` 로 stdio 실행
- [ ] `README`/`wiki/features/` 또는 신규 `wiki/integrations/mcp.md`에 Claude Code 붙이는 법 기록
  - 예시 `.mcp.json`:
    ```json
    {
      "mcpServers": {
        "knowledge-rag": {
          "command": "/Users/hal2001/workspace/projects/personal/knowledge-rag/.venv/bin/python",
          "args": ["-m", "apps.mcp_server"],
          "cwd": "/Users/hal2001/workspace/projects/personal/knowledge-rag"
        }
      }
    }
    ```
- [ ] 스모크 테스트 — Claude Code 세션에서 `search_docs("ROS의 주요 구성요소는?")` 호출 결과가 기존 `/query` 출력의 `sources`와 일치하는지
- [ ] LangSmith 트레이스에 `mcp_tool` 태그 추가(기존 `tracing_context` 확장) — MCP 경유 호출도 관측 가능
- [ ] ADR-018 신규 — "RAG를 MCP 서버로 익스포트: 최소 2 tool, 관리 기능 제외" *(TASK-006 철회로 미작성. 재개 시 신규 번호로 재할당)*
- [ ] changelog `[0.11.0]` 항목
- [ ] requirements.txt 업데이트

**완료 기준**:
1. `python -m apps.mcp_server` 가 stdio에서 MCP 핸드셰이크 응답 정상
2. Claude Code에 `.mcp.json` 연결 후 `search_docs`·`list_docs` 둘 다 호출 성공
3. 반환 결과가 웹 UI `/query` sources와 동일 doc_id/score
4. ADR-018·changelog 반영 *(TASK-006 철회로 미발행. 재개 시 다음 가용 번호 사용)*

**의도적으로 제외 (단계적 확장)**:
- `ingest_doc`, `delete_doc` — 관리 기능은 웹 UI에만 (보안·경쟁 상태)
- `get_doc_chunks` — 필요 시 TASK-006 이후 추가
- HTTP 서버 모드, 인증 — stdio 로컬 전용이라 불필요
- 원격 MCP 호스팅 — ISSUE-001 해결(HTTPS) 이후 검토

**주의사항**:
- MCP 서버는 **웹 API 서버(`uvicorn`)와 별도 프로세스**. Qdrant·Postgres 연결은 공유하지만 FastAPI 의존성 주입 시스템 대신 `build_embeddings()`·`get_reranker()` 직접 호출 필요
- `apps/config.py`의 `lru_cache`된 `get_settings()`는 MCP 프로세스에서도 동일하게 동작
- stdio 서버는 `stdout`에 JSON-RPC만 써야 함 — logger가 stdout에 찍으면 프로토콜 깨짐. **로그 핸들러를 `stderr`로** 설정 확인 필요
- Claude Code의 MCP 서버 재시작은 Claude Code 자체 재시작이 필요. `.mcp.json` 변경 후 Claude Code를 다시 열어야 반영됨

### ~~TASK-007: 후속 질문 제안 + 인덱스 커버리지 가시성~~ — ✅ 완료 (2026-04-22, Phase 1만)
→ ADR-019, changelog [0.12.0]

**Phase 1 완료**: 답변 후 3개 후속 질문 배지 + 클릭 재질의. 회귀 0 확인.
**Phase 2(빈 채팅 카드) 는 TASK-008로 승격**, Phase 3은 장기.

**우선순위**: 중 (UX 직결, Phase 1은 저비용)
**배경**: 현재 사용자가 "이 RAG가 무엇을 알고 있는지" 예측 불가. 답변이 나와도 **더 갈 수 있는 방향**을 스스로 찾아야 함. 인덱스에 있는 내용(ROS 영문 + 딥러닝 한국어 등)을 투명하게 보여주고, 각 답변에서 자연스러운 다음 질문을 제시해 탐색성을 높인다.
**목표**: (1) 답변 후 후속 질문 3개 자동 제안 + 배지 클릭 시 그 질문으로 즉시 재질의. (2) 빈 채팅 화면에 "이 시스템이 아는 내용 요약 + 예시 질문" 카드 표시
**범위**: Phase 1만 TASK-007로 먼저 구현. Phase 2/3은 결과 보고 별도 태스크로 승격

**Phase 1 — 답변 후 후속 질문 제안 (최소 구현)**:
- [ ] `packages/rag/generator.py` 프롬프트 확장:
  - 현재 `answer` 한 필드만 반환 → **`{"answer": "...", "suggestions": ["질문1", "질문2", "질문3"]}`** JSON 구조
  - OpenAI `response_format={"type":"json_object"}` 또는 JSON 모드로 구조 보장 (JSON 파싱 실패 시 suggestions=빈 리스트로 graceful degrade)
  - LLM에게 "답변의 맥락에서 사용자가 이어서 물어볼 만한 구체적 질문 3개"를 지시. 중복·메타질문(예: "더 있나요?") 금지 규칙 명시
- [ ] `apps/schemas/query.py`의 `QueryResponse`에 `suggestions: list[str] = []` 추가
- [ ] `packages/rag/pipeline.py`의 `query()` 반환 dict에 `suggestions` 포함
- [ ] `ui/app.py` 채팅 탭:
  - 답변 하단에 suggestions를 **클릭 가능한 배지** 3개로 (`st.button` 또는 columns로 나열)
  - 배지 클릭 시 `st.session_state["_pending_question"]`에 저장 → rerun → 자동 질의
  - 채팅 메시지 히스토리에도 suggestions 보존 (과거 메시지의 배지도 재클릭 가능)
- [ ] `.env`에 토글 `SUGGESTIONS_ENABLED=true|false`, `SUGGESTIONS_COUNT=3`
- [ ] `apps/config.py`에 동일 필드. 비활성 시 generator가 suggestions 생성 프롬프트 생략
- [ ] LangSmith 태그 — `tracing_context` 메타에 `suggestions_count` 추가
- [ ] 스모크: 동일 질의에서 suggestions 3개가 질문 형태로 생성되고, 클릭 시 재질의 플로우 성공
- [ ] ADR-019 신규 — "후속 질문 제안: LLM 단일 호출에 통합, JSON 구조화"
- [ ] changelog `[0.12.0]`

**Phase 2 — 빈 채팅 상태에 인덱스 커버리지 카드 (후속, TASK-007 종료 후 별도)**:
- 첫 진입 시 `GET /documents` + 상위 heading 통계로 "이 시스템이 아는 내용" 요약 생성
- 예시 질문 5개 — LLM이 인덱스 내용 요약을 보고 "사용자가 자연스럽게 물어볼 만한 5개 질문" 제안
- Streamlit 채팅 탭 empty state에 카드 + 예시 질문 배지
- 캐시: 문서 목록 변동 없으면 재계산 안 함

**Phase 3 — 탐색 사이드 패널 (더 나중)**:
- 답변의 sources heading_path에서 **형제 heading** 추출해 "같은 주제의 다른 절" 링크 제공
- 구현 규칙 기반 또는 heading 임베딩 유사도

**완료 기준 (Phase 1)**:
1. `/query` 응답에 `suggestions: list[str]` 항상 포함 (비활성 시 `[]`)
2. Streamlit 채팅 탭에서 suggestions 배지 3개 렌더, 클릭 시 재질의 작동
3. JSON 파싱 실패에도 answer는 정상 반환 (graceful degrade)
4. `SUGGESTIONS_ENABLED=false`로 토글 시 기존 동작 완전 복원 (회귀 0)
5. LangSmith에 suggestions 생성 기록

**의도적 제외 (Phase 1)**:
- **빈 채팅 카드, 예시 질문** — Phase 2로
- **형제 heading 사이드 패널** — Phase 3으로
- **사용자 클릭률 tracking / 추천 품질 평가 루프** — Phase 2 후 별도
- **MCP 서버 연동** — `search_docs` tool 응답에는 포함 안 함 (TASK-006 범위와 분리)

**주의사항**:
- LLM JSON 모드 미지원 모델(일부 GLM 변형)에서는 `response_format` 무시될 수 있음 — `llm_backend=glm`에서 스모크 추가
- 프롬프트에 "3개 생성"을 명시해도 LLM이 2개나 4개 반환할 수 있음 — 서버에서 `suggestions[:3]` 잘라 보정
- 답변이 "관련 문서를 찾지 못했습니다." 인 경우 suggestions는 빈 리스트로 강제 (무관한 질문 생성 방지)
- suggestions 생성은 기존 generate 호출에 통합되어 **추가 LLM 호출 0회**. 토큰만 약간 증가 (응답 +50~100토큰 예상)
- 한국어 질의에는 한국어 suggestions, 영문에는 영문으로 생성되도록 system prompt에 명시

### ~~TASK-008: 빈 채팅 인덱스 요약 카드 + 예시 질문 (TASK-007 Phase 2)~~ — ✅ 완료 (2026-04-22)
→ ADR-020, changelog [0.13.0]

**우선순위**: 중 (TASK-007 완료 후)
**전제**: TASK-007 코드·ADR·changelog 종료 후 착수
**배경**: 새 사용자가 채팅 창에 들어와도 "뭘 물어야 할지" 모름. 현재 인덱싱된 문서를 자연어로 요약해 첫 화면에 보여주면 온보딩 효과가 큼.

**서브태스크**:
- [ ] `apps/routers/documents.py`에 `GET /index/overview` 엔드포인트 추가 — 반환: `{doc_count, title_list, top_headings, suggested_questions: [5]}`
- [ ] 구현: `GET /documents` + 각 문서의 상위 heading 집계(Qdrant scroll로 limit 소량 + heading_path 빈도) + LLM 1회 호출로 예시 질문 5개 생성
- [ ] **캐싱**: 문서 목록 변동 없으면 인메모리 캐시 (업로드·삭제 시 무효화). LLM 반복 호출 방지
- [ ] `ui/app.py` 채팅 탭 empty state — `len(messages) == 0`일 때 카드 렌더:
  - 상단: "이 시스템이 아는 내용" 2~3줄 요약
  - 중단: 예시 질문 5개 배지 (클릭 시 `st.session_state["_pending_question"]`으로 즉시 질의)
- [ ] `.env` 토글 `INDEX_OVERVIEW_ENABLED=true|false`
- [ ] ADR-020 신규
- [ ] changelog `[0.13.0]`

**완료 기준**:
1. `/index/overview` 엔드포인트가 캐시된 결과 반환 (재호출 시 LLM 호출 없음)
2. 빈 채팅에 카드·예시 질문 5개 렌더, 클릭 재질의 정상
3. 업로드/삭제 후 캐시 무효화 동작

**의도적 제외**: 토픽 클라우드 시각화, 엔티티 그래프, 문서별 자동 요약 카드 — Phase 3 이후

### ~~TASK-009: 디스크 정리 + 긴 청크 누락 제거~~ — ✅ 완료 (2026-04-22)
→ ADR-021, changelog [0.14.0]

**우선순위**: 저 (작지만 점진 해소)
**전제**: TASK-008 완료 후
**배경**: (a) 문서 삭제 시 `data/uploads/`·`data/markdown/` 원본 파일이 정리되지 않아 고아 파일 누적. (b) HybridChunker 결과 5~10%가 임베딩 512토큰 상한 초과 — 일부 내용이 임베딩 경계에서 잘려 검색에 안 잡힘

**서브태스크**:
- [ ] `apps/routers/documents.py`의 `delete_doc`에 `unlink(missing_ok=True)` 추가 — `data/uploads/{doc_id}.*`, `data/markdown/{doc_id}.md`
- [ ] 테스트: 업로드 → 삭제 후 해당 doc_id 파일이 전부 사라지는지 확인
- [ ] `packages/loaders/docling_loader.py`의 `HybridChunker` 인자 조정 — 토큰 기반 max_tokens 옵션 확인·적용 (Docling 버전에 따라 `tokenizer` 설정)
- [ ] 재인덱싱 후 "Token indices sequence length > 512" 경고가 사라지는지 확인 (0건이 이상적, 1% 이하가 실용선)
- [ ] TASK-004 벤치 재실행 — Hit@3·faithfulness 회귀 없음 확인
- [ ] ADR-021 신규 (간단)
- [ ] changelog `[0.14.0]`

**완료 기준**:
1. 문서 삭제 후 `data/uploads/`·`data/markdown/` 고아 파일 0건
2. 재인덱싱 시 토큰 초과 경고 ≤1%
3. Hit@3 / faithfulness 회귀 0

**주의사항**:
- 고아 파일 정리는 단순 삭제라 `DELETE` 엔드포인트에서 예외 없이 `missing_ok=True` 사용 — 이미 없으면 조용히 넘김
- 토큰 상한 조정은 재인덱싱 필요 — TASK-002의 재인덱싱 플로우 재활용 (`pipeline/rebuild_index.py`)
- max_tokens를 너무 작게 잡으면 청크 수 증가 → latency·비용 증가. 현재 경고 임베딩 모델(1536-d)의 512 토큰 한계에 맞춰 ~480 정도가 안전

### ~~TASK-010: 폴더 단위 일괄 색인 CLI 스크립트~~ — ✅ 완료 (2026-04-23)
→ ADR-022, changelog [0.15.0], [setup.md "대량 문서 색인" 섹션](wiki/onboarding/setup.md)

**우선순위**: 중 (대량 문서 등록 시 필수)
**전제**: TASK-009 완료 (디스크 정리·토큰 상한). 현재 시스템의 중복 감지(ADR-005)·원본 보관(ADR-010)·자동 OCR(ADR-004)·HybridChunker(ADR-009)·토큰 상한(ADR-021)이 모두 준비되어 재실행 안전성 확보됨
**배경**: 현재 문서 등록 경로는 (a) Streamlit UI 수동 업로드 1건씩, (b) `POST /ingest` API 1건씩, (c) `scripts/ingest_sample.py` 단일 파일 테스트뿐. 수십~수백 개 문서를 폴더 단위로 한 번에 등록할 수단이 없음
**목표**: 한 명령으로 지정 폴더 내 모든 지원 문서(`.pdf/.txt/.md/.docx`)를 **하위 폴더 포함(재귀)** 순회해 자동 업로드·색인. 중복(L1 SHA-256) 자동 스킵, 실패 리포트 JSON 저장. 재실행 안전
**범위**: CLI만. 관리자 UI 버튼·API 엔드포인트는 **인증·공개배포 묶음과 함께 보류** (현재 인증 미도입이라 관리자 UI에 무인증 버튼 노출 금지)

**서브태스크**:
- [ ] `scripts/bulk_ingest.py` 신설
- [ ] CLI 인자 설계:
  - `--dir PATH` (필수, 절대·상대 경로)
  - `--recursive` / `-r` (기본 **True**, 하위 폴더 전부 탐색)
  - `--no-recursive` (최상위 폴더만)
  - `--include "*.pdf *.txt *.md *.docx"` (기본 4종)
  - `--exclude REGEX` (파일 경로 정규식으로 제외, 반복 허용)
  - `--title-from {filename|relpath|stem}` (기본 `stem` — 확장자 제외 파일명)
  - `--source-prefix PATH` (선택, source 메타에 붙일 접두 — 예: "acme/docs/")
  - `--workers N` (기본 1, 순차 처리. 2+ 시 병렬이나 Docling 모델 메모리 주의)
  - `--dry-run` (실제 업로드 없이 탐색 결과와 중복 예상만 출력)
  - `--fail-fast` (첫 실패 시 전체 중단. 기본은 스킵 후 계속)
  - `--report PATH` (기본 `data/eval_runs/bulk_ingest_<timestamp>.json`)
  - `--api-base URL` (기본 `http://localhost:8000`)
- [ ] 구현:
  - `Path(dir).rglob(pattern)` 기반 재귀 탐색, `--exclude` 정규식으로 필터
  - 진행 표시는 `tqdm`. 각 파일마다 `POST /ingest` 호출 (직접 `pipeline.ingest` 대신 HTTP로 — L1 중복 감지·content_hash 일관성 유지)
  - 응답 분류: `200 OK` → ok, `409 Conflict` → duplicate (로그만, 실패 아님), 그 외 → failed
  - 결과 리포트 스키마:
    ```json
    {
      "run_id": "...",
      "dir": "...", "recursive": true, "include": [...], "exclude": [...],
      "total": N, "ok": N, "duplicate": N, "failed": N,
      "results": [
        {"path": "...", "status": "ok|duplicate|failed",
         "doc_id": "...", "chunk_count": N, "error": "..."}
      ],
      "started_at": "...", "finished_at": "...", "elapsed_sec": N
    }
    ```
- [ ] Docling 모델 프리로드: 첫 파일에서 다운로드 트리거되므로 tqdm에 "첫 파일 오래 걸림" 주석
- [ ] 대용량 안전장치: 업로드 직전 파일 크기 체크해 `MAX_UPLOAD_SIZE_MB` 초과 시 `skipped_too_large`로 분류
- [ ] `scripts/` 디렉터리에 사용 예시 README 또는 본 파일 docstring에 2~3 예시
- [ ] 테스트: `tests/integration/test_bulk_ingest.py` 신규 (임시 디렉터리에 샘플 파일 3개 생성 → 실행 → 결과 JSON 검증)
- [ ] `wiki/onboarding/setup.md`에 "대량 문서 색인" 섹션 추가 + 실행 명령 예시
- [ ] ADR 신규 (차기 가용 번호, TASK-010 완료 시 결정) — "대량 색인 전략: CLI 스크립트 우선, API는 인증·공개배포와 함께 미래 도입"
- [ ] changelog `[0.15.0]`

**완료 기준**:
1. `python scripts/bulk_ingest.py --dir /path/to/docs` 실행 시 하위 폴더 포함 전 파일 순회·업로드
2. 중복(409) 응답을 `duplicate`로 집계하고 실패로 처리하지 않음
3. `--dry-run` 모드가 업로드 전 대상 파일 목록·중복 예상 출력
4. 결과 JSON 파일이 `data/eval_runs/bulk_ingest_<ts>.json`으로 저장
5. 한 파일 실패 시 전체 중단되지 않고 다음 파일 계속 (`--fail-fast` 예외)

**의도적 제외**:
- **관리자 UI 버튼**: 인증 없는 현 단계에서 노출 금지 (인증·공개배포 묶음과 함께 도입)
- **중복 재검증(L2/L3)**: 기존 L1(SHA-256)으로 충분. L2는 장기 검토
- **병렬 처리 기본값**: 기본 순차. `--workers` 옵션만 제공해 사용자가 명시적으로 선택
- **원격 폴더/S3/cloud storage**: 로컬 파일시스템만. 필요 시 별도 태스크

**주의사항**:
- 스캔 PDF가 섞이면 OCR 자동 실행되어 파일당 수 분~수십 분 소요 가능. 폴더가 크면 **백그라운드로 실행**하고 LangSmith로 진행 모니터링 권장
- 동시에 여러 `bulk_ingest`를 돌리지 말 것 — 같은 `doc_id` 경쟁, content_hash UNIQUE 충돌 가능
- 재실행 시 이미 등록된 파일은 409로 스킵되므로 중단 후 재시작 안전 (progress resume 대용)
- API 서버(`uvicorn`)가 사전에 실행 중이어야 함. Docling·Reranker 모델 워밍업까지 5~60초 소요
- 스크립트는 **로컬에서만** 실행. 원격 API에 대량 업로드는 네트워크·비용 고려 (`--api-base` 지정 시 인증 필요)

- [ ] 
- [ ] 

---

## 장기 / 검토 중

- [x] Reranking 도입 (FlashRank 로컬, 2026-04-19)
- [x] 멀티모달 (이미지 포함 PDF) — Docling으로 기본 지원
- [x] 대화 히스토리 영속화 + 최근 20턴 컨텍스트 주입 (2026-04-21)
- [x] 중복 업로드 방지 L1 (SHA-256 파일 해시, 2026-04-21)
- [x] LangSmith 관측 통합 (2026-04-21)
- [x] 파싱 후 정규화 (2026-04-21)
- [x] FlashRank 재순위 실제 활성화 (2026-04-21) — 단 한↔영 크로스 모델 평가 필요
- [x] HybridChunker(docling-core) 도입 + 전체 heading 경로 breadcrumb 주입 (2026-04-21)
- [x] 원본 파일 영구 보관 (2026-04-21)
- [x] 다국어 rerank 모델 도입 (bge-reranker-v2-m3, 2026-04-22, TASK-001)
- [x] 하이브리드 검색 (BM25 sparse + dense + RRF, Kiwi 한국어 전처리) (2026-04-23, TASK-011, ADR-023)
- [ ] HybridChunker 토큰 상한 설정 (512 토큰 초과 청크 방지)
- [ ] 중복 감지 L2 (정규화 텍스트 해시) / L3 (임베딩 유사도 경고)
- [ ] 스트리밍 응답
- [ ] 사용자 피드백 루프
- [ ] 평가 지표 측정 (Precision@K, Recall@K, MRR)
- [ ] **인증 (API Key 또는 OAuth)** — 🛑 사용자 지시까지 전부 보류 (2026-04-22 결정, 개인·내부 시스템 단계). 재개 시 "인증·공개배포 묶음"의 일부로 ISSUE-001 + 관리자 UI 2단계와 함께 처리
- [ ] 대화 요약(summary) 메모리 — 긴 세션 초기 문맥 보존
- [ ] **Graph RAG (보류)** — 비용·복잡도 높음. 재평가 조건: ① 문서 수 100+, ② 질의 로그에서 multi-hop/cross-document 패턴이 상당 비율로 확인, ③ 경량 대안(엔티티 추출, heading 트리 등)으로도 "적극적 질의" 요구가 충족되지 않을 때. 착수 시 별도 ADR 작성 필수 (인덱싱 비용 $30~120/현재 규모, Neo4j·AGE 중 저장소 선택, incremental 업데이트 전략)
- [ ] **MCP 서버 익스포트 (철회 후 장기 검토)** — TASK-006에서 철회됨(2026-04-22). Claude Code/Cursor 등 MCP 클라이언트에서 이 RAG를 `search_docs`/`list_docs` tool로 소비하는 통합. 재개 조건: ① 외부 에이전트가 이 지식 베이스를 소비할 구체적 유스케이스 발생, ② 운영 배포 후 stdio가 아닌 HTTP/SSE 모드 필요성 판단. 재개 시 신규 태스크로 정의 (원본 서브태스크는 roadmap의 `~~TASK-006~~` 섹션 참고)

---

## TASK-012: Cloudflare Tunnel + Access 외부 노출 게이트웨이

**상태**: queued (후순위, 2026-04-23 큐잉)
**우선순위**: 낮음 — 사용자 "착수" 지시 시 진행
**착수 전제조건**: 도메인을 Cloudflare 네임서버로 이전 완료 (사용자 개인 작업)
**관련**: 신규 ADR (착수 시 작성·번호 부여 예정)

### 배경
외부(사용자 지인·자기 모바일) 에서 RAG 시스템에 접속해 테스트할 채널이 필요. 현재 상태:
- Streamlit 8501·FastAPI 8000 모두 localhost 바인드, 인증 없음
- 인증·공개배포 묶음 전체 보류(2026-04-22) 중이라 앱 내 인증 TASK 진행 불가
- 이 TASK는 "외부 테스트 접근 게이트" 최소 조각만 꺼낸 것. **묶음 전체 해제 아님**

### 목표
**앱 코드 수정 0**으로 외부 접속·이메일 OTP 인증·HTTPS 종단을 한 번에 해결. 후속으로 필요해지면 Clerk·자체 게이트로 확장 가능한 구조 확보.

### 아키텍처 결정 (초안, 착수 시 신규 ADR로 확정)
- **Cloudflare Tunnel** — 내 장비에서 아웃바운드 연결만 맺고 inbound 포트 개방 없음. 공격 표면 최소
- **Cloudflare Access (Zero Trust Free)** — 엣지에서 One-time PIN(이메일 OTP) 인증. 정책: `HAL2001` 화이트리스트 (실 이메일은 Cloudflare 대시보드에만 저장)
- **노출 포트**: 8501(Streamlit)만. 8000(FastAPI)은 localhost 유지 — Streamlit이 서버 사이드로 호출하므로 외부 노출 불필요
- **도메인**: 사용자 소유 도메인의 서브도메인(`rag.<domain>`) 사용

### 범위 — 사용자가 직접 해야 할 일 (계정·대시보드 작업)

Cloudflare 계정·도메인 소유자 인증·대시보드 GUI가 필요한 작업은 **사용자만 수행 가능**. 에이전트는 대신 못 한다.

- [ ] **Cloudflare 계정 생성 또는 로그인** ([dash.cloudflare.com](https://dash.cloudflare.com))
- [ ] **도메인 네임서버 이전** — 현재 도메인 등록기관(가비아·카페24·GoDaddy 등) 관리 페이지에서 네임서버를 Cloudflare가 지정한 2개로 변경. 전파 10분~24시간
- [ ] **Zero Trust 대시보드 진입** ([one.dash.cloudflare.com](https://one.dash.cloudflare.com)) → 팀 이름 설정 → Free 플랜 선택
- [ ] **Tunnel 생성** — Networks → Tunnels → Create a tunnel → Cloudflared → 이름 `knowledge-rag` → 설치 명령 복사
- [ ] 본인 장비에서 `cloudflared service install <token>` 실행 (에이전트가 도울 수 있지만 token은 사용자가 대시보드에서 복사해야 함)
- [ ] **Public Hostname 추가** — Subdomain `rag`, Domain `<your-domain>`, Service `HTTP` `localhost:8501`
- [ ] **Access Application 추가** — Access → Applications → Add → Self-hosted → 이름·도메인 입력
- [ ] **Policy 작성** — Action `Allow`, Include → Emails → `HAL2001`의 실 이메일 (여러 명이면 콤마), Session `24h`, Identity providers에 `One-time PIN` 체크. **실 이메일 주소는 위키·커밋 메시지에 평문 기록 금지**, Cloudflare 대시보드에만 저장
- [ ] **외부 기기에서 접속 테스트** — 이메일 OTP 수신·입력 → Streamlit 진입 확인
- [ ] **미등록 이메일 차단 확인** — 본인 아닌 이메일로 시도 → 거부 화면
- [ ] (실운영 시) 이메일 화이트리스트 주기적 점검, 이탈한 테스터 제거

### 범위 — 에이전트가 할 일 (코드·문서 작업)

착수 지시 시 에이전트가 `/rag-commit` 절차와 함께 진행:

- [ ] `wiki/deployment/runbook.md` 신규/갱신 — 위 사용자 작업을 재현 가능한 순서로 기록, 스크린샷 경로 placeholder, 문제 발생 시 롤백 절차
- [ ] `wiki/architecture/decisions.md` — 신규 ADR (착수 시 번호 부여, 결정 내용·대안(Clerk, Auth0) 비교·왜 Access인가·재개 조건)
- [ ] `project-wiki/changelog.md` — `[0.17.0]` 추가 (코드 변경 없지만 운영 경로 변경은 사용자 가시적)
- [ ] `wiki/overview.md` — 진행표에 "외부 접근" 상태 갱신, 최근 결정에 신규 ADR, 완료 태스크 표에 TASK-012
- [ ] (선택) [ui/app.py](ui/app.py) — 사이드바에 `cf-access-authenticated-user-email` 헤더 값 표시 (코드 3~5줄, `AUTH_ENABLED=false`이거나 헤더 부재 시 "로컬" 표기)
- [ ] `log.md`에 impl 항목 append
- [ ] `wiki/troubleshooting/common.md` — OTP 미수신·도메인 전파 지연·셀프락 해제 사례 기록

### 의도적 제외 (보류 묶음 유지)
- 앱 내 패스워드 게이트·Clerk·Auth0 등 **애플리케이션 레이어 인증** — Cloudflare Access로 충분
- 다중 사용자·역할(admin/guest) 분리
- FastAPI 8000의 외부 노출·인증
- ISSUE-001 모바일 업로드 이슈 해소 (별건)
- 관리자 UI 2단계(백그라운드 재색인·벤치 UI 버튼)
- 공개 배포·사용자 모집·운영 모니터링 체계

### 완료 기준
- 외부 네트워크(모바일 4G·타 PC)에서 `https://rag.<domain>`에 접속
- 미등록 이메일 → 접근 차단
- 등록 이메일 → OTP 수신·입력 후 Streamlit 정상 이용 (업로드·질의 전부)
- HTTPS 인증서 유효, 내 장비 inbound 포트 개방 0
- 재현 문서: runbook만 보고 다른 환경에서 동일 셋업 가능

### 회귀 전략
- `cloudflared tunnel stop` 한 번으로 외부 노출 즉시 종료
- Access Policy에서 Allow → Block 한 번이면 모든 접근 차단
- 앱 코드 건드리지 않으므로 로컬 개발 영향 0

### 리스크 체크
- **Cloudflare Free 50 MAU 제한** — 개인·소규모 테스트는 여유
- **이메일 OTP 발송 딜레이** — 스팸함 가능성, 최초 로그인 시 확인
- **도메인 이전 다운타임** — 사용자가 외부 서비스에 해당 도메인 쓰고 있으면 주의. 새 서브도메인 전용 사용 권장
- **Access 정책 오설정으로 셀프락** — `Everyone` 정책 실수 주의, 테스트 후 `Bypass` 정책은 즉시 제거

---

## TASK-013: MkDocs Material + GitHub Pages 문서 사이트

**상태**: queued (후순위, 2026-04-23 큐잉)
**우선순위**: 낮음 — 사용자 "착수" 지시 시 진행
**관련**: 신규 ADR (착수 시 작성·번호 부여 예정)

### 배경
현재 `project-wiki/`는 **5단계 깊이 중첩 구조**(architecture/·features/·issues/open/·reviews/ …)가 정보 조직의 핵심. GitHub Wiki는 flat 전제라 네비게이션 손실이 큼. 외부 공개·검색 가능한 문서 사이트가 필요하지만 현 구조 재작성 없이 그대로 쓸 수 있는 경로가 요구됨.

### 목표
`project-wiki/` 디렉터리 **그대로** 정적 사이트로 빌드·배포. 푸시하면 자동 갱신.

### 아키텍처 결정 (초안, 착수 시 신규 ADR로 확정)
- **MkDocs + Material theme** — 파이썬 생태, 중첩 nav 네이티브, 검색·다크모드·코드 하이라이트 내장
- **소스**: `project-wiki/` 그대로 사용 (`docs_dir: project-wiki`)
- **빌드**: GitHub Actions (`mkdocs gh-deploy` 또는 Actions로 `gh-pages` 브랜치 배포)
- **배포처**: GitHub Pages (public repo, 무료). URL: `https://<user>.github.io/knowledge-rag/`
- **내부 링크**: 현재 상대 경로 `[x](wiki/architecture/decisions.md)`는 대부분 그대로 동작. 문제 링크만 소폭 조정

### 범위
- [ ] `mkdocs.yml` 루트에 추가 — `docs_dir`, `site_name`, `nav`(자동 or 수동), Material 플러그인, 검색 한국어 토크나이저(`lunr-languages` 또는 내장 ko)
- [ ] `.github/workflows/docs.yml` — push 시 `pip install mkdocs-material` → `mkdocs build` → `peaceiris/actions-gh-pages` 로 `gh-pages` 브랜치 push
- [ ] GitHub 저장소 Settings → Pages → Source: `gh-pages` branch (사용자 대시보드 작업)
- [ ] 내부 링크 호환성 점검 — `mkdocs build --strict`로 깨진 링크 0 확보
- [ ] `/rag-lint` 스크립트에 `mkdocs build --strict` 호출 추가(lint 실패로 연결)
- [ ] `wiki/deployment/runbook.md`에 로컬 미리보기(`mkdocs serve`)·배포 실패 복구 절차
- [ ] (선택) 커스텀 도메인 — Cloudflare에 도메인 있으면 `docs.<domain>` CNAME으로 연결

### 범위 — 사용자 작업
- [ ] GitHub Settings → Pages → Source `gh-pages` branch 활성화 (1회, 1분)
- [ ] (선택) 커스텀 도메인 원하면 Cloudflare DNS에 CNAME 추가

### 의도적 제외
- **위키 구조 flatten** — 현재 중첩 유지가 전제. 바꿀 일 없음
- **사설 정보 공개 점검** — security.md PII 정책으로 이미 관리 중, 이 TASK에서 중복 안 함
- **다국어 사이트** — 현 위키는 한국어 단일
- **검색 고도화(Algolia 등)** — Material 내장 검색으로 충분
- **Docusaurus / GitBook / BookStack** — 대안 검토 완료, MkDocs가 현 구조에 최적

### 완료 기준
- `https://<user>.github.io/knowledge-rag/` 접속 → 사이드바에 architecture/·features/·issues/ 등 중첩 표시
- 검색창에서 "하이브리드 검색" → ADR-023·changelog 히트
- main에 push → 1~2분 내 사이트 자동 갱신
- 내부 링크 404 발생 0, `mkdocs build --strict` 통과
- 로컬 `mkdocs serve`로 커밋 전 미리보기 가능

### 회귀 전략
- `mkdocs.yml`·워크플로 파일 제거 + `gh-pages` 브랜치 삭제로 **3분 내 완전 롤백**
- 사이트가 안 떠도 저장소·위키는 영향 0 (현재 경로 그대로)

### 리스크 체크
- **링크 형식 차이**로 소수 404 가능 — `--strict` 빌드 실패 시 로그 보고 정정
- **MkDocs 한국어 검색 인덱싱 품질** — 일부 토큰화 문제 가능, 필요 시 `lunr-languages` 설정 또는 CJK 호환 검색 플러그인 교체
- **GitHub Actions 무료 시간(2,000분/월)** — 이 용도로는 수 분/월 수준, 여유 충분
- **Private 저장소 + Pages** — Free 플랜은 public만 가능(현재 public이라 무관). 나중에 private로 바꿀 때 재검토

---

## TASK-019: 사용자 UI NextJS 분리 + Clerk 인증

**상태**: queued (**최우선**, 2026-04-25 큐잉) — TASK-018 완료 다음 자리, 다른 후순위 큐(TASK-012/013/020)보다 먼저 진행
**우선순위**: 최우선 — 사용자 명시 지정 (2026-04-25)
**관련**: 신규 ADR (착수 시 작성·번호 부여 예정, 다음 가용 ADR-030)

### 배경
`ui/app.py` 853줄 단일 Streamlit이 7탭(채팅·도서관·문서·잡·대화·시스템·평가)을 모두 담당. 알려진 한계:
- `st.tabs`가 프로그램적 탭 전환 미지원 → 도서관·랜딩의 자동 이동 트리거 4건이 토스트 안내만 남기고 멈춤
- 모바일에서 `file_uploader` 표시 누락(ISSUE-001), suggestions 배지 클릭 무반응(ISSUE-002) 등 모바일 UX 한계
- 사용자 화면(채팅·도서관·대화)과 관리자 화면(문서·잡·시스템·평가)이 한 앱에 섞여 있어 외부 공개·단순화·인증 도입 모두 어려움
- 인증 없음 — 외부 접근 시 사용자별 데이터 격리 불가

### 목표
사용자 측 화면(채팅·도서관·대화)을 NextJS로 분리하고 Clerk로 인증한다. 관리자 측 화면(문서·잡·시스템·평가)은 Streamlit에 그대로 둔다(코드 동결). LLM·RAG 처리는 모두 FastAPI 단일 진실. NextJS는 thin client.

### 아키텍처 결정 (초안, 착수 시 ADR-030으로 확정)

- **분리 정책**: 사용자 = NextJS / 관리자 = Streamlit (포트 분리, 동일 FastAPI 백엔드 공유)
- **인증**: NextJS만 Clerk 보호. Streamlit은 LAN 무인증 그대로 (Streamlit 동결 정책)
- **인증 분리 전략 (Origin 분기)**:
  | 요청 출처 / 헤더 | 처리 |
  |---|---|
  | `Authorization: Bearer <Clerk JWT>` | Clerk 검증 → `user_id = clerk.user_id` 주입 |
  | 헤더 없음 + LAN/localhost origin | `user_id = 'admin'` 자동 주입 (Streamlit + 로컬 스크립트) |
  | 헤더 없음 + 외부 origin | `401 Unauthorized` |
- **상태 관리**: TanStack Query (서버 상태) + URL state (스코프·세션) + Zustand (필요 시 클라이언트 상태)
- **UI**: shadcn/ui (Radix 기반, 접근성·다크모드 내장)
- **API 클라이언트**: `openapi-typescript`로 OpenAPI 스키마 자동 변환
- **인증 보류 묶음 영향**: (가) Clerk(앱 내 인증)만 부분 해제. **나머지 4개(ISSUE-001 / 관리자 UI 2단계 / HTTPS 배포 / 관리자 UI 버튼)는 보류 유지**

### 페이지 구성 (2 + 사이드바 흡수)
- `/` 또는 `/chat` — 채팅 (URL state로 `session_id`, `doc_filter`, `category`, 추후 `series`)
- `/library` — 도서관 (URL state로 `q`, `type`, `category`)
- `/conversations` 라우트 없음 (사이드바에 흡수)

### 레이아웃 (AppShell)
- **상단 헤더**: 앱명 + 카테고리 칩(라벨만, 첫 칩 `🌐 전체`, NULL 카테고리는 `기타` 통일 표기)
- **사이드바**: ＋ 새 대화 / 대화 목록(자기 user_id만) / 하단 📚 도서관 링크. 데스크톱 펼침, 모바일 drawer 닫힘
- **메인**: 활성 스코프 배지(있을 때) + 페이지 본문

### 활성 스코프 배지 (3 타입, 한 번에 하나)
우선순위: **series > category > doc** (단순화)
- 📚 시리즈 한정 (TASK-020 완료 후 활성)
- 📂 카테고리 한정
- 📖 문서 한정
- 🌐 전체 (배지 미표시, 기본)

### 사용자 흐름 — NextJS 측
- 채팅: 메시지 히스토리, 후속 질문 배지(NextJS 본질 해결), 소스 expander, doc_filter/category_filter, 빈 채팅 랜딩 카드(요약·카테고리 분포·주제 칩·예시 질문·최근 문서 카드·전체 expander)
- 도서관: 검색·형식·카테고리 필터, 카드 그리드, 그룹핑(기타 마지막), 카드 상세(abstract·sample questions·meta), [이 책에 대해 묻기]·[카테고리에 묻기]
- 대화(사이드바): 자기 user_id 세션 목록·새 대화·세션 클릭 시 채팅으로 이동(`?session_id=`)·hover 시 🗑️
- 세션 제목: 첫 질문 일부 자동 사용 (현재 백엔드 정책 유지)

### 데이터 모델 변경
- `conversations.user_id TEXT NOT NULL` 컬럼 추가 (sentinel idempotent 마이그레이션, advisory lock)
- 인덱스 `ix_conversations_user_id`
- 기존 행 백필: `'admin'` 일괄 업데이트 (삭제 안 함)
- Streamlit 신규 세션도 미들웨어가 `'admin'`으로 자동 부여

### 백엔드 영향 (FastAPI 측)
- `apps/middleware/auth.py` (신규) — Clerk JWT 검증 + Origin 분기 + 'admin' 기본값
- `apps/schemas/query.py` — `QueryRequest.category_filter: Optional[str]` 추가 (현재 `doc_filter`만)
- `packages/rag/{pipeline,retriever}.py` — `category_filter` 통과, Qdrant 필터 절(`payload.category`)
- `apps/routers/query.py` — request 통과, user_id 주입
- `apps/routers/conversations.py` — `user_id` 필터, owner 검증(다른 user_id 접근 시 404)
- `packages/db/repository.py` — conversations CRUD에 user_id 통과
- LangSmith 트레이스 — `category_filter`·`user_id` 메타 추가
- CORS — NextJS dev origin(`http://localhost:3000`) 허용

### 범위 — 에이전트 (착수 시)

**NextJS 프로젝트:**
- [ ] `web/` 디렉터리 신설 — NextJS 14/15 App Router · TypeScript · ESLint · prettier
- [ ] `@clerk/nextjs` 통합 — `<ClerkProvider>`, `middleware.ts` 보호 라우트, `<SignIn/>·<SignUp/>·<UserButton/>` 컴포넌트
- [ ] shadcn/ui 셋업 (button, card, input, select, dialog, sheet, sidebar, tabs/segments, badge, scroll-area, toast)
- [ ] TanStack Query Provider, OpenAPI 클라이언트(`openapi-typescript`)
- [ ] AppShell — 상단 헤더(카테고리 칩) + 사이드바(대화·도서관) + 메인
- [ ] `/chat` 페이지 — 메시지 히스토리·소스 expander·후속 질문·empty state(카테고리·주제 칩·예시·최근 문서)·doc_filter·category_filter
- [ ] `/library` 페이지 — 필터 바·카드 그리드·그룹핑(기타 마지막)·카드 상세 토글
- [ ] 사이드바 대화 목록 — 자기 user_id만 자동 refetch·세션 클릭 라우팅·삭제 hover 액션
- [ ] 활성 스코프 배지 + 해제 흐름
- [ ] URL state 라우팅 — 도서관→채팅 자동 이동(NextJS App Router native)
- [ ] 모바일 drawer + 가로 스크롤 카테고리 칩
- [ ] 에러·로딩·빈 데이터 처리

**FastAPI 측 보강:**
- [ ] `apps/middleware/auth.py` — Clerk JWT 검증 + Origin 분기(LAN→admin) + 외부 origin 401
- [ ] `category_filter` 추가 (스키마·pipeline·retriever·router·LangSmith)
- [ ] CORS 허용
- [ ] `conversations.user_id` 마이그레이션 + repository 필터
- [ ] owner 검증 (404 응답)

**문서:**
- [ ] ADR-030 — 사용자/관리자 UI 분리, Clerk 결정·대안 비교(Auth0·Supabase Auth·자체 구현·Cloudflare Access), Origin 분기 전략, 인증 묶음 부분 해제 방침
- [ ] `wiki/architecture/stack.md` — NextJS·shadcn/ui·TanStack Query·Clerk 추가
- [ ] `wiki/api/endpoints.md` — `category_filter`·CORS·인증 미들웨어 동작
- [ ] `wiki/features/admin_ui.md` — 분리 정책 명시 + Streamlit 범위(관리자 잔류) + 동결 정책
- [ ] `wiki/security.md` — Clerk 키 보관, 인증 분리(Origin 분기), 사용자 데이터 격리
- [ ] `wiki/onboarding/setup.md` — `cd web && pnpm dev` 절차, Clerk 키 발급 가이드
- [ ] `wiki/deployment/runbook.md` — docker-compose에 NextJS 서비스 추가, 포트 분리(8501 admin / 3000 user / 8000 API)
- [ ] `project-wiki/changelog.md` — 신규 버전(코드 변경 큼)
- [ ] `wiki/overview.md` — 진행표·최근 결정·완료 태스크
- [ ] `log.md` impl 항목

### 의도적 제외
- **Streamlit 측 모든 수정** — 사용자 명시 지시까지 동결 (메모리 `feedback_streamlit_no_edit`). 안내 문구·hide 토글·인증 통합 일체
- **HTTPS 배포·도메인** — 별건(TASK-012 Cloudflare Tunnel과 묶이는 흐름)
- **관리자 UI 2단계** — 보류 묶음에 잔류
- **ISSUE-001 모바일 업로드** — 보류 묶음에 잔류 (관리자 측이라 NextJS와 무관)
- **사용자 vs 관리자 역할 분리** — Clerk Organizations·publicMetadata role 미사용. 모든 로그인 사용자 동등
- **비밀번호 로그인** — 비번 관리 부담 회피. 이메일 OTP만
- **소셜 로그인** — Phase 1 미포함 (필요 시 후속)
- **'admin' 사용자에 NextJS UI 접근** — Streamlit 대화는 Streamlit에서만 본다는 분리 정책. NextJS 사용자 사이드바엔 자기 user_id 세션만
- **답변 스트리밍(SSE)** — 별건 후속 검토. Phase 1 미포함
- **시리즈 카드·시리즈 스코프 배지** — TASK-020 완료 시점에 NextJS에 추가하는 흐름. NextJS는 우선 `series_id NULL` 가정 동작
- **다국어** — 한국어 단일
- **PWA(설치 가능)** — 별건 후속 검토
- **관리자 모드 NextJS 이전** — 인증 묶음 추가 해제 시 재검토
- **사용자 측 시리즈 편집** — read-only (관리자 전용, TASK-020 영역)
- **익명 사용** — 로그인 필수
- **B2B/SSO/SAML/Clerk Organizations** — Pro 이상 기능, 현 단계 미사용

### 외부 의존·키 (사전 합의 사항)
- Clerk 계정 생성 (사용자 직접) — Free 플랜 (10k MAU/월 무료)
- API 키 2~3개 (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, 선택 `CLERK_WEBHOOK_SECRET`)
- 신규 패키지: `@clerk/nextjs`, NextJS 14/15, shadcn/ui, TanStack Query, openapi-typescript

### 완료 기준
- `cd web && pnpm dev` 한 줄로 사용자 UI 기동
- 채팅·도서관·대화(사이드바) 3 영역 모두 동작
- 자동 페이지 이동 4 트리거가 모두 정상 작동(Playwright 검증)
- 모바일 viewport에서 drawer·카테고리 칩·카드 그리드·후속 질문 배지 정상(ISSUE-002 본질 해결 확인)
- `category_filter` 적용 시 해당 카테고리 문서만 검색됨
- Clerk 미인증 외부 origin → `/sign-in` 리다이렉트
- Streamlit 호출(LAN, 헤더 없음) → user_id `'admin'`으로 자동 처리, 코드 변경 0
- 사용자 A가 사용자 B 세션 GET 시 404
- FastAPI 8000 외부 노출 시 헤더 없는 외부 origin 401
- ADR-030, 위키 8개 페이지 갱신, changelog 신버전

### 회귀 전략
- Streamlit은 그대로 살아 있어 사용자 UI 미공개 시 즉시 회귀
- NextJS 빌드 실패 시 Streamlit으로 즉시 회귀 (현재 8501 그대로 운영)
- `category_filter` 백엔드 변경은 default `None` → 기존 호출 100% 후방호환
- 인증 미들웨어는 `AUTH_ENABLED=false` 토글로 도입 시점 분리 가능 (Clerk 미발급 환경에서 테스트용)
- conversations 마이그레이션 down: `ALTER TABLE conversations DROP COLUMN user_id` 별도 마이그레이션
- CORS는 dev에서만 허용, prod에선 reverse proxy

### 리스크
- **Origin 분기의 LAN 신뢰 가정** — FastAPI 8000을 외부 노출하면 LAN IP 위장 가능. 외부 노출 시점에 reverse proxy로 Origin 정규화 필수
- **모바일 동작 검증** — Playwright만으로는 실기기 호환 100% 보장 못 함. 실제 iOS Safari·Android Chrome 실측 필요
- **Streamlit/NextJS 디자인 일관성** — 의도적 분리이므로 큰 문제 아님. 외부 노출 시점에 정리
- **OpenAPI 스키마 동기화** — FastAPI 변경 시 NextJS 클라이언트 재생성 필요. CI에 빌드 단계 추가
- **Clerk Free 플랜 한도** — 10k MAU/월. 1인·소규모 무관, 외부 공개 확장 시 점검
- **마이그레이션 충돌** — bulk_ingest 또는 indexer 진행 중 ALTER 실행 시 락 대기. TASK-018 패턴(advisory lock + sentinel) 재사용으로 회피
- **'admin' 사용자 데이터 누적** — Streamlit 사용자 세션이 모두 'admin' 단일 누적. 운영 데이터 폭증 시 별도 정리 정책 필요(현 단계 무영향)

### 산정 합계
**7~9일 (집중 작업, 중앙값 7~8일)** — Clerk 통합 + Origin 분기 미들웨어 + user_id 마이그레이션 + 사용자별 세션 격리 보호 라우트 +1.5~2일 합산.

---

## TASK-020: Series/묶음 문서 — ✅ 완료 (2026-04-28)
→ ADR-029, changelog [0.26.0], `apps/routers/series.py`, `packages/series/`, `scripts/suggest_series.py`

**결과**:
- `series` 1급 시민 + `documents` 4컬럼 + 색인 시점 휴리스틱(LLM 호출 0)
- API 10개, 매처 단위 26/26 회귀, 통합 smoke 정상
- 백필 dry-run 107건 → suggested 6 / low 18 / no_candidate 83
- Streamlit 동결 정책 정합 — 검수는 FastAPI + CLI 두 경로 (NextJS admin 검수 페이지는 별건)

**아래는 큐잉 시점 원본 정의 (참고용 보존)**:

**상태**: queued (후순위, 2026-04-25 큐잉)
**우선순위**: 낮음 — 사용자 "착수" 지시 시 진행
**관련**: 신규 ADR (착수 시 작성·번호 부여 예정, 다음 가용 ADR-029)

### 배경
하나의 저작이 여러 파일로 쪼개져 인덱싱되는 경우(예: 30챕터 책)가 흔함. 현재 데이터 모델은 업로드 1건 = `documents` 1행이라 같은 책의 챕터들이 흩어져 있다. 결과:
- 도서관 카드가 30개로 흩어져 가시성 ↓
- "이 책에 대해 묻기"는 1챕터에만 한정. 책 전체에 대한 질의 불가
- 카테고리·태그·요약이 챕터별로 따로 산정되어 일관성 ↓

### 목표
시리즈/묶음을 1급 시민으로 도입(Option A 스키마). 색인 시점에 휴리스틱이 자동 묶기를 수행하고, 관리자는 사후 검수(Confirm/Detach)로 정정한다. 사용자는 도서관에서 시리즈 카드 단위로 탐색하고, 채팅에서 시리즈 한정 스코프로 질의할 수 있다.

### 아키텍처 결정 (초안, 착수 시 신규 ADR로 확정)

**Option D 채택 — Series 1급 시민 + 자동 묶기 하이브리드.**

검토한 대안:
- **A**: Series 1급 시민(스키마) — 깔끔하나 묶는 흐름이 사용자 부담
- **B**: 태그 기반 느슨한 묶음(`series:os3ep`) — 1급 시민 아님, UI 그룹화 자연스럽지 않음
- **C**: 제목 prefix 휴리스틱 자동 — 사용자 입력 0이지만 휴리스틱은 반드시 오작동
- **D (채택)**: A 스키마 + 색인 시점 자동 묶기 + 관리자 검수 — 1급 시민 + 자동화 + 정정 가능

### 데이터 모델 (초안)
```sql
CREATE TABLE series (
  series_id    TEXT PRIMARY KEY,
  title        TEXT NOT NULL,
  description  TEXT,
  cover_doc_id TEXT,            -- 대표 문서 (선택)
  series_type  TEXT DEFAULT 'book',  -- book | series | volume
  created_at   TIMESTAMPTZ
);

ALTER TABLE documents
  ADD COLUMN series_id           TEXT REFERENCES series(series_id),
  ADD COLUMN volume_number       INT,            -- 1, 2, 3 ... (nullable)
  ADD COLUMN volume_title        TEXT,           -- "Chapter 1: Intro"
  ADD COLUMN series_match_status TEXT DEFAULT 'none';
  -- enum: none | auto_attached | suggested | confirmed | rejected

CREATE INDEX ix_documents_series ON documents(series_id);
```

**Qdrant payload**: 각 청크에 `series_id`, `series_title` 추가 — payload 부분 갱신(재인덱싱 회피) + keyword index.

### 색인 시점 자동 묶기 흐름
indexer_worker BackgroundTasks 체인을 확장: `summary → classify → series_match`.

신뢰도 임계값으로 분기:

| 신뢰도 | 조건 | 처리 |
|---|---|---|
| **High** | 동일 source 폴더 + 공통 prefix ≥ 8자 + 동일 doc_type + 숫자 시퀀스(Chapter N / Vol N / 단순 번호) | **auto_attached** — `series_id` 자동 채움, Qdrant payload 갱신, 신규 시리즈면 `series` 행 자동 생성 |
| **Medium** | High 조건 일부만 충족 | **suggested** — `series_id NULL` 유지, 검수 큐에만 후보 등록 |
| **Low / 매칭 없음** | 휴리스틱 후보 0 | 처리 없음 (`status=none`) |

실패 격리: series_match 실패해도 인덱싱은 성공으로 마무리 (TASK-014 summary 패턴 동일).

### 범위 — 에이전트가 할 일 (착수 시)

**백엔드:**
- [ ] 마이그레이션 `0004_add_series_tables.sql` — sentinel 패턴, advisory lock으로 idempotent (TASK-018 패턴 재사용)
- [ ] `packages/db/models.py` — `SeriesRecord`, `DocumentRecord`에 series 4컬럼 추가
- [ ] `packages/db/repository.py` — series CRUD, `attach_to_series`, `detach_from_series`, `update_match_status`
- [ ] `packages/series/matcher.py` (신규) — 휴리스틱 + 신뢰도 점수 산출. `find_candidates(doc) → list[SeriesCandidate]`
- [ ] `packages/series/__init__.py` — `series_match_for_doc(doc_id)` 진입점
- [ ] `packages/vectorstore/qdrant_store.py` — `set_series_payload(doc_ids, series_id, series_title)` (부분 업데이트)
- [ ] `apps/indexer_worker.py` — BackgroundTasks 체인에 series_match 단계 추가
- [ ] `apps/schemas/query.py` — `QueryRequest.series_filter: Optional[str]`
- [ ] `packages/rag/{pipeline.py,retriever.py}` — series_filter 통과, Qdrant 필터 절(`payload.series_id`)
- [ ] `apps/routers/series.py` (신규) — `GET/POST/PATCH/DELETE /series`, `POST /series/{id}/members`, `POST /documents/{id}/series_match/confirm|reject`
- [ ] `apps/routers/documents.py` — `/documents` 응답에 series 정보 포함, `series_match_status` 필터
- [ ] `apps/schemas/documents.py` — `SeriesItem`, `DocumentItem`에 series 필드 추가
- [ ] LangSmith 트레이스 — `series_filter` 메타 추가
- [ ] `scripts/suggest_series.py` (신규) — 백필용 휴리스틱 일괄 실행, 보고서 JSON

**Streamlit 관리자 UI:**
- [ ] 신규 탭 또는 문서 탭 내부 섹션 "시리즈 검수"
  - 자동 묶기 검수 큐 (`auto_attached`) — [확정] / [Detach] / [다른 시리즈로 이동]
  - 묶기 후보 큐 (`suggested`) — [시리즈로 생성] / [기존 시리즈에 합치기] / [건너뜀]
  - 시리즈 편집 — 메타·멤버 관리, 표지 문서 변경
- [ ] 문서 탭 다중 선택 → [시리즈로 묶기] (수동 경로)

**NextJS (TASK-019 등록 후 그 위에) — 별도 작업이지만 묶음 차원에서 명시:**
- [ ] 도서관 시리즈 카드 그룹화 렌더 (시리즈 카드 vs 단일 카드)
- [ ] 시리즈 상세 뷰 (구성 챕터 N개 리스트)
- [ ] 활성 스코프 배지에 `📚 시리즈 한정` 타입 추가
- [ ] 시리즈 한정 스코프 라우팅 (`/chat?series=...`)

**문서:**
- [ ] ADR-029 — Option A/B/C/D 트레이드오프, Option D 결정 근거, 신뢰도 임계값, 실패 격리
- [ ] `wiki/data/schema.md` — series 테이블·컬럼·payload 갱신
- [ ] `wiki/api/endpoints.md` — `/series` CRUD + `/query.series_filter` + match confirm/reject
- [ ] `wiki/features/admin_ui.md` — 시리즈 검수 섹션
- [ ] `project-wiki/changelog.md` — 신규 버전 (코드 변경 큼)
- [ ] `wiki/overview.md` — 진행표·최근 결정·완료 태스크
- [ ] `log.md` impl 항목

### 의도적 제외
- **재바인딩 무한 시도** — 관리자가 detach한 문서는 동일 휴리스틱으로 다시 자동 묶이지 않도록 `series_match_status=rejected` 마킹으로 기억
- **사용자 측 시리즈 편집 권한** — 관리자 전용 유지. NextJS 사용자 UI는 read-only
- **자동 제안 LLM 보조** — 비용·키 사전 합의 규칙(`feedback_cost_keys`)에 따라 별건. 휴리스틱이 부족하면 그때 합의
- **시리즈와 카테고리·doc 동시 스코프 활성** — 단순화(우선순위: series > category > doc, 한 번에 하나만)
- **시리즈 자동 분류** — 시리즈 자체에 별도 카테고리·태그 부여하지 않음(멤버 문서의 카테고리를 집계해 표면화만)
- **시리즈 단위 요약** — 멤버 요약을 합치는 별도 LLM 호출 도입 안 함(별건 후속 가능성)

### 완료 기준
- 마이그레이션 idempotent(advisory lock + sentinel) 통과
- Qdrant payload 동기화: 기존 문서 백필 일괄 batch update 성공 (재인덱싱 0)
- 새 문서 인덱싱 시 series_match 자동 실행됨 — 인덱싱 성공·실패 격리 보장
- High 신뢰도 케이스: 자동으로 `series_id`/`status=auto_attached`로 채워진 채 done
- `/query.series_filter` 적용 시 해당 시리즈 멤버 청크만 검색됨, vector·hybrid 양 경로 통과
- Streamlit 검수 페이지: 두 큐(auto_attached / suggested) 노출 + Confirm/Detach 동작
- detach된 문서는 `status=rejected` → 동일 휴리스틱이 재바인딩 시도하지 않음
- 도서관 카드: 시리즈 멤버는 시리즈 카드로 응축, 일반 문서는 단일 카드 (NextJS 도입 시점에)

### 회귀 전략
- `series_id IS NULL` 문서는 기존 동작 100% 보존 (단일 카드, doc_filter 그대로)
- `SERIES_ENABLED=true|false` 토글로 도입 시점 분리 가능 (자동 묶기만 비활성화 시 스키마는 유지하되 휴리스틱만 끔)
- 마이그레이션 rollback: 별도 down 마이그레이션 (`DROP TABLE series`, `ALTER TABLE documents DROP COLUMN ...`)
- 백필 실패 시 `series_id` NULL로 되돌리는 1줄 SQL

### 리스크 체크
- **High 신뢰도 임계값이 공격적이면** 잘못된 자동 묶기가 양산되어 관리자 검수 부담 ↑. 보수적 임계값으로 시작 후 운영 데이터로 조정
- **인덱싱 처리량 영향** — series_match가 모든 신규 문서마다 N개 기존 문서·시리즈와 비교. N 작을 땐 무시 가능, 수천 단위 시 인덱스·캐시 필요 (현 20문서 단계는 무영향)
- **Qdrant payload 일괄 갱신과 동시 인덱싱 충돌** — indexer_worker 1프로세스라 자연 직렬화로 회피
- **시리즈 카드 vs 단일 카드의 시각적 일관성** — 도서관 카드 디자인 변동. NextJS 시점에 같이 손보면 비용 작음
- **관리자 검수 부담 누적** — auto_attached 큐가 방치되면 신뢰도 평가 어려움. 검수 페이지 진입 시 미처리 N건 알림 표시로 완화

---

## TASK-021: 프로젝트 프로세스 정기 모니터링 + 워커 RSS 가드 — ✅ 완료 (2026-04-28)
→ ADR-031, changelog [0.24.0], [wiki/deployment/monitoring.md](wiki/deployment/monitoring.md)

**결과**: 스크립트 2개 + LaunchAgents 2개 도입, launchd 등록 시 즉시 1회 실행 + 정기 fork 정상. 모의 SIGTERM 테스트 통과(decoy 프로세스 KILL + 사후 dump 82KB + 자기 PID 제외 검증). ISSUE-005/004 위키 cross-link 완료. TASK-019 Phase B 재개 차례.

---

### 원본 정의 (참고용 보존)

**상태**: queued (2026-04-28 큐잉) — TASK-019 일시 중단 후 끼워넣기. 시스템 freeze 재발 차단이 NextJS 개발 환경 안정성에 직결되는 운영 인프라
**우선순위**: 현재 — 사용자 명시 지시 (2026-04-28)
**관련**: 신규 ADR (착수 시 작성·번호 부여 예정, 다음 가용 ADR-031). [ISSUE-005](wiki/issues/open/ISSUE-005-memory-guard-worker-scapegoat.md) 후속

### 배경
ISSUE-005(메모리 가드 워커 누명 사건, 2026-04-27) 이후 강화 모니터(`/tmp/krag_monitor.py`)는 워커 lifecycle에 묶여 워커 종료와 함께 사라졌다. 2026-04-28 10:10 워커 SIGTERM 시점부터 모니터 부재 — 다음 사건 발생 시 사후 추적 도구 0. 또한 ISSUE-004(Docling 메모리 long-tail) 누수/fragmentation 가설이 idle RSS 13.18GB 평탄 유지로 보강됐으나, 자동 차단 장치는 없음. **워커와 무관하게 상시 가동되는 정기 모니터 + 프로세스별 임계 기반 가드**가 필요.

### 목표
프로젝트(knowledge-rag) 관련 프로세스를 **정기 스냅샷**으로 관찰하고, 워커 RSS가 임계를 넘으면 **그 워커만** 자동 SIGTERM하는 운영 인프라를 도입한다. ISSUE-005 누명(다른 범인을 잡는 사고)을 구조적으로 차단한다.

### 아키텍처 결정 (초안, 착수 시 ADR-031로 확정)

**관찰과 가드의 분리**:
| 컴포넌트 | 주기 | 역할 | 대상 | 동작 |
|---|---|---|---|---|
| `scripts/krag_snapshot.py` | **5분** | 정기 관찰(전용) | 모든 knowledge-rag 관련 프로세스 + 시스템 전체 | 스냅샷 1회 dump → 종료 |
| `scripts/krag_guard.py` | **30초** | 프로세스별 임계 가드 | `apps.indexer_worker` 한정 | RSS ≥ 임계 시 그 PID에만 SIGTERM + 알림 |

두 컴포넌트 모두 launchd가 fork — 데몬 상시 가동 없음, 워커 lifecycle과 독립.

**스냅샷 1회 내용**:
- 시각, 시스템 used%/free%/load1/load5
- knowledge-rag 프로세스 (PID/RSS/%CPU/etime/cmd) — `cwd` 또는 cmdline에 knowledge-rag 포함
- 시스템 전체 RSS top 10
- 인기 포트 LISTEN 카운트(3000/8000/8501)
- 한 줄당 fsync, append 모드

**가드 정책 (사용자 합의 2026-04-28)**:
- **대상**: `apps.indexer_worker` 한정 (NextJS dev / Streamlit / Uvicorn은 제외)
- **임계**: RSS ≥ **14GB** (ISSUE-004 idle 13.18GB 평탄 + 1GB 여유)
- **시그널**: SIGTERM only (graceful 7초 검증됨, SIGKILL 미사용)
- **자동 재기동**: 없음 — 사용자가 상태 보고 결정
- **알림**: macOS 알림 켬 (osascript display notification, 외부 키 0)

**저장**:
- 스냅샷: `data/diag/snapshot/YYYYMMDD.log` — 일자별 단일 파일 (5분 × 288회/일 × ~20줄 ≈ ~1MB/일)
- 가드: `data/diag/guard/YYYYMMDD.log` — 가드 실행 로그(임계 미도달은 1줄, kill 발생 시 사후 snapshot dump 포함)
- 7일 후 gzip 자동 압축 (스크립트 내 자가 처리)

**launchd plist**:
- `~/Library/LaunchAgents/com.knowledge-rag.snapshot.plist` — 5분 주기 (`StartInterval=300`)
- `~/Library/LaunchAgents/com.knowledge-rag.guard.plist` — 30초 주기 (`StartInterval=30`)

### 범위 — 에이전트가 할 일 (착수 시)

**스크립트:**
- [ ] `scripts/krag_snapshot.py` — 단발 실행, knowledge-rag 프로세스 식별(`pwdx`/cmdline grep), top 10 RSS dump, 포트 LISTEN, fsync append
- [ ] `scripts/krag_guard.py` — `apps.indexer_worker` PID 식별, RSS ≥ 14GB 시 SIGTERM + osascript 알림 + `data/diag/snapshot/` 사후 dump
- [ ] 7일 gzip 회전 로직 (양 스크립트 공통 헬퍼)

**launchd:**
- [ ] `~/Library/LaunchAgents/com.knowledge-rag.snapshot.plist` (StartInterval=300)
- [ ] `~/Library/LaunchAgents/com.knowledge-rag.guard.plist` (StartInterval=30)
- [ ] `launchctl load` 절차 + `launchctl list | grep knowledge-rag` 확인

**문서:**
- [ ] ADR-031 — 관찰/가드 분리 결정, 임계값 14GB 근거(ISSUE-004 측정), 대상 워커 한정 사유(ISSUE-005 누명 회피)
- [ ] `wiki/deployment/monitoring.md` (신설) — 모니터링/가드 운영 가이드, plist 등록 절차, 로그 위치, 임계 조정 방법
- [ ] `wiki/issues/open/ISSUE-005-*.md` — 운영 조치 섹션에 본 TASK 도입 cross-link, "관찰 모니터 부재" 단서 보완 명시
- [ ] `wiki/issues/open/ISSUE-004-*.md` — 자동 차단 안전망 도입 명시 (해결 방향 5번 일부 충족)
- [ ] `wiki/index.md` — Deployment 표 monitoring.md 상태 `draft` → `active`
- [ ] `project-wiki/changelog.md` — 신규 버전 (운영 인프라)
- [ ] `wiki/overview.md` — 진행표·최근 결정·완료 태스크
- [ ] `log.md` impl 항목

### 의도적 제외
- **시스템 used% 임계 가드** — ISSUE-005 누명 사건의 결함 그대로. RSS 기반 프로세스별 가드만
- **워커 외 프로세스 가드** (NextJS dev / Streamlit / Uvicorn) — 개발 중인 프로세스를 자동 kill하면 사용자 혼란. 추후 합의 시 화이트리스트 확장
- **자동 재기동** — kill 후 사람이 상태 보고 결정. launchd KeepAlive 미사용
- **`INDEXER_MAX_JOBS` 자가 종료** — ISSUE-004 후속 안 5번. 본 TASK 범위 밖, 별건 후속
- **외부 알림** (Slack / 이메일) — 비용·키 사전 합의 규칙. macOS 로컬 알림만
- **메트릭 시각화** (Grafana / 시계열 DB) — 텍스트 로그 + grep 기반 운영, 위 단계 진입 시 별건
- **가드 로직 ISSUE-005 본격 개선** (RSS top 식별 → 진짜 범인 종료) — 본 TASK는 워커 한정 안전판. 시스템 전체 가드 재설계는 별건

### 완료 기준
- `scripts/krag_snapshot.py` 1회 실행 시 정상 dump (시스템 used%/프로세스 목록/포트/top RSS)
- `scripts/krag_guard.py` 1회 실행 시 워커 미가동 상태에서 정상 종료(0 exit, 로그 1줄), 워커 RSS < 14GB일 때 정상 종료(no-op)
- launchd 등록 후 5분 내 첫 스냅샷 발생 + 30초 내 첫 가드 실행 확인
- 모의 테스트: 워커 RSS를 14GB 초과로 강제(또는 임계를 임시로 낮춰) → 30초 내 SIGTERM + macOS 알림 + 사후 snapshot dump
- 일자 회전: 자정 경계에서 새 파일 생성, 7일 전 파일 gzip 검증 (date stub로 시뮬레이션)
- ADR-031 본문 작성 완료, monitoring.md 신설, ISSUE-005/004 cross-link

### 회귀 전략
- launchd plist `unload` 한 줄로 즉시 무력화: `launchctl unload ~/Library/LaunchAgents/com.knowledge-rag.guard.plist`
- 가드 임계는 plist 환경변수(`KRAG_GUARD_RSS_GB=14`) 또는 스크립트 상수, 1줄 변경으로 조정
- kill 정책 비활성: 가드 스크립트 `--observe-only` 플래그 (관찰 전용 회귀)
- 데이터 정합성에 영향 없음 (관찰·SIGTERM only, DB 변경 0, Qdrant 변경 0)

### 리스크 체크
- **임계 14GB가 너무 공격적** — 정상 잡 처리 중 13GB 피크 후 14GB 잠깐 터치 시 false positive. 합의 시 30초 단발이 아닌 2회 연속 14GB 도달 시 컷으로 보강 검토 가능 (ADR-031 설계 단계에서 결정)
- **macOS 알림 권한** — 첫 실행 시 시스템 권한 다이얼로그. 거부되면 무음 kill됨 (로그엔 남음, 즉 사후 추적 가능)
- **launchd plist 사용자 영역 한정** — 로그아웃 시 가드 정지. 시스템 전역 가드는 별건(권한 부담 큼)
- **자기 자신을 죽일 가능성** — 가드 스크립트 자체 PID 제외 로직 명시 필요
- **idle 13.18GB 평탄(ISSUE-004 가설)이 실제 상시 패턴** — 임계 14GB는 매우 빠듯. 운영 데이터로 16GB 등 조정 검토

**상태**: queued (2026-04-25 큐잉)
**우선순위**: 중간~높음 — 사용자 명시 요구. 검색 품질이 아닌 **"이 RAG에 어떤 정보가 있는지" 탐색 가능성** 개선
**착수 전제조건**: 현재 진행 중인 `bulk_ingest /Volumes/shared/ingaged` (34개 PDF, 2026-04-25 10:38 시작, ETA 14:15 KST 전후) **완료 후** 데이터 작업(마이그레이션·요약 배치·자동 분류 배치) 시작. 코드·문서·ADR 초안 작성은 ingest 도중에도 가능하나, `apps/main.py` 라우트 등록·`ALTER TABLE`·`overwrite_payload` 등은 ingest 종료까지 보류
**관련**: 신규 ADR (착수 시 번호 부여, 단일 컬렉션 + 메타데이터 전략·자동 분류 결정 기록)

### 묶음 배경
사용자가 채팅 화면에서 "이 시스템이 뭘 알고 있는지" 가늠하기 어려움. 현재 admin 문서 목록(TASK-005)은 운영자 관점이지 탐색용이 아님. 인덱싱된 문서를 **사용자가 카탈로그로 일람·요약 조회·해당 문서로 즉시 질의**할 수 있어야 한다.

### 묶음 의존 관계
```
TASK-014 (요약)  ─┐
                 ├──→ TASK-016 (카탈로그 UI) ──→ TASK-017 (랜딩 확장)
TASK-015 (분류)  ─┘
```
- TASK-014/015는 독립 진행 가능하나, TASK-015 자동 분류는 TASK-014 요약의 `topics[]`를 활용하므로 **TASK-014 → TASK-015 권장 순서**
- TASK-016은 TASK-014/015 데이터 모두 필요
- TASK-017은 TASK-016의 컴포넌트 재사용해 빈 채팅 카드로 압축

### 묶음 의도적 제외
- **수동 카테고리 입력 강제** — 자동 추출이 1차, 사용자 수정은 옵션
- **컬렉션 분리** — 단일 Qdrant 컬렉션 유지, ADR에 회귀 조건 명시
- **태그 정규화·병합 UI** — 태그 폭주 시 별건
- **카테고리 트리 GUI 편집** — `config/categories.yaml` 수기 편집부터
- **검색 필터·부스팅 API 활성화** — 별도 후속 TASK(가칭 TASK-018)로 분리

---

## ~~TASK-014: 문서 요약 시스템~~ — ✅ 완료 (2026-04-25)
→ ADR-024, changelog [0.18.0]

**결과**: 16문서 파일럿 모두 success(평균 3.7s/문서, 총 56s, 비용 ≈ $0.08), 환각 0건. 모델은 사용자 합의로 **gpt-4o-mini** 채택(`ANTHROPIC_API_KEY` 부담 회피, ADR-014 LLM 토글 인프라 재활용). 향후 정량 비교 필요 시 Anthropic Haiku로 토글 가능.

**부수 핫픽스**: `apps/routers/ingest.py`의 async 라우트 내부 sync 호출이 event loop를 블록하던 문제를 `asyncio.to_thread`로 해소. bulk_ingest 진행 중에도 `/query`·`/health` 응답 가능. 근본 해결은 TASK-018(색인 워커 분리).

---

### 원본 정의 (참고용 보존)

**상태**: queued (2026-04-25 큐잉)
**우선순위**: 높음 — TASK-015/016/017의 핵심 데이터
**관련**: 신규 ADR (착수 시 번호 부여)

### 배경
사용자에게 "이 문서가 뭐에 대한 것인지" 즉시 보여주려면 문서 단위 자연어 요약이 필요. 현재는 제목·source·페이지 수만 노출. 카탈로그·랜딩·소스 카드 어디서도 의미 단서가 부족.

### 목표
문서당 **한 줄 요약 + 개요 + 주제 태그 + 예시 질문**을 1회 생성·영구 캐시. 후속 TASK 모두에서 재사용.

### 설계 결정 (초안)
- **모델**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) — 비용·지연 최적, 한국어 품질 충분
- **입력**: 문서당 첫 5~10청크(약 2~4K 토큰). 100+ 청크 긴 책은 hierarchical 보강은 후속(현재는 앞부분 편향 감수)
- **저장**: Postgres `documents.summary JSONB` 영구 캐시 — 재인덱싱 시에만 재생성. 사용자 "재요약" 버튼은 강제 재생성 트리거
- **JSON 스키마**:
  ```json
  {
    "one_liner": "한 줄 요약 (40자 이내)",
    "abstract": "3~5문장 개요",
    "topics": ["주제1", "주제2", "주제3"],
    "target_audience": "초급/중급/고급 + 대상 독자",
    "sample_questions": ["문서로 답할 수 있는 구체 질문 3개"]
  }
  ```
- **환각 차단**: 프롬프트에 "문서에 없는 내용 생성 금지", `sample_questions`는 불확실하면 빈 배열 허용
- **실패 격리**: summary 생성 실패해도 인덱싱은 성공. `summary_generated_at = NULL` 상태로 남겨 배치에서 재시도

### 범위
- [ ] Postgres 마이그레이션 — `documents`에 `summary JSONB`, `summary_model VARCHAR`, `summary_generated_at TIMESTAMPTZ` 추가
- [ ] `packages/summarizer/document_summarizer.py` 신설 — Anthropic SDK, JSON schema 강제, prompt caching 적용
- [ ] 프롬프트 템플릿 (`packages/summarizer/prompts.py`) — 한국어 자연어, 환각 방지, 예시 2~3개 few-shot
- [ ] `scripts/generate_summaries.py` — 미요약 문서 일괄 처리, 진행률·재시도·rate limit·진행 로그
- [ ] 신규 인덱싱 훅 — `apps/routers/documents.py` 업로드 완료 후 비동기 summary 생성 (실패 무관)
- [ ] `GET /documents/{doc_id}/summary` API + 응답 스키마
- [ ] `POST /documents/{doc_id}/summary/regenerate` (admin 전용) — 강제 재생성
- [ ] 파일럿 배치 — 보유 47문서 실행, 품질 수동 검수 (예상 비용 ~$0.1)
- [ ] 결과 검수 후 프롬프트 1~2회 튜닝
- [ ] ADR 작성 (모델·스키마·캐시 정책)
- [ ] changelog `[0.18.0]` 항목, log.md impl 항목

### 완료 기준
- 모든 인덱싱 문서가 `summary` JSONB 보유 (또는 NULL + 재시도 큐)
- API로 단건 조회 가능
- 신규 업로드 시 자동 생성 (비동기)
- 프롬프트 출력이 환각 없이 문서 내용에 충실

### 회귀 전략
- 컬럼 DROP 마이그레이션 역방향
- API 라우트 제거 시 다른 코드 영향 0 (요약은 부가 정보)
- 프롬프트 변경 후 결과가 나쁘면 이전 프롬프트로 복원 + 영향 문서만 재생성

### 리스크
- **앞부분 편향** — 책 서문이 일반적이면 요약 빈약. 100+ 청크 긴 문서엔 후속 hierarchical TASK 필요
- **API 장애·rate limit** — 배치 재시도, 일 cost cap 설정
- **품질 편차** — 한국어 전문 서적은 맥락 누락 가능, 검수 + 프롬프트 튜닝 1~2회 필요

---

## TASK-018: 색인 워커 프로세스 분리 — Postgres `ingest_jobs` 큐 + indexer

**상태**: queued (2026-04-25 큐잉)
**우선순위**: 높음 — bulk_ingest 진행 중 사용자 query 지연·블록 직접 해소
**관련**: TASK-010(bulk CLI), TASK-014(summary 훅) 핫픽스 후속, 신규 ADR(착수 시 번호 부여, 다음 가용 ADR-025)

### 배경
- 현재 ingest는 FastAPI 같은 프로세스에서 동기로 처리 — Docling 파싱이 CPU·메모리를 점유하는 동안 `/query`·`/health` 응답이 사용자에게 체감될 정도로 느려짐
- TASK-014 핫픽스(`asyncio.to_thread`)로 event loop 블록은 풀렸지만, 같은 프로세스 자원 경합은 여전. 큰 PDF 50건 일괄 색인 시 사용자 채팅이 영향
- bulk_ingest는 HTTP `POST /ingest`를 줄줄이 호출 — uvicorn 재기동·실수 종료에 색인 잡 손실

### 목표
색인을 **별도 워커 프로세스**로 분리. FastAPI는 사용자 요청만 처리, 색인 잡은 큐에 들어가 워커가 순차 처리. bulk_ingest는 큐에 직접 enqueue.

### 설계 결정 (초안)
- **큐**: Postgres `ingest_jobs` 테이블. `SELECT … FOR UPDATE SKIP LOCKED`로 멀티 워커도 안전. 의존성 추가 0 (이미 Postgres 사용 중)
- **상태 머신**: `pending → in_progress → done|failed`, 재시도 카운터·실패 사유·`enqueued_at`/`started_at`/`finished_at`
- **워커 프로세스**: `apps/indexer_worker.py` — 폴링 루프(2~5초 간격) + 잡 처리 + summary 훅까지 한 번에 (TASK-014 BackgroundTasks를 워커로 이관)
- **API 변경**: `POST /ingest`는 파일 저장 + 큐 enqueue + 즉시 `202 Accepted` + `{job_id, doc_id, status: "pending"}` 응답
- **bulk_ingest CLI**: `--via-queue` 옵션 신설 — HTTP 거치지 않고 직접 큐에 enqueue
- **운영**: docker-compose에 `indexer` 서비스 추가, FastAPI는 `--workers 1`로 충분. 워커 수는 `INDEXER_CONCURRENCY=1` 기본
- **관측**: 워커 진행을 LangSmith에 기존 `rag.ingest` 트레이스로 묶음, `GET /jobs?status=pending` admin 라우트(인증 미도입 단계는 로컬 LAN 한정)

### 범위 — 코드
- [ ] Postgres 마이그레이션 `0002_add_ingest_jobs.sql` — `id BIGSERIAL PK, doc_id, file_path, title, source, content_hash, status, retry_count, error, timestamps`
- [ ] `packages/jobs/queue.py` 신설 — `enqueue()`, `claim()`(SKIP LOCKED), `mark_done()`, `mark_failed()`
- [ ] `apps/indexer_worker.py` — entry point `python -m apps.indexer_worker`, signal 핸들러로 graceful shutdown
- [ ] `apps/routers/ingest.py` — 인덱싱 직접 호출 제거, 큐 enqueue + `202` 응답 + `IngestResponse`에 `job_id` 추가
- [ ] `apps/routers/jobs.py` 신규 — `GET /jobs/{job_id}`, `GET /jobs?status=pending|failed&limit=N`
- [ ] `scripts/bulk_ingest.py` — `--via-queue` 분기 (HTTP 경로는 deprecation 경고만, 한 릴리스 유지)
- [ ] docker-compose `indexer` 서비스 (uvicorn 이미지 재사용, command만 다름)
- [ ] TASK-014 `BackgroundTasks` 훅 제거 → 워커가 인덱싱 직후 같은 트랜잭션 흐름에서 summary 호출
- [ ] `wiki/architecture/decisions.md` ADR-025 신규 — 큐 선택지 비교, 단일 vs 멀티 워커, 회귀 전략
- [ ] `changelog.md` `[0.19.0]`, `log.md` impl 항목, `roadmap.md` ✅ 마킹

### 완료 기준
- bulk_ingest 50건 진행 중에도 `/query` p95 latency가 색인 정지 상태와 동일 (±10%)
- uvicorn 재기동·indexer 재기동에도 큐의 미완료 잡이 자동 재처리됨
- `--via-queue` 모드 bulk_ingest가 100% 잡 enqueue 성공
- TASK-014 summary가 워커에서 정상 트리거(BackgroundTasks 제거 후 회귀 0)

### 의도적 제외
- Redis/RabbitMQ/Celery — 의존성 추가 없이 Postgres로 충분
- 분산 워커 (멀티 머신) — 단일 노드 멀티 프로세스만
- UI 잡 진행 표시 — 별건(관리자 UI 2단계 합류 시점)
- 워커 자동 스케일링 — 정적 `INDEXER_CONCURRENCY`만

### 회귀 전략
- 컬럼·서비스 제거 마이그레이션 역방향
- `ENQUEUE_MODE=sync|queue` 토글로 단계 전환 — sync 모드에서는 기존 동작 회귀
- bulk_ingest의 `--via-queue` 미지정 시 HTTP 경로 한 릴리스 유지

### 리스크
- **워커 1개에 PDF 100MB가 걸리면 뒤 잡 모두 대기** — 우선 단일 워커로 단순화, 필요 시 `INDEXER_CONCURRENCY` 증가
- **FastAPI/워커 모델 메모리 중복** — Reranker는 FastAPI에만, 워커는 Docling만. 임베딩은 둘 다 필요 (배포 메모리 ~2GB 추가 예상)
- **트랜잭션 경계** — 잡 claim·document INSERT·status update가 분리. SKIP LOCKED로 동시성, 멱등 키(`content_hash`) 유지

---

## ~~TASK-015: 카테고리 메타데이터 + 자동 분류~~ — ✅ 완료 (2026-04-25)
→ ADR-025, changelog [0.19.0]

**결과**: 파일럿 20문서 정확도 20/20 (rule 16 + LLM 4, 총 5.7초, ≈$0.001). categories.yaml 9개 카테고리 + 단일 Qdrant 컬렉션 유지(payload index 4개) 결정. PATCH `/documents/{id}` 메타데이터 수정 API + ingest 폼 옵션 파라미터 동시 도입.

---

### 원본 정의 (참고용 보존)

**상태**: queued (2026-04-25 큐잉)
**우선순위**: 중간 — TASK-016 그룹핑의 축
**관련**: TASK-014(요약 활용), 신규 ADR (단일 컬렉션 + 메타데이터 결정)

### 배경
현재 `documents` 테이블·Qdrant payload에 분류 필드 0개. 카탈로그 그룹핑·필터·도서관 뷰의 기반이 비어 있음. 책만 인덱싱 중인 상태에서 아티클·논문·메모가 추가될 때 운영 분리 부담을 줄이려면 단일 컬렉션 + 메타데이터 전략이 적합.

### 목표
문서별 `doc_type`(형식) · `category`(도메인) · `tags`(자유 라벨)를 **수동 입력 부담 없이 자동 채움**. 사용자 입력은 옵션이지 필수 아님.

### 설계 결정 (초안)
- **단일 Qdrant 컬렉션 유지** — 컬렉션 분리는 "임베딩 모델을 유형별로 달리 써야 할 때"까지 보류. ADR에 회귀 조건 명시
- **`doc_type` enum**: `book` | `article` | `paper` | `note` | `report` | `web` | `other` (default `book`)
- **`category`**: 단일 문자열, `config/categories.yaml`로 초기 트리 관리 (계층형 "ai/ml" 허용)
- **`tags`**: 문자열 배열, **TASK-014 요약의 `topics[]`를 그대로 채택** (별도 입력 UI 없음)
- **자동 분류 파이프라인**:
  1. `topics[]`를 `categories.yaml` 라벨과 키워드 매칭 (1차)
  2. 매칭 실패 시 LLM에 "categories.yaml 중 가장 적합한 1개 + 신뢰도" 분류 요청 (TASK-014 호출과 동일 turn에 통합 가능)
  3. 신뢰도 낮으면 `category=NULL` 유지, admin UI에 "검토 필요" 배지

### 범위
- [ ] Postgres 마이그레이션 — `doc_type VARCHAR NOT NULL DEFAULT 'book'`, `category VARCHAR NULL`, `tags JSONB DEFAULT '[]'::jsonb`, CHECK 제약(doc_type enum)
- [ ] `DocumentRecord`/`DocumentItem` 스키마 동기화
- [ ] Qdrant payload에 동일 3필드 동기화 (`packages/vectorstore/qdrant_store.py` 인덱싱 경로)
- [ ] Qdrant payload index 추가 — `doc_type`·`category` keyword 인덱스, `tags` keyword 배열 인덱스 (이후 검색 필터 활성화 시 사용)
- [ ] 기존 청크 마이그레이션 스크립트 (`scripts/migrate_payload_meta.py`) — scroll → Postgres 조회 → `overwrite_payload` 온라인 업데이트
- [ ] `config/categories.yaml` 신설 — 사용자 보유 도서 기준 초기 트리 (착수 시 사용자와 확정)
- [ ] `packages/classifier/category_classifier.py` 신설 — topics 매칭 + LLM fallback
- [ ] 자동 분류 배치 (`scripts/classify_documents.py`) — 미분류 문서 일괄 실행
- [ ] 업로드 API 옵션 파라미터 — `doc_type`·`category`·`tags` (모두 optional, 자동 추정 우선)
- [ ] 업로드 폼: 자동 추정 결과 표시 + "수정" 옵션 (강제 입력 아님)
- [ ] admin UI 문서 목록에 분류 컬럼 추가, 신뢰도 낮은 문서에 배지
- [ ] 카테고리·태그 변경 API (`PATCH /documents/{doc_id}`) — 사용자 수정 반영
- [ ] 테스트 — 스키마 기본값·enum, 마이그레이션 건전성, 자동 분류 정확도 (수동 라벨 10개 비교)
- [ ] ADR 작성 (단일 컬렉션 결정, 자동 분류 전략, 컬렉션 분리 회귀 조건)
- [ ] changelog `[0.19.0]`, log.md impl 항목

### 의도적 제외 (후속)
- 검색 시 메타데이터 필터·부스팅 (별건 TASK)
- 패싯 검색 사이드바 (TASK-016에서 일부, 본격은 별건)
- 카테고리 트리 GUI 편집 — YAML 수기 편집

### 완료 기준
- 모든 문서가 `doc_type`(필수) + `category`(or NULL) + `tags[]`(or [])로 채워짐
- 새 업로드 시 자동 분류 실행, 실패는 NULL 허용
- Qdrant payload index 생성 확인 (`get_collection`으로 확인)
- 기존 47문서 백필 완료, 회귀 0

### 회귀 전략
- 마이그레이션 역방향: 컬럼·인덱스 DROP
- Qdrant payload 필드는 default 처리 — 삭제 안 해도 무해
- UI 토글로 분류 표시 off 가능

### 리스크
- **categories.yaml 조기 동결** — 초기 카테고리 변동 잦음, 재분류 배치 필요성 인지
- **자동 분류 오류** — LLM이 잘못된 카테고리 부여 가능, "검토 필요" 배지 + 사용자 수정 경로 필수
- **Qdrant payload 업데이트 부하** — 컬렉션 크기 비례, `overwrite_payload`로 온라인 처리

---

## TASK-016: 사용자용 문서 카탈로그 UI ("도서관" 탭)

**상태**: queued (2026-04-25 큐잉)
**우선순위**: 높음 — 사용자 명시 핵심 요구 ("색인된 전체 문서 목록 접근 + 카테고리별 + 요약")
**관련**: TASK-014(요약), TASK-015(분류), 신규 ADR

### 배경
admin 문서 목록(TASK-005)은 운영자용. 사용자가 RAG가 아는 내용을 탐색·해당 문서로 질의 시작할 수 있는 별개 UI가 필요. 핵심: 카테고리 그룹·요약 즉시 노출·"이 책에 대해 묻기" 액션.

### 목표
별도 "도서관" 탭에서 (a) 전체 문서 일람, (b) 카테고리별 그룹 보기, (c) 요약 즉시 확인, (d) 클릭 한 번으로 해당 문서로 한정 질의 시작.

### 설계 결정 (초안)
- **위치**: Streamlit `st.tabs(["채팅", "도서관", "관리자"])` 통합 — 기존 페이지 구조 유지
- **기본 뷰**: 카테고리 그룹 (collapsible expander)
- **대안 뷰**: 평면 그리드(최신순/제목순/카테고리순 정렬)
- **검색**: 제목·태그·요약 텍스트 ILIKE — Postgres 인덱스(GIN tsvector)로 가속
- **요약 노출**: 카드에는 `one_liner` + `topics` 칩 3개, "요약 보기" 클릭 시 모달에 abstract + sample_questions
- **"질문하기" 액션**: 채팅 탭으로 이동 + 입력창에 "이 문서에 대해..." 자동 채움 + `doc_filter={doc_id}` 적용
- **`doc_filter` 검색 한정**: 검색 시 Qdrant filter `must: doc_id == X` 적용 (이미 가능, 라우트에서 옵션 파라미터로 노출)

### 범위
- [ ] API 신설:
  - `GET /library/catalog?category=&doc_type=&q=&sort=&page=&limit=` — 페이지네이션, 정렬
  - `GET /library/categories` — 카테고리 목록 + 문서 수 집계
  - `GET /library/recent?limit=5`
  - `GET /library/stats` — 총 문서 수, 카테고리 수, 최근 추가 건수
- [ ] 기존 `POST /chat` 또는 `/query`에 `doc_ids: list[str]` 옵션 파라미터 추가 — 특정 문서로 검색 한정
- [ ] Streamlit `ui/pages/library.py` 신설:
  - 최상단: 통계 바 + 검색창 + 정렬 셀렉트
  - 카테고리 그룹: `st.expander`로 카테고리별 문서 카드 그리드 (3열)
  - 카드 컴포넌트(`ui/components/doc_card.py`): doc_type 아이콘·제목·one_liner·topics 칩·[요약 보기]·[질문하기]
  - 요약 모달: `st.dialog` 또는 expander에 abstract + sample_questions(클릭 가능 칩) + target_audience + 메타
  - 필터 사이드바: 카테고리 다중·doc_type 다중·태그 클릭·날짜 범위·"샘플 질문 있음만" 토글
- [ ] sample_question 칩 클릭 → 채팅 탭 이동 + 질문 + doc_filter 적용
- [ ] doc_type 아이콘·색상 헬퍼 (`ui/components/badges.py`) — 책📖/아티클📰/논문📄/메모📝/리포트📊/웹🌐
- [ ] `tabs` 내비게이션 통합 — 기존 채팅 화면 유지
- [ ] 미분류 문서(`category=NULL`) 별도 그룹 표시 ("미분류")
- [ ] 빈 카탈로그 상태(0문서) 안내 + "업로드하러 가기" 링크
- [ ] E2E 테스트 — 카드 렌더링·필터·"질문하기" 액션 라우팅
- [ ] ADR 작성 (탭 통합 결정, doc_filter 라우팅 패턴)
- [ ] changelog `[0.20.0]`, log.md impl 항목

### 의도적 제외
- 원문 미리보기(청크 노출) — 별건, 저작권·UX 별도 검토
- 패싯 검색 본격 구현(다중 facet 카운트 갱신) — 단순 필터로 시작
- 문서 간 유사도 네트워크 뷰 — 후기 단계
- 사용자별 즐겨찾기·읽은 문서 표시 — 별건

### 완료 기준
- "도서관" 탭에서 전체 문서가 카테고리별 그룹으로 보임
- 검색·정렬·필터 동작
- 카드 [요약 보기] → 모달, [질문하기] → 채팅 이동 + 해당 문서 한정 검색
- 47문서 기준 첫 렌더 1초 이내, 페이지네이션 정상

### 회귀 전략
- 탭 제거하면 기존 채팅·관리자 화면 영향 0
- API 라우트는 부가, 제거 시 다른 경로 영향 0
- `doc_filter` 옵션은 기본 미지정이므로 영향 0

### 리스크
- **요약 미생성 문서**(TASK-014 부분 실패) — 카드에 "요약 생성 중" placeholder + 재시도 버튼
- **카테고리 미분류 폭주** — TASK-015 신뢰도 임계 조정 + 검토 배지로 흡수
- **Streamlit 모달 한계** — `st.dialog` 미지원 버전이면 expander로 폴백

---

## TASK-017: 랜딩 대시보드 확장 (빈 채팅 카드 v2)

**상태**: queued (2026-04-25 큐잉)
**우선순위**: 중간 — TASK-016의 미니 버전, 1~2일 작업
**관련**: TASK-008(완료, ADR-020) 확장, TASK-014/015/016 데이터 활용

### 배경
TASK-008로 빈 채팅에 인덱스 요약 카드 + 예시 질문이 이미 존재. 본 TASK는 그 카드를 **"이 시스템이 아는 것"을 더 풍부하게** 표현하도록 확장. TASK-014 요약과 TASK-015 카테고리 데이터가 채워진 시점에 자연스러움.

### 목표
빈 채팅 진입 시 "뭘 물어볼지 모르겠다" 상태를 즉시 해소. 주제 칩·예시 질문·최근 추가 문서·"전체 도서관 보기" 진입로 노출.

### 설계 결정 (초안)
- **TASK-008 카드 확장** — 신규 페이지 X, 기존 빈 채팅 영역에 섹션 추가
- **데이터 소스**:
  - 통계: `GET /library/stats`
  - 주제 칩: 모든 문서의 `topics[]` 빈도 집계 상위 8개
  - 예시 질문: 무작위 문서 3~5개의 `sample_questions` 샘플링 (요청마다 새로고침)
  - 최근 추가: `GET /library/recent?limit=3`
- **상호작용**:
  - 주제 칩 클릭 → 입력창에 키워드 자동 입력 (전송 X, 사용자가 다듬을 여지)
  - 예시 질문 칩 클릭 → 입력창에 질문 자동 입력
  - 최근 문서 카드 [이 책에 대해 묻기] → 채팅 시작 + doc_filter
  - "전체 도서관 보기" → TASK-016 탭으로 이동
- **사라지는 시점**: 사용자가 첫 메시지 입력하면 카드 영역 숨김

### 범위
- [ ] `GET /library/topics?limit=8` — `topics[]` 집계 상위 N개 (Postgres `jsonb_array_elements` + group by)
- [ ] `GET /library/sample-questions?limit=5` — 무작위 문서의 sample_questions 샘플링
- [ ] `ui/components/landing_card.py` 신설 — 통계·주제 칩·예시 질문·최근 문서 4섹션
- [ ] 기존 TASK-008 카드 영역(`ui/app.py` 빈 채팅 분기)에 통합
- [ ] 칩 클릭 → 입력창 prefill 로직 (Streamlit `st.session_state`)
- [ ] "전체 도서관 보기" 버튼 → 탭 전환 트리거
- [ ] E2E 테스트 — 빈 채팅 상태에서 4섹션 렌더, 칩 클릭 prefill, 첫 메시지 후 카드 숨김
- [ ] changelog `[0.21.0]`, log.md impl 항목 (ADR-020 확장 명시)

### 의도적 제외
- 사용자별 추천 (개인화 추천 모델) — 별건
- 주제 클러스터링 기반 동적 그룹 — 후기, 단순 빈도 집계로 시작
- 카테고리 파이 차트·태그 클라우드 시각화 — 별건 (TASK-016에 일부 통계만)

### 완료 기준
- 빈 채팅 화면에서 4섹션이 즉시 렌더
- 칩·카드 클릭 → 입력창 prefill 또는 탭 이동 동작
- 첫 메시지 입력 시 카드 영역 자연스럽게 숨김
- 47문서 기준 카드 첫 렌더 500ms 이내

### 회귀 전략
- 컴포넌트 제거 시 TASK-008 v1 카드로 자동 복원
- API 라우트는 부가, 제거 시 영향 0

### 리스크
- **`topics[]` 빈도 편중** — 책 위주 코퍼스에서 특정 주제 폭주 가능, top-N 노출만으로 해소
- **랜덤 샘플링 일관성** — 새로고침마다 변하면 혼란, 세션 단위 캐시 또는 시드 고정 옵션

---

## 완료된 항목

| 항목 | 완료일 |
|------|--------|
| 위키 초기 구조 설정 | 2026-04-17 |
| 전체 RAG 파이프라인 구현 (M1·M2·M4) | 2026-04-19 |
| 대화 히스토리 DB 저장 + 최근 20턴 컨텍스트 주입 | 2026-04-21 |
| 중복 업로드 방지 L1 (SHA-256 파일 해시) | 2026-04-21 |
| LangSmith 관측 통합 (`@traceable` + 세션 태그 + 단계별 타이머) | 2026-04-21 |
| 파싱 후 정규화 (단어 분리 복구·페이지 번호 제거 등) | 2026-04-21 |
| 모바일 업로드 호환 + 상한 200MB + score_threshold 튜닝 | 2026-04-21 |
| HybridChunker + 전체 heading 경로 breadcrumb + 페이지 번호 복구 | 2026-04-21 |
| 원본 파일 영구 보관 (재인덱싱 가능 구조) | 2026-04-21 |
| FlashRank 재순위 실제 활성화 | 2026-04-21 |
| 기존 6개 문서 마크다운 fallback으로 재인덱싱 완료 (ROS PDF 1619→800청크) | 2026-04-21 |
| TASK-001 BGE-reranker-v2-m3 도입 + 토글 + A/B 비교 | 2026-04-22 |
| TASK-003 LLM 백엔드 토글 인프라 (openai/glm/custom, ADR-014) | 2026-04-22 |
| TASK-004 평가 프레임워크 (Ragas + 자체 벤치, 기반선 수립, ADR-015) | 2026-04-22 |
| TASK-002 BGE-M3 임베딩 토글 + A/B (OpenAI 기본 유지, ADR-016) | 2026-04-22 |
| TASK-005 관리자 UI 1단계 (5개 탭, 청크 미리보기, ADR-017) | 2026-04-22 |
| TASK-007 Phase 1 — 후속 질문 제안 (LLM JSON 통합, ADR-019) | 2026-04-22 |
| TASK-008 — 빈 채팅 인덱스 요약 카드 + 예시 질문 (ADR-020) | 2026-04-22 |
| TASK-009 — DELETE 파일 정리 + HybridChunker 토큰 상한 480 (ADR-021) | 2026-04-22 |
| TASK-010 — 폴더 단위 일괄 색인 CLI + 재실행 안전성 (ADR-022) | 2026-04-23 |
