import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { DataHub } from "@/components/data-hub/data-hub";

export const metadata: Metadata = { title: "Data Hub" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <DataHub />
    </Suspense>
  );
}
