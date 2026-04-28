import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright 설정 — TASK-019 Phase B 회귀 검증.
 *
 * 두 운영 모드 분리 회귀 (ADR-030):
 *
 * Phase 1 (AUTH_ENABLED=false, 기본):
 *   pnpm exec playwright test ui-flow
 *   → 사용자 UI 흐름 (페이지 로드·URL state·모바일 drawer). 무방호 라우트.
 *   → auth-protected.spec.ts / api-proxy.spec.ts는 자동 skip.
 *
 * Phase 2 (AUTH_ENABLED=true, 미들웨어 보호):
 *   AUTH_ENABLED=true pnpm exec playwright test auth-protected
 *   → Clerk 비로그인 상태 /sign-in 리다이렉트(307) 검증.
 *   → ui-flow.spec.ts는 자동 skip.
 *
 * 인증된 흐름(로그인 후 페이지 동작) 회귀는 `@clerk/testing` 도입 후 별건.
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
