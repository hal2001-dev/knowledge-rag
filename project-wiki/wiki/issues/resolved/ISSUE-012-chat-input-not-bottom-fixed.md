---
name: ISSUE-012 채팅 입력창이 하단에 고정되지 않음 — 스크롤 내려야 보임
description: 사용자가 채팅 페이지에 진입하거나 응답 토큰이 누적되면 입력창이 페이지 하단에 고정되지 않고 콘텐츠 끝으로 밀려나 스크롤해야 보였음. body의 min-h-full + html 무제약 overflow가 원인. h-full + overflow-hidden으로 뷰포트에 정확히 묶어 해결.
type: issue
---

# ISSUE-012: 채팅 입력창이 하단에 고정되지 않음

**상태**: resolved · 2026-04-30
**발생일**: 2026-04-30
**해결일**: 2026-04-30
**관련 기능**: NextJS 채팅 UI(ADR-030, TASK-024)
**관련 코드**:
- [web/app/layout.tsx](../../../../web/app/layout.tsx) — `<html>`/`<body>` height 정책

---

## 증상

채팅 페이지에서 ChatInput이 뷰포트 하단에 고정되지 않고 페이지 끝으로 밀려남. 사용자가 스크롤을 내려야 입력창이 보였음. TASK-024 스트리밍으로 답변 토큰이 누적되면서 더 두드러짐.

## 원인 분석

레이아웃 트리:
- `<html className="h-full">` — height: 100% (뷰포트)
- `<body className="min-h-full flex flex-col">` — **min-height: 100%** ← 콘텐츠가 길어지면 100% 너머로 자라남
- `<AppShell><div className="flex flex-1 min-h-0 flex-col">` — 부모 높이를 기준으로 flex 분배

`min-h-full`은 "최소 100%"라 콘텐츠가 많으면 body가 뷰포트보다 커짐 → 내부 `flex-1 min-h-0 overflow-y-auto`(메시지 영역)와 ChatInput이 묶일 기준 높이가 사라져 ChatInput이 페이지 끝(스크롤 후)에 위치. 추가로 `<html>`에 overflow 제한이 없어 페이지 자체가 스크롤 가능 상태였음.

## 해결 방법

`web/app/layout.tsx`:
- `<html>`: `h-full` → `h-full overflow-hidden`
- `<body>`: `min-h-full flex flex-col` → `h-full flex flex-col overflow-hidden`

이제 뷰포트가 정확히 100vh에 묶이고, AppShell의 flex 체인이 ChatInput을 항상 하단에 고정. 메시지 영역만 자체 overflow-y-auto로 스크롤.

## 검증

Playwright 측정:
- viewport h: 795px
- 메시지 영역(`flex-1 overflow-y-auto`): 677px (자체 스크롤)
- ChatInput: 65px (top: 743 / bottom: 783, 항상 뷰포트 하단)
- documentScrollable: false

## 재발 방지

NextJS 16 + Tailwind 환경에서 풀 페이지 레이아웃 패턴은 `html.h-full` + `body.h-full + overflow-hidden`이 표준. 새 페이지 추가 시 이 정책 따르면 됨.

**관련**: TASK-024(스트리밍 SSE) — 토큰 누적 시 더 두드러져서 발견 계기
