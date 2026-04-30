/**
 * FastAPI 클라이언트 — openapi-fetch 위에 Clerk JWT 자동 첨부.
 *
 * 클라이언트 컴포넌트 전용. 서버 컴포넌트는 `auth()`로 토큰 직접 발급 후 fetch 사용.
 * paths 타입은 `pnpm gen:api`로 OpenAPI 스키마에서 자동 갱신.
 */
"use client";

import createClient from "openapi-fetch";
import { useAuth } from "@clerk/nextjs";
import { useMemo } from "react";
import type { paths } from "@/types/api";
import { AUTH_ENABLED } from "@/lib/auth-flag";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/**
 * Clerk 활성: 현재 사용자 JWT를 자동 첨부.
 * Clerk 비활성: 토큰 없이 same-origin 호출 (FastAPI 측이 LAN/localhost를 admin으로 자동 부여).
 *
 *   const api = useApiClient();
 *   const { data, error } = await api.GET("/conversations");
 */
function useApiClientWithAuth() {
  const { getToken } = useAuth();

  return useMemo(() => {
    const client = createClient<paths>({ baseUrl: API_BASE_URL });
    client.use({
      async onRequest({ request }) {
        const token = await getToken();
        if (token) {
          request.headers.set("Authorization", `Bearer ${token}`);
        }
        return request;
      },
    });
    return client;
  }, [getToken]);
}

function useApiClientNoAuth() {
  return useMemo(() => createClient<paths>({ baseUrl: API_BASE_URL }), []);
}

export const useApiClient: typeof useApiClientWithAuth =
  AUTH_ENABLED ? useApiClientWithAuth : useApiClientNoAuth;

export const apiBaseUrl = API_BASE_URL;
