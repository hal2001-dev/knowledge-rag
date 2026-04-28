import { test, expect } from "@playwright/test";

/**
 * /api/* same-origin 프록시 검증 — Phase 2 (AUTH_ENABLED=true) 모드.
 *
 * 실행 방법:
 *   AUTH_ENABLED=true pnpm exec playwright test api-proxy
 *
 * 비인증 상태에서 /api/* 호출 시 Clerk middleware가 /sign-in 으로 리다이렉트(307).
 * Phase 1(AUTH_ENABLED=false)에서는 라우트 무방호라 다른 동작이라 skip.
 */
test.describe("Phase 2 — /api 프록시 + Clerk 게이트", () => {
  test.skip(
    process.env.AUTH_ENABLED !== "true",
    "AUTH_ENABLED=true 환경에서만 실행 (Phase 2 회귀)",
  );

  test("/api/health 비인증 상태 → /sign-in 리다이렉트", async ({ request }) => {
    const resp = await request.get("/api/health", { maxRedirects: 0 });
    expect(resp.status()).toBe(307);
    expect(resp.headers()["location"]).toContain("/sign-in");
  });
});
