"use client";

/**
 * TASK-024: RAG SSE 스트리밍 hook.
 *
 * fetch + ReadableStream을 사용 (EventSource는 POST 미지원·헤더 자유도 낮음).
 * 이벤트:
 *   meta        → {session_id}
 *   sources     → SourceItem[]
 *   token       → string  (반복)
 *   suggestions → string[]
 *   done        → {latency_ms}
 *   error       → {message}
 *
 * 호출자는 콜백으로 각 이벤트를 처리. AbortController로 사용자 측 중단 가능.
 */
import { useCallback, useRef, useState } from "react";
import { apiBaseUrl } from "@/lib/api/client";
import type { QueryRequest, SourceItem } from "@/lib/api/types";

export type StreamHandlers = {
  onMeta?: (data: { session_id: string }) => void;
  onSources?: (sources: SourceItem[]) => void;
  onToken?: (text: string) => void;
  onSuggestions?: (items: string[]) => void;
  onDone?: (data: { latency_ms?: number }) => void;
  onError?: (message: string) => void;
};

export function useRagStream() {
  const [isPending, setIsPending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsPending(false);
  }, []);

  const send = useCallback(async (req: QueryRequest, handlers: StreamHandlers) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsPending(true);

    try {
      const res = await fetch(`${apiBaseUrl}/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        const text = await res.text().catch(() => res.statusText);
        handlers.onError?.(text || `HTTP ${res.status}`);
        return;
      }

      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";

      // SSE 파서 — 빈 줄(\n\n) 단위로 이벤트 분할
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;

        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          let event = "message";
          const dataLines: string[] = [];
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
          }
          if (dataLines.length === 0) continue;
          let data: unknown;
          try {
            data = JSON.parse(dataLines.join("\n"));
          } catch {
            continue;
          }

          switch (event) {
            case "meta":
              handlers.onMeta?.(data as { session_id: string });
              break;
            case "sources":
              handlers.onSources?.(data as SourceItem[]);
              break;
            case "token":
              if (typeof data === "string") handlers.onToken?.(data);
              break;
            case "suggestions":
              handlers.onSuggestions?.(data as string[]);
              break;
            case "done":
              handlers.onDone?.(data as { latency_ms?: number });
              break;
            case "error":
              handlers.onError?.((data as { message: string }).message);
              break;
          }
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      handlers.onError?.((e as Error).message);
    } finally {
      setIsPending(false);
      abortRef.current = null;
    }
  }, []);

  return { send, cancel, isPending };
}
