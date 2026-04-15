"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";

type Point = { d: string; c: number };

export function Sparkline({ data, up }: { data: Point[]; up: boolean }) {
  if (!data || data.length === 0) return <div className="h-[160px] text-fg-3 flex items-center">데이터 없음</div>;
  const color = up ? "var(--color-accent)" : "var(--color-down)";
  const min = Math.min(...data.map((p) => p.c));
  const max = Math.max(...data.map((p) => p.c));
  return (
    <div className="h-[160px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
          <YAxis hide domain={[min * 0.995, max * 1.005]} />
          <Tooltip
            contentStyle={{
              background: "var(--color-bg-2)",
              border: "1px solid var(--color-border)",
              borderRadius: 0,
              fontFamily: "var(--font-mono)",
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--color-fg-3)" }}
            itemStyle={{ color: "var(--color-fg)" }}
            formatter={(v: number) => [v.toLocaleString("ko-KR"), "close"]}
            labelFormatter={(l) => l}
          />
          <Line type="monotone" dataKey="c" stroke={color} dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
