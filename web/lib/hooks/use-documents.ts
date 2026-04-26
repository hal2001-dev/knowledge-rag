"use client";

import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "@/lib/api/client";
import { keys } from "@/lib/api/keys";

/** 인덱싱된 문서 목록 (도서관 카드 그리드). */
export function useDocuments() {
  const api = useApiClient();
  return useQuery({
    queryKey: keys.documents.list(),
    queryFn: async () => {
      const { data, error } = await api.GET("/documents");
      if (error) throw error;
      return data;
    },
  });
}
