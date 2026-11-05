import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "Demand & Inventory" };

export default function Page() {
  return <ComingSoon navKey="inventory" features={["안전재고·재주문점", "보충 추천과 근거", "수요예측 모델 백테스트", "WAPE·MAE·Bias·MAPE", "보충 추천 CSV"]} />;
}
