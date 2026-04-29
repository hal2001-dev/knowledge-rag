"use client";

/**
 * ISSUE-006/007: 활성 스코프(doc_filter / category / series_filter)에 따라 분기하는 빈 채팅 화면.
 *
 * 정책 — 우선순위 doc > category > series (ADR-029):
 *   - doc_filter 활성   → 그 책 1권 summary + sample_questions만. 인덱스 전체 영역 모두 숨김
 *   - category 활성     → 그 카테고리 안의 문서 카드 N개 + 책별 sample 1개씩
 *   - series_filter 활성 → 그 시리즈 멤버 카드 + 첫 권 sample_questions
 *   - 그 외 (전체)       → 기존 EmptyState (인덱스 전체)
 *
 * sample_question 클릭 시 onPickQuestion이 호출되고, 호출자(ChatPage.sendMessage)가
 * 활성 doc_filter/category/series_filter를 그대로 통과시켜 retrieval 정합도 보장.
 */
import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQueryState, parseAsString } from "nuqs";
import { useDocuments } from "@/lib/hooks/use-documents";
import { useSeriesMembers, useSeriesList } from "@/lib/hooks/use-series";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { BookOpen, MessageCircle } from "lucide-react";
import { readSummary, type DocumentItem } from "@/lib/api/types";
import { EmptyState } from "@/components/chat/empty-state";

export function ScopedEmptyState({
  onPickQuestion,
}: {
  onPickQuestion: (q: string) => void;
}) {
  const [docFilter] = useQueryState("doc_filter", parseAsString);
  const [category] = useQueryState("category", parseAsString);
  const [seriesFilter] = useQueryState("series_filter", parseAsString);

  // 우선순위 doc > category > series
  if (docFilter) return <DocScoped docId={docFilter} onPickQuestion={onPickQuestion} />;
  if (category !== null) return <CategoryScoped category={category} onPickQuestion={onPickQuestion} />;
  if (seriesFilter) return <SeriesScoped seriesId={seriesFilter} onPickQuestion={onPickQuestion} />;
  return <EmptyState onPickQuestion={onPickQuestion} />;
}

// ─────────────────────────────────────────────────────
// doc_filter 활성 — 그 책 한 권만
// ─────────────────────────────────────────────────────


function DocScoped({
  docId,
  onPickQuestion,
}: {
  docId: string;
  onPickQuestion: (q: string) => void;
}) {
  const docsQuery = useDocuments();
  const router = useRouter();
  const doc = useMemo(
    () => (docsQuery.data?.documents ?? []).find((d) => d.doc_id === docId),
    [docsQuery.data, docId],
  );

  if (docsQuery.isLoading) {
    return (
      <div className="space-y-4 max-w-3xl mx-auto py-8">
        <Skeleton className="h-32" />
        <Skeleton className="h-24" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-16 gap-3">
        <h2 className="text-base font-semibold">📖 책을 찾을 수 없음</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          doc_id {docId.slice(0, 8)}…에 해당하는 문서가 인덱스에 없습니다.
        </p>
        <Button size="sm" variant="outline" onClick={() => router.replace("/chat")}>
          전체 채팅으로
        </Button>
      </div>
    );
  }

  const summary = readSummary(doc);
  const samples = (summary?.sample_questions ?? []).slice(0, 5);

  return (
    <div className="space-y-4 max-w-3xl mx-auto py-6">
      <Card>
        <CardContent className="p-5 space-y-3">
          <div className="flex items-start gap-2">
            <Badge variant="secondary" className="shrink-0">📖 이 책 한정</Badge>
            <h2 className="text-base font-semibold">{doc.title}</h2>
          </div>
          {summary?.one_liner && (
            <p className="text-sm text-muted-foreground">{summary.one_liner}</p>
          )}
          {summary?.abstract && (
            <p className="text-sm leading-relaxed">{summary.abstract}</p>
          )}
          {(summary?.topics ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {(summary?.topics ?? []).slice(0, 6).map((t, i) => (
                <Badge key={i} variant="outline" className="text-[10px]">{t}</Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {samples.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="text-xs text-muted-foreground">
              💡 이 책에서 나올 수 있는 질문 (클릭 즉시 질의 — 이 책 한정)
            </div>
            <div className="flex flex-wrap gap-1.5">
              {samples.map((q, i) => (
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

      {samples.length === 0 && (
        <Card>
          <CardContent className="p-4 text-xs text-muted-foreground italic">
            아직 이 책의 예시 질문이 생성되지 않았습니다. 자유롭게 질문해 보세요.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────
// category 활성 — 그 카테고리 안의 책들
// ─────────────────────────────────────────────────────

function CategoryScoped({
  category,
  onPickQuestion,
}: {
  category: string;
  onPickQuestion: (q: string) => void;
}) {
  const docsQuery = useDocuments();
  const docsInCategory = useMemo(() => {
    const all = docsQuery.data?.documents ?? [];
    if (category === "") return all.filter((d) => !d.category);
    return all.filter((d) => d.category === category);
  }, [docsQuery.data, category]);

  if (docsQuery.isLoading) {
    return (
      <div className="space-y-4 max-w-3xl mx-auto py-8">
        <Skeleton className="h-32" />
      </div>
    );
  }

  // 책별 sample_question 1개씩, 최대 6개 표시
  type SampleEntry = { doc: DocumentItem; question: string };
  const samplesByDoc: SampleEntry[] = docsInCategory
    .map((d) => {
      const sm = readSummary(d);
      const q = (sm?.sample_questions ?? [])[0];
      return q ? ({ doc: d, question: q }) : null;
    })
    .filter((x): x is SampleEntry => x !== null)
    .slice(0, 6);

  const label = category === "" ? "기타" : category;

  return (
    <div className="space-y-4 max-w-3xl mx-auto py-6">
      <Card>
        <CardContent className="p-5 space-y-2">
          <div className="flex items-start gap-2">
            <Badge variant="secondary" className="shrink-0">📂 카테고리 한정</Badge>
            <h2 className="text-base font-semibold">{label}</h2>
            <span className="text-xs text-muted-foreground">
              ({docsInCategory.length}권)
            </span>
          </div>
        </CardContent>
      </Card>

      {samplesByDoc.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="text-xs text-muted-foreground">
              💡 이 카테고리에서 나올 수 있는 질문 (책별 1개씩, 클릭 즉시 질의)
            </div>
            <div className="space-y-1.5">
              {samplesByDoc.map((s, i) => (
                <Button
                  key={i}
                  size="sm"
                  variant="secondary"
                  className="w-full justify-start h-auto whitespace-normal text-left text-xs leading-snug py-1.5"
                  onClick={() => onPickQuestion(s.question)}
                >
                  <span className="flex-1">{s.question}</span>
                  <span className="ml-2 text-[10px] text-muted-foreground line-clamp-1">
                    ← {s.doc.title}
                  </span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {samplesByDoc.length === 0 && (
        <Card>
          <CardContent className="p-4 text-xs text-muted-foreground italic">
            이 카테고리에 sample_question이 캐시된 책이 아직 없습니다. 자유롭게 질문해 보세요.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────
// series_filter 활성 — 그 시리즈 멤버
// ─────────────────────────────────────────────────────

function SeriesScoped({
  seriesId,
  onPickQuestion,
}: {
  seriesId: string;
  onPickQuestion: (q: string) => void;
}) {
  const seriesListQuery = useSeriesList();
  const membersQuery = useSeriesMembers(seriesId);

  const series = useMemo(
    () => (seriesListQuery.data?.series ?? []).find((s) => s.series_id === seriesId),
    [seriesListQuery.data, seriesId],
  );
  const members = membersQuery.data?.members ?? [];

  if (membersQuery.isLoading || seriesListQuery.isLoading) {
    return (
      <div className="space-y-4 max-w-3xl mx-auto py-8">
        <Skeleton className="h-32" />
      </div>
    );
  }

  // 시리즈 첫 권(volume 1 또는 가장 작은 volume)의 sample_question 5개를 시리즈 대표로
  const sortedMembers = [...members].sort((a, b) => {
    const av = a.volume_number ?? Number.MAX_SAFE_INTEGER;
    const bv = b.volume_number ?? Number.MAX_SAFE_INTEGER;
    return av - bv;
  });
  const cover = sortedMembers[0];
  const coverSummary = cover ? readSummary(cover) : null;
  const samples = (coverSummary?.sample_questions ?? []).slice(0, 5);

  return (
    <div className="space-y-4 max-w-3xl mx-auto py-6">
      <Card>
        <CardContent className="p-5 space-y-3">
          <div className="flex items-start gap-2">
            <Badge variant="secondary" className="shrink-0">
              <BookOpen className="size-3 mr-0.5" />
              시리즈 {sortedMembers.length}권
            </Badge>
            <h2 className="text-base font-semibold">
              {series?.title ?? seriesId.slice(0, 12)}
            </h2>
          </div>
          {series?.description && (
            <p className="text-sm text-muted-foreground">{series.description}</p>
          )}
          <div className="flex flex-wrap gap-1.5">
            {sortedMembers.map((d) => (
              <Badge key={d.doc_id} variant="outline" className="text-[10px]">
                {d.volume_number ? `Vol ${d.volume_number}` : "—"} {d.volume_title ?? d.title}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {samples.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="text-xs text-muted-foreground">
              💡 이 시리즈에서 나올 수 있는 질문 (대표 권 기준, 클릭 즉시 질의)
            </div>
            <div className="flex flex-wrap gap-1.5">
              {samples.map((q, i) => (
                <Button
                  key={i}
                  size="sm"
                  variant="secondary"
                  className="h-auto whitespace-normal text-left text-xs leading-snug py-1.5"
                  onClick={() => onPickQuestion(q)}
                >
                  <MessageCircle className="size-3 mr-1" />
                  {q}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {samples.length === 0 && (
        <Card>
          <CardContent className="p-4 text-xs text-muted-foreground italic">
            대표 권의 sample_question이 아직 캐시되지 않았습니다. 자유롭게 질문해 보세요.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
