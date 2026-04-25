# Architecture Decision Records (ADR)

**마지막 업데이트**: 2026-04-21

설계에서 중요한 결정을 내릴 때마다 여기에 기록합니다.
"왜 이렇게 했지?" 를 나중에 찾아보기 위한 파일입니다.

---

## ADR 형식

```
## ADR-NNN: 결정 제목
**날짜**: YYYY-MM-DD
**상태**: [proposed|accepted|deprecated|superseded by ADR-NNN]

### 배경
왜 이 결정이 필요했는가

### 선택지
1. 옵션 A — 장단점
2. 옵션 B — 장단점

### 결정
무엇을 선택했고 왜

### 결과
이 결정의 영향 및 트레이드오프
```

---

## ADR-001: 벡터 DB — Qdrant 선택
**날짜**: 2026-04-19
**상태**: accepted

### 배경
문서 임베딩을 저장하고 유사도 검색을 수행할 벡터 DB가 필요.

### 선택지
1. **FAISS** — 로컬, 빠름, 별도 서버 불필요, persistence 직접 관리 / 삭제 미지원
2. **Chroma** — 로컬 DB, 메타데이터 필터링 편리
3. **Qdrant** — Docker 기반, doc_id 필터 삭제 지원, langchain-qdrant 공식 통합
4. **Pinecone** — 관리형 클라우드, 비용 발생

### 결정
**Qdrant** 선택. Docker로 로컬 운영 가능하고 doc_id 필터 기반 삭제를 네이티브로 지원해 문서 삭제 요구사항 충족. LangChain 공식 통합 패키지(`langchain-qdrant`) 제공.

### 결과
- Docker 의존성 추가 (`docker-compose.yml`)
- FAISS 대비 삭제·필터링 기능 우수
- 로컬 개발 시 포트 6333 사용

---

## ADR-002: Chunking 전략
**날짜**: 2026-04-19
**상태**: accepted

### 배경
PDF를 어떻게 쪼갤 것인가. chunk size와 overlap이 검색 품질에 직접 영향.

### 선택지
1. **Fixed size** (512 tokens, overlap 50) — 단순, 문맥 단절 가능
2. **Sentence-based** — 문장 경계 존중, 크기 불균일
3. **Recursive character** (LangChain) — 단락 → 문장 → 단어 순서로 분할
4. **Semantic chunking** — 의미 기반, 비용 높음

### 결정
**RecursiveCharacterTextSplitter (512자, overlap 50)** 채택. Docling이 1차 청킹한 결과를 그대로 사용하되, 512자 초과 청크만 재분할. 한국어·영어 혼합 문서에서 토큰 기반보다 문자 기반이 안정적.

### 결과
- `langchain-text-splitters` 패키지 사용
- 테이블·이미지 청크는 분할하지 않고 원본 유지 (content_type 태깅)

---

## ADR-003: 임베딩 모델 선택
**날짜**: 2026-04-19
**상태**: accepted

### 배경
한국어 문서를 포함할 경우 다국어 모델 필요 여부 검토.

### 선택지
1. **OpenAI text-embedding-3-small** — 성능 좋음, API 비용 발생, 1536차원
2. **OpenAI text-embedding-3-large** — 더 높은 성능, 더 높은 비용
3. **BGE-M3** — 오픈소스, 다국어 지원, 로컬 실행 가능
4. **ko-sroberta-multitask** — 한국어 특화

### 결정
**OpenAI text-embedding-3-small** 선택. 한국어·영어 혼합 문서에서 충분한 성능, 빠른 프로토타이핑에 적합. 추후 BGE-M3으로 교체 가능하도록 embeddings 계층 추상화.

### 결과
- Qdrant 컬렉션 vector size: 1536
- API 비용 발생 (usage 모니터링 필요)

---

## ADR-004: 문서 파서 선택
**날짜**: 2026-04-19
**상태**: accepted

### 배경
PDF의 텍스트뿐 아니라 테이블·이미지까지 구조화 추출 필요.

### 선택지
1. **pdfplumber** — 텍스트·표 추출, 이미지 미지원
2. **PyMuPDF** — 빠름, 이미지 추출 가능, 표 구조화 약함
3. **Docling (IBM)** — 텍스트·테이블·이미지 통합 추출, LangChain 공식 통합

### 결정
**Docling 2.x** 선택. 테이블을 Markdown으로 변환하고 이미지 캡션 추출 지원. `langchain-docling` 패키지로 LangChain 파이프라인에 직접 통합.

### 결과
- 파싱 시 `data/markdown/{doc_id}.md`에 전체 문서 저장
- content_type 메타데이터로 text/table/image 청크 구분
- Docling 모델 최초 실행 시 다운로드 필요 (약 1~2GB)
- **스캔 PDF OCR**: Docling의 `PdfPipelineOptions.do_ocr=True` 기본값으로 **자동 처리**됨 (EasyOCR 내장). 텍스트 레이어 있는 PDF는 OCR 건너뛰고 직접 추출, 스캔 PDF는 자동으로 OCR 경로 진입. 전체 E2E 프로세스는 [spec.md PDF 처리 프로세스](../data/spec.md#pdf-처리-프로세스-end-to-end) 참고
  - 2026-04-23 확인: 위키 초기 기록(spec.md의 "스캔 PDF = OCR 필요·추후 검토", troubleshooting의 "OCR 미지원")은 **추정이었을 뿐 실제 코드는 처음부터 OCR 동작** — 정정 완료

---

## ADR-005: 중복 업로드 감지 — L1(파일 해시)부터 적용
**날짜**: 2026-04-21
**상태**: accepted

### 배경
`/ingest`가 매 호출마다 `uuid.uuid4()`로 새 `doc_id`를 생성해 동일 파일을 재업로드하면 벡터·메타데이터·마크다운이 전부 중복 생성되던 문제 (실제로 `data/markdown/` 내 동일 내용 파일 2벌 확인).

### 선택지
1. **L1 파일 해시** — 업로드 바이트의 SHA-256을 `documents.content_hash`(UNIQUE)에 저장, 충돌 시 409
2. **L2 정규화 텍스트 해시** — Docling 파싱 후 마크다운 텍스트의 해시. 포맷만 다른 동일 내용도 감지 가능하나 파싱 비용을 일단 지불해야 함
3. **L3 의미 유사도** — 대표 청크 임베딩의 코사인 유사도 ≥0.95 경고. 리비전 차이 감지 가능, 구현 비용 최고

### 결정
**L1 먼저 단독 적용.** 구현이 단순하고 "동일 바이트 재업로드" 80%+ 케이스를 막을 수 있음. L2/L3는 필요 시 후속 도입.

### 결과
- `ALTER TABLE documents ADD COLUMN content_hash VARCHAR(64)` + UNIQUE INDEX 적용
- `apps/routers/ingest.py`에서 `hashlib.sha256(content).hexdigest()` 후 `get_document_by_hash()` 조회 → 충돌 시 `409 Conflict` + 기존 `doc_id`/`title`/`content_hash` 반환 (idempotent)
- 기존 레코드는 `content_hash=NULL` — UNIQUE 인덱스는 NULL 중복을 허용하므로 호환성 문제 없음
- 한계: 파싱·포맷 차이가 있는 동일 내용은 감지 불가 → L2 도입 시 해결

---

## ADR-006: 대화 히스토리 — 최근 N턴만 DB에서 로드해 주입
**날짜**: 2026-04-21
**상태**: accepted

### 배경
단일 턴 QA만 지원하던 상태에서, 후속 질문의 대명사/지시어(예: "그게 뭔데?", "그럼 다른 경우는?")를 해결할 필요가 생김. 히스토리를 어디에 저장하고 얼마나 주입할지 결정 필요.

### 선택지
1. **In-memory 딕셔너리** — 간단. 서버 재시작 시 소실, 다중 워커 부적합
2. **DB 저장 + 매 요청마다 최근 N개 로드** — 영속성·다중 워커 안전, 토큰 비용·컨텍스트 길이 제어 가능
3. **LangChain `ConversationBufferMemory` / summary 메모리** — 추상화 이득은 있으나 본 프로젝트는 이미 얇은 파이프라인이라 오버엔지니어링

### 결정
**옵션 2 채택, `N = 20`**. `conversations`/`messages` 테이블을 만들고 매 `/query`마다 현재 턴 저장 **전**에 최근 20개 메시지 스냅샷을 LLM에 주입 (`SystemMessage → Human/AIMessage× → 현재 질문`).

### 결과
- 신규 테이블: `conversations`, `messages(session_id, created_at IDX)`
- `/query`에 `session_id` 옵션 추가, 응답에도 `session_id` 포함 (없으면 서버가 신규 발급)
- `/conversations` CRUD 추가
- Streamlit이 `st.session_state["session_id"]`를 유지
- 20턴 = 사용자 10 + 어시스턴트 10 정도의 근사. 필요 시 `MAX_HISTORY` 상수로 쉽게 조정 가능
- 한계: 긴 세션에서 초기 문맥은 유실됨 → 추후 요약(summary) 메모리 또는 슬라이딩 윈도우 + 핵심 턴 고정 검토

---

## ADR-007: 관측 플랫폼 — LangSmith 채택
**날짜**: 2026-04-21
**상태**: accepted

### 배경
질의 품질 튜닝(청킹·임베딩·score threshold) 시 실제 retrieve 결과·LLM 입출력·지연시간을 눈으로 확인할 수단이 필요. 또한 인덱싱 소요시간을 기록해 문서 크기/유형별 병목을 파악해야 함.

### 선택지
1. **LangSmith** — LangChain 생태 네이티브, `@traceable` 한 줄로 임의 함수 래핑, 대화 세션 필터/테그 지원
2. **OpenTelemetry + Jaeger/Tempo** — 벤더 중립, 데이터 파이프라인(Docling·Qdrant) 포함 전 구간 관측 가능. 운영 복잡도 높음
3. **Langfuse** — 오픈소스 셀프호스트, LangSmith 대안

### 결정
**LangSmith**. 코드베이스가 이미 LangChain 체인을 사용하고, 현재 단계에선 관측 대상이 LLM 호출·retrieve 정도라 OTel 수준의 전 구간 추적은 과잉. 추후 필요 시 OTel 병행 고려.

### 결과
- `.env`의 `LANGCHAIN_TRACING_V2/API_KEY/PROJECT/ENDPOINT` 4개 변수로 활성/비활성 토글
- LangChain이 `os.environ`을 직접 읽으므로 `apps/main.py` lifespan에서 Pydantic 값을 환경변수로 export하는 `_configure_langsmith()` 호출
- `RAGPipeline.ingest`/`query`에 `@traceable(run_type="chain", name="rag.*")` 부착
- 질의 시 `tracing_context(tags=["session:<id>"], metadata={"session_id", "history_turns"})`로 run 태깅 → 대시보드에서 세션별 필터링 가능
- `ingest` 내부에 단계별 타이머 추가 (파싱/청킹/저장 ms) — LangSmith에는 부모 run elapsed로, 서버 로그에는 분해된 시간으로 기록
- 보안: API 키는 `.env`에만, `.gitignore`로 제외. 채팅/PR에 평문 노출 시 즉시 revoke

---

## ADR-008: 파싱 품질 개선 — 파싱 후 정규화를 로더 계층에 삽입
**날짜**: 2026-04-21
**상태**: accepted

### 배경
Docling 출력이 대체로 깨끗하지만 (1) 단어 중간에서 줄바꿈된 하이픈(`robot-\nics`), (2) 숫자만 있는 페이지 번호 줄, (3) 테이블 정렬용 연속 공백, (4) NBSP/ZWSP 등 비정상 공백이 누적. 이들이 청크 토큰 낭비·검색 recall 저하·청크 분할 오염을 유발.

### 선택지
1. **파싱 후 정규화** (로더 계층) — Docling 출력을 한 번 cleanup하고 저장·임베딩
2. **Docling 파싱 옵션 조정** — `PdfPipelineOptions`로 해결 시도. 현 아티팩트에는 효과 제한적
3. **HybridChunker로 교체** — docling-core의 구조 인식 청커. 효과 크지만 전체 재인덱싱 필요
4. **임베딩 모델 교체** (BGE-M3 등) — 컬렉션 재생성 필요

### 결정
**옵션 1 단독 적용.** 최소 침습·최고 ROI. 옵션 3/4는 별도 ADR로 분리해 단계적 평가.

### 결과
- `packages/loaders/docling_loader.py`에 `_normalize`(청크용)와 `_normalize_markdown`(저장 파일용) 유틸
  - NFC 유니코드 정규화
  - `(\w)-\s*\n\s*(\w)` → 단어 연결 복구
  - `^\s*\d{1,4}\s*$` 페이지 번호 라인 제거
  - `[\u00A0\u2000-\u200B\u202F\u205F\u3000]` 비정상 공백 → 일반 공백
  - 연속 공백 2+ → 단일, 연속 개행 3+ → 2
- **테이블 보존**: 청크에서는 `content_type=="table"`이면 skip, 저장 마크다운에서는 `|...|` 행은 건드리지 않음
- 효과 측정(기존 1619청크 PDF에 후향적 적용): 503,765→502,949자(−816), 11,816→11,610줄(−206, ≈페이지 번호 제거분)
- 기존 인덱스 무영향. 새 업로드부터 적용. 기존 문서 재색인은 `pipeline/rebuild_index.py`로 수동
- 후속 과제: HybridChunker 도입(별도 ADR), FlashRank 재순위 실제 활성화

---

## ADR-009: 청킹 — HybridChunker 명시 + 전체 heading 경로 breadcrumb 주입
**날짜**: 2026-04-21
**상태**: accepted

### 배경
Qdrant payload 분석 결과 `dl_meta.headings`가 항상 **1개 원소**(최하위 heading)만 담겨 있었고, `page`는 전부 0이었음. 실제로는 langchain-docling 내부가 기본 `HybridChunker()`를 사용하고 있었지만 기본 옵션이 상위 계층을 유지하지 않았고, 페이지 번호 추출은 잘못된 키를 보고 있었다. 결과: 청크 단독으로 "어느 장/절의 내용인지" 판단 불가 → retrieval 정확도 저하.

### 선택지
1. 기존 `DOC_CHUNKS` 기본 유지 — 아무 변화 없음
2. **HybridChunker 명시 인스턴스화**, 옵션 `always_emit_headings=True`·`omit_header_on_overflow=False` 주고 `langchain-docling`의 `chunker=` 파라미터로 주입
3. HybridChunker 대신 `HierarchicalChunker` 직접 사용 — 저수준 제어 가능하나 커스텀 코드 다량
4. langchain-docling 우회하고 `DocumentConverter` + `HybridChunker.chunk()`를 직접 호출

### 결정
**옵션 2 채택.** 옵션 3/4는 유지보수 비용만 늘고 기능적 이득이 작음.

추가로 **breadcrumb 수동 주입**: `heading_path`를 `" > "`로 연결해 청크 content 앞에 prepend. HybridChunker `contextualize()`가 이미 본문 앞에 말단 heading을 넣어두므로, 정확히 그만큼을 제거해 중복 방지 (`_strip_leading_headings`).

### 결과
- 청크 콘텐츠 형태: `"Chapter 1 > Section 1.1\n\n본문..."`
- ROS PDF 기준 **1619 → 800 청크 (−51%)** — 같은 부모 heading 아래 작은 청크가 merge_peers로 병합됨
- 각 청크가 "어느 장·어느 절"인지 단독으로 파악 가능 → 임베딩 문맥화 ↑, LLM 프롬프트도 자연스러워짐
- 페이지 번호 복구: `_extract_page_no()`가 `dl_meta.doc_items[*].prov[0].page_no`에서 추출. 단, 마크다운 입력 시 `prov` 없음 → `page=0` 유지
- 2차 청커(`RecursiveCharacterTextSplitter`) 상한은 512→2000자로 완화하고 방어 역할로만 유지
- 한계: 임베딩 모델의 512 토큰 상한을 넘는 청크가 5~10% 발생 (경고 로그). 토큰 기반 상한 설정은 후속 과제

---

## ADR-010: 원본 파일 영구 보관 — 재인덱싱 가능 구조
**날짜**: 2026-04-21
**상태**: accepted

### 배경
기존 `apps/routers/ingest.py`는 `try/finally: upload_path.unlink()`로 업로드 후 원본을 즉시 삭제. HybridChunker 옵션 튜닝·임베딩 모델 교체 등의 실험을 위한 재인덱싱 시 입력 소스가 없어 마크다운 fallback만 가능 → Docling의 구조 인식·페이지 번호 등 일부 이점 손실.

### 선택지
1. **원본 보관** (`data/uploads/{doc_id}{ext}`) — 디스크 사용 증가, 하지만 재인덱싱·감사·오류 재현에 필수
2. 마크다운만 보관 — 디스크 소형, 하지만 Docling 파싱 재현 불가
3. 보관 기간 정책(예: 90일 TTL) — 복잡도 증가

### 결정
**옵션 1 단독.** 개인 프로젝트 규모에서 디스크 우려는 작고, 재인덱싱 필요성이 실제로 반복해서 발생 중.

### 결과
- `ingest.py`: 성공 시 원본 보존, **인덱싱 실패 시에만** 정리
- 기존에 업로드되어 이미 소실된 6개 문서는 이번 재인덱싱에서 마크다운 fallback으로 진행. 이후 업로드부터는 원본 보존
- 후속 과제: 업로드 디렉터리 용량 모니터링, DELETE 시 원본 파일도 동반 삭제 여부 검토 (현재 미삭제)

---

## ADR-011: 재순위 — FlashRank 실제 활성화 + 관찰된 한계
**날짜**: 2026-04-21
**상태**: accepted (후속 과제 있음)

### 배경
`packages/rag/retriever.py`에 `build_reranking_retriever()`가 존재했으나 **실제로는 호출되지 않고** `retrieve()`가 Qdrant 점수 정렬만 수행. 즉 "reranking을 한다"고 문서화되어 있었으나 실제 동작 안 함.

### 결정
- `retrieve()`를 재작성해 Qdrant에서 `initial_k` 후보 조회 → FlashRank로 재순위 → `top_n` 반환
- `Ranker(model_name="ms-marco-MiniLM-L-12-v2")`를 프로세스 전역 싱글톤으로 관리 (모델 로드 수 초 지연)
- 반환 `ScoredChunk.score`를 FlashRank 점수(0~1, 관련도)로 교체

### 결과 & 관찰
- 모델 로드 로그 확인, 점수 분포가 Qdrant 코사인(0.3~0.5)과 전혀 다른 범위(0.05~0.99)로 바뀜 → 재순위 동작 확인
- **한계**: MS MARCO가 영어 코퍼스이므로 **한국어 질의 + 영문 문서** 크로스에서 오동작. 예: "ROS의 주요 구성요소는?" → 한국어 딥러닝 문서의 "CONTENTS" 섹션이 0.988점을 받고 실제 관련 ROS 청크는 0.059점
- 후속 과제 (→ ADR-012에서 해결):
  - 다국어 rerank 모델 평가 (`ms-marco-MultiBERT-L-12`, `bge-reranker-v2-m3` 등)
  - 질의 언어 감지 후 영어 문서용/한국어 문서용 분리 처리
  - 또는 재순위 전 질의 번역 (query translation) 도입

---

## ADR-012: 재순위 다국어화 — BGE-reranker-v2-m3 채택 + 백엔드 토글
**날짜**: 2026-04-22
**상태**: accepted (supersedes ADR-011 한계)
**관련**: ADR-011, TASK-001, [evaluation.md](../features/evaluation.md)

### 배경
ADR-011에서 관찰된 FlashRank 한↔영 크로스 실패를 해결하기 위해 다국어 cross-encoder를 평가·도입. 추가로 실험 재현·회귀 가능성을 위해 백엔드를 런타임 토글로 구성.

### 선택지
1. **BGE-reranker-v2-m3** (`BAAI/bge-reranker-v2-m3`, 100+ 언어 학습, 568MB)
2. `ms-marco-MultiBERT-L-12` — FlashRank 경로 유지. 성능 보고 편차 큼
3. 질의 번역 + 기존 FlashRank 유지 — 번역 비용·지연
4. 언어 감지 → 문서군별 분기 — 복잡도 증가

### 결정
**옵션 1 채택 + 백엔드 토글**. 단일 모델이 한/영 모두 커버해 구현이 단순. 토글로 A/B 회귀 가능.

### 구현
- `packages/rag/reranker.py` 신설: `Reranker` 프로토콜 + `FlashRankReranker` + `BgeM3Reranker`. `get_reranker(backend, model_name)` 팩토리가 싱글톤 관리.
- BGE는 `sentence_transformers.CrossEncoder`로 로드하고 logit→sigmoid로 0~1 스케일링.
- `packages/rag/retriever.py`를 reranker 주입형으로 재작성. `apps/dependencies.py`에서 설정값 기반 인스턴스화.
- `.env`: `RERANKER_BACKEND`, `RERANKER_MODEL_NAME`, `RERANKER_WARMUP`. 기본 `bge-m3`, warmup on.
- `apps/main.py` lifespan에서 `reranker_warmup=true`일 때 더미 rerank 호출로 모델 preload (첫 사용자 지연 제거).
- `RAGPipeline.query`에 `tracing_context(tags=["reranker:<backend>"], metadata={"reranker_backend": ...})` 태깅으로 LangSmith에서 backend별 필터링 가능.

### 결과
| 질의(한국어) | FlashRank 1위 | BGE-M3 1위 |
|------|---------|---------|
| ROS의 주요 구성요소는? | 밑바닥부터_시작하는_딥러닝 ❌ | **Learning ROS** ✅ |
| navigation stack은 무엇인가? | Learning ROS | Learning ROS (score↑) |
| 자율 주행 | 딥러닝(정답) | 딥러닝(정답) |
| 오차역전파법 | 딥러닝(정답) | 딥러닝(정답) |
| Robotics Programming을 하는 방법은? | Learning ROS | Learning ROS |

- **완료 기준 충족**: ROS 영문 청크가 한국어 질의 top-3 전원 진입, 무관한 한국어 딥러닝 목차가 1위로 올라가는 사례 제거
- 점수 분포: BGE-M3가 0.5~0.7로 더 의미 있는 스펙트럼, FlashRank는 0.99+로 overconfident
- 비용: 로드 ~4초(캐시 후), 추론 50~150ms/청크 on CPU
- `features/evaluation.md`에 A/B 표 기록

### 한계 / 후속
- BGE도 CPU 추론이라 `initial_k=20`에서 총 1~3초 추가. GPU 또는 `initial_k=10`으로 완화 가능
- 매우 긴 청크(>512 토큰)는 내부에서 잘림 — 구조 인식 청킹과 결합해 영향 최소화
- 한국어 임베딩 품질 자체가 병목이 될 경우 TASK-002(BGE-M3 임베딩 교체)로 확장

---

## ADR-013: LLM 공급자 — gpt-4o-mini 유지 (GLM 교체 안 함)
**날짜**: 2026-04-22
**상태**: accepted

### 배경
GLM(Zhipu) 계열 모델이 OpenAI-호환 엔드포인트로 쉽게 대체 가능한 상황에서, 성능·비용 관점에서 교체 여부 검토가 요청됨.

### 비교 요약
| 축 | gpt-4o-mini | GLM-4.6 / GLM-4-Flash |
|----|---|---|
| 한국어 답변 품질 | 안정 최상위 | GLM-4.6 근접, Flash는 한 단계 낮고 출력에 중국어 혼입 사례 |
| 컨텍스트 준수(hallucination 억제) | 강함 | GLM은 컨텍스트 외 추측 경향이 상대적으로 높다는 보고 |
| 지시/시스템 프롬프트 준수 | 안정 | 일부 질의에서 출력이 짧아지는 사례 |
| 가격 | $0.15 / $0.60 per 1M 토큰 | Flash 사실상 무료, 4.6 저가 |
| 안전 필터 | 표준 | 중국 규제로 특정 주제 필터 강함 — RAG 문서가 걸릴 가능성 |
| 지연시간/SLA (국내) | 일관 | 리전·피크 편차 |

### 결정
**gpt-4o-mini 유지.** 이 프로젝트의 주 과업은 "검색된 청크 3개를 한국어로 성실히 재구성"으로 단순하고, 이 과업에서 두 모델 체감 차이는 크지 않지만 **컨텍스트 준수·안전 필터·생태계 안정성**에서 OpenAI가 더 예측 가능. 비용도 현재 규모에서 월 수 달러 수준이라 교체 유인이 약함.

### 결과
- 코드 변경 없음
- 추후 비용 폭증 시나리오, 또는 데이터 주권 요구가 생기면 재평가 (재평가 시 이미 설계된 "백엔드 토글" 패턴을 LLM에도 적용해 A/B로 결정)
- 모델 교체는 [packages/llm/chat.py](../../../packages/llm/chat.py) 한 파일 + `.env` 키 교체로 가능하다는 점을 유지보수 메모로 기록

---

## ADR-014: LLM 백엔드 토글 인프라 (ADR-013 후속)
**날짜**: 2026-04-22
**상태**: accepted
**관련**: ADR-013 (gpt-4o-mini 유지 결정), TASK-003

### 배경
ADR-013에서 gpt-4o-mini 유지로 결론 났지만, 향후 비용·데이터 주권·A/B 실험 요구가 생겼을 때 코드 수정 없이 `.env`만으로 공급자를 바꿀 수 있는 토글 인프라가 필요. Reranker에서 이미 검증된 패턴(ADR-012)을 LLM에도 이식.

### 선택지
1. **OpenAI-호환 토글만** (`ChatOpenAI` 한 클래스로 base_url/api_key/model만 교체)
2. 공급자별 네이티브 SDK 지원 (langchain-zhipuai 등) — 패키지 호환성 부담
3. 추상화 인터페이스 + 2종 구현 (reranker와 동일)

### 결정
**옵션 1.** GLM/DeepSeek/Qwen 등 주요 중국계/오픈 공급자가 전부 OpenAI-호환 엔드포인트를 제공하므로 `ChatOpenAI` 단일 클래스로 충분. 타입 힌트·LangChain·LangSmith 호환성 완벽 유지.

### 구현
- `.env`: `LLM_BACKEND`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE` 5개 변수 (모두 빈 값 허용)
- `apps/config.py`: 5개 필드 + 기존 `openai_chat_model`·`openai_chat_temperature`를 legacy fallback으로 유지
- `packages/llm/chat.py` 재작성:
  - `_BACKENDS` 맵: `openai`(`api.openai.com/v1`, `gpt-4o-mini`), `glm`(`open.bigmodel.cn/api/paas/v4/`, `glm-4-flash`), `custom`(완전 수동)
  - `_resolve(settings)`: `LLM_*` → (openai 한정) `OPENAI_*` → backend 기본값 우선순위로 해석
  - `LLM_TEMPERATURE`는 `str`로 받아 빈 문자열이면 legacy 파라미터로 fallback (Pydantic 빈 문자열 → float 파싱 실패 방지)
  - `ChatOpenAI(model, temperature, openai_api_key, openai_api_base)` 반환 (타입·동작 불변)
- `packages/rag/pipeline.py`: `RAGPipeline.query`의 `tracing_context`에 `llm:<backend>` 태그 + `llm_backend`·`llm_model` 메타 추가 (LangSmith에서 backend별 필터링)
- 기본값: `LLM_BACKEND=openai`, 실효 모델 `gpt-4o-mini` — ADR-013 결론 준수 (회귀 0)

### 결과
- 스모크 테스트: 기본 `LLM_BACKEND=openai`로 `/query` 정상(답변·출처·지연 이전과 동일)
- 로그: `질의: ... (reranker=bge-m3, llm=openai:gpt-4o-mini)` 형태로 backend·모델 가시성 확보
- LangSmith: `llm:openai` 태그 + 메타 기록 확인
- 모델 교체는 이제 다음 한 줄이면 완료:
  ```
  LLM_BACKEND=glm
  LLM_API_KEY=<glm key>
  # LLM_MODEL 비우면 glm-4-flash 사용, 다른 모델 원하면 LLM_MODEL=glm-4.6 등
  ```

### 한계 / 후속
- `custom` backend는 반드시 `LLM_BASE_URL`·`LLM_API_KEY`·`LLM_MODEL` 전부 필요 (에러 메시지로 안내)
- OpenAI 완벽 호환이 아닌 공급자는 `n`, `logprobs`, `tool_choice` 등 일부 파라미터 미지원 가능 — 현재 코드는 이들 파라미터를 쓰지 않으므로 영향 없음
- GLM에서 `temperature=0.0` 시 출력이 짧아지는 경향이 있다는 보고 — 실제 전환 시 0.3~0.5 시도 권장 (`.env`의 `LLM_TEMPERATURE=0.3`)
- A/B 정량 비교는 TASK-004에서 제공할 Ragas/LangSmith 평가 프레임워크로 수행

---

## ADR-015: 평가 프레임워크 — Ragas + 자체 Retrieval 벤치 + LangSmith
**날짜**: 2026-04-22
**상태**: accepted
**관련**: TASK-004, [evaluation.md](../features/evaluation.md)

### 배경
지금까지의 개선(HybridChunker, FlashRank→BGE-m3, heading breadcrumb, LLM 토글)이 **정성 판단**으로만 진행. 이후 실험(임베딩 교체, 하이브리드 검색, 프롬프트 튜닝)도 수치 없이는 결정이 어렵고, 회귀 탐지도 불가.

### 선택지
1. **수동 라벨 + 자체 스크립트만** — Precision@K / Recall@K / MRR. 빠름, 답변 품질 제한
2. **Ragas 통합** — RAG 전용 표준 지표 (faithfulness, answer_relevancy, context_precision/recall)
3. **LangSmith Evaluators 단독** — 기존 트레이스 위에서 dataset·evaluator 정의. built-in이 제한적
4. **옵션 1 + 2 + 3 결합**

### 결정
**옵션 4 결합.**
- Phase 1(Retrieval, 빠름): 자체 스크립트로 Hit/Precision/Recall/MRR. reranker A/B에 최적
- Phase 2(Answer, 느림): Ragas로 답변 품질 4종 지표. LLM-as-judge
- LangSmith: 두 스크립트의 실행 이력을 자동 수집 (기존 `@traceable`에 의해)

### 구현
- `tests/eval/dataset.jsonl` — 12개 질의 (ko/en/mixed) + `expected_doc_ids` 라벨
- `scripts/bench_retrieval.py`:
  - argparse `--backend flashrank bge-m3` 로 A/B 가능
  - unique-document 기반 Precision/Recall (청크 중복 카운트 버그 수정)
  - `data/eval_runs/retrieval_<ts>.json` 저장
- `scripts/bench_answers.py`:
  - `retrieve()`를 직접 호출해 **전체 청크 content를 Ragas에 전달** (기존 pipeline.query의 200자 excerpt 사용 시 faithfulness가 0.15로 급락하는 버그 발견 후 수정)
  - metrics: `Faithfulness`, `ResponseRelevancy`, `LLMContextPrecisionWithoutReference`, `LLMContextRecall`
  - judge: gpt-4o-mini (비용 고려). 중요 의사결정 시 gpt-4o로 교체 권장
  - LangSmith에 run 자동 기록
- `requirements.txt`에 `ragas>=0.2`, `datasets>=4.0` 추가

### 결과 (기반선, 2026-04-22)
**Phase 1 A/B** (12 질의):

| 지표 | FlashRank | BGE-M3 |
|------|-----------|--------|
| Hit@3 | 0.917 | **1.000** |
| Precision@3 | 0.847 | **1.000** |
| Recall@3 | 0.861 | **0.944** |
| MRR | 0.833 | **1.000** |

**Phase 2** (BGE-M3 + gpt-4o-mini):

| 지표 | 값 |
|------|-----|
| faithfulness | 0.886 |
| answer_relevancy | 0.648 |
| context_precision | 0.986 |
| context_recall | 0.942 (self-reference) |

### 후속 원칙 (강제)
1. 모든 품질 관련 ADR은 **before/after 수치 동반**
2. reranker/LLM backend 교체 시 Phase 1+2 모두 재실행 후 결정
3. 튜닝·평가 질의 분리 (현재는 공용, 향후 hold-out 5개 분리)

### 한계 / 후속
- judge LLM이 답변 LLM과 동일 — 편향 가능. 중요 판정은 judge를 gpt-4o로 고정
- `answer_relevancy` 0.648이 낮게 보이는데 답변이 길어 주변 정보가 많아서 — 프롬프트 간결화가 다음 실험 후보
- reference(정답 문자열) 미라벨 — Phase 2 context_recall 해석 주의
- Ragas judge 비용: 한 번 전체 실행 ≈ $0.05~0.1

---

## ADR-016: Embedding 백엔드 — OpenAI 유지, BGE-M3 토글 확보
**날짜**: 2026-04-22
**상태**: accepted (supersedes TASK-002의 "교체" 가정)
**관련**: TASK-002, ADR-012, ADR-015

### 배경
reranker를 다국어(BGE-M3)로 바꾼 뒤에도 임베딩은 `text-embedding-3-small`(영어 위주 학습)로 남아있어 retrieval 1단계(후보 수집)에서 한↔영 크로스 약점이 여전할 가능성이 있었다. 다국어 임베딩(BGE-M3, 1024-d, 로컬)으로 교체 시 이득이 있는지 **정량 A/B**로 검증.

### 선택지
1. **OpenAI 유지** — 변동 없음, 기반선 유지
2. **BGE-M3 단독 채택** — 비용 0, 다국어 특화, Qdrant 컬렉션 재생성 필요
3. **토글 추가 + 기본 OpenAI** — 확장성만 확보, 기본은 보수적

### 실험 (TASK-004 프레임워크로 A/B)
**조건**: 동일 dataset 12개 질의, reranker=bge-m3 고정, LLM=gpt-4o-mini 고정. 임베딩만 교체.

| 지표 | OpenAI (text-embedding-3-small, 1536-d) | BGE-M3 (1024-d, 로컬) | Δ |
|------|---|---|---|
| Hit@3 | 1.000 | 1.000 | = |
| Precision@3 | 1.000 | 1.000 | = |
| Recall@3 | 0.944 | 0.944 | = |
| MRR | 1.000 | 1.000 | = |
| Retrieval latency | 580ms | **423ms** | −27% |
| faithfulness | 0.886 | 0.857 | −3% |
| answer_relevancy | 0.648 | 0.618 | −5% |
| context_precision | 0.986 | 0.924 | −6% |
| context_recall | 0.942 | 0.917 | −3% |

### 결정
**옵션 3 채택: OpenAI 기본 유지 + BGE-M3 토글 제공.**
- Retrieval 4종 지표는 이미 상한(1.0 근처) — 교체 이득 없음
- Answer 지표는 **소폭 하락**. 임베딩이 바뀌면 후보 분포도 달라지고 LLM이 본 context도 미묘히 바뀌는데 그 결과가 자 ROS/딥러닝 dataset에서는 OpenAI 쪽이 약간 더 유리
- Retrieval latency 27% 개선은 장점이나 전체 `/query` latency(5초) 대비 미미
- ADR-013(LLM OpenAI 유지)의 보수적 원칙 일관성

### 구현
- `apps/config.py`: `embedding_backend`, `embedding_model_name`, `embedding_warmup` 3개 필드
- `.env(.example)`: `EMBEDDING_BACKEND=openai|bge-m3`, `EMBEDDING_MODEL_NAME`, `EMBEDDING_WARMUP`
- `packages/llm/embeddings.py` 재작성: `_EmbeddingWithDim` 래퍼가 `embedding_dim`·`backend`·`model` 속성 노출
- `packages/vectorstore/qdrant_store.py`:
  - `VECTOR_SIZE` 상수 제거 → 임베딩의 `embedding_dim` 속성 기반
  - 기존 컬렉션의 차원이 현재 임베딩과 다르면 `CollectionDimensionMismatch` 예외 (재인덱싱 유도)
- `pipeline/rebuild_index.py`: reranker 주입으로 `RAGPipeline` 생성자 갱신 — 차원 변경 재인덱싱도 지원
- `requirements.txt`: `langchain-huggingface` 추가 (HuggingFaceEmbeddings 계열)

### 결과
- 기본값 `EMBEDDING_BACKEND=openai` 유지 → **회귀 0**
- `EMBEDDING_BACKEND=bge-m3 && python pipeline/rebuild_index.py`로 즉시 전환 가능
- 본 실험에서 전환과 복원 사이클 2회 무장애 수행(Qdrant 컬렉션 차원 자동 감지·검증 동작 확인)

### 한계 / 후속
- 한국어·영어 혼합 dataset이 12개 소규모라 모델 간 작은 차이를 감지하기에 통계적 힘이 약함. 더 큰 실사용자 질의가 누적되면 재평가
- GPU 없는 CPU 환경에서는 BGE-M3 인덱싱이 OpenAI 대비 느림(약 5배). 본 프로젝트 규모에선 수용 가능하나 대량 업로드 시 고려
- 한국어 문서가 주를 이루는 dataset이 새로 들어오면 BGE-M3가 역전할 가능성 있음 — TASK-004 프레임워크로 언제든 재검증 가능

---

## ADR-017: 관리자 UI 단계적 도입 (1단계 = Streamlit 탭)
**날짜**: 2026-04-22
**상태**: accepted
**관련**: TASK-005, [admin_ui.md](../features/admin_ui.md), ISSUE-001

### 배경
문서·대화·설정·벤치 결과가 분산되어 운영 가시성이 낮고, 대화 세션은 UI 없이 CRUD API만 있어 누적만 됨. 설정 백엔드가 현재 어떤 값인지 UI에서 확인 불가 — 실험 중 안전장치가 없음.

### 선택지
1. **1단계: 현 Streamlit 앱 내 `st.tabs` 추가** — 최소 침습, LAN 전용
2. 2단계: `ui/pages/admin.py` 분리 + `ADMIN_PASSWORD`
3. 3단계: FastAPI+Jinja 또는 React 전용 대시보드

### 결정
**1단계부터 순차 도입.** 2단계는 HTTPS 배포·ISSUE-001 해결과 묶어 승격. 3단계는 규모 확장 시.

### 구현 (1단계, TASK-005)
- `ui/app.py`를 `st.tabs(["채팅","문서","대화","시스템","평가"])` 구조로 재작성
- **채팅**: 기존 기능 유지, `session_id` 뱃지 표시
- **문서**: 업로드/목록/삭제 + **청크 미리보기** (`GET /documents/{id}/chunks?limit=10`)
- **대화**: `GET /conversations` 목록, 선택 시 `GET /conversations/{id}` 메시지 뷰, 삭제
- **시스템**: Reranker/LLM/Embedding/Qdrant/Health/LangSmith 6개 카드 — **읽기 전용**
- **평가**: `data/eval_runs/*.json` 최신 Retrieval + Answer 지표 카드, 최근 10개 히스토리 테이블
- 백엔드 신규: `QdrantDocumentStore.scroll_by_doc_id()` + `GET /documents/{doc_id}/chunks` 엔드포인트 + `ChunkPreview`·`ChunkPreviewResponse` 스키마

### 의도적으로 제외
- 설정 변경 UI (서버 재시작 필요, 경쟁 상태) → `.env` 편집 + 재시작 안내
- 재인덱싱/벤치 실행 버튼 (블로킹, 비용) → CLI로 수행
- 인증 (1단계는 LAN 전용)
- 자세한 내용은 [admin_ui.md](../features/admin_ui.md)

### 결과
- 탭 전환으로 채팅 `session_id`·`messages` 유실 없음 (세션 상태 명시적 키 사용)
- 문서·대화 CRUD + 청크 미리보기 스모크 통과
- 시스템 탭이 `get_settings()` + `QdrantClient.get_collection()`을 실시간 반영
- 평가 탭이 `data/eval_runs/`의 최신 결과를 자동 로드

### 후속 (2/3단계 예정 ADR은 실제 승격 시 신규 작성)
- 2단계: ISSUE-001 동반 해결, HTTPS 배포, `ADMIN_PASSWORD`
- 3단계: 청크 검색 디버거, 벤치 시계열 차트, 설정 토글 UI

---

## ADR-019: 후속 질문 제안 — 단일 LLM 호출에 JSON 구조화로 통합
**날짜**: 2026-04-22
**상태**: accepted
**관련**: TASK-007 Phase 1

### 배경
사용자가 답변을 받은 뒤 "다음에 뭘 물어야 하지?"를 스스로 찾아야 함. 현재 UX는 각 질의가 독립적이라 탐색 연쇄가 끊긴다. 후속 질문 제안을 붙이면 클릭 한 번으로 대화가 자연스럽게 깊어진다.

### 선택지
1. **단일 LLM 호출에 JSON 통합** — `{"answer": ..., "suggestions": [...]}`. 추가 호출 0회, 토큰만 소폭 증가
2. 답변 생성 후 **별도 LLM 호출로 suggestions만 생성** — 구현 단순, 비용 2배, 지연↑
3. **임베딩/규칙 기반 생성** — heading_path·TF-IDF 같은 규칙. 비용 0이나 품질 낮고 자연어 문장 생성 어려움

### 결정
**옵션 1.** 이유:
- 추가 호출 0 → 비용·지연 영향 미미 (응답 토큰만 +50~100)
- JSON 모드로 파싱 안정성 확보 (`response_format={"type":"json_object"}`)
- 답변과 suggestions이 같은 컨텍스트를 공유 → 자연스러운 후속 질문

### 구현
- `packages/rag/generator.py`: 두 종류 system prompt(plain / with_suggestions) + `json.loads` 파싱 + 파싱 실패 시 graceful degrade(answer는 원문, suggestions=[])
- `apps/config.py`: `suggestions_enabled: bool = True`, `suggestions_count: int = 3`
- `.env(.example)`: `SUGGESTIONS_ENABLED`, `SUGGESTIONS_COUNT`
- `apps/schemas/query.py`: `QueryResponse.suggestions: list[str] = []`
- `packages/rag/pipeline.py`: `generate()` 반환을 dict로 바꾸고 `suggestions` 전파. `tracing_context` 태그에 `suggestions:<bool>`, 메타에 `suggestions_enabled/count` 추가
- `apps/routers/query.py`: `QueryResponse` 생성 시 `suggestions=result.get("suggestions",[])`
- `ui/app.py`: `_render_suggestions()` 헬퍼로 배지 렌더. 클릭 시 `st.session_state["_pending_question"]`에 세팅 → rerun → 자동 질의. 과거 메시지의 suggestions도 재클릭 가능하도록 `messages[i]["suggestions"]`에 보존

### 결과
- 스모크: "ROS의 주요 구성요소는?" 질의 시 한국어 suggestions 3개 정상 생성
  - "ROS의 파일 시스템 레벨에 대해 더 알고 싶습니다."
  - "계산 그래프 레벨에서 어떤 개념들이 포함되나요?"
  - "ROS 커뮤니티 레벨의 자원에는 어떤 것들이 있나요?"
- `SUGGESTIONS_ENABLED=false` 회귀 테스트: `suggestions=0`, answer는 기존과 동일 → **회귀 0** 확인
- 답변이 "관련 문서를 찾지 못했습니다."류 불충분 응답이면 suggestions를 빈 리스트로 강제 (무관한 질문 생성 방지)

### 한계 / 후속
- **LLM이 3개보다 적거나 많이 반환**할 수 있음 — 서버에서 `suggestions[:N]` 잘라 보정
- **JSON 모드 미지원 모델**(일부 GLM 변형): `response_format` TypeError catch 후 평문 요청, 파싱 실패 시 graceful degrade
- **Phase 2 (빈 채팅 인덱스 요약 카드)** 는 TASK-008로 분리
- **Phase 3 (형제 heading 기반 탐색 사이드 패널)** 은 더 후속
- 사용자 클릭률·품질 평가는 TASK-004 프레임워크 확장에서 검토 (현재는 수동 관찰)

### 회고·수정 이력 (미해결 — ISSUE-002)
- **2026-04-22 fix v1 (0.14.1, 오진)**: `st.rerun()` 중복 호출로 추정. 수동 호출 제거. 증상 지속.
- **2026-04-22 fix v2 (0.14.2, 오진)**: `st.chat_message` 내부 버튼으로 추정. 렌더를 블록 바깥으로 이동. 증상 지속.
- **2026-04-22 fix v3 (0.14.3, 오진)**: 버튼 `key` 불일치로 추정. 라이브·히스토리 key를 `msg_{msg_idx}`로 통일. 모바일에서 증상 여전히 재현됨이 확인됨
- **결론**: 3회 수정이 전부 근본 원인이 아니었음. 증상이 **모바일 특정**일 가능성 높음(ISSUE-001과 같은 계열). `ISSUE-002`로 분리 등록하고 "인증·공개배포 묶음"과 함께 HTTPS 배포 후 재검증하기로 결정
- **보존 이유**: v1~v3 수정은 모두 Streamlit 모범 사례에 부합 — `st.rerun()` 중복 금지, 컨테이너 위젯 바깥에서 `st.button` 렌더, 같은 논리적 위젯의 key 통일. 원인이 아니었더라도 되돌리지 않음
- **상세**: [ISSUE-002](../issues/open/ISSUE-002-suggestion-badge-click-unresponsive.md)

---

## ADR-020: 인덱스 커버리지 카드 — `GET /index/overview` + 인메모리 캐시
**날짜**: 2026-04-22
**상태**: accepted
**관련**: TASK-008 (TASK-007 Phase 2에서 승격)

### 배경
ADR-019로 답변 후 후속 질문은 해결됐지만, **빈 채팅 empty state**에서 사용자는 "뭘 물어야 할지" 여전히 모름. 현재 인덱싱된 문서를 자연어로 요약하고 예시 질문 5개를 첫 화면에 보여주면 온보딩 효과가 큼.

### 선택지
1. **전용 엔드포인트 `/index/overview` + 인메모리 캐시** — 서버에서 LLM 호출 1회, 클라이언트는 fetch만
2. **클라이언트(Streamlit)에서 매 진입 시 LLM 직접 호출** — 캐시 관리 어려움, 비용 폭증
3. **정적 요약만** — heading 집계만으로 정적 문자열. LLM 품질 없음, 다국어·자연어 요약 불가
4. **업로드 시 사전 생성** — 배치 작업으로 업로드 성공 후 요약 생성. 구현 복잡도 증가

### 결정
**옵션 1.** 서버 측 캐시가 가장 단순하고 LLM 비용을 1회/문서 변경 사이클로 억제 가능.

### 구현
- `apps/schemas/documents.py`: `IndexOverviewResponse(doc_count, titles, top_headings, summary, suggested_questions)`
- `apps/routers/documents.py`:
  - `GET /index/overview` 신규 — 처리 순서:
    1. `list_documents` 결과와 doc_id 리스트로 cache_key 계산
    2. 캐시 히트면 즉시 반환
    3. 각 문서 상위 50 청크 샘플링 → heading_path[0]의 빈도로 top_headings 추출
    4. 문서 제목·top_headings를 LLM(JSON 모드)에 전달 → summary + suggested_questions 5개 생성
    5. 결과 캐시
  - `invalidate_index_overview_cache()`: 업로드(`ingest.py`)·삭제(`documents.py` DELETE)에서 호출
- `apps/config.py`·`.env`: `INDEX_OVERVIEW_ENABLED=true|false` 토글
- `ui/app.py` 채팅 탭:
  - `len(messages) == 0`일 때 `st.container(border=True)`로 카드 렌더
  - 구성: "이 시스템이 아는 내용" 제목 + summary + 인덱싱된 문서 expander + 예시 질문 5개 배지
  - 배지 클릭 → `_pending_question` 세팅 → 자동 재질의 (TASK-007의 플로우 재사용)
  - 업로드·삭제 시 `st.session_state["_index_overview"] = None`로 클라이언트 캐시도 무효화

### 결과
- 1차 호출: 한국어 요약 2~3문장 + 예시 질문 5개 정상 생성 (latency 약 2~3초 LLM 포함)
- 2차 호출: **5ms** (캐시 히트, LLM 호출 0)
- 업로드/삭제 → 자동 무효화 → 다음 호출에서 재생성
- 사용자 체감: 빈 채팅에 **"어떤 질문을 할 수 있는가"** 를 즉시 파악

### 한계 / 후속
- top_headings 품질이 heading_path[0]에 의존 — 일부 문서(딥러닝 한국어)는 "또는 return np .sum(x**2)" 같은 노이즈 heading이 상위로 올라오는 경우가 관찰됨. 향후 heading 정제(짧거나 숫자 포함 등 필터) 고려
- LLM JSON 모드 미지원 공급자에서는 요약·질문이 없거나 fallback 문구로 대체
- Phase 3(형제 heading 기반 사이드 패널)은 별도 태스크로 분리
- 토픽 클라우드·엔티티 네트워크 같은 시각화는 의도적 제외 (Graph RAG 재검토 시점에 묶어서)

---

## ADR-021: 디스크 고아 정리 + HybridChunker 토큰 상한 명시
**날짜**: 2026-04-22
**상태**: accepted
**관련**: TASK-009, ADR-009(HybridChunker), ADR-010(원본 파일 보존)

### 배경
두 개의 누적된 기술 부채를 한 태스크로 해소:
1. **고아 파일**: ADR-010으로 원본 파일을 `data/uploads/`에 영구 보관하도록 바꾼 뒤, DELETE 엔드포인트가 Qdrant·PostgreSQL만 정리하고 디스크는 건드리지 않아 삭제 후에도 `data/uploads/{doc_id}.*`·`data/markdown/{doc_id}.md`가 남아 디스크 누수 발생
2. **토큰 초과 경고**: HybridChunker 기본 설정은 tokenizer `max_tokens`를 명시하지 않아 "Token indices sequence length > 512" 경고가 청크 5~10%에서 발생. 임베딩 모델 512 토큰 한계에서 일부 내용이 잘려 검색 정확도 손실

### 선택지 (부채 1: 파일 정리)
1. DELETE 엔드포인트에서 `unlink(missing_ok=True)`로 직접 정리
2. 별도 정기 청소 작업(cron job)
3. 파일을 DB(BLOB)로 이관

### 선택지 (부채 2: 토큰 상한)
1. **`HybridChunker(tokenizer=HuggingFaceTokenizer(max_tokens=480))`** — 명시적 토크나이저
2. 청킹 후 토큰 수 체크해 초과 청크만 재분할
3. max_tokens를 기본 512로 두고 경고만 무시

### 결정
- 부채 1 → **옵션 1**: DELETE 경로에서 즉시 정리. 복잡도 0, 사용자 의도와 가장 일치
- 부채 2 → **옵션 1**: 토크나이저 명시로 HybridChunker가 청킹 시점에 상한 강제. 안전 마진 32토큰(heading breadcrumb 여유)을 두어 **480으로 설정**

### 구현
- `apps/routers/documents.py` DELETE:
  - `Path(settings.upload_dir).glob(f"{doc_id}.*")` 순회 → `unlink()` (missing_ok semantics)
  - `Path(settings.markdown_dir) / f"{doc_id}.md"` 존재 시 삭제
  - 삭제된 파일 수를 로그
- `packages/loaders/docling_loader.py`:
  - `HuggingFaceTokenizer(tokenizer=AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2"), max_tokens=480)`
  - import 실패·버전 불일치 시 기본 HybridChunker로 fallback (`try/except` + 경고 로그)

### 결과
- **스모크**: 업로드→두 파일 생성 확인→DELETE 200→두 파일 모두 삭제 확인
- **토큰 경고**: API 기동 후 `grep -c "Token indices sequence length"` = **0** (이전 재인덱싱에서는 수십 건)
- 기존 문서는 재인덱싱하지 않으면 Qdrant 청크는 그대로 유지 — 토큰 상한 효과는 새 업로드부터 적용

### 한계 / 후속
- 480토큰 기준으로 청크 수는 소폭 증가할 수 있음 (같은 heading 하의 병합이 더 빈번하게 경계 넘음). TASK-004 벤치 재실행 시 확인
- fallback 경로에서는 토큰 경고가 돌아올 수 있으나 `sentence-transformers`가 이미 설치되어 있어 정상 경로 사용됨
- 백필: 기존 6개 문서의 남은 마크다운·업로드 파일은 없음(재인덱싱 과정에서 이미 정리됨). 필요 시 수동 `find data/ -name "<doc_id>*" -delete`

---

## ADR-022: 대량 색인 — CLI 스크립트 우선, API는 인증·공개배포와 함께 미래 도입
**날짜**: 2026-04-23
**상태**: accepted
**관련**: TASK-010, ADR-005(중복 감지), ADR-010(원본 보관), ADR-017(관리자 UI 1단계)

### 배경
단일 업로드만 가능한 현재 구조로는 수십~수백 개 문서가 있는 폴더를 등록하기 어렵다. 3가지 선택지가 있었고 **현 시스템의 인증 상태**가 결정을 좌우.

### 선택지
1. **CLI 스크립트만 (`scripts/bulk_ingest.py`)** — 로컬 전용, 인증 불필요, 기존 `/ingest` HTTP 재활용
2. 새 API 엔드포인트 `POST /bulk_ingest` + 관리자 UI 버튼 — 원격에서도 트리거 가능, 그러나 **인증 없이 노출 위험**
3. 현재 UI의 다중 파일 `st.file_uploader(accept_multiple_files=True)` 추가 — 중간 선택지, 대량 업로드 시 브라우저 메모리·네트워크 부담

### 결정
**옵션 1 단독.** 이유:
- 인증·공개배포 묶음이 **사용자 지시까지 전부 보류** 상태 (2026-04-22). 무인증 상태에서 대량 업로드 API·UI 버튼 노출은 보안 경계 위반
- 기존 `POST /ingest`에 L1 중복 감지(ADR-005)·원본 보관(ADR-010)·자동 OCR(ADR-004)·토큰 상한(ADR-021)이 이미 갖춰져 있어 CLI는 얇은 래퍼로 충분
- 한 번의 스크립트 수정으로 재실행·중복 스킵·리포트를 전부 만족

### 구현
- `scripts/bulk_ingest.py`
  - `Path.rglob`로 재귀 탐색 (기본 `--recursive=True`)
  - 확장자 필터(`--include`), 정규식 exclude(`--exclude`), 제목 자동 생성(`--title-from stem|filename|relpath`), source 접두(`--source-prefix`), `--dry-run`, `--fail-fast`, `--workers`, `--api-base`, `--report`
  - API `POST /ingest` HTTP로 호출 — 각 파일의 content_hash 계산·중복 감지 서버 로직 일관성 유지
  - 응답: 200 → ok, 409 → duplicate(스킵, 실패 아님), 기타 → failed
  - `MAX_UPLOAD_SIZE_MB` 초과 파일은 `skipped_too_large`로 분류
  - 진행은 tqdm(있으면), 결과 JSON을 `data/eval_runs/bulk_ingest_<ts>.json`에 저장
- 통합 테스트: `tests/integration/test_bulk_ingest.py` — dry-run 기반 6개 케이스 (재귀·no-recursive·exclude·include·없는 폴더·빈 폴더)

### 결과
- 스모크: 3개 파일 재귀 업로드 → 6.8초 / 재실행 0.0초(전부 409 스킵)
- 통합 테스트 6개 통과
- 재실행 안전성 확보 (progress resume을 L1 중복 감지가 대체)

### 의도적 제외 (현 단계)
- **관리자 UI 버튼**: 인증 없는 상태에서 노출 금지 — 인증·공개배포 묶음과 함께 재논의
- **`POST /bulk_ingest` API**: 동일 이유
- **S3/원격 스토리지**: 로컬 파일시스템만
- **대화형 진행 표시(websocket)**: tqdm·LangSmith 트레이스로 충분

### 한계 / 후속
- CLI는 **로컬 또는 같은 LAN 내부**에서만 실행 (`--api-base` 지정 시 네트워크 경유하나 현 시스템은 무인증)
- 동시 실행 시 같은 파일이 두 프로세스에 걸리면 content_hash UNIQUE 충돌 가능 — 스크립트 단일 실행 원칙
- 스캔 PDF 섞이면 OCR 자동 실행으로 파일당 수 분 소요 가능 (ADR-004)
- 인증·공개배포 묶음 재개 시점에 관리자 UI 2단계에 "폴더 경로 입력 → 백그라운드 실행 + 진행 표시" 패턴으로 승격 후보

---

## ADR-023: 하이브리드 검색 — Qdrant 네이티브 sparse(BM25) + dense + RRF 병합
**날짜**: 2026-04-23
**상태**: accepted
**관련**: TASK-011, ADR-012(reranker), ADR-016(embedding)

### 배경
벡터 유사도만으로는 **정확 키워드 매칭**(고유명사·숫자·버전·약어)이 약함. 한국어 고유명사나 "ROS 2.0.3" 같은 질의가 임베딩 공간에서 희석돼 놓치는 케이스가 실제로 관측 가능. BM25 같은 전통 키워드 검색이 이런 질의에는 강함. 두 경로를 병렬 실행 후 Reciprocal Rank Fusion으로 병합하면 서로의 약점 보완.

### 선택지
1. **Qdrant 네이티브 sparse vectors + Query API `FusionQuery.RRF`** — Qdrant 1.9+가 제공. 별도 저장소 없이 같은 컬렉션에 named vector(dense+sparse)로 저장
2. 별도 BM25 엔진(`rank_bm25` in-memory / Elasticsearch / OpenSearch) + 클라이언트 측 RRF — 인프라 추가, 동기화 필요
3. 현 상태 유지 — 품질 지표 이미 상한이라 투자 ROI 낮다고 판단 가능

### 결정
**옵션 1.** Qdrant가 이미 Docker로 운영 중이고 sparse vector + Query API + RRF를 네이티브 지원(qdrant-client 1.17.1에서 확인). 별도 인프라 없고 재인덱싱만으로 전환 가능.

### 구현
- **Sparse embedder** (`packages/rag/sparse.py`):
  - `fastembed.SparseTextEmbedding(model_name="Qdrant/bm25")`로 BM25 sparse vector 생성
  - 한국어는 **Kiwi 형태소 분석**으로 명사·동사·외국어·숫자·한자·어근만 추려 공백 조인 후 BM25에 투입 (영어는 전처리 없이)
  - `_has_korean()` 체크로 언어 자동 분기, 프로세스 전역 싱글톤(Kiwi·BM25 모델 로드 1회)
- **`QdrantDocumentStore`** 재작성:
  - 생성자에 `search_mode ∈ {"vector","hybrid"}`, `sparse_embedder` 받음
  - `vector` 모드: 기존 unnamed `VectorParams` + `langchain_qdrant.QdrantVectorStore` 경로 유지
  - `hybrid` 모드: named vectors (`dense`, `sparse`) 컬렉션 생성. `add_documents`는 raw `PointStruct`로 dense·sparse 동시 upsert. 검색은 `client.query_points`에 `prefetch=[dense, sparse]` + `FusionQuery(fusion=Fusion.RRF)`
  - 컬렉션 구조 불일치 시 `CollectionDimensionMismatch` 예외로 재인덱싱 강제
- **설정·토글** (`.env`, `apps/config.py`): `SEARCH_MODE=vector|hybrid`, `SPARSE_MODEL_NAME=Qdrant/bm25`
- **DI·rebuild·bench**: `apps/dependencies.py`, `pipeline/rebuild_index.py`, `scripts/bench_retrieval.py`, `scripts/bench_answers.py` 모두 `settings.search_mode` 기반으로 `SparseEmbedder` 주입
- **재인덱싱**: 기존 컬렉션은 unnamed vector 구조라 hybrid로 전환하려면 삭제·재생성 필요. `pipeline/rebuild_index.py`가 컬렉션 삭제 후 재구성

### 결과 (2026-04-23 재인덱싱 후)
**재인덱싱**: 6개 문서 → 1209 하이브리드 포인트 저장 (각 포인트에 dense 1536-d + sparse BM25 named vectors)

**Phase 1 벤치 비교** (TASK-004 프레임워크, 12 질의, reranker=bge-m3):

| 지표 | vector (ADR-015 기반선, 2026-04-22) | hybrid (2026-04-23) | Δ |
|------|------|------|---|
| Hit@3 | 1.000 | 1.000 | = |
| Precision@3 | 1.000 | 1.000 | = |
| Recall@3 | 0.944 | 0.944 | = |
| MRR | 1.000 | 1.000 | = |
| 평균 지연 | 580ms | **1008ms** | +74% (sparse 인코딩 비용) |

**Phase 2**: 동일 LLM·reranker 경로라 회귀 가능성이 낮아 본 TASK에서 생략. 추후 dataset이 확장되거나 키워드 실패 사례가 관찰되면 재실행 의무화

### 관찰·한계
- 현재 dataset(12 질의)은 기반선이 이미 상한(Hit@3=1.0)이라 **하이브리드의 이득이 드러나지 않음**. 이득은 dataset이 다양해지고 "정확 매칭" 질의가 추가돼야 관찰됨
- **지연 증가 +74%** (580ms → 1008ms): sparse vector 인코딩 + Qdrant 두 검색 병렬 수행. reranker warm-up·FastEmbed 모델 로드 오버헤드 포함
- Kiwi가 한국어만 전처리 — 일본어·중국어 문서 추가 시 별도 토크나이저 필요
- Qdrant의 Fusion.RRF는 `k=60` 상수로 내부 계산 (튜닝 불가). 필요 시 클라이언트 측 재구현 가능

### 기본값
`SEARCH_MODE=hybrid`로 적용. 이득은 dataset 의존이지만 회귀 0 확인됐고 장기적 확장성이 우수. vector 단독으로 회귀하려면 토글 + 재인덱싱 필요 (컬렉션 구조 다름)

### 후속
- TASK-011 이후 "정확 매칭 요구가 강한 질의" 10~20개 dataset에 추가 → hybrid 이득을 정량 증명
- 하이브리드 전용 Ragas 벤치 재실행 (시간 여유 있을 때)
- 다국어 토크나이저 확장 (일본어 MeCab, 중국어 jieba 등 — 현재 dataset에 없어 보류)

---

## ADR-024: 문서 자동 요약 — gpt-4o-mini · JSONB 영구 캐시 · 인덱싱 후 비동기 훅
**날짜**: 2026-04-25
**상태**: accepted
**관련**: TASK-014, ADR-014(LLM 백엔드 토글), 후속 TASK-015/016/017

### 배경
사용자가 카탈로그·랜딩·소스 카드에서 "이 문서가 무엇에 대한 것인지" 즉시 식별할 수 있어야 한다. 현재는 제목·source·페이지 수만 노출돼 의미 단서가 부족하고, "지식 도서관" 후속 TASK(K015 자동 분류, K016 카탈로그 UI, K017 랜딩 확장) 모두가 문서 단위 자연어 요약을 공통 입력으로 가정한다.

### 선택지
1. **gpt-4o-mini + 기존 LLM_BACKEND 인프라 재활용** — 신규 키 0, 비용 ~$0.005/문서, 한국어 자연스러움 양호, JSON mode 지원
2. **Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) + Anthropic SDK 신규 도입** — 한국어 자연스러움·환각 억제 우위, prompt caching 네이티브. 단 `ANTHROPIC_API_KEY` 추가·SDK 의존성·코드 분기 비용
3. **GLM 등 OpenAI-호환 저가 백엔드** — 기존 토글로 전환 가능, 비용 더 낮음. 한국어 품질 검증 필요·일부 주제 안전 필터 위험
4. 요약 미도입 — K015/K016/K017 모두 영향. 사용자 가치 손실 큼

### 결정
**옵션 1 (gpt-4o-mini)**. 결정 근거:
- TASK-014가 K015·K016·K017의 입력 데이터를 만드는 단계라 **빠른 합류**가 핵심
- 기존 `LLM_BACKEND=openai` 인프라 그대로, 코드·배포 변동 0
- 시범 1건 + 전체 16건 검수 결과 환각 0건, 한국어 자연스러움 카탈로그·랜딩에 충분
- Anthropic Haiku 전환 여력은 토글 인프라(ADR-014)로 1시간 내 가능 — 후속 TASK에서 한국어 품질 정량 비교가 필요해지면 재평가

### 구현
- **Postgres 마이그레이션** (`packages/db/migrations/0001_add_summary_columns.sql`):
  ```sql
  ALTER TABLE documents
      ADD COLUMN IF NOT EXISTS summary              JSONB,
      ADD COLUMN IF NOT EXISTS summary_model        TEXT,
      ADD COLUMN IF NOT EXISTS summary_generated_at TIMESTAMPTZ;
  ```
  `connection.py`의 `_apply_alter_migrations`가 sentinel 컬럼 존재 여부를 먼저 검사해 ALTER 자체를 회피 — `AccessExclusiveLock` 충돌 방지(이미 있는 컬럼은 ALTER 시도조차 안 함)
- **요약 모듈** (`packages/summarizer/`):
  - `prompts.py` — system 프롬프트(환각 차단 규칙·JSON 스키마 명시) + few-shot 2개(영문 ROS 책 / 정보 부족 분기 보고서). 정보 부족 시 빈 배열·빈 문자열 허용으로 환각 방지
  - `document_summarizer.py` — `summarize_document(title, chunks, settings, llm)` 1회 LLM 호출, JSON 모드 강제, 첫 8청크·청크당 1500자 상한, 실패는 빈 `SummaryResult`로 graceful degrade
- **JSON 스키마**: `{one_liner ≤40자, abstract 3~5문장, topics[3~7], target_audience, sample_questions[정확히 3개]}`
- **인덱싱 훅**: `apps/routers/ingest.py`의 응답 직후 `BackgroundTasks`로 `generate_summary_for_doc` 호출. 요약 실패해도 인덱싱 응답은 200 유지(독립 DB 세션·예외 격리)
- **API**: `GET /documents/{doc_id}/summary` (NULL 허용), `POST /documents/{doc_id}/summary/regenerate` (동기 강제 재생성, 인증 미도입 단계라 로컬 LAN 전용)
- **일괄 스크립트** (`scripts/generate_summaries.py`): `--dry-run`/`--regenerate`/`--limit`/`--doc-id`/`--report`. 결과 JSON을 `data/eval_runs/summaries_<ts>.json`에 저장
- **설정 토글**: `SUMMARY_ENABLED=true|false` (기본 true). false 시 ingest 훅·재생성 API 비활성

### 결과 (2026-04-25 파일럿 16문서)
- 시범 1건 + 일괄 15건 모두 success — 평균 3.7s/문서, 총 56초, 비용 ≈ $0.08
- 환각 0건 (한국어 시스템 설계 / 영문 ROS / 짧은 더미 문서 모두 검수)
- 정보 부족 문서는 `target_audience=""`, `sample_questions=[]`로 정직하게 빈값 처리
- 영문 원본 → 한국어 요약 + 기술 용어 원어 유지 (예: "ROS", "USB 카메라 드라이버")

### 관찰·한계
- **앞부분 편향**: 첫 8청크만 입력. 책 서문이 일반적인 100+ 청크 긴 문서는 요약 빈약 가능 — hierarchical summary는 후속 별건
- **재요약 트리거**: `POST .../regenerate` 동기 — 인덱싱 워커 분리(TASK-018) 후 큐 기반으로 재정의 예정
- **gpt-4o-mini JSON mode**: 안정적이지만 GLM 일부 변형은 미지원 — 향후 LLM 백엔드 전환 시 backend별 JSON 모드 가용성 점검 필요
- **인증 미도입 단계라 `regenerate` API는 로컬 LAN 전용** — 인증·공개배포 묶음 해제 후 admin 인증으로 보호

### 기본값
- `SUMMARY_ENABLED=true`, 모델은 `LLM_BACKEND=openai`(gpt-4o-mini) 재사용
- 회귀: `SUMMARY_ENABLED=false`로 ingest 훅·API 비활성, summary 컬럼은 NULL 유지

### 후속
- TASK-015 자동 분류는 `summary.topics[]`를 그대로 `tags[]`로 채택 (별도 입력 UI 없음)
- TASK-016 카탈로그 UI는 `summary.one_liner`/`abstract` 즉시 노출, `sample_questions`는 "이 책에 대해 묻기" 액션 시드
- TASK-017 랜딩 확장은 최근 인덱스된 문서의 `one_liner`를 칩으로 표시
- (장기) 한국어 품질 정량 비교 필요해지면 Anthropic Haiku로 토글 — ADR-014 인프라 재사용

---

## ADR-025: 카테고리 메타데이터 — 단일 컬렉션 + 룰 매칭 우선·LLM fallback
**날짜**: 2026-04-25
**상태**: accepted
**관련**: TASK-015, ADR-024(요약 활용), 후속 TASK-016/017

### 배경
"지식 도서관" 카탈로그·랜딩의 그룹핑·필터 축이 필요. 현재 `documents`/Qdrant payload에 분류 필드 0개. 책·아티클·노트가 섞여도 운영 분리 비용 없이 처리할 단일 자료구조와, **사용자 입력 부담 0** 자동 분류 파이프라인이 필요.

### 선택지
1. **Qdrant 컬렉션 분리** (book/article/paper 별도 컬렉션) — 격리·독립 인덱싱은 좋지만 임베딩 모델·검색 라우팅·관리 비용이 커짐. 임베딩이 같은데 컬렉션을 나누는 건 과도
2. **단일 컬렉션 + payload 메타데이터** — 1개 컬렉션 유지, 청크 payload에 `doc_type/category/tags` 동기화 + keyword payload index. 쿼리 시 필터 추가 0~수 ms. 인프라 복잡도 0
3. 카테고리 미도입 — TASK-016/017이 모든 문서를 평면 그리드로만 노출. 사용자 가치 손실
4. 사용자가 매번 수동 입력 — 입력 부담 큼, 누락 가능성. 단독 채택은 부적절

### 결정
**옵션 2 (단일 컬렉션 + payload)** + **자동 분류**(룰 매칭 우선 → LLM fallback). 회귀 조건: 임베딩 모델을 doc_type별로 달리 써야 할 명확한 근거가 생기면 컬렉션 분리 재평가.

### 구현
- **Postgres 마이그레이션** (`packages/db/migrations/0002_add_classification_columns.sql`):
  ```sql
  ALTER TABLE documents
      ADD COLUMN IF NOT EXISTS doc_type            VARCHAR(16) NOT NULL DEFAULT 'book',
      ADD COLUMN IF NOT EXISTS category            VARCHAR(64),
      ADD COLUMN IF NOT EXISTS category_confidence REAL,
      ADD COLUMN IF NOT EXISTS tags                JSONB DEFAULT '[]'::jsonb;
  -- documents_doc_type_check, ix_documents_doc_type, ix_documents_category 추가
  ```
  Sentinel 컬럼(`doc_type`)으로 idempotent 처리 — `connection.py`의 `_apply_alter_migrations`가 이미 있는 컬럼이면 ALTER 시도 자체를 회피
- **doc_type enum**: `book | article | paper | note | report | web | other` (default `book`). file_type/source 휴리스틱(`pdf→book`, `docx→report`, `txt|md→note`, `http(s)→web`)으로 자동 추정
- **`category`**: 단일 문자열 (`web/frontend`, `ai/ml` 등 계층형 ID 허용). NULL 허용 — 신뢰도 낮으면 `category=NULL` 유지 가능하나 현 구현은 LLM 응답을 수용하고 confidence 값을 표면에 노출
- **`tags`**: 문자열 배열, **TASK-014 `summary.topics[]`를 그대로 채택**. 별도 입력 UI 없음
- **카테고리 트리** (`config/categories.yaml`): `version` + `categories[]` (id/label/keywords). 키워드는 한·영 혼용 가능. `other`는 fallback 의미라 항상 마지막
- **분류 파이프라인** (`packages/classifier/category_classifier.py`):
  1. 제목 + `summary.topics`를 lowercase 텍스트로 결합
  2. categories.yaml 각 카테고리에 대해 키워드 hits 카운트, 가장 높은 카테고리 선택. confidence = `min(1, hits/len(keywords) * 1.5)`
  3. hits 0이면 LLM fallback (gpt-4o-mini, JSON mode) — `{id, confidence}` 한 번에. 응답 ID가 enum에 없으면 `fallback_unknown`
  4. LLM confidence < 0.4 면 `category` 그대로 두되 confidence를 admin에 노출 (사용자가 수정할 수 있는 PATCH API 별도)
- **Qdrant payload** (`qdrant_store.py`):
  - `_ensure_payload_indexes()` — `metadata.doc_id|doc_type|category|tags` 4개에 keyword 인덱스 생성(`PayloadSchemaType.KEYWORD`, idempotent)
  - `set_classification_payload(doc_id, doc_type=, category=, tags=)` — `client.set_payload(points=Filter(...))`로 doc_id 단위 일괄 갱신. 부분 업데이트라 다른 metadata 키 보존
- **API 변경**:
  - `POST /ingest`: 옵션 Form 파라미터 `doc_type`/`category`/`tags`(콤마 구분 문자열). 명시값 있으면 자동 추정 비활성화 + summary만 비동기 생성
  - `PATCH /documents/{id}`: `DocumentPatchRequest` (모두 optional, None은 no-op). DB + Qdrant payload 동시 갱신. doc_type enum 422 검증
  - 기존 `POST /ingest` 응답·`DocumentItem` 응답에 `doc_type/category/category_confidence/tags` 추가
- **백그라운드 헬퍼**: 사용자 미지정 인덱싱은 `classify_and_summarize_for_doc(doc_id)`로 통합 — summary 생성 후 같은 turn에 분류, 사용자 지정 인덱싱은 `generate_summary_for_doc`만
- **일괄 스크립트** (`scripts/classify_documents.py`): `--dry-run/--regenerate/--limit/--doc-id/--report`. method counter(rule/llm/fallback_unknown)·결과 JSON 리포트

### 결과 (2026-04-25 파일럿 20문서)
- 20/20 success, **rule 16건(LLM 호출 0)**, **LLM fallback 4건**(비용 ≈ $0.001), 총 5.7초
- 분류 정확도 수동 검수: 20/20 적절(웹/딥러닝/시스템 설계/로보틱스/프로그래밍/모바일/기타 모두 의도 일치)
- 부분 fallback 사례: 폴리머클레이(점토 공예) → other 0.3, 헌법재판소 → other 0.3, 중복테스트 → other 0.3 — 라이브러리에 없는 도메인은 정직하게 "other" + low confidence로 표면화
- doc_type 휴리스틱 정확: pdf→book, txt→note, docx→report

### 관찰·한계
- **신뢰도 낮은 LLM 분류**(< 0.4)도 카테고리를 보존하고 confidence만 낮게 노출 — admin UI에서 confidence 임계로 "검토 필요" 배지 가능. 더 엄격한 정책으로 NULL 강제도 가능하지만 현 구현은 정보 보존 우선
- **categories.yaml 조기 동결 위험**: 새 도메인(예: 통계/금융/법) 등록 시 키워드만 추가하면 즉시 매칭 — 코드 변경 0
- **동음이의·복합 도메인**: "C++와 CUDA 딥러닝"처럼 cpp + ai/ml 양쪽 매칭 가능한 경우 hits 단순 합산으로 한쪽이 채택됨. 다중 라벨이 필요해지면 별건
- **검색 시 메타데이터 필터·부스팅**은 본 ADR 범위 밖 — payload index만 깔아 두고 활용은 후속(쿼리 시 `metadata.category`/`metadata.tags` 필터)

### 기본값
- 자동 분류 활성: 인덱싱 후 `BackgroundTasks`에서 summary 직후 자동 호출
- 사용자 명시 분류값(`POST /ingest`의 doc_type/category/tags)이 있으면 우선
- 회귀: PATCH로 사용자가 임의로 수정 가능. 카테고리 컬럼 DROP은 마이그레이션 역방향

### 후속
- TASK-016 카탈로그 UI에서 category 그룹·tags 칩·confidence 배지 표면화
- TASK-017 랜딩 카드에 주제 칩(가장 빈번한 tags) 노출
- (검색) `apps/routers/query.py`에 `category`/`tags` 필터 옵션 — 별건. payload index는 이미 깔려 있어 추가 비용 없음
- (장기) categories.yaml GUI 편집 — 현재는 수기 편집 + 재실행

---

## ADR-026: 도서관 탭 — 카테고리 그룹 카드 + doc_filter 한정 질의 라우팅
**날짜**: 2026-04-25
**상태**: accepted
**관련**: TASK-016, ADR-024(요약 데이터), ADR-025(분류 데이터), TASK-008/ADR-020(빈 채팅 카드)

### 배경
관리자 "문서" 탭(TASK-005)은 운영자용이라 사용자 탐색에 부적합. 사용자가 RAG 지식 베이스를 탐색하고 특정 문서에 대해 즉시 질문할 수 있는 별개 UI가 필요하다. 데이터는 K014(요약) + K015(분류)로 채워져 있고, 이를 카드 그리드와 카테고리 그룹으로 즉시 노출하는 단계.

### 선택지
1. **신규 "도서관" 탭** — 채팅 옆 별도 탭. 검색·필터·카테고리 그룹·카드 그리드·"이 책에 대해 묻기" 버튼. 채팅 탭과 active_doc_filter 상태로 연결. 옵션 1 채택
2. 기존 "문서" 탭에 사용자 뷰 토글 — 운영/사용자 경로가 같은 탭에 섞이면 모드 전환 비용 큼
3. 빈 채팅 empty state에서만 노출 — TASK-017 영역. 도서관은 항상 접근 가능해야 함
4. 별도 페이지(`ui/pages/library.py`) — Streamlit multi-page는 인증·헤더 분리 시점(2단계, 인증·공개배포 묶음)에 채택. 1단계는 탭만

### 결정
**옵션 1**. 도서관 탭은 1단계 admin UI(TASK-005, ADR-017)와 같은 모놀리식 레이아웃에 신설하되, **탭 위치를 채팅 직후·문서 직전**으로 둬 사용자 우선 정렬을 시각적으로 강제.

### 구현
- **데이터 소스**: 기존 `GET /documents` (DocumentItem이 K015 4필드 + K014 summary 보유)를 그대로 재사용 — 신규 API 0
- **탭 구조** (`ui/app.py`):
  - 상단 필터 바: 검색 input(제목·요약·태그·topics 일괄 매칭) / `doc_type` selectbox / `category` selectbox(`(전체)`/`(미분류)` 포함)
  - 본문: `category` 단위 섹션(알파벳순) + `(미분류)` 마지막 + 3-column 카드 그리드
  - 카드: 제목, `summary.one_liner`, `summary.topics[:5]` 칩, [상세] [이 책에 대해 묻기] 버튼
  - confidence < 0.4 카드는 ⚠️ 배지 — admin 검수 시그널
  - [상세] 토글 — 같은 카드 안에 abstract + sample_questions 버튼들 + meta(source/file_type/indexed_at/confidence)
- **`doc_filter` 라우팅**:
  - 카드의 [이 책에 대해 묻기] 또는 sample_questions 버튼 클릭 → `st.session_state["active_doc_filter"] = {"doc_id", "title"}`
  - sample_questions는 `_pending_question`까지 동시 세팅해 채팅 탭에서 즉시 질의
  - 채팅 탭 상단에 활성 배지 + [전체 검색] 해제 버튼
  - `/query` POST에 `doc_filter` 필드를 함께 전달. backend 관통: `QueryRequest` → `pipeline.query(doc_filter=)` → `retrieve(doc_id=)` → `similarity_search_with_score(doc_id=)` (vector·hybrid 양쪽 이미 지원)
  - LangSmith 메타에 `doc_filter` 표기, 태그에 `doc_filter:{doc_id[:8]}`
- **상태 라이프사이클**: 사용자가 [전체 검색] 클릭 또는 다른 책의 [이 책에 대해 묻기] 클릭 시까지 유지. 세션 초기화는 영향 없음(질의 한정 해제는 별개)
- **검색**: 단순 `search_q in lower(haystack)` — 제목 + one_liner + abstract + topics + tags 결합. 추후 K017과 함께 `category` 패싯이나 정렬을 확장 가능
- **카드 스타일**: 빌트인 `st.container(border=True)` + 헤더/캡션. 카드 안 두 칸 버튼(상세/이 책에 대해 묻기) — 모바일 좁은 폭에서도 가독

### 결과 (현 20문서)
- 카테고리 8개(ai/ml, software/architecture, programming/cpp|network|systems, web/frontend, mobile/android, robotics) + (미분류) 0
- 카드 그리드 렌더 정상, 배지·요약·칩·버튼 모두 동작
- doc_filter 활성 시 검색 latency 미미(filter 절 추가 ms 수준)

### 관찰·한계
- **카드 상세 토글이 같은 카드 안에서 펼쳐짐** → 그리드 레이아웃이 일시적으로 비대칭. Streamlit native modal은 1.36+ 필요 — 도입 검토는 별건
- **파일럿 16~20건 규모에서는 카드 그리드 충분**. 100+ 문서 시 가상 스크롤·페이징 필요. 하지만 현재 보유 규모를 고려해 단순 렌더 채택
- **doc_filter는 단일 문서만** — 다중 문서 한정(예: 특정 카테고리 한정)은 후속 별건 (`category` 패싯 검색)
- **재인덱싱·요약 미생성 문서**: `one_liner`가 비면 "_요약 생성 중…_" placeholder. K014 BackgroundTasks가 비동기라 신규 업로드 직후 잠시 placeholder 노출

### 기본값
- 도서관 탭 항상 노출(토글 없음)
- doc_filter 활성 상태는 사용자 명시 해제까지 유지
- 회귀: TASK-005 admin UI(문서 탭)는 그대로 — 인증·공개배포 묶음 해제 시 도서관(사용자) / 문서(admin) 분리 페이지로 승격

### 후속
- TASK-017 빈 채팅 카드에 도서관 진입로 + 주제 칩
- 카드의 PATCH UI(사용자가 잘못 분류된 카테고리/태그 즉석 수정) — admin 인증 후 도입
- `category` 패싯 검색·정렬(최근 인덱스/이름순) — 별건
- 카드 상세 modal 전환 (Streamlit 1.36+ `st.dialog`) — 의존성 검증 후 별건

---

## ADR-027: 랜딩 카드 v2 — 카테고리 분포·주제 칩·최근 문서 카드
**날짜**: 2026-04-25
**상태**: accepted
**관련**: TASK-017, ADR-020(랜딩 카드 v1·`/index/overview` 캐시), ADR-024(요약), ADR-025(분류), ADR-026(도서관 탭)

### 배경
TASK-008(ADR-020)로 빈 채팅에 "이 시스템이 아는 내용 + 예시 질문 5개"가 이미 있다. K014(요약) + K015(분류)가 채워진 시점이라, 이 카드를 **단발 진입로**가 아니라 **탐색 시작점**으로 확장한다 — 도서관 탭(K016)으로 가기 전에도 빈 채팅에서 즉시 (a) 어떤 카테고리/주제가 있는지 (b) 최근 추가된 책이 무엇인지 (c) 한 번 클릭으로 한정 질의·검색 시작이 가능해야 한다.

### 선택지
1. **`/index/overview` 응답 확장** + 빈 채팅 카드 컴포넌트 추가 (옵션 1, 채택)
2. 신규 엔드포인트(예: `/landing/v2`)로 분리 — 캐시·무효화 흐름이 둘로 갈라져 비용 큼
3. 빈 채팅 카드를 도서관 탭의 미니 임베드로 — 두 위치에서 동일 컴포넌트 유지보수 비용

### 결정
**옵션 1**. 기존 `index_overview` 캐시 흐름·캐시 무효화(ADR-020) 그대로 유지하면서 응답에 3 필드만 추가:
- `top_tags: list[str]` — 모든 문서의 `tags` 빈도 상위 12 (UI는 6개만 칩으로 노출)
- `categories: list[{id,label,count}]` — 카테고리 분포. label은 `categories.yaml` 매칭으로 보강(없으면 id)
- `recent_docs: list[RecentDocItem]` — 최근 인덱싱된 6개. `{doc_id, title, one_liner, category}`

UI는 기존 카드 안에 (a) 카테고리 분포 라인 (b) 주제 칩 6개 (c) 예시 질문(기존) (d) 최근 문서 카드 3-grid (e) 전체 문서 expander 순으로 배치.

### 구현
- **백엔드** (`apps/routers/documents.py`):
  - `index_overview` 함수 끝에서 `tag_counter`/`cat_counter`로 분포 계산 (records 1회 순회)
  - `categories.yaml` 1회 로드해 label 매핑. 파일 없거나 파싱 실패해도 graceful (id 그대로)
  - `recent_docs` 6개 생성 — `list_documents`가 이미 `indexed_at desc` 정렬이라 추가 정렬 없이 `records[:6]`
  - LLM 호출은 그대로 1회 — `top_tags/categories/recent_docs`는 모두 DB 데이터로만 파생, 비용·지연 추가 0
- **스키마** (`apps/schemas/documents.py`):
  - `RecentDocItem` 신설
  - `IndexOverviewResponse`에 `top_tags=[], categories=[], recent_docs=[]` (모두 default 빈값으로 후방호환)
- **UI** (`ui/app.py`):
  - 빈 채팅 카드 본문 재구성 — summary 직후 카테고리 분포 한 줄 → 주제 칩 → 예시 질문 → 최근 문서 카드 → 전체 문서 expander
  - 주제 칩 클릭 → `library_search` 사전 채우고 toast 안내 → 사용자가 도서관 탭으로 이동
  - 최근 문서 카드의 [이 책에 대해 묻기] → `active_doc_filter` 세팅 (도서관 탭과 동일 라우팅)
- **캐시**: 기존 `_overview_cache` 그대로. 신규 필드는 동일 캐시 dict에 저장됨. 업로드/삭제 시 `invalidate_index_overview_cache()`로 동시 무효화

### 결과
- LLM 호출 횟수 변화 없음 (1회 캐시)
- 응답 페이로드 증가 — 현 20문서 기준 `~1.5KB → ~3KB` (top_tags 12, categories 8, recent 6 항목)
- UI 렌더 시간 변화 미미

### 관찰·한계
- **카테고리 label 한국어**: `categories.yaml` label이 사용자 가시 텍스트 — 한국어로 작성된 상태 유지 필요
- **주제 칩 빈도**: 현재 단순 카운트. 100+ 문서 시 stop-word(예: "기초", "입문") 빈출 가능 — 별건으로 IDF·blacklist 도입 검토
- **최근 문서 6개**: 인덱싱 직후 요약이 아직 없으면 `one_liner=null`. UI에서 category fallback으로 처리(`_요약 생성 중…`이 아닌 `_<category>_`)
- **모바일 폭**: 칩·카드 그리드가 좁은 폭에서 1열로 떨어짐 — Streamlit 기본 동작이라 별도 처리 안 함

### 기본값
- `top_tags`/`categories`/`recent_docs`는 항상 응답에 포함 (빈 배열 가능). UI는 빈 배열이면 해당 섹션 자체를 렌더하지 않음
- `INDEX_OVERVIEW_ENABLED=false` 시 모든 섹션 비활성 (기존 동작 유지)
- 회귀: 이전 응답을 받는 클라이언트는 신규 필드를 무시하면 됨 — 후방 호환

### 후속
- 칩 IDF·blacklist 정제 — 별건
- 카드 상세 modal (`st.dialog`) 도입 시 도서관 탭 카드와 통합 — 별건
- 최근 문서 정렬 옵션(인기/최근/A-Z) — 별건

---

## ADR-028: 색인 워커 분리 — Postgres `ingest_jobs` 큐 + indexer 프로세스
**날짜**: 2026-04-25
**상태**: accepted
**관련**: TASK-018, ADR-014(ingest 핫픽스 turn에 추가된 `asyncio.to_thread`), TASK-014/015(BackgroundTasks 훅 이관)

### 배경
- 사용자가 bulk_ingest로 50+ 파일을 동시 색인하면 FastAPI 단일 프로세스에서 Docling 파싱이 CPU·메모리를 점유, `/query`·`/health` 응답이 체감 가능 수준으로 저하
- TASK-014에서 `asyncio.to_thread` 핫픽스로 event loop 차단은 풀었지만, 같은 프로세스 자원 경합은 여전. 또 uvicorn 재기동 시 진행 중 인덱싱이 손실
- `BackgroundTasks`로 처리하던 summary/classify는 응답 후 라이프사이클이 끝나면 손실 — 잡 추적·재시도 불가

### 선택지
1. **Postgres `ingest_jobs` 테이블 + 별도 워커 프로세스** — 의존성 0 추가(Postgres 기존), `SELECT … FOR UPDATE SKIP LOCKED`로 멀티 워커 안전. 채택
2. Redis + RQ/Celery — 표준이지만 Redis 1개 인프라 추가, 운영 컨테이너 +1
3. 파일 시스템 inbox 폴더 watch — race·고아 파일·실패 이력 추적 까다로움
4. uvicorn workers ≥2 — 같은 프로세스 자원 경합은 해소하지만 Docling/Reranker 메모리 ×2, 잡 손실 문제 유지
5. 현 상태 유지 — 사용자 통증 직접 호소 중이라 부적절

### 결정
**옵션 1**. 이유:
- Postgres 큐 한 줄 (`ingest_jobs` 테이블)로 추가 인프라 0
- `SKIP LOCKED`로 워커 N개 안전, 1개로 시작
- 잡 상태 머신(`pending → in_progress → done|failed`) + retry 카운터 + 에러 메시지 보존 → 재시도·디버깅 가시성
- 회귀 토글(`INGEST_MODE=queue|sync`)로 기존 sync 동작 즉시 복원 가능

### 구현
- **마이그레이션** `0003_add_ingest_jobs.sql`:
  ```
  ingest_jobs(id BIGSERIAL PK, doc_id, file_path, title, source, content_hash,
              user_doc_type/category/tags(JSONB),
              status CHECK in (pending|in_progress|done|failed|cancelled),
              retry_count, error TEXT, enqueued_at/started_at/finished_at)
  -- ix_ingest_jobs_status_enqueued, ix_ingest_jobs_doc_id
  ```
  Sentinel은 `("table", "ingest_jobs")` — 컬럼이 아닌 테이블 존재 검사. `connection.py`의 sentinel 시스템을 column/table 양쪽 지원하도록 일반화
- **마이그레이션 동시성 처리** (race fix): uvicorn + indexer_worker가 동시 기동되면 같은 마이그레이션을 두 프로세스가 실행해 `pg_type` UNIQUE 위반 발생. 모든 sentinel 통과 시 빠른 경로(lock 없이 종료) + 미적용 시 `pg_advisory_xact_lock(<project_id>)`로 트랜잭션 단위 직렬화 + lock 획득 후 sentinel 재확인
- **Queue API** (`packages/jobs/queue.py`):
  - `enqueue_job(...)` — 사전 발급된 doc_id, 사용자 명시 분류값 함께 저장
  - `claim_next_job()` — `UPDATE … SET status='in_progress' WHERE id = (SELECT id … WHERE status='pending' ORDER BY enqueued_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING id`. 동시 워커 N개 안전
  - `mark_done(job_id, doc_id)` / `mark_failed(job_id, error, retry=bool)` / `get_job` / `list_jobs(status)`
- **워커** (`apps/indexer_worker.py`):
  - 엔트리포인트 `python -m apps.indexer_worker`
  - 폴링 루프(빈 큐 시 backoff 3→15초), claim → `pipeline.ingest` → `create_document` → 사용자 분류 우선 적용 → `_generate_summary_inner` → `_classify_doc` → cache 무효화 → `mark_done`
  - 예외 → mark_failed (retry < 3이면 pending 되돌림)
  - SIGTERM/SIGINT 핸들러로 현재 잡 끝까지 처리 후 종료
- **`POST /ingest`**:
  - `INGEST_MODE=queue`(기본): 파일 저장 + `enqueue_job` + `202 Accepted` + `{doc_id, status:"pending", job_id}` 응답
  - `INGEST_MODE=sync`: 기존 동작(라우트 안에서 인덱싱 + BackgroundTasks summary/classify) 유지 — 회귀
- **`GET /jobs/{id}` / `GET /jobs?status=&limit=`** (`apps/routers/jobs.py`): 운영자 read-only 가시성. 인증 미도입 단계라 로컬 LAN 전용
- **`bulk_ingest --via-queue`**: HTTP 거치지 않고 Postgres에 직접 enqueue. FastAPI 미기동 환경에서도 사용 가능. 파일은 `data/uploads/{doc_id}{ext}`로 복사. 결과 리포트에 `enqueued` 카운터 추가 (HTTP 모드도 응답이 `pending`이면 enqueued로 분류)
- **docker-compose**: 호스트 venv에서 두 프로세스(uvicorn + worker) 실행을 표준 운영 절차로 두고 docker-compose.yml에 주석 가이드 추가. 앱 컨테이너화는 Dockerfile 별건 TASK
- **응답 스키마**: `IngestResponse`에 `job_id: Optional[int]` 추가 (queue 모드만 채워짐, sync 모드는 None)

### 결과 (2026-04-25 스모크)
- `INGEST_MODE=queue` 기본으로 전환
- 작은 파일 1건 enqueue → claim → 인덱싱(4초) → 요약 → 분류 → done — 총 **9초** 만에 완료
- 잡 상태 추적: `pending → in_progress (4s) → done`
- 사용자 명시 미지정 케이스에서 자동 분류 정상(`note / software/architecture` LLM fallback)
- 워커가 죽어도 잡은 `in_progress` 상태로 남아있어 수동 재시도 가능 (현재는 자동 stale 회수 미구현)
- uvicorn 재기동에도 큐의 미완료 잡은 그대로 보존 — 워커가 다시 폴링하면 처리 재개

### 관찰·한계
- **마이그레이션 race**: 첫 동시 기동 시 `pg_type` UNIQUE 위반 발생 → advisory lock + 빠른 경로로 해소. 운영 중 추가 마이그레이션 시 동일 패턴 적용
- **stale `in_progress` 회수 미구현**: 워커가 OOM·SIGKILL로 죽으면 잡이 영구 in_progress 잔존. 후속으로 `started_at < NOW() - 1h` 잡을 자동 pending 복귀하는 housekeeping 추가 필요
- **단일 워커 처리량**: PDF 100MB 1건이 큐 헤드에 있으면 뒤 잡 모두 대기. `INDEXER_CONCURRENCY=1` 기본, 필요 시 워커 N개 띄우면 SKIP LOCKED로 자동 분산
- **메모리 비용**: FastAPI(Reranker) + indexer(Docling) 양쪽 모델 메모리. Reranker는 워커에 불필요·Docling은 FastAPI에 불필요. 현재는 `get_pipeline()` 공유로 둘 다 같은 의존성 그래프 — 메모리 절약 별건
- **`bulk_ingest` HTTP 모드**: FastAPI가 큐 모드일 때 응답이 `pending`이면 응답 시점엔 색인 미완료 — 결과 JSON의 `chunk_count`/`has_tables`/`has_images`는 비어 있음. 사용자가 결과 검수 시 `/jobs` 또는 `/documents/{id}` 다시 조회 필요
- **사용자 명시 분류값**: 큐 잡에 그대로 저장(JSON), 워커가 인덱싱 직후 적용. 자동 분류는 skip

### 기본값
- `INGEST_MODE=queue`
- 워커 1개(`INDEXER_CONCURRENCY=1`, env로 노출은 별건)
- retry 3회, retry 후 `failed`로 영구 처리
- 회귀: `INGEST_MODE=sync`로 단 한 줄 전환 — TASK-014 BackgroundTasks 흐름 그대로 복원

### 후속
- stale `in_progress` 잡 자동 회수 (housekeeping 잡 또는 워커 startup time 기준)
- 워커 N개 동시 운영 검증 — SKIP LOCKED는 안전하지만 LangSmith 트레이스에 worker_id 태깅 필요
- 잡 진행 UI (관리자 탭에 `/jobs?status=` 폴링 표시) — 인증 도입 후
- 앱 컨테이너 Dockerfile + docker-compose `indexer` 서비스 — 별건
- 큐 메트릭(처리량·평균 lag·실패율) — Prometheus 익스포터 별건
