"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useConversations, useDeleteConversation } from "@/lib/hooks/use-conversations";
import { UserButton } from "@clerk/nextjs";
import { AUTH_ENABLED } from "@/lib/auth-flag";
import { BookOpen, Plus, Trash2 } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";
import { format } from "date-fns";

/**
 * 좌측 사이드바: ＋ 새 대화 / 대화 목록 (자기 user_id) / 📚 도서관 링크 / UserButton.
 */
export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeSession = searchParams.get("session_id");
  const conversationsQuery = useConversations();
  const deleteMut = useDeleteConversation();

  const handleNewChat = () => {
    router.push("/chat");
    onNavigate?.();
  };

  const handlePickSession = (sid: string) => {
    router.push(`/chat?session_id=${sid}`);
    onNavigate?.();
  };

  return (
    <div className="flex flex-1 min-h-0 min-w-0 flex-col">
      {/* 새 대화 */}
      <div className="p-3">
        <Button onClick={handleNewChat} className="w-full justify-start" variant="default">
          <Plus className="mr-2 size-4" /> 새 대화
        </Button>
      </div>
      <Separator />

      {/* 대화 목록 — 일반 overflow-y-auto (Radix ScrollArea는 viewport가 display:table로 동작해 truncate를 깨뜨림) */}
      <div className="flex-1 overflow-y-auto min-w-0">
        <div className="p-2 text-xs text-muted-foreground">대화 목록</div>
        {conversationsQuery.isLoading && (
          <div className="px-3 text-sm text-muted-foreground">로딩…</div>
        )}
        {conversationsQuery.isError && (
          <div className="px-3 text-sm text-destructive">대화 목록을 불러올 수 없습니다.</div>
        )}
        {conversationsQuery.data?.conversations?.length === 0 && (
          <div className="px-3 text-sm text-muted-foreground">아직 대화가 없습니다.</div>
        )}
        <ul className="px-2 pb-2 space-y-0.5">
          {conversationsQuery.data?.conversations?.map((c) => {
            const sid = c.session_id;
            const isActive = activeSession === sid;
            const label = c.title || "(제목 없음)";
            const updated = c.updated_at ? format(new Date(c.updated_at), "MM-dd HH:mm") : "";
            return (
              <li key={sid} className="group relative">
                <button
                  className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                    isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/50"
                  }`}
                  onClick={() => handlePickSession(sid)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="truncate">{label}</div>
                    <div className="text-[10px] text-muted-foreground">{updated}</div>
                  </div>
                </button>
                <button
                  aria-label="대화 삭제"
                  className="absolute right-1 top-1 rounded p-1 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-destructive/20"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`"${label}" 대화를 삭제할까요?`)) {
                      deleteMut.mutate(sid);
                      if (isActive) router.push("/chat");
                    }
                  }}
                >
                  <Trash2 className="size-3.5 text-muted-foreground" />
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <Separator />

      {/* 도서관 링크 + UserButton */}
      <div className="p-3 space-y-2">
        <Link
          href="/library"
          onClick={onNavigate}
          className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
            pathname === "/library" ? "bg-accent text-accent-foreground" : "hover:bg-accent/50"
          }`}
        >
          <BookOpen className="size-4" /> 도서관
        </Link>
        {AUTH_ENABLED && (
          <>
            <Separator />
            <div className="flex items-center justify-between gap-2 px-1">
              <UserButton />
              <span className="text-xs text-muted-foreground">로그아웃은 아바타 메뉴에서</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
