"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "@/lib/api/client";
import { keys } from "@/lib/api/keys";
import type { QueryRequest } from "@/lib/api/types";

/** RAG 질의 mutation. 응답에 session_id가 포함되므로 호출자가 URL state 갱신. */
export function useRagQuery() {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (req: QueryRequest) => {
      const { data, error } = await api.POST("/query", { body: req });
      if (error) throw error;
      return data;
    },
    onSuccess: (data) => {
      // 세션이 새로 만들어졌거나 기존 세션에 메시지가 추가됐으니 무효화
      qc.invalidateQueries({ queryKey: keys.conversations.all });
      if (data?.session_id) {
        qc.invalidateQueries({ queryKey: keys.conversations.detail(data.session_id) });
      }
    },
  });
}
