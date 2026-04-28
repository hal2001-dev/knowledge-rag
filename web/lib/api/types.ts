/**
 * 자주 쓰는 응답 타입 별칭 — `types/api.ts`(자동 생성)에서 추출.
 * 페이지·hook 코드에서 `import type {Document, Conversation, ...}` 식으로 간결하게 사용.
 */
import type { components } from "@/types/api";

type S = components["schemas"];

export type DocumentItem = S["DocumentItem"];
export type RecentDocItem = S["RecentDocItem"];
export type IndexOverview = S["IndexOverviewResponse"];
export type ConversationSummary = S["ConversationSummary"];
export type ConversationDetail = S["ConversationDetail"];
export type MessageItem = S["MessageItem"];
export type ChunkPreview = S["ChunkPreview"];
export type SourceItem = S["SourceItem"];
export type QueryRequest = S["QueryRequest"];
export type QueryResponse = S["QueryResponse"];
// TASK-020 (ADR-029)
export type SeriesItem = S["SeriesItem"];
export type SeriesListResponse = S["SeriesListResponse"];
export type SeriesMembersResponse = S["SeriesMembersResponse"];
export type SeriesReviewItem = S["SeriesReviewItem"];

// summary와 categories(/index/overview)는 OpenAPI에 inline dict로 정의돼 unknown 키.
// UI에서 안전하게 다루기 위한 narrow types — backend SummaryDict 형태에 맞춤.
export type DocSummary = {
  one_liner?: string | null;
  abstract?: string | null;
  topics?: string[] | null;
  sample_questions?: string[] | null;
};

export type CategoryDistItem = {
  id: string | null;
  label?: string | null;
  count?: number;
};

/** doc.summary를 narrow type으로 안전 추출. null이면 null 반환. */
export function readSummary(d: DocumentItem): DocSummary | null {
  return (d.summary ?? null) as DocSummary | null;
}
