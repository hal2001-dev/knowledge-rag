---
name: ISSUE-011 채팅 사용자 메시지가 응답 도착 전까지 화면에 안 뜸 — 옵티미스틱 렌더 누락
description: 채팅에서 질문을 보내도 사용자 말풍선이 즉시 보이지 않고, 3~5초 후 응답이 도착하면 사용자 메시지와 어시스턴트 메시지가 동시에 화면에 뜸. conversation refetch 후에만 메시지가 렌더되는 구조여서 발생. pendingUserMessage 옵티미스틱 상태 추가로 해결.
type: issue
---

# ISSUE-011: 채팅 사용자 메시지가 응답 도착 전까지 화면에 안 뜸

**상태**: resolved · 2026-04-30
**발생일**: 2026-04-30
**해결일**: 2026-04-30
**관련 기능**: NextJS 사용자 UI(ADR-030)
**관련 코드**:
- [web/app/chat/page.tsx](../../../../web/app/chat/page.tsx) `sendMessage` / `messages` useMemo
- [web/lib/hooks/use-rag-query.ts](../../../../web/lib/hooks/use-rag-query.ts) `useRagQuery` mutation

---

## 증상

채팅에서 사용자가 질문을 입력하고 Enter를 눌러도, 사용자 말풍선이 즉시 화면에 뜨지 않음. 3~5초 후 응답이 도착하는 시점에 사용자 메시지와 어시스턴트 메시지가 **동시에** 한꺼번에 출현. 그 사이엔 "검색 및 답변 생성 중…" 인디케이터만 단독으로 떠 있어, 사용자가 자기 질문이 전송됐는지 직접 확인할 수 없는 UX 마찰.

## 원인 분석

`useRagQuery` mutation 호출 + `onSuccess`에서 `qc.invalidateQueries(...)`로 conversation 캐시 무효화 → conversation refetch → baseMessages 갱신 → 사용자/어시스턴트 메시지가 함께 렌더되는 구조. 옵티미스틱 사용자 메시지가 별도로 존재하지 않아서 mutation pending 동안 화면에 사용자 입력 흔적이 사라짐.

## 해결 방법

`web/app/chat/page.tsx`에 `pendingUserMessage: string | null` 상태 추가:

1. `sendMessage(text)` 시작 시 `setPendingUserMessage(text)`
2. `messages` useMemo에서 baseMessages 끝에 옵티미스틱 user 버블을 append (`lastBaseUser !== pendingUserMessage`인 경우만 — 중복 회피)
3. conversation refetch 후 `lastBaseUser === pendingUserMessage`가 되면 useEffect가 자동으로 `setPendingUserMessage(null)` (self-healing)
4. `sessionId` 변경(새 대화 등) 시 동기 리셋

React rules-of-hooks 안전: pendingUserMessage 상태는 항상 같은 hook 순서로 호출됨. 자동 클리어로 중복 렌더 0.

## 검증

Playwright `http://macstudio:3000/chat` — `테스트 질문 — 옵티미스틱 UI 검증` 입력 후 사용자 말풍선이 즉시 출현, 응답 도착 시 어시스턴트 답변이 그 아래에 추가되는 흐름 확인. type-check clean.

## 재발 방지

같은 패턴이 적용될 후속 작업 — TASK-024(스트리밍 SSE)에서 사용자 메시지 즉시 렌더 + 토큰 누적 렌더로 자연스럽게 통합 예정. 옵티미스틱 user 버블 코드는 그대로 유지(스트리밍 모드에서도 동일하게 필요).

**관련**: ADR-030(사용자 UI NextJS), TASK-024(스트리밍 SSE) — UX 개선 묶음
