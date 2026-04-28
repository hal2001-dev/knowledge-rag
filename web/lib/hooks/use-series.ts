"use client";

import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "@/lib/api/client";
import { keys } from "@/lib/api/keys";

/** 전체 시리즈 목록 + 멤버 수 (TASK-020). 도서관 시리즈 카드 그룹화용. */
export function useSeriesList() {
  const api = useApiClient();
  return useQuery({
    queryKey: keys.series.list(),
    queryFn: async () => {
      const { data, error } = await api.GET("/series");
      if (error) throw error;
      return data;
    },
  });
}

/** 단일 시리즈 멤버 목록 — 시리즈 상세 펼치기·"이 시리즈에 묻기"용. */
export function useSeriesMembers(seriesId: string | null) {
  const api = useApiClient();
  return useQuery({
    queryKey: seriesId ? keys.series.members(seriesId) : keys.series.all,
    enabled: !!seriesId,
    queryFn: async () => {
      const { data, error } = await api.GET("/series/{series_id}/members", {
        params: { path: { series_id: seriesId! } },
      });
      if (error) throw error;
      return data;
    },
  });
}
