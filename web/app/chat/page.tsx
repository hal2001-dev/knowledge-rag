"use client";

import { AppShell } from "@/components/app-shell";
import { ScopeBanner } from "@/components/chat/scope-banner";
import { MessageList, type AssistantMessage } from "@/components/chat/message-list";
import { Suggestions } from "@/components/chat/suggestions";
import { ChatInput } from "@/components/chat/chat-input";
import { ScopedEmptyState } from "@/components/chat/scoped-empty-state";
import { useConversation } from "@/lib/hooks/use-conversations";
import { useRagStream } from "@/lib/hooks/use-rag-stream";
import type { SourceItem } from "@/lib/api/types";
import { useQueryClient } from "@tanstack/react-query";
import { keys } from "@/lib/api/keys";
import { useQueryState, parseAsString } from "nuqs";
import { useEffect, useMemo, useRef, useState } from "react";

export default function ChatPage() {
  const [sessionId, setSessionId] = useQueryState("session_id", parseAsString);
  const [docFilter] = useQueryState("doc_filter", parseAsString);
  const [category] = useQueryState("category", parseAsString);
  const [seriesFilter] = useQueryState("series_filter", parseAsString);
  const [ask, setAsk] = useQueryState("ask", parseAsString);
  const ragStream = useRagStream();
  const conversation = useConversation(sessionId);
  const qc = useQueryClient();

  // 라이브 메시지 (스트림 응답)는 conversation refetch 전 즉시 표시 위해 별도 상태 보존.
  // sessionId 변경 시 동기 리셋 — useEffect+setState 안티패턴 회피
  const [liveSuggestions, setLiveSuggestions] = useState<string[]>([]);
  const [liveLatency, setLiveLatency] = useState<number | undefined>();
  const [liveSources, setLiveSources] = useState<SourceItem[] | undefined>();
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  // TASK-024: 스트리밍 중 누적되는 어시스턴트 텍스트
  const [streamingAnswer, setStreamingAnswer] = useState<string>("");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [prevSessionId, setPrevSessionId] = useState<string | null>(sessionId);
  if (prevSessionId !== sessionId) {
    setPrevSessionId(sessionId);
    setLiveSuggestions([]);
    setLiveLatency(undefined);
    setLiveSources(undefined);
    setPendingUserMessage(null);
    setStreamingAnswer("");
    setStreamError(null);
  }

  const askedRef = useRef(false);
  useEffect(() => {
    askedRef.current = false;
  }, [sessionId]);

  const baseMessages: AssistantMessage[] = useMemo(() => {
    return (conversation.data?.messages ?? []).map((m) => ({ ...m }));
  }, [conversation.data]);

  const lastBaseUser = useMemo(() => {
    for (let i = baseMessages.length - 1; i >= 0; i--) {
      if (baseMessages[i].role === "user") return baseMessages[i].content;
    }
    return null;
  }, [baseMessages]);
  useEffect(() => {
    if (pendingUserMessage && lastBaseUser === pendingUserMessage) {
      setPendingUserMessage(null);
    }
  }, [pendingUserMessage, lastBaseUser]);

  // 메시지 조립:
  //  1) baseMessages
  //  2) liveSources/suggestions/latency를 마지막 assistant에 머지
  //  3) 옵티미스틱 user 버블 append (refetch 전)
  //  4) 스트리밍 중인 assistant 버블 append (없는 경우만 — refetch에 포함되면 자동 드롭)
  const messages = useMemo(() => {
    let arr = baseMessages;
    if (
      liveSuggestions.length || liveLatency !== undefined || liveSources?.length
    ) {
      arr = [...baseMessages];
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
    }
    if (pendingUserMessage && lastBaseUser !== pendingUserMessage) {
      arr = [
        ...arr,
        { role: "user", content: pendingUserMessage } as AssistantMessage,
      ];
    }
    if (streamingAnswer) {
      arr = [
        ...arr,
        {
          role: "assistant",
          content: streamingAnswer,
          sources: liveSources,
        } as AssistantMessage,
      ];
    }
    return arr;
  }, [baseMessages, liveSuggestions, liveLatency, liveSources, pendingUserMessage, lastBaseUser, streamingAnswer]);

  const sendMessage = (text: string) => {
    setLiveSuggestions([]);
    setLiveLatency(undefined);
    setLiveSources(undefined);
    setStreamingAnswer("");
    setStreamError(null);
    setPendingUserMessage(text);
    // 활성 스코프 우선순위 doc > category > series (ADR-029)
    const effectiveCategory = docFilter ? null : category;
    const effectiveSeries = (docFilter || effectiveCategory) ? null : seriesFilter;

    let accumulated = "";
    ragStream.send(
      {
        question: text,
        session_id: sessionId,
        doc_filter: docFilter,
        category_filter: effectiveCategory,
        series_filter: effectiveSeries,
      },
      {
        onMeta: (data) => {
          if (data.session_id && data.session_id !== sessionId) {
            setSessionId(data.session_id);
          }
        },
        onSources: (s) => setLiveSources(s),
        onToken: (t) => {
          accumulated += t;
          setStreamingAnswer(accumulated);
        },
        onSuggestions: (items) => setLiveSuggestions(items),
        onDone: ({ latency_ms }) => {
          setLiveLatency(latency_ms);
          // 백엔드가 영속화한 어시스턴트 메시지가 conversation refetch에 포함될 것
          // streamingAnswer는 baseMessages가 갱신되면 useEffect에서 자동 클리어
          qc.invalidateQueries({ queryKey: keys.conversations.all });
        },
        onError: (msg) => setStreamError(msg),
      },
    );
  };

  // baseMessages가 streamingAnswer를 포함하면 스트리밍 상태 자동 클리어
  useEffect(() => {
    if (!streamingAnswer) return;
    for (let i = baseMessages.length - 1; i >= 0; i--) {
      if (baseMessages[i].role === "assistant" && baseMessages[i].content === streamingAnswer) {
        setStreamingAnswer("");
        return;
      }
    }
  }, [baseMessages, streamingAnswer]);

  // ?ask=... 자동 질의 (도서관에서 sample question 클릭으로 들어왔을 때)
  useEffect(() => {
    if (ask && !askedRef.current && !ragStream.isPending) {
      askedRef.current = true;
      sendMessage(ask);
      setAsk(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ask, ragStream.isPending]);

  const isEmpty = !sessionId && messages.length === 0;
  const lastAssistantSuggestions =
    messages.length > 0 && messages[messages.length - 1].role === "assistant"
      ? messages[messages.length - 1].suggestions ?? []
      : [];

  // 자동 스크롤 — 사용자가 위로 올려서 읽고 있으면 방해하지 않고, 거의 하단(120px 이내)이면 따라감
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickyRef = useRef(true);
  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.clientHeight - el.scrollTop;
    stickyRef.current = distanceFromBottom < 120;
  };
  useEffect(() => {
    if (!stickyRef.current) return;
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, streamingAnswer]);
  // 사용자가 새 질문 보낼 때는 항상 하단으로 점프 (sticky 강제 활성화)
  useEffect(() => {
    if (pendingUserMessage) stickyRef.current = true;
  }, [pendingUserMessage]);

  return (
    <AppShell>
      <ScopeBanner />

      <div className="flex flex-1 min-h-0 flex-col">
        <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-3 py-4">
          <div className="max-w-4xl mx-auto">
            {isEmpty ? (
              <ScopedEmptyState onPickQuestion={(q) => sendMessage(q)} />
            ) : (
              <>
                <MessageList messages={messages} />
                {ragStream.isPending && !streamingAnswer && (
                  <div className="mt-4 text-sm text-muted-foreground italic">
                    검색 중…
                  </div>
                )}
                {!ragStream.isPending && lastAssistantSuggestions.length > 0 && (
                  <Suggestions items={lastAssistantSuggestions} onPick={sendMessage} />
                )}
                {streamError && (
                  <div className="mt-4 text-sm text-destructive">
                    오류: {streamError}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <ChatInput
          onSend={sendMessage}
          pending={ragStream.isPending}
          onCancel={ragStream.isPending ? ragStream.cancel : undefined}
          placeholder={
            docFilter
              ? "이 책에 대해 질문하세요..."
              : category !== null
                ? "이 카테고리에 대해 질문하세요..."
                : seriesFilter
                  ? "이 시리즈에 대해 질문하세요..."
                  : "문서에 대해 질문하세요..."
          }
        />
      </div>
    </AppShell>
  );
}
