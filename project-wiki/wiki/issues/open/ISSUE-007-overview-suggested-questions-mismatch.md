---
name: ISSUE-007 /index/overview의 suggested_questions가 답변 가능 책 분포와 불일치
description: 인덱스 전체에서 LLM이 "골고루" 뽑은 예시 질문 5개가 retrieval로 답하기 어려운 토픽을 포함. 클릭 시 sources hit하지만 LLM "정보 없음" 류 답변.
type: issue
---

# ISSUE-007: /index/overview suggested_questions ↔ retrieval 정합 불일치

**상태**: open · **합의됨, 코드 수정 보류** (사용자 지시: 일단 문서만 등록)
**발생일**: 2026-04-28
**해결일**: -
**관련 기능**: [decisions.md](../../architecture/decisions.md) ADR-020(인덱스 커버리지 카드), ADR-027(랜딩 카드 v2)
**관련 코드**: [apps/routers/documents.py](../../../../apps/routers/documents.py) `_index_overview`, [web/components/chat/empty-state.tsx](../../../../web/components/chat/empty-state.tsx)
**관련 이슈**: ISSUE-006(EmptyState 스코프 인지 — 같이 해결), ISSUE-008(스코프 잔류)

---

## 증상

빈 채팅의 EmptyState에 떠 있는 "🎯 예시 질문 5개"를 클릭하면 sources는 hit하는 경우도 있으나 LLM이 "정보 없음" 류 응답을 반환하는 사례 발생.

대표 사례 (2026-04-28):
- 사용자가 본 5개 질문:
  1. 머신러닝을 혼자 공부하는 방법은 무엇인가요?
  2. 파이썬을 이용한 데이터 과학의 기본 개념은 무엇인가요?
  3. 클라우드 네이티브 자바의 장점은 무엇인가요?
  4. 인공생명에 대한 최신 연구 동향은 어떤 것이 있나요?
  5. 3D 게임 프로그래밍에서 중요한 기술은 무엇인가요?
- 5번 클릭 → sources 3건 hit (점수 OK)이었으나 LLM이 "관련 정보 없음" 응답
- 해당 책(게임 프로그래밍)이 retrieval 상위로 충분히 올라오지 않음

## 원인 분석

`/index/overview` (apps/routers/documents.py:_index_overview, ADR-020/ADR-027)은 인덱스 전체 메타(titles + top_headings + categories)를 gpt-4o-mini에 한 번 입력해 "예시 질문 5개"를 생성한다. 결과는 5분 캐시.

LLM은 "있을 법한 질문"을 상상해 만들지만:
- retrieval은 그 질문에 답할 청크를 책 본문에서 찾아야 함
- LLM이 빚어낸 질문이 실제 책 본문과 의미적으로 정렬되지 않으면 dense+BM25+RRF 모두 낮은 점수
- BGE-reranker가 끌어올려도 "관련 없음" 임계 안에서 답변 불가

즉 **suggested_questions의 생성 메커니즘과 검색 메커니즘이 분리**되어 있다.

## 해결 방법 (합의됨, 코드 수정 보류)

**옵션 (a)** — 인덱스 전체 LLM 추론 → 책 5권 랜덤 선정 + 각 책의 `summary.sample_questions[0]`를 직접 채택. LLM 호출 0(이미 인덱싱 시점에 캐시됨). 클릭 시 자동으로 그 책의 `doc_filter`도 함께 적용해 retrieval 정합 100% 보장.

데이터 모델 변경 0 — `documents.summary` JSONB의 `sample_questions`가 이미 영속화되어 있음.

대안 후보 (선택 안 함):
- (b) retrieval 0건 또는 답변 품질 낮을 때 score_threshold 자동 완화 — 부작용(잡음 증가)
- (c) suggested_question 클릭 시 자동으로 답변 가능 책의 doc_filter 적용 — (a)에 자연스럽게 포함됨

## 회귀 전략

- 현 LLM 호출 분기를 토글로 남겨두고 (a) 적용 (`OVERVIEW_QUESTIONS_MODE=cached|llm`) → 즉시 회귀 가능

## 재발 방지

- **데이터 정합 원칙**: 사용자에게 노출하는 추천 액션은 retrieval이 실제로 답할 수 있는 데이터에 grounded되어야 함. LLM이 빚어낸 추측 없이 캐시된 사실(sample_questions)을 그대로 사용.
- ADR-027 본문에 "책 단위 sample_question 활용 방식"을 권장 패턴으로 추가 (해결 시점에 갱신)
