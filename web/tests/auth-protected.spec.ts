import { test, expect } from "@playwright/test";

/**
 * Phase 2 — AUTH_ENABLED=true 모드 회귀 검증.
 *
 * 실행 방법:
 *   AUTH_ENABLED=true pnpm exec playwright test auth-protected
 *
 * 기본 실행 (AUTH_ENABLED=false)에서는 자동 skip.
 * Clerk 보호 라우트 + 공개 sign-in 페이지 검증.
 * 인증된 흐름은 @clerk/testing 도입 후 별건.
 */

test.describe("Phase 2 — Clerk 보호 라우트", () => {
  test.skip(
    process.env.AUTH_ENABLED !== "true",
    "AUTH_ENABLED=true 환경에서만 실행 (Phase 2 회귀)",
  );

  test("sign-in 페이지 — Clerk SignIn 컴포넌트 렌더", async ({ page }) => {
    await page.goto("/sign-in");
    await expect(page).toHaveURL(/\/sign-in/);
    await expect(
      page
        .getByRole("heading")
        .or(
          page.locator("input[type='email']").or(page.locator("input[name='identifier']")),
        )
        .first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("/ — 비로그인 상태에서 sign-in 으로 리다이렉트", async ({ page }) => {
    const resp = await page.goto("/");
    await expect(page).toHaveURL(/\/sign-in/);
    expect(resp?.status()).toBeLessThan(400);
  });

  test("/chat — 비로그인 상태에서 sign-in 으로 리다이렉트", async ({ page }) => {
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/sign-in/);
  });

  test("/library — 비로그인 상태에서 sign-in 으로 리다이렉트", async ({ page }) => {
    await page.goto("/library");
    await expect(page).toHaveURL(/\/sign-in/);
  });
});
