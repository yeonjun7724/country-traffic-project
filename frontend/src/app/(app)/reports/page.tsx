import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { ReportsScreen } from "@/components/screens/reports";

export const metadata: Metadata = { title: "Reports & Alerts" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ReportsScreen />
    </Suspense>
  );
}
