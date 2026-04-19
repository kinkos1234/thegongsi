"use client";

import { useEffect, useState } from "react";

type Point = { date: string; count: number };
type Response = { days: number; series: Point[] };

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

/** 최근 N일 이상 공시 일별 리본.
 *
 * MarketAnomalies가 비었을 때 히어로 아래에 조용히 노출되는 "시장 맥박".
 * 날짜 × count 세로 막대. count 0 = 얇은 선. 최고치 = 풀 높이.
 * 회색 톤으로 눈 방해 안 함. 호버 시 날짜·건수 툴팁.
 */
export function PulseRibbon({ days = 30 }: { days?: number }) {
  const [data, setData] = useState<Response | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    fetch(`${API}/api/stats/pulse?days=${days}`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setErr(true));
    return () => ctl.abort();
  }, [days]);

  if (err || !data) return null;

  // 날짜 윈도우 생성 (빈 날도 0으로 채움). 키는 YYYYMMDD로 정규화.
  const windowDays: Point[] = [];
  const today = new Date();
  const byDate = new Map(data.series.map((p) => [normalize(p.date), p.count]));
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const iso = d.toISOString().slice(0, 10).replace(/-/g, "");
    windowDays.push({ date: iso, count: byDate.get(iso) ?? 0 });
  }
  // normalize는 YYYY-MM-DD 및 YYYYMMDD 양쪽 받음
  const max = Math.max(1, ...windowDays.map((p) => p.count));
  const total = windowDays.reduce((acc, p) => acc + p.count, 0);

  if (total === 0) return null;

  const todayIdx = windowDays.length - 1;
  const todayCount = windowDays[todayIdx].count;
  const avg = total / windowDays.length;
  const peak = windowDays.reduce(
    (best, p, i) => (p.count > best.count ? { count: p.count, i } : best),
    { count: -1, i: 0 },
  );
  const ribbonH = 80;
  const activeDays = windowDays.filter((p) => p.count > 0).length;

  return (
    <section className="mt-8" aria-label={`최근 ${days}일 이상 공시 맥박`}>
      <div className="flex items-baseline justify-between mb-3 gap-4 flex-wrap">
        <p className="mono text-[11px] text-fg-3 tracking-[0.15em] uppercase">
          최근 {days}일 시장 맥박 · high+med
        </p>
        <p className="mono text-[11px] text-fg-3 tabular-nums">
          총 {total.toLocaleString("ko-KR")}건 · 일평균 {avg.toFixed(1)} · max {max} · 활동 {activeDays}/{days}일
        </p>
      </div>
      <div
        role="img"
        aria-label={`최근 ${days}일간 이상 공시 일별 건수. 총 ${total}건, 최대 ${max}건, 활동 ${activeDays}일.`}
        className="flex items-end gap-[2px] border-b border-border/50 relative"
        style={{ height: `${ribbonH}px` }}
      >
        {/* 평균 라인 — 일평균이 1 이상일 때만 (너무 낮으면 bottom에 겹쳐서 무의미) */}
        {avg >= 1 && (
          <span
            className="absolute inset-x-0 border-t border-dashed border-fg-3/30 pointer-events-none"
            style={{ bottom: `${(avg / max) * (ribbonH - 4)}px` }}
            aria-hidden="true"
          />
        )}
        {windowDays.map((p, i) => {
          const ratio = p.count / max;
          const h = Math.max(2, Math.round(ratio * (ribbonH - 4)));
          const isToday = i === todayIdx;
          const isPeak = i === peak.i && peak.count > 0;
          // Peak 우선, 그 다음 오늘(count>0 일 때만), 그 다음 일반/빈날.
          // 오늘이 0건이면 bar 자체는 회색으로 — 대신 오늘 위치는 아래 점선 마커로 표시.
          const bg = isPeak
            ? "bg-sev-high"
            : isToday && p.count > 0
            ? "bg-accent"
            : p.count > 0
            ? "bg-fg-2 hover:bg-accent"
            : "bg-border";
          return (
            <span
              key={p.date}
              title={`${formatDate(p.date)} · ${p.count}건${isToday ? " · 오늘" : ""}${isPeak ? " · 최대" : ""}`}
              className={`flex-1 min-w-[3px] ${bg} transition-colors relative`}
              style={{ height: `${h}px` }}
            >
              {/* 오늘 위치 마커 — bar 상단에서 리본 top 까지 점선 수직선으로 연결,
                  count 0 일 때도 "오늘 여기" 가 시각적으로 식별 가능 */}
              {isToday && (
                <span
                  aria-hidden="true"
                  className="absolute left-1/2 -translate-x-1/2 bottom-full border-l border-dashed border-accent/70 pointer-events-none"
                  style={{ height: `${ribbonH - h}px` }}
                />
              )}
            </span>
          );
        })}
      </div>
      {/* 축 라벨 — 시작일 · 오늘(건수 명시). 중간 max 레이블은 상단 meta 로 이동. */}
      <div className="flex justify-between mt-1.5">
        <span className="mono text-[10px] text-fg-3">
          {formatDate(windowDays[0].date)}
        </span>
        <span className="mono text-[10px] text-accent tabular-nums">
          {formatDate(windowDays[todayIdx].date)} · 오늘 {todayCount}건
        </span>
      </div>
    </section>
  );
}

function normalize(s: string): string {
  // YYYYMMDD 또는 YYYY-MM-DD 입력을 YYYYMMDD로 정규화
  return s.replace(/-/g, "").slice(0, 8);
}

function formatDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`;
}
