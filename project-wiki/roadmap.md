# 로드맵

**상태**: active
**마지막 업데이트**: 2026-04-21
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
→ ✅ TASK-007 → ✅ TASK-008 → ✅ TASK-009 → ✅ TASK-010 → ✅ TASK-011  (모든 예정 완료)
→ 🛑 인증·공개배포 전체 묶음 (사용자 지시까지 전부 보류, 2026-04-22)
     · ISSUE-001 (모바일 업로드) · 관리자 UI 2단계 · HTTPS 배포 · API 키/OAuth · 관리자 전용 UI 버튼
→ 🔄 장기 검토: Graph RAG, MCP 재개, 대화 요약, 인증, 스트리밍, L2 중복 감지
```

#### 사용자 관점 개선 경로 (요약)
| 단계 | 완료 시 체감 변화 |
|---|---|
| TASK-007 | 답변 아래에 "이어서 물을 질문 3개" 자동 배지 — 클릭으로 탐색 연쇄 |
| TASK-008 | 빈 채팅에 "이 시스템이 아는 내용" 요약 + 예시 질문 5개 |
| TASK-009 | 문서 삭제 시 디스크까지 완전 정리 + 긴 청크 누락 제거 |
| **TASK-010** | **폴더 단위 일괄 색인 CLI** — 한 명령으로 수십~수백 개 문서 자동 등록, 중복 건 스킵, 실패 리포트** |
| (보류) 인증·공개배포 묶음 | 모바일 업로드, HTTPS 외부 접속, 관리자/사용자 경로 분리, 재인덱싱/벤치 버튼 — 사용자 지시까지 전부 보류 |

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
