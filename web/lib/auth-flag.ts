/**
 * 클라이언트·서버 양쪽에서 동일하게 읽는 Clerk 토글.
 * `false`(기본)면 ClerkProvider / UserButton / useAuth 호출을 모두 우회.
 */
export const AUTH_ENABLED =
  process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";
