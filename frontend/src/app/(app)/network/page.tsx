import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "Network Intelligence" };

export default function Page() {
  return <ComingSoon navKey="network" features={["영업소 위험 레이어(등급·LISA)", "센터·배송지·배송 밀도 레이어", "가중치 재계산 + 시나리오 ID 저장", "센터 주변 고위험 영업소", "영업소 위험 CSV"]} />;
}
