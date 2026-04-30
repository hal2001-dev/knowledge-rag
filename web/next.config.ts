import type { NextConfig } from "next";

/**
 * FastAPI 호출을 same-origin으로 프록시 (브라우저는 어떤 origin이든 `/api/*` 사용 → Next dev가 백엔드로 전달).
 * 결과: 브라우저는 항상 같은 origin으로 fetch — CORS preflight 0, env-specific IP 노출 0.
 *
 * 클라이언트 측 base URL은 `.env.local`의 `NEXT_PUBLIC_API_BASE_URL=/api` 와 짝.
 * 백엔드가 어디 있든(localhost / Docker / 원격) 환경변수 `INTERNAL_API_URL`만 갈아치우면 됨.
 */
const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  // Turbopack workspace root을 web/으로 명시 — 프로젝트 루트의 pnpm-lock.yaml(Playwright용)이
  // 자동 추론을 흐리는 것을 방지. import.meta.dirname은 Node 20.11+ ESM에서 안전
  turbopack: {
    root: import.meta.dirname,
  },
  // Next 16: dev 서버 외부 origin 차단 — Tailscale·LAN IP에서 접속 시 허용
  // (localhost·127.0.0.1은 기본 허용)
  allowedDevOrigins: [
    "192.168.0.72",   // LAN
    "100.78.13.90",   // Tailscale (사용자 환경에서 접속 중인 IP)
    "macstudio",      // mDNS hostname
  ],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${INTERNAL_API_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
