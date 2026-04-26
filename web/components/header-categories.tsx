"use client";

/**
 * 상단 카테고리 칩. 첫 칩 🌐 전체(스코프 해제), 그 뒤로 카테고리 라벨.
 * `category_filter` URL state(nuqs)와 동기화. NULL 카테고리는 "기타"로 표시.
 */
import { useIndexOverview } from "@/lib/hooks/use-index-overview";
import { useQueryState, parseAsString } from "nuqs";
import { Button } from "@/components/ui/button";
import { useRouter, usePathname } from "next/navigation";
import { Globe, Folder } from "lucide-react";

// /index/overview의 categories는 OpenAPI에 inline dict로 정의돼 unknown 타입.
// UI에서 안전하게 다루기 위한 narrow type.
type CatItem = { id: string | null; label?: string | null; count?: number };

export function HeaderCategories() {
  const overview = useIndexOverview();
  const [category, setCategory] = useQueryState("category", parseAsString);
  const router = useRouter();
  const pathname = usePathname();

  const cats = ((overview.data?.categories ?? []) as unknown as CatItem[]);
  const hasUncategorized = cats.some((c) => c.id === null);

  const setScope = (next: string | null) => {
    setCategory(next);
    // 도서관/채팅 페이지가 아니면 채팅으로 이동하면서 카테고리 적용
    if (pathname !== "/chat" && pathname !== "/library") {
      router.push(next ? `/chat?category=${encodeURIComponent(next)}` : "/chat");
    }
  };

  return (
    <div className="flex items-center gap-1.5 py-1">
      <Button
        size="sm"
        variant={!category ? "default" : "ghost"}
        className="h-7 px-2 text-xs whitespace-nowrap"
        onClick={() => setScope(null)}
      >
        <Globe className="mr-1 size-3.5" /> 전체
      </Button>
      {cats.map((c) => {
        const id = c.id ?? "";
        const isActive = category === id || (category === "" && c.id === null);
        const label = c.id === null ? "기타" : (c.label ?? c.id ?? "기타");
        return (
          <Button
            key={c.id ?? "__null__"}
            size="sm"
            variant={isActive ? "default" : "ghost"}
            className="h-7 px-2 text-xs whitespace-nowrap"
            onClick={() => setScope(c.id ?? "")}
          >
            <Folder className="mr-1 size-3.5" /> {label}
          </Button>
        );
      })}
      {/* 카테고리 데이터 없을 때 fallback (NULL 그룹 처리는 위에서 cats가 채움) */}
      {!cats.length && !overview.isLoading && (
        <span className="text-xs text-muted-foreground px-2">카테고리 없음</span>
      )}
      {/* 미분류만 있는 케이스 */}
      {hasUncategorized && cats.length === 1 && (
        <span className="text-xs text-muted-foreground px-1">— 분류 가능한 카테고리가 늘어나면 여기 표시</span>
      )}
    </div>
  );
}
