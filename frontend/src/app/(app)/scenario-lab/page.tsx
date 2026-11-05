import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { ScenarioLabScreen } from "@/components/screens/scenario-lab";

export const metadata: Metadata = { title: "Scenario Lab" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ScenarioLabScreen />
    </Suspense>
  );
}
