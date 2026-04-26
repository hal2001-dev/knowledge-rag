"use client";

/**
 * 도서관 필터 바 — 검색·형식·카테고리. URL state(nuqs)로 동기화.
 * `category`는 상단 카테고리 칩과 공유되는 글로벌 스코프.
 */
import { useQueryState, parseAsString } from "nuqs";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search } from "lucide-react";

type Props = {
  docTypes: string[];
  categoryOptions: { id: string | null; label: string }[];
};

export const ALL_VALUE = "__all__";
export const UNCATEGORIZED_VALUE = "__null__";

export function FilterBar({ docTypes, categoryOptions }: Props) {
  const [q, setQ] = useQueryState("q", parseAsString.withDefault(""));
  const [type, setType] = useQueryState("type", parseAsString.withDefault(ALL_VALUE));
  const [category, setCategory] = useQueryState("category", parseAsString);

  const categoryValue = category === null ? ALL_VALUE : category === "" ? UNCATEGORIZED_VALUE : category;

  return (
    <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-border">
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value || null)}
          placeholder="제목·요약·태그…"
          className="pl-8"
        />
      </div>

      <Select value={type} onValueChange={(v) => setType(v === ALL_VALUE ? null : v)}>
        <SelectTrigger className="w-[120px]">
          <SelectValue placeholder="형식" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>형식 전체</SelectItem>
          {docTypes.map((t) => (
            <SelectItem key={t} value={t}>
              {t}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={categoryValue}
        onValueChange={(v) => {
          if (v === ALL_VALUE) setCategory(null);
          else if (v === UNCATEGORIZED_VALUE) setCategory("");
          else setCategory(v);
        }}
      >
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="카테고리" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>카테고리 전체</SelectItem>
          {categoryOptions.map((c) => (
            <SelectItem key={c.id ?? UNCATEGORIZED_VALUE} value={c.id ?? UNCATEGORIZED_VALUE}>
              {c.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
