"use client";

import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";

type Point = { d: string; c: number };

export function Sparkline({ data, up }: { data: Point[]; up: boolean }) {
  if (!data || data.length === 0) return <div className="h-[160px] text-fg-3 flex items-center">데이터 없음</div>;

  const closes = data.map((p) => p.c);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const isHalted = min === max;  // 전 기간 동일가 = 거래정지 의심

  if (isHalted) {
    return (
      <div className="h-[160px] border border-sev-med/30 bg-bg-2 flex flex-col items-center justify-center gap-2">
        <p className="mono text-[12px] text-sev-med uppercase tracking-wider">거래정지 의심</p>
        <p className="text-[13px] text-fg-2">
          최근 {data.length}거래일 가격 변동 없음 ({min.toLocaleString("ko-KR")}원 고정)
        </p>
      </div>
    );
  }

  // CSS var는 Recharts SVG attribute에 바로 안 먹을 수 있어 실 computed 값 resolution.
  // theme 토글 시 data-theme 변경 감지해 rerender.
  const [theme, setTheme] = useState(0);
  useEffect(() => {
    const obs = new MutationObserver(() => setTheme((t) => t + 1));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  const rootStyle =
    typeof window !== "undefined" ? getComputedStyle(document.documentElement) : null;
  const accentColor = rootStyle?.getPropertyValue("--color-accent").trim() || "#4ADE80";
  const downColor = rootStyle?.getPropertyValue("--color-down").trim() || "#A3A3A3";
  const color = up ? accentColor : downColor;
  void theme; // force re-read on theme change
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
