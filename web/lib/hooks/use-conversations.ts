"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "@/lib/api/client";
import { keys } from "@/lib/api/keys";

/** 자기 user_id 세션 목록 (Clerk JWT 자동 첨부, 백엔드가 owner 필터). */
export function useConversations() {
  const api = useApiClient();
  return useQuery({
    queryKey: keys.conversations.list(),
    queryFn: async () => {
      const { data, error } = await api.GET("/conversations");
      if (error) throw error;
      return data;
    },
  });
}

/** 단일 세션 상세 (메시지 포함). */
export function useConversation(sessionId: string | null) {
  const api = useApiClient();
  return useQuery({
    queryKey: sessionId ? keys.conversations.detail(sessionId) : keys.conversations.all,
    enabled: !!sessionId,
    queryFn: async () => {
      const { data, error } = await api.GET("/conversations/{session_id}", {
        params: { path: { session_id: sessionId! } },
      });
      if (error) throw error;
      return data;
    },
  });
}

/** 세션 삭제 + 목록 무효화. */
export function useDeleteConversation() {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const { data, error } = await api.DELETE("/conversations/{session_id}", {
        params: { path: { session_id: sessionId } },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.conversations.all });
    },
  });
}
