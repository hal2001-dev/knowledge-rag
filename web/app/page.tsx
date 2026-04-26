/**
 * Phase A 스텁 — Phase B에서 AppShell + /chat 본격 구현 시 redirect로 교체.
 * 현재는 Clerk 인증 + Provider 동작 검증용 placeholder.
 */
import { UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-2xl font-semibold">📚 Knowledge RAG</h1>
      <p className="text-sm text-muted-foreground">
        Phase A 셋업 완료. AppShell + /chat 구현은 Phase B.
      </p>
      <UserButton />
    </main>
  );
}
