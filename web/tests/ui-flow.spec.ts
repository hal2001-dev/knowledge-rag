import { test, expect } from "@playwright/test";

/**
 * Phase 1 — AUTH_ENABLED=false 모드 사용자 흐름 회귀.
 *
 * 실행 방법 (기본):
 *   pnpm exec playwright test ui-flow
 *
 * AUTH_ENABLED=true(Phase 2) 환경에서는 자동 skip.
 * 백엔드(FastAPI 8000) 미가동 상태에서도 페이지 로드·라우팅 자체는 검증 가능.
 * API 호출 결과는 빈 상태(EmptyState fallback)로 렌더되어야 한다.
 */

test.describe("Phase 1 — 사용자 UI 흐름", () => {
  test.skip(
    process.env.AUTH_ENABLED === "true",
    "AUTH_ENABLED=false 환경에서만 실행 (Phase 1 무방호 모드 회귀)",
  );

  test("/chat — 페이지 정상 로드 + 입력창·앱 헤더 노출", async ({ page }) => {
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/chat/);
    // AppShell 헤더의 앱명
    await expect(page.getByText("Knowledge RAG").first()).toBeVisible();
    // 채팅 입력 placeholder
    await expect(
      page.getByPlaceholder(/문서에 대해 질문/i),
    ).toBeVisible();
    // 보내기 버튼 (aria-label)
    await expect(page.getByRole("button", { name: "보내기" })).toBeVisible();
  });

  test("/library — 페이지 정상 로드 + 검색·필터 바 노출", async ({ page }) => {
    await page.goto("/library");
    await expect(page).toHaveURL(/\/library/);
    // 검색 placeholder (filter-bar.tsx 기준)
    await expect(page.getByPlaceholder(/제목.*요약.*태그/i)).toBeVisible();
  });

  test("/library?q=test — URL state로 검색어 동기화", async ({ page }) => {
    await page.goto("/library?q=test");
    const searchInput = page.getByPlaceholder(/제목.*요약.*태그/i);
    await expect(searchInput).toHaveValue("test");
  });

  test("/ — 루트 진입 시 /chat으로 리다이렉트 (Phase 1 무방호)", async ({ page }) => {
    await page.goto("/");
    // app/page.tsx가 redirect("/chat") 하므로 최종 URL이 /chat
    await expect(page).toHaveURL(/\/chat/, { timeout: 10_000 });
  });
});

test.describe("Phase 1 — 모바일 viewport drawer", () => {
  test.skip(
    process.env.AUTH_ENABLED === "true",
    "AUTH_ENABLED=false 환경에서만 실행",
  );

  test("모바일에서 사이드바 열기 버튼 노출 + drawer 동작", async ({ page, isMobile }) => {
    test.skip(!isMobile, "모바일 viewport(chromium-mobile 프로젝트)에서만 실행");

    await page.goto("/chat");
    const menuBtn = page.getByRole("button", { name: "사이드바 열기" });
    await expect(menuBtn).toBeVisible();
    await menuBtn.click();
    // drawer 안에 새 대화 등 사이드바 내용이 보여야 함 (Sheet open)
    await expect(page.locator('[role="dialog"]').first()).toBeVisible({
      timeout: 5_000,
    });
  });
});
