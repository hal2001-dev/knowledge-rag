---
name: ISSUE-006 EmptyState가 활성 스코프 무시 — 책/카테고리/시리즈 선택해도 인덱스 전체 화면 고정
description: 도서관에서 [이 책에 묻기] 등을 눌러 채팅에 진입해도 EmptyState가 인덱스 전체의 예시 질문·카드를 그대로 표시. 활성 doc_filter/category/series_filter를 인지하지 못함.
type: issue
---

# ISSUE-006: EmptyState가 활성 스코프(doc_filter/category/series_filter) 인지 0

**상태**: open · **WIP** (코드는 ScopedEmptyState로 교체 완료, 사용자 검증 전)
**발생일**: 2026-04-28
**해결일**: -
**관련 기능**: [features/admin_ui.md](../../features/admin_ui.md)(UI 정책), [decisions.md](../../architecture/decisions.md) ADR-027(랜딩 카드 v2), ADR-029(시리즈 1급 시민)
**관련 코드**: [web/components/chat/empty-state.tsx](../../../../web/components/chat/empty-state.tsx)(인덱스 전체 화면), [web/components/chat/scoped-empty-state.tsx](../../../../web/components/chat/scoped-empty-state.tsx)(신설 분기), [web/app/chat/page.tsx](../../../../web/app/chat/page.tsx)(교체)
**관련 이슈**: ISSUE-007(같이 해결), ISSUE-008(스코프 잔류 — 인접 결함, 코드 수정 보류)

---

## 증상

도서관 카드 [이 책에 묻기] 또는 시리즈 카드 [이 시리즈에 묻기] 클릭 → `/chat?doc_filter=...` 또는 `/chat?series_filter=...`로 진입. 그러나 빈 채팅 화면(EmptyState)이 그대로 인덱스 전체 메시지를 표시:

- 인덱스 전체 한 줄 요약 ("이 시스템이 아는 내용 …")
- 인덱스 전체에서 LLM이 뽑은 예시 질문 5개 (다른 책 토픽 섞여 있음)
- "최근 추가된 문서" 카드 6장 (다른 책 6권)

사용자가 본 케이스: "파이썬 데이터 사이언스 핸드북" 카드를 클릭한 적이 없는데도 빈 채팅에 그 책 카드가 보였고, 옆에 "3D 게임 프로그래밍에서 중요한 기술은 무엇인가요?" 예시 질문이 떠 있어 두 영역을 혼동.

추가로 "이 책에 묻기"로 진입했을 때 — ScopeBanner는 "📖 문서 한정"으로 정상 표시되지만 그 아래 EmptyState는 모든 책의 질문·카드를 노출해 사용자가 "선택한 책과 화면이 무관"하다고 보고.

## 원인 분석

`web/components/chat/empty-state.tsx`가 `useIndexOverview()` 훅 단일 의존. URL state(doc_filter/category/series_filter) 인지 0. 어떤 진입 경로에서도 같은 인덱스 전체 화면이 렌더됨.

활성 스코프는 ScopeBanner(상단 sticky)와 sendMessage 페이로드에만 반영되고, 빈 채팅 본문은 무관하게 동작 → "ScopeBanner는 책 표시인데 본문은 인덱스 전체"라는 분리된 상태.

## 해결 방법

`web/components/chat/scoped-empty-state.tsx` 신설 — URL state를 직접 읽어 4분기:

| 활성 스코프 | 노출 |
|---|---|
| `doc_filter` 활성 | 그 책의 title + one_liner + abstract + topics + **그 책의 sample_questions만** (인덱스 전체 영역 모두 숨김) |
| `category_filter` 활성 | 그 카테고리 안 책별 sample_question 1개씩, 최대 6개 (책 title hint 동반) |
| `series_filter` 활성 | 시리즈 멤버 카드(volume_number 순) + **첫 권 sample_questions** |
| 그 외 | 기존 EmptyState 그대로 (인덱스 전체) |

`app/chat/page.tsx`에서 EmptyState → ScopedEmptyState로 교체.

**추가 백엔드 0** — 기존 GET /documents 응답에 `summary.sample_questions`가 이미 포함되고, GET /series/{id}/members 응답에도 멤버의 summary가 담겨 있어 새 엔드포인트 불필요.

## 회귀 방지 / 검증

- `pnpm exec tsc --noEmit` 0 에러
- `pnpm exec eslint` 0 경고
- 라우트 hot-reload smoke (HTTP 200): `/chat`, `/chat?doc_filter=...`, `/chat?series_filter=...`
- 우선순위 doc > category > series 정렬 — ScopedEmptyState가 ScopeBanner와 동일 정책 사용 (ADR-029 정합)

## 재발 방지

- 사용자 UI에서 활성 스코프 정책은 한 번만 정의하고 모든 컴포넌트(ScopeBanner / ScopedEmptyState / sendMessage)가 같은 우선순위(doc > category > series)를 따른다는 정책을 [ADR-029](../../architecture/decisions.md)에 명시 (이미 명시됨)
- 추후 신규 스코프 도입 시 ScopedEmptyState에도 분기 추가 필요 — `troubleshooting/common.md`에 체크리스트 항목 추가 후속
