import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { TransportationScreen } from "@/components/screens/transportation";

export const metadata: Metadata = { title: "Transportation" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <TransportationScreen />
    </Suspense>
  );
}
