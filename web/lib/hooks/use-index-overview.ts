"use client";

import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "@/lib/api/client";
import { keys } from "@/lib/api/keys";

/** 채팅 빈 화면 랜딩 카드 + 상단 카테고리 칩 데이터 원천. 백엔드가 5분 캐시. */
export function useIndexOverview() {
  const api = useApiClient();
  return useQuery({
    queryKey: keys.indexOverview,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const { data, error } = await api.GET("/index/overview");
      if (error) throw error;
      return data;
    },
  });
}
