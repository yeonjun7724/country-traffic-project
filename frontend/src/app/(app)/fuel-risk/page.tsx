import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "Fuel & Risk" };

export default function Page() {
  return <ComingSoon navKey="fuel-risk" features={["경유가 민감도(기업 연료비)", "외부 유가·예측 (최신성 경고)", "기준 이벤트 전후 교통량", "외부 데이터 감사"]} />;
}
