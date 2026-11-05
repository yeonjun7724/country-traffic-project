import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "Transportation" };

export default function Page() {
  return <ComingSoon navKey="transportation" features={["Cost-to-Serve 상세", "연료비·연비 분석", "CVRP 배송 계획 대안", "현행 배차와 비교", "미배정 사유", "승인 요청 저장 (배차 확정 아님)"]} />;
}
