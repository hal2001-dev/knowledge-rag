---
name: ISSUE-008 스코프 전환 시 이전 스코프 URL 잔류 — 헤더 칩과 본문 불일치
description: 책/카테고리/시리즈 한 스코프를 활성화한 상태에서 다른 스코프를 클릭하면 새 스코프만 set되고 기존 스코프 URL state가 잔류. ScopeBanner 우선순위로 본문은 정상이지만 UI 표시(헤더 칩 활성색, URL 길이)가 일관성 깨짐.
type: issue
---

# ISSUE-008: 스코프 전환 시 이전 스코프 URL state 잔류

**상태**: open · **합의됨, 코드 수정 보류** (사용자 지시: 일단 문서만 등록)
**발생일**: 2026-04-28
**해결일**: -
**관련 기능**: [decisions.md](../../architecture/decisions.md) ADR-029(활성 스코프 우선순위 doc > category > series, 한 번에 하나)
**관련 코드**:
- [web/components/header-categories.tsx](../../../../web/components/header-categories.tsx) `setScope` (L25): `setCategory`만, doc_filter/series_filter 잔류
- [web/components/library/doc-card.tsx](../../../../web/components/library/doc-card.tsx) `askThisDoc` (L29): `/chat?doc_filter=` push, 기존 category 잔류 가능
- [web/components/library/series-card.tsx](../../../../web/components/library/series-card.tsx) `askThisSeries`/`askThisMember` (L38): 다른 스코프 청소 0
- [web/components/chat/empty-state.tsx](../../../../web/components/chat/empty-state.tsx) (L151): 최근 문서 카드/카테고리 칩 클릭 시 잔류

**관련 이슈**: ISSUE-006(ScopedEmptyState), ISSUE-007(suggested_questions 정합) — 같은 세션에서 발견

---

## 증상

한 스코프를 활성화한 채 다른 스코프 진입점을 클릭하면 URL에 두 스코프가 동시에 잔류.

| 진입 흐름 | 결과 URL | ScopeBanner 표시 | 헤더 카테고리 칩 | 본문(ScopedEmptyState) | 일관성 |
|---|---|---|---|---|---|
| 책 (`?doc_filter=X`) → 헤더 카테고리 Y 클릭 | `?doc_filter=X&category=Y` | 📖 X (doc 우선) | Y 활성색 | 책 X 화면 | **❌** |
| 카테고리 (`?category=Y`) → 도서관 책 X 클릭 | `?doc_filter=X&category=Y` | 📖 X | Y 활성색 | 책 X 화면 | **❌** |
| 시리즈 (`?series_filter=S`) → 헤더 카테고리 Y | `?series_filter=S&category=Y` | 📚 S | Y 활성색 | 시리즈 화면 | **❌** |
| 카테고리 (`?category=Y`) → 도서관 시리즈 S | `?category=Y&series_filter=S` | 📂 Y (cat 우선) | Y 활성색 | 카테고리 화면 | (시리즈는 우선순위 후순위라 일부 일치) |

## 원인 분석

활성 스코프 정책(ADR-029): 우선순위 doc > category > series, **한 번에 하나만 활성**. retrieval과 ScopeBanner는 이 정책을 따름:

```ts
// web/app/chat/page.tsx:sendMessage
const effectiveCategory = docFilter ? null : category;
const effectiveSeries = (docFilter || effectiveCategory) ? null : seriesFilter;
```

그러나 **스코프 전환 진입점**이 새 스코프만 set하고 기존 스코프를 URL에서 지우지 않아 사용자에게 보이는 UI 표시(헤더 칩 활성색, URL 길이, 일부 컴포넌트 재계산)가 일관성을 잃음.

retrieval 자체는 우선순위 정렬로 정상이지만, 사용자 신뢰 저하 + URL 공유·북마크가 모호.

## 해결 방법 (합의됨, 코드 수정 보류)

**원칙**: 한 스코프를 새로 활성화할 때 다른 스코프는 모두 null로 강제. ScopeBanner의 `clearAll` 정책을 모든 진입점에 일관 적용.

수정 파일 4개 + 회귀 검증 — 산정 30~45분:

| 파일 | 변경 |
|---|---|
| `header-categories.tsx:setScope` | `setCategory` 외 `setDocFilter(null)` + `setSeriesFilter(null)` 추가 |
| `library/doc-card.tsx:askThisDoc` | `/chat?doc_filter=...`로 push할 때 명시적으로 다른 스코프 제외(URL 재구성) |
| `library/series-card.tsx:askThisSeries`/`askThisMember` | 동일 |
| `chat/empty-state.tsx` | 카테고리 칩(L84)·최근 문서 카드(L151) 클릭 시 동일 |

## 회귀 전략

- ScopeBanner의 단일 dismiss(`setCategory(null)`만) 동작은 유지 — 사용자가 한 스코프만 끄고 싶을 때
- 정책 변경 후 Playwright Phase 1 ui-flow에 "스코프 전환 시 URL 정리" 케이스 추가

## 재발 방지

- 신규 스코프 도입 시 진입점 모두 `clearAll`형 정책을 따르도록 정책을 [common.md](../../troubleshooting/common.md) 또는 ADR-029에 명시 (해결 시점)
- 가능하면 헬퍼 함수 도입: `setExclusiveScope(scope: 'doc'|'category'|'series', value: string|null)` — 한 줄로 다른 스코프 null 처리
