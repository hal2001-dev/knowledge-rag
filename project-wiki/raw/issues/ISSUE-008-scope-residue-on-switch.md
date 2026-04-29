# ISSUE-008 raw — 스코프 전환 시 이전 스코프 URL 잔류

**보고 일자**: 2026-04-28
**보고자**: 사용자 (1인 운영자)

---

## 사건 (ISSUE-006/007과 같은 세션)

사용자 보고 — "책을 선택 하고 상위 카테고리를 변경 하면 뭐가 안맞지 않나?"

추적 결과 — 헤더 카테고리 칩, 도서관 책/시리즈 카드, EmptyState 최근 문서 카드 등 **스코프 전환 진입점이 모두 새 스코프만 set하고 기존 스코프는 URL에 잔류**시키는 패턴이 일관되게 발견됨.

## 의사결정 기록

- 2026-04-28 사용자: "일단 문서만 업데이트 해줘" → 코드 수정 보류, 별건 후속
- ISSUE-006/007과 인접 결함이지만 별도 이슈로 분리 (수정 범위가 4개 파일에 걸쳐 있고, ISSUE-006은 ScopedEmptyState로 표면적 동작이 정상화돼 운영상 충돌 작음)

## 첨부 — 검토한 4 파일

```
web/components/header-categories.tsx:25  setScope — setCategory만, doc_filter/series_filter 잔류
web/components/library/doc-card.tsx:29   askThisDoc — /chat?doc_filter= push, category 잔류 가능
web/components/library/series-card.tsx:38 askThisSeries/askThisMember — 다른 스코프 청소 0
web/components/chat/empty-state.tsx:151  최근 문서/카테고리 칩 클릭 — category/doc_filter 잔류
```

## 시나리오 표

| 진입 | 결과 URL | ScopeBanner | 헤더 칩 | 본문 | 정합 |
|---|---|---|---|---|---|
| 책 (`?doc_filter=X`) → 헤더 카테고리 Y 클릭 | `?doc_filter=X&category=Y` | 📖 X (doc 우선) | Y 활성색 | 책 X 화면 | **불일치** |
| 카테고리 (`?category=Y`) → 도서관 책 X 클릭 | `?doc_filter=X&category=Y` | 📖 X | Y 활성색 | 책 X 화면 | **불일치** |
| 시리즈 (`?series_filter=S`) → 헤더 카테고리 Y | `?series_filter=S&category=Y` | 📚 S | Y 활성색 | 시리즈 화면 | **불일치** |

## 정책 결정 필요

`ScopeBanner.clearAll`만 일관(모든 스코프 null) — 다른 진입점도 동일 정책 따르도록.
