"use client";

/**
 * 빈 채팅 화면 카드 v2 (TASK-019 Phase B / 백엔드 ADR-027 랜딩 카드 v2 데이터 활용).
 * - "이 시스템이 아는 내용" 요약
 * - 카테고리 분포 한 줄
 * - 주제 칩 6개 → 클릭 시 /library?q=<태그>
 * - 예시 질문 → 클릭 시 즉시 질의 (onPickQuestion)
 * - 최근 문서 카드 3개 → 클릭 시 /chat?doc_filter=<doc_id>
 * - 전체 문서 expander
 */
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useIndexOverview } from "@/lib/hooks/use-index-overview";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronDown, ChevronUp, Folder, Hash, MessageCircle } from "lucide-react";

type CatItem = { id: string | null; label?: string | null; count?: number };

export function EmptyState({
  onPickQuestion,
}: {
  onPickQuestion: (q: string) => void;
}) {
  const overview = useIndexOverview();
  const router = useRouter();
  const [expandedAll, setExpandedAll] = useState(false);

  if (overview.isLoading) {
    return (
      <div className="space-y-4 max-w-3xl mx-auto py-8">
        <Skeleton className="h-32" />
        <Skeleton className="h-24" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  const data = overview.data;
  if (!data || data.doc_count === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-16 gap-4">
        <h2 className="text-xl font-semibold">📚 무엇을 도와드릴까요?</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          아직 인덱싱된 문서가 없습니다. 관리자(Streamlit 8501)에서 업로드해 주세요.
        </p>
      </div>
    );
  }

  const categories = ((data.categories ?? []) as unknown as CatItem[]);
  const topTags = (data.top_tags ?? []).slice(0, 6);
  const examples = (data.suggested_questions ?? []).slice(0, 5);
  const recent = (data.recent_docs ?? []).slice(0, 3);
  const titles = data.titles ?? [];

  return (
    <div className="space-y-4 max-w-3xl mx-auto py-6">
      {/* 인덱스 요약 카드 */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="text-base font-semibold">👋 이 시스템이 아는 내용</h2>
          {data.summary && (
            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
              {data.summary}
            </p>
          )}

          {/* 카테고리 분포 */}
          {categories.length > 0 && (
            <div className="text-xs">
              <div className="text-muted-foreground mb-1.5">📂 카테고리 분포 (상단 칩에서 한정 가능)</div>
              <div className="flex flex-wrap gap-1.5">
                {categories.slice(0, 6).map((c, i) => {
                  const id = c.id ?? "";
                  const label = c.id === null ? "기타" : (c.label ?? c.id ?? "기타");
                  return (
                    <button
                      key={i}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 hover:bg-accent transition-colors"
                      onClick={() => router.push(`/chat?category=${encodeURIComponent(id)}`)}
                    >
                      <Folder className="size-3" />
                      <span>{label}</span>
                      {typeof c.count === "number" && (
                        <span className="text-muted-foreground">{c.count}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* 주제 칩 */}
          {topTags.length > 0 && (
            <div className="text-xs">
              <div className="text-muted-foreground mb-1.5">🏷️ 자주 등장하는 주제 (도서관에서 검색)</div>
              <div className="flex flex-wrap gap-1.5">
                {topTags.map((t, i) => (
                  <Link
                    key={i}
                    href={`/library?q=${encodeURIComponent(t)}`}
                    className="inline-flex items-center gap-1 rounded-md bg-accent/50 px-2 py-0.5 hover:bg-accent transition-colors"
                  >
                    <Hash className="size-3" />
                    {t}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 예시 질문 */}
      {examples.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="text-xs text-muted-foreground">🎯 예시 질문 (클릭 즉시 질의)</div>
            <div className="flex flex-wrap gap-1.5">
              {examples.map((q, i) => (
                <Button
                  key={i}
                  size="sm"
                  variant="secondary"
                  className="h-auto whitespace-normal text-left text-xs leading-snug py-1.5"
                  onClick={() => onPickQuestion(q)}
                >
                  {q}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 최근 문서 카드 */}
      {recent.length > 0 && (
        <div>
          <div className="text-xs text-muted-foreground mb-2 px-1">📖 최근 추가된 문서 (클릭 시 한정 모드)</div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {recent.map((d) => (
              <button
                key={d.doc_id}
                className="rounded-md border border-border p-3 text-left hover:bg-accent/40 transition-colors"
                onClick={() =>
                  router.push(`/chat?doc_filter=${encodeURIComponent(d.doc_id)}`)
                }
              >
                <div className="text-sm font-medium line-clamp-2">{d.title}</div>
                {d.one_liner && (
                  <div className="mt-1 text-xs text-muted-foreground line-clamp-2">
                    {d.one_liner}
                  </div>
                )}
                {!d.one_liner && d.category && (
                  <div className="mt-1 text-xs text-muted-foreground italic">
                    _{d.category}_
                  </div>
                )}
                <div className="mt-2 flex items-center gap-1 text-[10px] text-primary">
                  <MessageCircle className="size-3" /> 이 책에 묻기
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 전체 문서 expander */}
      {titles.length > 0 && (
        <div className="rounded-md border border-border">
          <button
            className="flex w-full items-center justify-between px-3 py-2 text-xs hover:bg-accent/40"
            onClick={() => setExpandedAll((v) => !v)}
          >
            <span>전체 문서 {data.doc_count}개</span>
            {expandedAll ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          </button>
          {expandedAll && (
            <div className="border-t border-border px-3 py-2 space-y-0.5">
              {titles.map((t, i) => (
                <div key={i} className="text-xs text-muted-foreground">
                  • {t}
                </div>
              ))}
              <div className="pt-2">
                <Link href="/library" className="text-xs underline">
                  📚 도서관에서 카드로 보기
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
