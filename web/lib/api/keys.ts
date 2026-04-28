/**
 * TanStack Query key factory. 모든 query key는 여기서 단일 정의.
 * 무효화·prefetch·낙관적 업데이트 시 `queryClient.invalidateQueries({ queryKey: keys.documents.all })` 식으로 사용.
 */
export const keys = {
  documents: {
    all: ["documents"] as const,
    list: () => [...keys.documents.all, "list"] as const,
    detail: (docId: string) => [...keys.documents.all, "detail", docId] as const,
    chunks: (docId: string) => [...keys.documents.all, "chunks", docId] as const,
  },
  conversations: {
    all: ["conversations"] as const,
    list: () => [...keys.conversations.all, "list"] as const,
    detail: (sessionId: string) => [...keys.conversations.all, "detail", sessionId] as const,
  },
  // TASK-020 (ADR-029)
  series: {
    all: ["series"] as const,
    list: () => [...keys.series.all, "list"] as const,
    detail: (seriesId: string) => [...keys.series.all, "detail", seriesId] as const,
    members: (seriesId: string) => [...keys.series.all, "members", seriesId] as const,
  },
  indexOverview: ["index-overview"] as const,
};
