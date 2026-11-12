/** 일별 차트 범례 — 차트(recharts)와 분리해 차트를 지연 로딩해도 섹션 머리글은 바로 보이게 */
export function DailyLegend() {
  return (
    <div className="flex items-center gap-3 text-small text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-chart-1/75" /> 운송비
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-3 rounded bg-chart-2" /> 지연율
      </span>
    </div>
  );
}
