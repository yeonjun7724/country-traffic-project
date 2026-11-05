"use client";

import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Schemas } from "@/lib/api";
import { dateLabel, isNum, pct, shortDate, won } from "@/lib/format";

type Point = Schemas["DailyPoint"];

/** 일별 운송비(막대, 좌축) + 지연율(선, 우축). 범례는 차트 밖 헤더에 — 제목·축과 겹치지 않게. */
export function DailyChart({ data, height = 260 }: { data: Point[]; height?: number }) {
  return (
    <div style={{ height }} className="w-full" role="img" aria-label="일별 운송비와 지연율 추이 차트">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 4 }} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }}
            minTickGap={24}
            tickMargin={8}
          />
          <YAxis
            yAxisId="cost"
            tickFormatter={(v) => (v === 0 ? "0" : won(v))}
            tickLine={false}
            axisLine={false}
            width={44}
            tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }}
          />
          <YAxis
            yAxisId="late"
            orientation="right"
            tickFormatter={(v) => pct(v, 0)}
            tickLine={false}
            axisLine={false}
            width={38}
            domain={[0, (max: number) => Math.max(0.1, Math.ceil(max * 10) / 10)]}
            tick={{ fontSize: 11, fill: "var(--subtle-foreground)" }}
          />
          <Tooltip cursor={{ fill: "var(--muted)", opacity: 0.6 }} content={<Tip />} />
          <Bar yAxisId="cost" dataKey="cost" fill="var(--chart-1)" fillOpacity={0.75} radius={[3, 3, 0, 0]} maxBarSize={22} />
          <Line
            yAxisId="late"
            dataKey="late_rate"
            stroke="var(--chart-2)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DailyLegend() {
  return (
    <div className="flex items-center gap-3 text-[11.5px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-chart-1/75" /> 운송비
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-3 rounded bg-chart-2" /> 지연율
      </span>
    </div>
  );
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="min-w-40 rounded-lg border border-border bg-popover px-3 py-2 text-[12px] shadow-lg">
      <div className="mb-1 font-medium">{dateLabel(p.date)}</div>
      <Row k="운송비" v={isNum(p.cost) ? `${won(p.cost, { compact: false })}원` : "—"} dot="bg-chart-1" />
      <Row k="배송" v={`${p.shipments.toLocaleString()}건`} />
      <Row k="지연율" v={isNum(p.late_rate) ? pct(p.late_rate) : "판정 불가"} dot="bg-chart-2" />
    </div>
  );
}

function Row({ k, v, dot }: { k: string; v: string; dot?: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        {dot && <span className={`size-2 rounded-full ${dot}`} />}
        {k}
      </span>
      <span className="font-medium tabular">{v}</span>
    </div>
  );
}
