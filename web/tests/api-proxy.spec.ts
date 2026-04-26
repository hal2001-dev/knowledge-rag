import { test, expect } from "@playwright/test";

/**
 * /api/* same-origin 프록시 검증 — Clerk 보호 + Next dev rewrites 동작.
 *
 * 비인증 상태에서 /api/* 호출 시 Clerk middleware가 /sign-in 으로 리다이렉트.
 * 이 동작이 정상이면 프록시 + 인증 미들웨어가 결합되어 작동 중.
 */
test("/api/health 비인증 상태 → /sign-in 리다이렉트", async ({ request }) => {
  const resp = await request.get("/api/health", { maxRedirects: 0 });
  expect(resp.status()).toBe(307);
  expect(resp.headers()["location"]).toContain("/sign-in");
});
