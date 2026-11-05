import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { CopilotScreen } from "@/components/screens/copilot";

export const metadata: Metadata = { title: "AI Copilot" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <CopilotScreen />
    </Suspense>
  );
}
