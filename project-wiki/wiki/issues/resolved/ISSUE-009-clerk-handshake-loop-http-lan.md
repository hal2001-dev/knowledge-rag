---
name: ISSUE-009 Clerk dev handshake 무한 루프 — HTTP LAN host 접속 시 도서관·채팅 화면 0건
description: NextJS 사용자 UI를 http://macstudio:3000 같은 LAN hostname으로 접속하면 Clerk dev instance의 handshake 응답 쿠키가 Secure 플래그를 달고 와서 HTTP 컨텍스트에서 저장되지 않음 → handshake 무한 루프 → React Query가 fetch를 시작 못해 도서관 화면이 비어 보임. NEXT_PUBLIC_AUTH_ENABLED=false로 ClerkProvider/UserButton/useAuth 호출 자체를 우회해 해결.
type: issue
---

# ISSUE-009: Clerk dev handshake 무한 루프 — HTTP LAN host 접속 시 도서관 0건

**상태**: resolved (workaround) · Phase 1 NEXT_PUBLIC_AUTH_ENABLED=false 토글로 우회. Phase 2(인증 활성) 시 HTTPS 또는 Clerk hosts 등록 필요.
**발생일**: 2026-04-30
**해결일**: 2026-04-30
**관련 기능**: [decisions.md](../../architecture/decisions.md) ADR-030(NextJS 분리 + Clerk 인증 + Phase 1/2 토글)
**관련 코드**:
- [web/.env.local](../../../../web/.env.local) — `NEXT_PUBLIC_AUTH_ENABLED=false` 추가
- [web/lib/auth-flag.ts](../../../../web/lib/auth-flag.ts) — 신규, 클라이언트·서버 단일 토글
- [web/lib/api/client.ts](../../../../web/lib/api/client.ts) — `useApiClientWithAuth`/`useApiClientNoAuth` 분기
- [web/app/layout.tsx](../../../../web/app/layout.tsx) — `<ClerkProvider>` 조건부 렌더
- [web/components/sidebar.tsx](../../../../web/components/sidebar.tsx) — `<UserButton>` 조건부 렌더
- [web/next.config.ts](../../../../web/next.config.ts) — `allowedDevOrigins`에 `macstudio` 추가

---

## 증상

`http://macstudio:3000/library` 접속 시:
- 도서관 화면 "총 0/0개 문서" — 카드/카테고리 칩 0
- 사이드바 "대화 목록" 영원히 "로딩…"
- DevTools Network: 같은 패턴이 무한 반복
  ```
  GET /library → 307
  GET clerk.accounts.dev/v1/client/handshake → 307
  GET /library?__clerk_handshake=... → 307
  GET /library → 307  (다시)
  ...
  ```
- `/api/documents`·`/api/series` 호출이 한 번도 발생하지 않음

서버 측은 정상: `curl http://macstudio:3000/api/documents` → 200 (107건)

## 원인 분석

Clerk dev instance가 핸드셰이크 응답에서 세션 쿠키를 다음 속성으로 내려보냄:
```
Set-Cookie: __clerk_db_jwt=...; Path=/; Secure; SameSite=None
```

브라우저 정책: **`Secure` 쿠키는 HTTPS 컨텍스트에서만 저장**. `localhost`는 예외 처리되지만 `macstudio` 같은 LAN hostname은 그렇지 않음.

→ HTTP로 접속한 macstudio host에서는 쿠키가 저장되지 않고, 다음 요청이 다시 미인증 상태로 들어가 핸드셰이크 무한 루프. ClerkProvider가 client-side에서 안정 상태(loaded)에 도달 못 하니 `useAuth()`도 settle 안 되고 React Query의 queryFn 실행 흐름이 막혀 fetch 자체가 발생 안 함.

`AUTH_ENABLED=false`(server) 토글은 `proxy.ts`(미들웨어)만 우회하고 **클라이언트 측 ClerkProvider 마운트는 막지 못함** — Phase 1 토글 설계의 사각.

## 해결 방법

`NEXT_PUBLIC_*` 환경변수로 클라이언트에서도 동일 토글을 읽도록 분리하고, `false`일 때 다음 3곳을 모두 우회:

1. **`<ClerkProvider>` 미렌더** (`app/layout.tsx`) — ClerkProvider 마운트 자체 차단으로 핸드셰이크 진입점 봉쇄
2. **`useAuth()` 미호출** (`lib/api/client.ts`) — 두 함수 정의 후 모듈 로드 시점에 `AUTH_ENABLED ? withAuth : noAuth`로 export 한 번만 결정. 같은 컴포넌트 인스턴스가 항상 같은 hook을 호출하므로 React rules-of-hooks 안전
3. **`<UserButton>` 미렌더** (`components/sidebar.tsx`) — Clerk context 없으면 throw하므로 조건부 렌더

부수: NextJS 16 dev 서버의 `allowedDevOrigins`에 `macstudio` 추가 — 안 추가해도 페이지 자체는 뜨지만 webpack HMR WS가 차단됨.

## 검증

Playwright로 `http://macstudio:3000/library` 재접속:
- console errors 0
- `/api/documents` → 200 (107건)
- `/api/series` → 200 (3건)
- `/api/conversations` → 200
- `/api/index/overview` → 200
- 도서관 그리드: 카테고리 칩 8개 + "총 107/107개 문서"

## 재발 방지

**Phase 2(인증 활성) 진입 조건** — ADR-030 후속 합의 필요:
1. **macstudio hostname을 HTTPS로 노출** — 자체서명 인증서 / Tailscale Funnel / Caddy reverse proxy 중 택1
2. **또는 Clerk dashboard에서 instance hosts에 `macstudio` 추가** — Clerk 측이 Secure 플래그를 host policy에 따라 조정해 주는지 검증 필요 (dev instance 한정 가능성)
3. **또는 HTTPS 진입만 허용**하고 HTTP 접속 차단 — 가장 단순하나 LAN dev UX 저하

후속 작업: Phase 2 결정 시 ADR-030 본문에 "Phase 2 prereq"로 위 옵션 검토 결과 추가.

**관련**: ADR-030(NextJS 분리 + Phase 1/2 토글), [troubleshooting/common.md](../../troubleshooting/common.md) 신설 항목
