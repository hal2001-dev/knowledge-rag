# Wiki Log

이 파일은 append-only입니다. 항목을 수정하지 말고 새 항목을 위에 추가하세요.
`grep "^## \[" log.md | head -10` 으로 최근 항목을 빠르게 확인할 수 있습니다.

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
