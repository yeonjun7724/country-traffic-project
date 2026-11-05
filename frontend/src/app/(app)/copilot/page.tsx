import type { Metadata } from "next";

import { ComingSoon } from "@/components/app/coming-soon";

export const metadata: Metadata = { title: "AI Copilot" };

export default function Page() {
  return <ComingSoon navKey="copilot" features={["읽기 전용 분석 도구 12종", "근거 도구 결과 표시", "키 없음·오류 시 규칙 기반 폴백", "도구 단계 스트리밍"]} />;
}
