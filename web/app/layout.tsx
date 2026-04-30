import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { AUTH_ENABLED } from "@/lib/auth-flag";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: process.env.NEXT_PUBLIC_APP_NAME ?? "Knowledge RAG",
  description: "사용자 측 RAG 채팅 + 도서관 (관리자 화면은 Streamlit 8501)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const tree = (
    <html
      lang="ko"
      className={`${geistSans.variable} ${geistMono.variable} h-full overflow-hidden antialiased`}
    >
      <body className="h-full flex flex-col bg-background text-foreground overflow-hidden">
        <Providers>{children}</Providers>
      </body>
    </html>
  );

  return AUTH_ENABLED ? <ClerkProvider>{tree}</ClerkProvider> : tree;
}
