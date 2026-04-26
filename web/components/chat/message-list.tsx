"use client";

/**
 * 채팅 메시지 리스트 — 사용자/어시스턴트 말풍선 + 소스 expander.
 * 답변 본문은 react-markdown + remark-gfm으로 렌더.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, FileText, Image as ImageIcon, Table } from "lucide-react";
import { useState } from "react";
import type { MessageItem, SourceItem } from "@/lib/api/types";

const BADGE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  text: FileText,
  table: Table,
  image: ImageIcon,
};

export type AssistantMessage = MessageItem & {
  sources?: SourceItem[];
  latency_ms?: number;
  suggestions?: string[];
};

export function MessageList({ messages }: { messages: AssistantMessage[] }) {
  return (
    <div className="space-y-4">
      {messages.map((m, i) => (
        <Bubble key={i} message={m} />
      ))}
    </div>
  );
}

function Bubble({ message }: { message: AssistantMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : ""}>
      <div className={`max-w-[85%] ${isUser ? "" : "w-full"}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 ${
            isUser ? "bg-primary text-primary-foreground" : "bg-accent/40"
          }`}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap text-sm">{message.content}</div>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceExpander sources={message.sources} latencyMs={message.latency_ms} />
        )}
      </div>
    </div>
  );
}

function SourceExpander({
  sources,
  latencyMs,
}: {
  sources: SourceItem[];
  latencyMs?: number;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1.5">
      <button
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => setOpen((v) => !v)}
      >
        <ChevronDown
          className={`size-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
        📎 소스 {sources.length}개
        {typeof latencyMs === "number" && <span> · {latencyMs}ms</span>}
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          {sources.map((s, i) => {
            const ContentIcon =
              BADGE_ICON[s.content_type ?? "text"] ?? FileText;
            return (
              <Card key={i} className="border-muted-foreground/20">
                <CardContent className="px-3 py-2">
                  <div className="flex items-center gap-1.5 text-xs">
                    <ContentIcon className="size-3.5 text-muted-foreground" />
                    <span className="font-medium truncate flex-1">{s.title}</span>
                    {typeof s.page === "number" && (
                      <Badge variant="outline" className="text-[10px]">
                        p.{s.page}
                      </Badge>
                    )}
                    <Badge variant="secondary" className="text-[10px]">
                      {s.score.toFixed(3)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-3">
                    {s.excerpt}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
