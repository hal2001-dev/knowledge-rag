import { test, expect } from "@playwright/test";

/**
 * /api/* same-origin 프록시 검증 — Phase 2 (AUTH_ENABLED=true) 모드.
 *
 * 실행 방법:
 *   AUTH_ENABLED=true pnpm exec playwright test api-proxy
 *
 * proxy.ts(`isPublicRoute`) 의도:
 *   - 공개:   /sign-in, /sign-up, /api/health
 *   - 보호:   그 외 모든 /api/* (Clerk 비로그인 시 307 → /sign-in)
 *
 * Phase 1(AUTH_ENABLED=false)에서는 라우트 무방호라 다른 동작이라 skip.
 */
test.describe("Phase 2 — /api 프록시 + Clerk 게이트", () => {
  test.skip(
    process.env.AUTH_ENABLED !== "true",
    "AUTH_ENABLED=true 환경에서만 실행 (Phase 2 회귀)",
  );

  test("/api/conversations 비인증 상태 → /sign-in 리다이렉트 (보호 경로)", async ({
    request,
  }) => {
    const resp = await request.get("/api/conversations", { maxRedirects: 0 });
    expect(resp.status()).toBe(307);
    expect(resp.headers()["location"]).toContain("/sign-in");
  });
});
