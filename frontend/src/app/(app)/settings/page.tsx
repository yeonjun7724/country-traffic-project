import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/app/app-shell";
import { SettingsScreen } from "@/components/screens/settings";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <SettingsScreen />
    </Suspense>
  );
}
