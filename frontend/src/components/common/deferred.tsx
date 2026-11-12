"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * 화면에 가까워질 때만 렌더 (첫 화면 메인 스레드·API 호출 절약).
 * - 자리(minHeight)를 실제 높이와 같게 잡아 렌더 시 화면이 밀리지 않게 한다.
 * - id 를 주면 렌더 전에도 같은 id 를 자리 표시자가 가진다 → `#id` 링크로 들어오면 즉시 렌더하고 그 위치로 스크롤된다.
 * - threshold 는 '얼마나 보여야' 렌더할지 (지도처럼 무거운 것은 0.5 — 첫 화면 가장자리에 살짝 걸친 상태로는 불러오지 않음).
 */
export function Deferred({
  children,
  minHeight,
  id,
  className,
  rootMargin = "300px 0px",
  threshold = 0,
  placeholder,
  label = "아래 내용",
}: {
  children: ReactNode;
  minHeight: number;
  id?: string;
  className?: string;
  rootMargin?: string;
  threshold?: number;
  placeholder?: ReactNode;
  /** 자리 표시자의 접근 가능한 이름 */
  label?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (show) return;
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") return setShow(true);
    const byHash = () => {
      if (id && window.location.hash === `#${id}`) setShow(true);
    };
    byHash();
    window.addEventListener("hashchange", byHash);
    const io = new IntersectionObserver(
      (es) => {
        if (es.some((e) => e.isIntersecting && e.intersectionRatio >= threshold)) setShow(true);
      },
      { rootMargin: threshold > 0 ? "0px" : rootMargin, threshold: threshold > 0 ? [threshold] : [0] },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      window.removeEventListener("hashchange", byHash);
    };
  }, [show, id, rootMargin, threshold]);

  if (show) return <>{children}</>;
  return (
    <div ref={ref} id={id} className={cn("scroll-mt-28", className)} style={{ minHeight }} aria-busy="true" aria-label={`${label} 불러오기 대기`}>
      {placeholder ?? <Skeleton className="rounded-xl" style={{ height: minHeight }} />}
    </div>
  );
}
