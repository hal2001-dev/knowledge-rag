---
name: retrieval
description: 검색 파이프라인 — 임베딩·하이브리드·reranker·동반 검색 정책 hub. 결정 근거는 각 ADR 참조
type: feature
---

# Retrieval — 검색 파이프라인

**상태**: active
**마지막 업데이트**: 2026-04-30
**관련 페이지**: `architecture/decisions.md`, `data/schema.md`, `features/evaluation.md`

## 요약

질문이 들어오면 다음 단계를 거쳐 LLM 컨텍스트가 만들어진다.
1. **implicit doc_filter 매칭**(ADR-034) — 질문 본문에 책 제목이 명시되면 자동 doc_filter
2. **similarity_search**(`packages/vectorstore/qdrant_store.py`) — vector 또는 hybrid(dense+sparse RRF) 모드(ADR-023)
3. **rerank**(`packages/rag/reranker.py`) — flashrank(영어) 또는 bge-m3(다국어, ADR-016) top_n=5
4. **heading prefix 동반 검색**(ADR-035, **기본 OFF**) — hit 청크의 `heading_path[:depth]` 공유 인접 청크를 companion으로 동반(LLM 컨텍스트 only, sources 미노출)
5. **generate**(`packages/rag/generator.py`) — companion·hit 동일 가중으로 컨텍스트 주입

## 활성 스코프 우선순위 (ADR-029)

`doc_filter > category_filter > series_filter` (한 번에 하나만 적용). 상위 우선순위 인자가 들어오면 하위는 무시된다. implicit doc_filter는 explicit scope 모두 None일 때만 동작.

## heading prefix 동반 검색 — ADR-035

| 환경 변수 | 기본값 | 의미 |
|---|---|---|
| `HEADING_EXPAND_ENABLED` | `false` | 동반 검색 활성화 토글. 안정화 후 별도 PR로 true 전환 |
| `HEADING_EXPAND_PREFIX_DEPTH` | `1` | `heading_path` 앞에서 매칭에 쓸 토큰 수(1=장, 2=장+절) |
| `HEADING_EXPAND_NEIGHBORS` | `2` | hit당 동반시킬 인접 청크 최대 수 |

### 동작 요약

- `expand_enabled=true`이면 reranker 통과 hit 각각에 대해 같은 doc_id + `heading_path[:depth]` 공유 청크를 N개 회수해 companion으로 결과 list 끝에 append
- companion: `metadata.companion=True`, score=0.0, **응답 sources에서 제외**(LLM 컨텍스트만 들어감, 사용자 화면 변경 0)
- 중복 `(doc_id, chunk_index)`는 set으로 1차 차단, hits·이전 companions 모두 exclude
- LangSmith 메타 `expanded_chunks_count`로 동반 분포 관찰

### 회귀

`HEADING_EXPAND_ENABLED=false`(기본): retriever는 reranker 결과만 반환 — 0.30.x 동작 100% 보존. payload index 추가는 idempotent로 트래픽 영향 0.

### 한계

- heading 없는 청크(평문 PDF)는 동반 0
- depth=1로 prefix가 너무 광범위한 짧은 책에선 의미적 인접성 보장 X — neighbors=2 cap으로 폭발만 방지
- LLM 컨텍스트 +10 청크(top_k=5 × 2) — gpt-4o-mini 128k 한도 대비 미미하나 비용 미세 증가

## 출처

- ADR-016, ADR-023, ADR-029, ADR-034, ADR-035 — `architecture/decisions.md`
- 코드: `packages/rag/retriever.py`, `packages/rag/pipeline.py`, `packages/vectorstore/qdrant_store.py`
- 테스트: `tests/unit/test_retriever_heading_expand.py`
