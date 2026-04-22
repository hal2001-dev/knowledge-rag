# 성능 평가 (Evaluation)

**상태**: active
**마지막 업데이트**: 2026-04-22
**관련 페이지**: `retrieval.md` _(미작성)_, `embedding.md` _(미작성)_, [decisions.md](../architecture/decisions.md)

---

## 현재 최신 지표 (2026-04-22 기반선, TASK-004)

**dataset**: [tests/eval/dataset.jsonl](../../../tests/eval/dataset.jsonl) · 12개 질의 (ko/en/mixed) · 문서 6개(ROS 3벌 + 딥러닝 한국어 + 노이즈 2)
**설정**: OpenAI text-embedding-3-small, Qdrant initial_k=20, BGE-reranker-v2-m3 top-3, gpt-4o-mini, judge=gpt-4o-mini

### Phase 1 — Retrieval (`scripts/bench_retrieval.py`)

| 지표 | FlashRank | BGE-M3 (기본) | Δ |
|------|-----------|----------------|---|
| Hit@3 | 0.917 | **1.000** | +9% |
| Precision@3 (doc-unique) | 0.847 | **1.000** | +18% |
| Recall@3 (doc-unique) | 0.861 | **0.944** | +10% |
| MRR | 0.833 | **1.000** | +20% |
| 평균 지연 | 441ms | 580ms | +32% |

질의별 Hit@3에서 FlashRank가 놓친 유일 케이스: `q11 ROS에서 토픽과 서비스의 차이는?` (BGE-M3는 히트).

### Phase 2 — Answer Quality (`scripts/bench_answers.py`, Ragas)

| 지표 | 값 | 해석 |
|------|-----|------|
| faithfulness | **0.886** | 답변 주장의 88.6%가 retrieved context에 직접 근거 — 양호 |
| answer_relevancy | 0.648 | 답변이 질문에 의미적으로 관련된 정도 — 중간 (긴 답변·주변 정보 포함으로 낮아짐) |
| context_precision | **0.986** | 가져온 3청크 중 답변에 기여한 비율 — 매우 높음 |
| context_recall | 0.942 | reference 커버리지. **주의**: 현재 dataset에 reference 없어 self-reference로 계산 → 낮아질 수는 없는 상한 추정치. 실질 ground truth 라벨링 필요 |

---

## 실행 방법

### Retrieval 지표 (Phase 1, 단독 backend)
```bash
.venv/bin/python scripts/bench_retrieval.py
```

### Retrieval A/B 비교
```bash
.venv/bin/python scripts/bench_retrieval.py --backend flashrank bge-m3
```

### 답변 품질 지표 (Phase 2, Ragas)
```bash
# 전체 (약 2~3분, API 호출 100~150회)
.venv/bin/python scripts/bench_answers.py

# 스모크 (약 30초)
.venv/bin/python scripts/bench_answers.py --limit 3
```

결과는 `data/eval_runs/{retrieval|answers}_<timestamp>.json`에 저장. LangSmith 활성 시 대시보드 `knowledge-rag` 프로젝트에 run이 자동 누적.

---

## 해석 가이드

### 어느 지표를 먼저 볼 것인가

1. **Hit@3** — retrieval 최소 건전성. 1.0 근처가 아니면 임베딩·청킹부터 재검토
2. **faithfulness** — hallucination 측정의 1차 지표. 0.85+ 유지가 목표
3. **answer_relevancy** — LLM 프롬프트 품질 지표. 0.7+ 목표. 낮으면 system prompt나 generator 조정
4. **context_precision/recall** — 검색 대비 답변 품질의 연결도. 함께 낮으면 reranker, 한쪽만 낮으면 top_k/initial_k 조정

### 지표 비교 원칙

- 모든 ADR은 **before/after 수치 동반**. 수치 없이 결정 금지
- reranker/LLM backend 바꾼 후 반드시 양 Phase 재실행
- 튜닝 질의와 평가 질의를 분리 (현재 dataset은 전 공용 — 향후 hold-out 5개 분리 권장)

---

## 평가 데이터셋

| 이름 | 문서 수 | 질문 수 | 비고 |
|------|---------|---------|------|
| tests/eval/dataset.jsonl | 6 | 12 | ko 7 / en 4 / mixed 2. 정답 `expected_doc_ids` 라벨링 완료. reference(정답 문자열) 미포함 → Phase 2는 self-reference 해석 |

### 다음 개선

- [ ] reference(정답 답변 문자열) 10개 추가 → context_recall 진짜 값 확보
- [ ] hold-out 질의 5개 분리 (튜닝 vs 평가)
- [ ] 질의 20~30개로 확장

---

## 실험 기록

실험마다 아래 형식으로 추가합니다.

```
### 실험 YYYY-MM-DD: 변경 내용 한 줄 요약
- **변경**: 무엇을 바꿨는가
- **이유**: 왜 바꿨는가
- **결과**: 지표 변화 (이전 → 이후)
- **결론**: 유지 / 롤백 / 추가 실험 필요
```

### 실험 2026-04-22-a: Reranker 다국어화 (FlashRank → BGE-reranker-v2-m3)

- **변경**: `packages/rag/reranker.py` 추상화 + 2종 구현, `.env`의 `RERANKER_BACKEND` 토글 도입 (TASK-001, ADR-012)
- **이유**: FlashRank `ms-marco-MiniLM-L-12-v2`가 한↔영 크로스에서 오동작
- **결과** (Phase 1, 12개 질의 평균):
  - Hit@3 0.917 → **1.000**
  - Precision@3 0.847 → **1.000**
  - Recall@3 0.861 → **0.944**
  - MRR 0.833 → **1.000**
- **결론**: BGE-M3 채택 확정. 정량 근거 확보.

### 실험 2026-04-22-b: 측정 프레임워크 도입 (TASK-004)

- **변경**: `scripts/bench_retrieval.py` + `scripts/bench_answers.py` 신설, Ragas + LangSmith 통합, [tests/eval/dataset.jsonl](../../../tests/eval/dataset.jsonl) 12개 질의 라벨링
- **이유**: 이전 ADR들이 정성 판단에 의존 — 이후 모든 실험에서 수치 근거 필수화
- **결과**: 위 "현재 최신 지표" 표가 기반선
- **결론**: 유지. 모든 후속 ADR은 before/after 수치 동반 원칙 (ADR-015)

### 실험 2026-04-22-c: Embedding 다국어화 A/B (OpenAI vs BGE-M3, TASK-002)

- **변경**: `packages/llm/embeddings.py` 추상화 + 2종(`openai`, `bge-m3`), Qdrant 차원 자동 감지
- **이유**: reranker 다국어화(ADR-012) 후 남은 한↔영 크로스 병목이 임베딩 1단계에 있을 가능성 검증
- **조건**: dataset 12개 질의, reranker=bge-m3, LLM=gpt-4o-mini 고정, 임베딩만 교체

| 지표 | OpenAI | BGE-M3 | Δ |
|------|--------|--------|---|
| Hit@3 | 1.000 | 1.000 | = |
| Precision@3 | 1.000 | 1.000 | = |
| Recall@3 | 0.944 | 0.944 | = |
| MRR | 1.000 | 1.000 | = |
| Retrieval latency | 580ms | 423ms | **−27%** |
| faithfulness | 0.886 | 0.857 | −3% |
| answer_relevancy | 0.648 | 0.618 | −5% |
| context_precision | 0.986 | 0.924 | −6% |
| context_recall | 0.942 | 0.917 | −3% |

- **결론**: **OpenAI 기본 유지 + BGE-M3 토글 확보** (ADR-016). Retrieval 지표 동률 + Answer 소폭 하락. 전환 이득 없음. 한국어 중심 dataset이 새로 들어오면 재평가.

---

## 평가 방법

- **Retrieval 평가**: 정답 문서가 top-K에 포함되는지 (`expected_doc_ids`로 수동 라벨)
- **Generation 평가**: Ragas (faithfulness, answer_relevancy, context_precision/recall) + LLM-as-judge(gpt-4o-mini)
- **E2E 평가**: LangSmith 트레이스 + 두 스크립트의 aggregate 지표

---

## 알려진 취약점

- **Judge 편향**: judge LLM이 답변 생성 LLM과 동일 모델(gpt-4o-mini)이라 자기평가 편향 가능. 중요 의사결정 시에는 judge를 gpt-4o 또는 다른 모델로 교체 권장
- **Dataset 과적합 위험**: 12개 질의가 튜닝·평가 공용. 추가 hold-out 세트 필요
- **Reference 부재**: `context_recall`은 현재 self-reference로 계산되어 실질 값 해석 주의
- **Ragas judge 비용**: 한 번 실행에 100~150 API call, 약 $0.05~0.1 소모 (질의·지표 수에 비례)
