"use client";

import { useEffect, useState } from "react";

type Point = { date: string; ratio: number | null; volume: number | null };
type Response = { ticker: string; days: number; series: Point[] };

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

/** 공매도 비중 리본 — 한국 시장 고유 시각 언어.
 *
 * 30일 시계열을 얇은 가로 리본으로 압축. 각 날짜는 비중(0~1)에 비례한 색 농도 셀.
 * 전체 평균 이상인 날은 accent, 이하는 fg-2 계조. 오늘 이상치는 sev-high.
 * 큰 차트 대신 "한 줄 요약" — 공시 리서치 흐름을 방해하지 않는 미세 정보 레이어.
 */
export function ShortSellingRibbon({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Response | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    fetch(`${API}/api/companies/${ticker}/short-selling?days=30`, {
      signal: ctl.signal,
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setErr(true));
    return () => ctl.abort();
  }, [ticker]);

  if (err || !data || data.series.length === 0) return null;

  const ratios = data.series
    .map((p) => (p.ratio ?? 0) as number)
    .filter((r) => r > 0);
  if (ratios.length === 0) return null;

  const avg = ratios.reduce((a, b) => a + b, 0) / ratios.length;
  const max = Math.max(...ratios);
  const latest = data.series[data.series.length - 1];
  const latestRatio = latest?.ratio ?? null;
  const latestPct = latestRatio !== null ? (latestRatio * 100).toFixed(2) : "—";
  const avgPct = (avg * 100).toFixed(2);
  const deviation = latestRatio !== null ? (latestRatio - avg) / avg : 0;
  const elevated = latestRatio !== null && latestRatio > avg * 1.3;

  return (
    <section className="mt-6 border border-border/40 bg-bg-2/40 px-4 py-3">
      <div className="flex items-baseline justify-between mb-2">
        <p className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em]">
          공매도 비중 · 30일
        </p>
        <p className="mono text-[11px] tabular-nums">
          <span className={elevated ? "text-sev-high" : "text-fg"}>{latestPct}%</span>
          <span className="text-fg-3">
            {" "}
            · 평균 {avgPct}%{" "}
            {latestRatio !== null && (
              <>
                ({deviation >= 0 ? "+" : ""}
                {(deviation * 100).toFixed(0)}%)
              </>
            )}
          </span>
        </p>
      </div>
      <div
        role="img"
        aria-label={`최근 30일 공매도 비중. 최근 ${latestPct}%, 평균 ${avgPct}%.`}
        className="flex items-stretch gap-[2px] h-[12px]"
      >
        {data.series.map((p) => {
          const r = (p.ratio ?? 0) as number;
          const isElevated = r > avg * 1.3;
          const isAboveAvg = r >= avg;
          const opacity = max > 0 ? Math.max(0.15, r / max) : 0.15;
          const bg = isElevated
            ? "bg-sev-high"
            : isAboveAvg
            ? "bg-accent"
            : "bg-fg-2";
          return (
            <span
              key={p.date}
              title={`${p.date} · ${(r * 100).toFixed(2)}%`}
              className={`flex-1 min-w-[3px] ${bg} transition-opacity`}
              style={{ opacity }}
            />
          );
        })}
      </div>
      <p className="mono text-[10px] text-fg-3 mt-2 tracking-wider">
        KRX 공매도 통계 · 평균 대비 +30% 초과 시 sev-high 하이라이트
      </p>
    </section>
  );
}
