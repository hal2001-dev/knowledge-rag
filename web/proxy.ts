/**
 * Next.js 16 `proxy.ts` (formerly `middleware.ts`).
 * Clerk 인증 게이트 — ADR-030 Phase 1/2 토글.
 *
 * Phase 1 (AUTH_ENABLED=false, 기본):
 *   - clerkMiddleware는 통과만 — Clerk 세션 컨텍스트는 ClerkProvider가 관리
 *   - 모든 라우트 무인증 접근 가능. FastAPI 측 미들웨어가 LAN/localhost 'admin' 자동 부여
 *
 * Phase 2 (AUTH_ENABLED=true):
 *   - 보호 라우트(/, /chat, /library) 비로그인 시 /sign-in 리다이렉트
 *   - /sign-in, /sign-up, /api/health 공개
 */
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health(.*)",
]);

export const proxy = clerkMiddleware(async (auth, req) => {
  // Phase 1: AUTH_ENABLED=false 시 인증 게이트 우회
  if (process.env.AUTH_ENABLED !== "true") return;

  if (!isPublicRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // 정적 파일·_next 내부 자산 제외
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // API/trpc는 항상 통과
    "/(api|trpc)(.*)",
  ],
};
