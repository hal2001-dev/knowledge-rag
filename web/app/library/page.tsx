"use client";

import { AppShell } from "@/components/app-shell";
import { useDocuments } from "@/lib/hooks/use-documents";
import { useSeriesList } from "@/lib/hooks/use-series";
import { useQueryState, parseAsString } from "nuqs";
import { FilterBar } from "@/components/library/filter-bar";
import { DocCard } from "@/components/library/doc-card";
import { SeriesCard } from "@/components/library/series-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import type { DocumentItem, SeriesItem } from "@/lib/api/types";
import { readSummary } from "@/lib/api/types";
import { MessageCircle } from "lucide-react";

const ETC_LABEL = "기타";

export default function LibraryPage() {
  const docsQuery = useDocuments();
  const seriesQuery = useSeriesList();
  const router = useRouter();
  const [q] = useQueryState("q", parseAsString.withDefault(""));
  const [type] = useQueryState("type", parseAsString.withDefault("__all__"));
  const [category] = useQueryState("category", parseAsString);

  const docs: DocumentItem[] = useMemo(
    () => docsQuery.data?.documents ?? [],
    [docsQuery.data],
  );
  const allSeries: SeriesItem[] = useMemo(
    () => seriesQuery.data?.series ?? [],
    [seriesQuery.data],
  );

  // 필터에 쓸 형식·카테고리 옵션
  const docTypes = useMemo(
    () => Array.from(new Set(docs.map((d) => d.doc_type ?? "book"))).sort(),
    [docs],
  );
  const categoryOptions = useMemo(() => {
    const map = new Map<string | null, { id: string | null; label: string; count: number }>();
    for (const d of docs) {
      const id = d.category ?? null;
      const label = id ?? ETC_LABEL;
      const cur = map.get(id);
      if (cur) cur.count += 1;
      else map.set(id, { id, label, count: 1 });
    }
    const arr = Array.from(map.values());
    arr.sort((a, b) => {
      if (a.id === null) return 1;
      if (b.id === null) return -1;
      return (a.label ?? "").localeCompare(b.label ?? "");
    });
    return arr;
  }, [docs]);

  // 필터 적용
  const filtered = useMemo(() => {
    const qLower = (q ?? "").toLowerCase().trim();
    return docs.filter((d) => {
      if (type !== "__all__" && (d.doc_type ?? "book") !== type) return false;
      if (category !== null) {
        const docCat = d.category ?? "";
        if (category === "" && docCat !== "") return false;
        if (category !== "" && docCat !== category) return false;
      }
      if (qLower) {
        const sm = readSummary(d);
        const hay = [
          d.title,
          sm?.one_liner ?? "",
          sm?.abstract ?? "",
          (sm?.topics ?? []).join(" "),
          (d.tags ?? []).join(" "),
        ]
          .join(" ")
          .toLowerCase();
        if (!hay.includes(qLower)) return false;
      }
      return true;
    });
  }, [docs, q, type, category]);

  // TASK-020: 시리즈 묶기. filtered 중 series_id가 있는 멤버는 시리즈 카드로 응축.
  // 시리즈 자체는 멤버가 1건이라도 (필터에 매칭된 멤버가 있어야) 표시.
  const seriesGroups = useMemo(() => {
    const memberMap = new Map<string, DocumentItem[]>();
    for (const d of filtered) {
      if (!d.series_id) continue;
      const arr = memberMap.get(d.series_id) ?? [];
      arr.push(d);
      memberMap.set(d.series_id, arr);
    }
    const groups: { series: SeriesItem; members: DocumentItem[] }[] = [];
    for (const s of allSeries) {
      const ms = memberMap.get(s.series_id);
      if (ms && ms.length > 0) groups.push({ series: s, members: ms });
    }
    groups.sort((a, b) => a.series.title.localeCompare(b.series.title));
    return groups;
  }, [filtered, allSeries]);

  // 카테고리 그룹핑 — 시리즈 묶음에 들어간 멤버는 제외 (중복 표시 방지)
  const grouped = useMemo(() => {
    const map = new Map<string, DocumentItem[]>();
    for (const d of filtered) {
      if (d.series_id) continue;
      const key = d.category ?? ETC_LABEL;
      const arr = map.get(key) ?? [];
      arr.push(d);
      map.set(key, arr);
    }
    const keys = Array.from(map.keys()).sort((a, b) => {
      if (a === ETC_LABEL) return 1;
      if (b === ETC_LABEL) return -1;
      return a.localeCompare(b);
    });
    return keys.map((k) => ({ key: k, docs: map.get(k)! }));
  }, [filtered]);

  // category 스코프 활성 시 [이 카테고리에 묻기] 라벨용
  const activeCatLabel =
    category === null
      ? null
      : category === ""
        ? ETC_LABEL
        : (categoryOptions.find((c) => c.id === category)?.label ?? category);

  const askCategory = () => {
    if (category === null) return;
    router.push(`/chat?category=${encodeURIComponent(category)}`);
  };

  return (
    <AppShell>
      <FilterBar docTypes={docTypes} categoryOptions={categoryOptions} />

      <div className="flex-1 overflow-y-auto p-3">
        {/* 카테고리 한정 모드 안내 */}
        {activeCatLabel !== null && (
          <div className="mb-3 flex items-center justify-between gap-2 rounded-md border border-border bg-accent/40 px-3 py-2">
            <div className="text-xs">
              📂 <span className="font-semibold">{activeCatLabel}</span> 카테고리 필터 적용
              ({filtered.length}/{docs.length}개 문서)
            </div>
            <Button size="sm" onClick={askCategory}>
              <MessageCircle className="size-3.5" />
              <span className="ml-1">이 카테고리에 묻기</span>
            </Button>
          </div>
        )}

        {docsQuery.isLoading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-48" />
            ))}
          </div>
        )}

        {docsQuery.isError && (
          <div className="text-sm text-destructive">
            문서 목록을 불러올 수 없습니다.
          </div>
        )}

        {!docsQuery.isLoading && filtered.length === 0 && (
          <div className="py-16 text-center text-sm text-muted-foreground">
            {docs.length === 0 ? (
              <>아직 인덱싱된 문서가 없습니다. 관리자(Streamlit 8501) 측에서 업로드하세요.</>
            ) : (
              <>필터에 매칭되는 문서가 없습니다.</>
            )}
          </div>
        )}

        {seriesGroups.length > 0 && (
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-semibold">
              📚 시리즈 <span className="ml-1 text-xs text-muted-foreground">· {seriesGroups.length}</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {seriesGroups.map(({ series, members }) => (
                <SeriesCard key={series.series_id} series={series} members={members} />
              ))}
            </div>
          </section>
        )}

        {grouped.map(({ key, docs }) => (
          <section key={key} className="mb-6">
            <h2 className="mb-2 text-sm font-semibold">
              {key} <span className="ml-1 text-xs text-muted-foreground">· {docs.length}</span>
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {docs.map((d) => (
                <DocCard key={d.doc_id} doc={d} />
              ))}
            </div>
          </section>
        ))}

        <div className="text-xs text-muted-foreground text-right pr-1 pb-2">
          총 {filtered.length}/{docs.length}개 문서
        </div>
      </div>
    </AppShell>
  );
}
