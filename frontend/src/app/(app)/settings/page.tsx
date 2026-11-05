import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return <ComingSoon navKey="settings" features={["KPI 목표", "사용자·권한", "시스템 상태", "감사 로그"]} />;
}
