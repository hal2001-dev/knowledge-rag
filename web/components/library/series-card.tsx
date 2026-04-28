"use client";

/**
 * 도서관 시리즈 카드 — 한 시리즈에 속한 멤버 N권을 응축한 카드.
 * 펼치면 멤버 목록(volume_number 순) + 각 권의 "이 책에 묻기" 단축 + 시리즈 전체에 묻기.
 *
 * TASK-020 (ADR-029): 사용자가 30챕터 책을 한 단위로 탐색·질의 가능.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ChevronDown, ChevronUp, BookOpen, MessageCircle } from "lucide-react";
import type { DocumentItem, SeriesItem } from "@/lib/api/types";

export function SeriesCard({
  series,
  members,
}: {
  series: SeriesItem;
  members: DocumentItem[];
}) {
  const [expanded, setExpanded] = useState(false);
  const router = useRouter();

  const sorted = [...members].sort((a, b) => {
    const av = a.volume_number ?? Number.MAX_SAFE_INTEGER;
    const bv = b.volume_number ?? Number.MAX_SAFE_INTEGER;
    if (av !== bv) return av - bv;
    return (a.title ?? "").localeCompare(b.title ?? "");
  });

  const askThisSeries = () => {
    router.push(`/chat?series_filter=${encodeURIComponent(series.series_id)}`);
  };
  const askThisMember = (docId: string) => {
    router.push(`/chat?doc_filter=${encodeURIComponent(docId)}`);
  };

  return (
    <Card className="flex flex-col border-amber-300/60 bg-amber-50/30 dark:border-amber-700/40 dark:bg-amber-950/20">
      <CardContent className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start gap-1">
          <Badge variant="secondary" className="shrink-0 text-[10px]">
            <BookOpen className="size-3 mr-0.5" />
            시리즈 {sorted.length}권
          </Badge>
          <h3 className="text-sm font-semibold leading-tight line-clamp-2 flex-1">
            {series.title}
          </h3>
        </div>

        {series.description && (
          <p className="text-xs text-muted-foreground line-clamp-3">
            {series.description}
          </p>
        )}

        <div className="text-[10px] text-muted-foreground">
          타입: {series.series_type}
          {series.cover_doc_id && <> · 표지: {series.cover_doc_id.slice(0, 8)}…</>}
        </div>

        <div className="mt-auto flex gap-1.5 pt-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            <span className="ml-1">권 목록</span>
          </Button>
          <Button size="sm" className="flex-1" onClick={askThisSeries}>
            <MessageCircle className="size-3.5" />
            <span className="ml-1 truncate">이 시리즈에 묻기</span>
          </Button>
        </div>

        {expanded && (
          <>
            <Separator className="my-2" />
            <div className="space-y-1">
              {sorted.map((d) => (
                <button
                  key={d.doc_id}
                  className="flex w-full items-center gap-2 rounded-md border border-border/60 px-2 py-1.5 text-left text-xs hover:bg-accent/40 transition-colors"
                  onClick={() => askThisMember(d.doc_id)}
                  title="이 권 한정으로 채팅"
                >
                  <Badge variant="outline" className="shrink-0 text-[10px]">
                    {d.volume_number ? `Vol ${d.volume_number}` : "—"}
                  </Badge>
                  <span className="flex-1 line-clamp-1">
                    {d.volume_title ?? d.title}
                  </span>
                  <Badge
                    variant="secondary"
                    className="shrink-0 text-[9px]"
                    title={`매치 상태: ${d.series_match_status}`}
                  >
                    {d.series_match_status}
                  </Badge>
                </button>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
