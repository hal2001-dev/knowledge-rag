import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright 설정 — TASK-019 Phase B 회귀 검증.
 *
 * 인증 필요 라우트(/chat, /library)는 Clerk 세션이 필요한데,
 * 이 단계에서는 공개 라우트(`/sign-in`, `/sign-up`)와 Clerk middleware의
 * 보호 동작(307 → /sign-in)만 검증.
 *
 * 인증된 흐름 회귀는 후속 Phase에서 `@clerk/testing` 도입 후 별건.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    locale: "ko-KR",
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "pnpm dev",
        url: "http://localhost:3000/sign-in",
        timeout: 120_000,
        reuseExistingServer: true,
      },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      // 모바일 Safari/iOS WebKit 대신 chromium에서 mobile viewport 에뮬레이션
      // (webkit 브라우저 별도 다운로드 회피, 핵심은 viewport·반응형 레이아웃 검증).
      name: "chromium-mobile",
      use: {
        ...devices["Pixel 5"],
        // Pixel 5는 chromium 기반이라 별도 다운로드 불필요
      },
    },
  ],
});
