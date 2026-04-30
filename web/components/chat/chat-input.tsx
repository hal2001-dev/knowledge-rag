"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Send, Loader2, X } from "lucide-react";

export function ChatInput({
  onSend,
  pending,
  disabled,
  onCancel,
  placeholder = "문서에 대해 질문하세요...",
}: {
  onSend: (text: string) => void;
  pending: boolean;
  disabled?: boolean;
  onCancel?: () => void;
  placeholder?: string;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // textarea 자동 높이 (1~6 lines)
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || pending) return;
    onSend(text);
    setValue("");
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-border bg-background p-3">
      <div className="flex items-end gap-2 max-w-4xl mx-auto">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          disabled={disabled || pending}
          rows={1}
          className="flex-1 min-h-[40px] max-h-[200px] resize-none rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {pending && onCancel ? (
          <Button
            onClick={onCancel}
            size="icon"
            variant="destructive"
            aria-label="중지"
            title="응답 중지"
          >
            <X className="size-4" />
          </Button>
        ) : (
          <Button
            onClick={submit}
            disabled={disabled || pending || !value.trim()}
            size="icon"
            aria-label="보내기"
          >
            {pending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          </Button>
        )}
      </div>
    </div>
  );
}
