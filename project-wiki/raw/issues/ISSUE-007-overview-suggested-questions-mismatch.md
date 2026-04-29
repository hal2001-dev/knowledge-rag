# ISSUE-007 raw — /index/overview suggested_questions가 답변 가능 책과 불일치

**보고 일자**: 2026-04-28
**보고자**: 사용자 (1인 운영자)

---

## 사건 (ISSUE-006과 같은 세션)

빈 채팅의 EmptyState에 떠 있던 "🎯 예시 질문 5개" 중 "3D 게임 프로그래밍에서 중요한 기술은 무엇인가요?"를 클릭. 검색 sources는 hit했지만 LLM이 "관련 정보 없음" 류 답변을 반환.

질문 생성 메커니즘 추적:
- `/index/overview`가 인덱스 전체(107권)의 titles + top_headings + categories를 LLM(gpt-4o-mini)에 한 번 입력해 "예시 질문 5개" 생성
- 생성된 질문은 인덱스 전체에서 "골고루" 뽑힌 것이라 책 토픽 분포에 의존
- 클릭 시 sendMessage는 doc_filter 없이 인덱스 전체 검색 — 게임 책이 retrieval 상위로 안 올라오면 답변 품질 저하

핵심: **suggested_questions를 만드는 LLM 추론 결과와 실제 retrieval이 답할 수 있는 청크 분포가 어긋남**. LLM은 "있을 법한 질문"을 상상해 만들지만 retrieval은 그 질문에 답할 청크를 책 본문에서 찾아야 함.

## 의사결정 기록

- 2026-04-28 사용자: ISSUE-006과 함께 등록 합의
- 수정안 (a) 채택 합의: LLM 추론 → **책 5권 무작위 선정 + 각 책의 sample_question 1개씩** 직접 사용 (LLM 호출 0, 캐시된 책별 sample 그대로 활용 → 클릭 시 doc_filter도 자동 적용해 retrieval 정합 100%)
- 산정 1.5시간

## 첨부 데이터

`/index/overview`의 suggested_questions (gpt-4o-mini, 1회 호출, 5분 캐시):
```
- 머신러닝을 혼자 공부하는 방법은 무엇인가요?
- 파이썬을 이용한 데이터 과학의 기본 개념은 무엇인가요?
- 클라우드 네이티브 자바의 장점은 무엇인가요?
- 인공생명에 대한 최신 연구 동향은 어떤 것이 있나요?
- 3D 게임 프로그래밍에서 중요한 기술은 무엇인가요?  ← 사용자 클릭, 답변 부정적
```

107권의 책별 `summary.sample_questions`는 인덱싱 시점 LLM 호출로 캐시되어 있음 — 데이터 가용. (a) 안은 이 캐시를 직접 활용.
