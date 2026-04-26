"use client";

import { Button } from "@/components/ui/button";

export function Suggestions({
  items,
  onPick,
}: {
  items: string[];
  onPick: (q: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="mt-2">
      <div className="text-xs text-muted-foreground mb-1">💡 이어서 물을 질문</div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((s, i) => (
          <Button
            key={i}
            size="sm"
            variant="secondary"
            className="h-auto whitespace-normal text-left text-xs leading-snug py-1.5"
            onClick={() => onPick(s)}
          >
            {s}
          </Button>
        ))}
      </div>
    </div>
  );
}
