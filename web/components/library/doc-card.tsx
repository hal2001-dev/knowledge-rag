"use client";

/**
 * 도서관 카드 — 제목 / 한 줄 요약 / topics / [상세] [이 책에 묻기].
 * 상세 토글 시 abstract · sample_questions · meta 노출.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ChevronDown, ChevronUp, MessageCircle } from "lucide-react";
import type { DocumentItem } from "@/lib/api/types";
import { readSummary } from "@/lib/api/types";

export function DocCard({ doc }: { doc: DocumentItem }) {
  const [expanded, setExpanded] = useState(false);
  const router = useRouter();
  const summary = readSummary(doc);
  const oneLiner = summary?.one_liner ?? "";
  const topics = (summary?.topics ?? []).slice(0, 5);
  const abstract = summary?.abstract ?? "";
  const sampleQuestions = summary?.sample_questions ?? [];
  const lowConfidence =
    typeof doc.category_confidence === "number" && doc.category_confidence < 0.4;

  const askThisDoc = () => {
    router.push(`/chat?doc_filter=${encodeURIComponent(doc.doc_id)}`);
  };

  const askThisQuestion = (q: string) => {
    const params = new URLSearchParams({
      doc_filter: doc.doc_id,
      ask: q,
    });
    router.push(`/chat?${params.toString()}`);
  };

  return (
    <Card className="flex flex-col">
      <CardContent className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start gap-1">
          <h3 className="text-sm font-semibold leading-tight line-clamp-2 flex-1">
            {doc.title}
          </h3>
          {lowConfidence && (
            <Badge variant="outline" className="text-[10px]" title="자동 분류 신뢰도 낮음">
              ⚠️
            </Badge>
          )}
        </div>

        {oneLiner ? (
          <p className="text-xs text-muted-foreground line-clamp-3">{oneLiner}</p>
        ) : (
          <p className="text-xs text-muted-foreground italic">_요약 생성 중…_</p>
        )}

        {topics.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {topics.map((t, i) => (
              <Badge key={i} variant="secondary" className="text-[10px]">
                {t}
              </Badge>
            ))}
          </div>
        )}

        <div className="mt-auto flex gap-1.5 pt-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            <span className="ml-1">상세</span>
          </Button>
          <Button size="sm" className="flex-1" onClick={askThisDoc}>
            <MessageCircle className="size-3.5" />
            <span className="ml-1 truncate">이 책에 묻기</span>
          </Button>
        </div>

        {expanded && (
          <>
            <Separator className="my-2" />
            {abstract && <p className="text-xs leading-relaxed mb-2">{abstract}</p>}
            {sampleQuestions.length > 0 && (
              <div className="space-y-1">
                <div className="text-[10px] font-medium text-muted-foreground">
                  💡 이 책에서 나올 수 있는 질문
                </div>
                {sampleQuestions.map((q, i) => (
                  <Button
                    key={i}
                    size="sm"
                    variant="secondary"
                    className="w-full justify-start h-auto whitespace-normal text-left text-xs leading-snug py-1.5"
                    onClick={() => askThisQuestion(q)}
                  >
                    {q}
                  </Button>
                ))}
              </div>
            )}
            <div className="mt-2 text-[10px] text-muted-foreground space-y-0.5">
              {doc.source && <div>source: {doc.source.slice(0, 60)}</div>}
              {doc.file_type && <div>형식: {doc.file_type}</div>}
              {doc.indexed_at && <div>인덱싱: {String(doc.indexed_at).slice(0, 10)}</div>}
              {typeof doc.category_confidence === "number" && (
                <div>신뢰도: {doc.category_confidence.toFixed(2)}</div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
