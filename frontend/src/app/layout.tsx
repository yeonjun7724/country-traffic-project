import type { Metadata, Viewport } from "next";

import { Providers } from "@/components/providers";
import { preloadScript } from "@/lib/preload";

import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "LogisRisk", template: "%s · LogisRisk" },
  description: "물류·유통 운영 분석 플랫폼 — KPI·운송비·배차·재고·시나리오",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafc" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1117" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        {/* 첫 페인트 전: 마지막으로 확인한 '샘플 워크스페이스 여부'로 배너 자리를 미리 잡는다 (배너가 늦게 끼어들며 화면이 밀리던 CLS).
            값이 없으면 서버 기본 워크스페이스(샘플)로 가정. 실제 표시는 /api/me 응답이 최종 결정한다. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var w=localStorage.getItem("lr.workspace")||"_default";var m=JSON.parse(localStorage.getItem("lr.demoByWs")||"{}");document.documentElement.dataset.demo=(w in m?m[w]:true)?"1":"0"}catch(e){document.documentElement.dataset.demo="1"}`,
          }}
        />
        {/* 첫 화면 데이터 선요청 (lib/preload) — JS 를 받는 동안 API 를 미리 부른다 */}
        <script dangerouslySetInnerHTML={{ __html: preloadScript(process.env.NEXT_PUBLIC_API_BASE ?? "") }} />
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
          crossOrigin="anonymous"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
