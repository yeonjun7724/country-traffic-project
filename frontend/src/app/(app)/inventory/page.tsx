import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { InventoryScreen } from "@/components/screens/inventory";

export const metadata: Metadata = { title: "Demand & Inventory" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <InventoryScreen />
    </Suspense>
  );
}
