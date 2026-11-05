import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "Scenario Lab" };

export default function Page() {
  return <ComingSoon navKey="scenario-lab" features={["Baseline·A·B 비교", "원인 기여도(워터폴)", "민감도 분석", "센터 중단 분석", "저장·복제·승인", "Excel 내보내기"]} />;
}
