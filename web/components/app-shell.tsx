"use client";

/**
 * AppShell — 상단 카테고리 칩(데스크톱 헤더) + 좌측 사이드바(드로어 모바일) + 메인.
 * Phase B 진입의 뼈대. 자식 컴포넌트는 후속 단계에서 채움.
 */
import { useState } from "react";
import Link from "next/link";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";
import { Sidebar } from "./sidebar";
import { HeaderCategories } from "./header-categories";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex flex-1 min-h-0 flex-col">
      {/* 상단 헤더 — 앱명 + 카테고리 칩 (데스크톱) */}
      <header className="flex items-center gap-3 border-b border-border bg-background/80 backdrop-blur px-3 py-2 md:px-4">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          aria-label="사이드바 열기"
          onClick={() => setMobileOpen(true)}
        >
          <Menu className="size-4" />
        </Button>
        <Link href="/chat" className="font-semibold whitespace-nowrap">
          📚 Knowledge RAG
        </Link>
        <div className="flex-1 min-w-0 overflow-x-auto">
          <HeaderCategories />
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* 사이드바 — 데스크톱 펼침, 모바일 drawer */}
        <aside className="hidden md:flex w-64 shrink-0 border-r border-border">
          <Sidebar />
        </aside>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-72 p-0">
            <SheetTitle className="sr-only">사이드바</SheetTitle>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>

        {/* 메인 */}
        <main className="flex flex-1 min-w-0 flex-col">
          {children}
        </main>
      </div>
    </div>
  );
}
