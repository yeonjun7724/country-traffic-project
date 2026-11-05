"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { BrandMark } from "@/components/app/brand";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(`/control-tower/${window.location.search}`);
  }, [router]);
  return (
    <div className="flex min-h-svh items-center justify-center bg-canvas">
      <BrandMark className="size-10 animate-pulse" />
    </div>
  );
}
