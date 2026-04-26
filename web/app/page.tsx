import { redirect } from "next/navigation";

/**
 * 루트는 채팅으로 영구 리다이렉트. AppShell + 페이지 본문은 /chat에서 시작.
 */
export default function Home() {
  redirect("/chat");
}
