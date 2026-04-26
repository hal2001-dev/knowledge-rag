/**
 * FastAPI 클라이언트 — openapi-fetch 위에 Clerk JWT 자동 첨부.
 *
 * 클라이언트 측 호출만 처리. 서버 컴포넌트는 Clerk `auth()`로 직접 토큰 발급 후 사용.
 *
 * 타입은 `types/api.ts` 가 OpenAPI 스키마로부터 자동 생성된 후 활성화.
 * 현재는 Phase 1 스키마(Knowledge RAG API)와 호환되는 임시 paths 형태.
 */
"use client";

import createClient from "openapi-fetch";
import { useAuth } from "@clerk/nextjs";
import { useMemo } from "react";

// TODO Phase 2 후속: openapi-typescript로 자동 생성된 paths 타입으로 교체
// import type { paths } from "@/types/api";
type paths = Record<string, never>;

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/**
 * 현재 사용자의 Clerk JWT를 자동 첨부하는 fetch 클라이언트 hook.
 *
 * 사용:
 *   const api = useApiClient();
 *   const { data, error } = await api.GET("/conversations");
 */
export function useApiClient() {
  const { getToken } = useAuth();

  return useMemo(() => {
    const client = createClient<paths>({ baseUrl: API_BASE_URL });

    client.use({
      async onRequest({ request }) {
        // Clerk가 발급한 short-lived JWT를 Authorization 헤더에 첨부.
        // FastAPI 측 AuthMiddleware가 이 헤더를 검증해 user_id를 주입.
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

export const apiBaseUrl = API_BASE_URL;
