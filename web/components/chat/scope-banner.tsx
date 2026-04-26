"use client";

/**
 * 활성 스코프 배지 — 우선순위 doc > category. 한 번에 하나만 활성.
 * 채팅 페이지 상단에 sticky banner.
 */
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useQueryState, parseAsString } from "nuqs";
import { useRouter } from "next/navigation";
import { useDocuments } from "@/lib/hooks/use-documents";
import { useIndexOverview } from "@/lib/hooks/use-index-overview";
import { X } from "lucide-react";

export function ScopeBanner() {
  const [docFilter, setDocFilter] = useQueryState("doc_filter", parseAsString);
  const [category, setCategory] = useQueryState("category", parseAsString);
  const docsQuery = useDocuments();
  const overview = useIndexOverview();
  const router = useRouter();

  // 우선순위: doc > category
  const docs = docsQuery.data?.documents ?? [];
  const docTitle = docFilter ? docs.find((d) => d.doc_id === docFilter)?.title : undefined;

  type CatItem = { id: string | null; label?: string | null; count?: number };
  const cats = ((overview.data?.categories ?? []) as unknown as CatItem[]);
  const catItem = category !== null
    ? cats.find((c) => (c.id ?? "") === category)
    : undefined;
  const catLabel = category === null ? null : (catItem?.label ?? (category === "" ? "기타" : category));
  const catCount = catItem?.count;

  const clearAll = () => {
    setDocFilter(null);
    setCategory(null);
    // URL 정리
    router.replace("/chat");
  };

  if (docFilter) {
    return (
      <div className="flex items-center gap-2 border-b border-border bg-blue-50 dark:bg-blue-950/30 px-3 py-2 text-sm">
        <Badge variant="secondary" className="shrink-0">📖 문서 한정</Badge>
        <span className="flex-1 min-w-0 truncate">
          <span className="font-medium">{docTitle ?? docFilter.slice(0, 8)}</span> 에 한정해 답변합니다
        </span>
        <Button size="sm" variant="ghost" className="h-7" onClick={clearAll}>
          <X className="size-3.5 mr-1" /> 전체 검색
        </Button>
      </div>
    );
  }

  if (category !== null) {
    return (
      <div className="flex items-center gap-2 border-b border-border bg-amber-50 dark:bg-amber-950/30 px-3 py-2 text-sm">
        <Badge variant="secondary" className="shrink-0">📂 카테고리 한정</Badge>
        <span className="flex-1 min-w-0">
          <span className="font-medium">{catLabel}</span>
          {typeof catCount === "number" && <span className="text-muted-foreground"> ({catCount}개 문서)</span>}
          {" "}카테고리에 한정해 답변합니다
        </span>
        <Button size="sm" variant="ghost" className="h-7" onClick={() => setCategory(null)}>
          <X className="size-3.5 mr-1" /> 전체 검색
        </Button>
      </div>
    );
  }

  return null;
}
