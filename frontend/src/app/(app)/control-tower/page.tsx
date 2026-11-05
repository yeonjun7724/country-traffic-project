import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { ControlTower } from "@/components/control-tower/control-tower";

export const metadata: Metadata = { title: "Control Tower" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ControlTower />
    </Suspense>
  );
}
