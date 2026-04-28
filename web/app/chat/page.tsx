"use client";

import { AppShell } from "@/components/app-shell";
import { ScopeBanner } from "@/components/chat/scope-banner";
import { MessageList, type AssistantMessage } from "@/components/chat/message-list";
import { Suggestions } from "@/components/chat/suggestions";
import { ChatInput } from "@/components/chat/chat-input";
import { EmptyState } from "@/components/chat/empty-state";
import { useConversation } from "@/lib/hooks/use-conversations";
import { useRagQuery } from "@/lib/hooks/use-rag-query";
import type { SourceItem } from "@/lib/api/types";
import { useQueryState, parseAsString } from "nuqs";
import { useEffect, useMemo, useRef, useState } from "react";

export default function ChatPage() {
  const [sessionId, setSessionId] = useQueryState("session_id", parseAsString);
  const [docFilter] = useQueryState("doc_filter", parseAsString);
  const [category] = useQueryState("category", parseAsString);
  const [ask, setAsk] = useQueryState("ask", parseAsString);
  const ragMutation = useRagQuery();
  const conversation = useConversation(sessionId);

  // 라이브 메시지 (mutation 응답)는 conversation refetch 전 즉시 표시 위해 별도 상태 보존.
  // sessionId 변경 시 동기 리셋 — useEffect+setState 안티패턴 회피 (React docs: "Adjusting state on prop change")
  const [liveSuggestions, setLiveSuggestions] = useState<string[]>([]);
  const [liveLatency, setLiveLatency] = useState<number | undefined>();
  const [liveSources, setLiveSources] = useState<SourceItem[] | undefined>();
  const [prevSessionId, setPrevSessionId] = useState<string | null>(sessionId);
  if (prevSessionId !== sessionId) {
    setPrevSessionId(sessionId);
    setLiveSuggestions([]);
    setLiveLatency(undefined);
    setLiveSources(undefined);
  }

  // ?ask=... 자동 질의 가드 — ref만 만지므로 set-state-in-effect 룰 미저촉
  const askedRef = useRef(false);
  useEffect(() => {
    askedRef.current = false;
  }, [sessionId]);

  // 메시지: 서버 conversation 우선, 없으면 빈
  const baseMessages: AssistantMessage[] = useMemo(() => {
    return (conversation.data?.messages ?? []).map((m) => ({ ...m }));
  }, [conversation.data]);

  // 마지막 assistant 메시지에 라이브 suggestions/latency/sources 머지
  // (sources는 백엔드가 messages 페이로드에 영속화하지 않으므로 conversation refetch 후에도 라이브 값 유지)
  const messages = useMemo(() => {
    if (!liveSuggestions.length && liveLatency === undefined && !liveSources?.length) {
      return baseMessages;
    }
    const arr = [...baseMessages];
    for (let i = arr.length - 1; i >= 0; i--) {
      if (arr[i].role === "assistant") {
        arr[i] = {
          ...arr[i],
          suggestions: liveSuggestions,
          latency_ms: liveLatency,
          sources: liveSources ?? arr[i].sources,
        };
        break;
      }
    }
    return arr;
  }, [baseMessages, liveSuggestions, liveLatency, liveSources]);

  const sendMessage = (text: string) => {
    setLiveSuggestions([]);
    setLiveLatency(undefined);
    setLiveSources(undefined);
    ragMutation.mutate(
      {
        question: text,
        session_id: sessionId,
        doc_filter: docFilter,
        category_filter: docFilter ? null : category,
      },
      {
        onSuccess: (data) => {
          if (data.session_id && data.session_id !== sessionId) {
            setSessionId(data.session_id);
          }
          // 응답 sources/latency/suggestions를 message-list에 직접 주입할 수 없으니 별도 보존
          setLiveSuggestions(data.suggestions ?? []);
          setLiveLatency(data.latency_ms);
          setLiveSources(data.sources ?? []);
          // ScopeBanner 활성 시 conversation refetch는 hook의 invalidate가 처리
        },
      },
    );
  };

  // ?ask=... 자동 질의 (도서관에서 sample question 클릭으로 들어왔을 때)
  useEffect(() => {
    if (ask && !askedRef.current && !ragMutation.isPending) {
      askedRef.current = true;
      sendMessage(ask);
      setAsk(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ask, ragMutation.isPending]);

  const isEmpty = !sessionId && messages.length === 0;
  const lastAssistantSuggestions =
    messages.length > 0 && messages[messages.length - 1].role === "assistant"
      ? messages[messages.length - 1].suggestions ?? []
      : [];

  return (
    <AppShell>
      <ScopeBanner />

      <div className="flex flex-1 min-h-0 flex-col">
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <div className="max-w-4xl mx-auto">
            {isEmpty ? (
              <EmptyState onPickQuestion={(q) => sendMessage(q)} />
            ) : (
              <>
                <MessageList messages={messages} />
                {ragMutation.isPending && (
                  <div className="mt-4 text-sm text-muted-foreground italic">
                    검색 및 답변 생성 중…
                  </div>
                )}
                {!ragMutation.isPending && lastAssistantSuggestions.length > 0 && (
                  <Suggestions items={lastAssistantSuggestions} onPick={sendMessage} />
                )}
                {ragMutation.isError && (
                  <div className="mt-4 text-sm text-destructive">
                    오류: {(ragMutation.error as Error)?.message ?? "응답 실패"}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <ChatInput
          onSend={sendMessage}
          pending={ragMutation.isPending}
          placeholder={
            docFilter
              ? "이 책에 대해 질문하세요..."
              : category !== null
                ? "이 카테고리에 대해 질문하세요..."
                : "문서에 대해 질문하세요..."
          }
        />
      </div>
    </AppShell>
  );
}

