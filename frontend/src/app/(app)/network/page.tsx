import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { NetworkScreen } from "@/components/screens/network";

export const metadata: Metadata = { title: "Network Intelligence" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <NetworkScreen />
    </Suspense>
  );
}
