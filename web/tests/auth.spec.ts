import { test, expect } from "@playwright/test";

/**
 * Clerk 보호 라우트 + 공개 sign-in 페이지 검증.
 * 인증된 흐름은 @clerk/testing 도입 후 별건.
 */

test("sign-in 페이지 — Clerk SignIn 컴포넌트 렌더", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page).toHaveURL(/\/sign-in/);
  // Clerk SignIn 컴포넌트가 hydrate되면 어떤 form/입력 요소가 나타남
  await expect(
    page.getByRole("heading").or(page.locator("input[type='email']").or(page.locator("input[name='identifier']"))).first(),
  ).toBeVisible({ timeout: 15_000 });
});

test("/ — 비로그인 상태에서 sign-in 으로 리다이렉트", async ({ page }) => {
  const resp = await page.goto("/");
  // 결과 URL이 /sign-in 으로 시작해야 함 (Clerk 보호)
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
