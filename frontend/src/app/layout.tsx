import type { Metadata } from "next";
import { NavBar } from "@/components/NavBar";
import { MobileTabBar } from "@/components/MobileTabBar";
import { ConventionOnboarding } from "@/components/ConventionOnboarding";
import { EditorialMasthead } from "@/components/EditorialMasthead";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Gongsi · 더공시 — DART-native AI 주식 리서치",
  description: "Korean disclosures, deciphered. DART 공시 + GraphRAG + DD 메모. 오픈소스 AI 리서치 터미널.",
};

// FOUC/하이드레이션 방지 — HTML 파싱 직후 테마·컨벤션 즉시 적용.
// 테마 저장 없으면 prefers-color-scheme 존중. 컨벤션 저장 없으면 us(초록=상승) 기본.
const THEME_INIT_SCRIPT = `
(function() {
  try {
    var saved = localStorage.getItem('comad_stock_theme');
    var prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
    var theme = saved || (prefersLight ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
    var conv = localStorage.getItem('comad_stock_convention') || 'us';
    document.documentElement.setAttribute('data-convention', conv);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
    document.documentElement.setAttribute('data-convention', 'us');
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.css"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=EB+Garamond:wght@500;600&family=Gowun+Batang:wght@400;700&family=Hahmlet:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
        />
      </head>
      <body className="pb-16 md:pb-0">
        <EditorialMasthead />
        <NavBar />
        {children}
        <MobileTabBar />
        <ConventionOnboarding />
      </body>
    </html>
  );
}
