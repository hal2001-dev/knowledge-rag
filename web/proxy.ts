/**
 * Next.js 16 `proxy.ts` (formerly `middleware.ts`).
 * Clerk 인증을 모든 라우트에 강제. 공개 라우트(/sign-in, /sign-up)만 면제.
 */
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
]);

export const proxy = clerkMiddleware(async (auth, req) => {
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
