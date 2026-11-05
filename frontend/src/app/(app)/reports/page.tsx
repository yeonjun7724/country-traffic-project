import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "Reports & Alerts" };

export default function Page() {
  return <ComingSoon navKey="reports" features={["Excel 리포트", "경영진 요약 (PDF 인쇄)", "알림 규칙 설정", "조치 워크플로"]} />;
}
