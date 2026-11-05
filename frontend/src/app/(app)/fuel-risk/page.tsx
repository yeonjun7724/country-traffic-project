import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { FuelRiskScreen } from "@/components/screens/fuel-risk";

export const metadata: Metadata = { title: "Fuel & Risk" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <FuelRiskScreen />
    </Suspense>
  );
}
