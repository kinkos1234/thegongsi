"use client";

import { useEffect, useState } from "react";

type Coverage = {
  disclosures?: number;
  anomalies_7d?: number;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

function isoWeek(d: Date): { year: number; week: number } {
  // ISO 8601 week number
  const target = new Date(d.valueOf());
  const dayNr = (d.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNr + 3);
  const firstThursday = target.valueOf();
  target.setUTCMonth(0, 1);
  if (target.getUTCDay() !== 4) {
    target.setUTCMonth(0, 1 + ((4 - target.getUTCDay()) + 7) % 7);
  }
  const week = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
  return { year: d.getUTCFullYear(), week };
}

function kstNow(): { date: string; time: string } {
  const now = new Date();
  const kstMs = now.getTime() + 9 * 3600 * 1000 - now.getTimezoneOffset() * 60 * 1000;
  const k = new Date(kstMs);
  const y = k.getUTCFullYear();
  const m = String(k.getUTCMonth() + 1).padStart(2, "0");
  const d = String(k.getUTCDate()).padStart(2, "0");
  const hh = String(k.getUTCHours()).padStart(2, "0");
  const mm = String(k.getUTCMinutes()).padStart(2, "0");
  return { date: `${y}-${m}-${d}`, time: `${hh}:${mm}` };
}

/** 정기간행물 스타일 얇은 바 — Financial Times / NYT 마스트헤드 오마주.
 *
 * VOL · ISO 주차 · KST 타임스탬프 · 오늘 수집 공시 수. 한국 리서치 저널 톤.
 */
export function EditorialMasthead() {
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [now, setNow] = useState(() => kstNow());

  useEffect(() => {
    // 1분마다 시계 갱신
    const tick = setInterval(() => setNow(kstNow()), 60_000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    fetch(`${API}/api/stats/coverage`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setCoverage)
      .catch(() => {});
    return () => ctl.abort();
  }, []);

  const today = new Date();
  const { year, week } = isoWeek(today);
  const weekLabel = `VOL.${year} · W${String(week).padStart(2, "0")}`;

  return (
    <div className="border-b border-border/60 bg-bg-2/40">
      <div className="mx-auto max-w-[1280px] px-6 sm:px-8 py-2 flex flex-wrap items-center justify-between gap-x-6 gap-y-1 text-[11px]">
        <div className="flex items-center gap-4">
          <span className="mono text-fg-2 tracking-[0.15em]">{weekLabel}</span>
          <span className="mono text-fg-3 tracking-wider hidden sm:inline">
            KST {now.date} {now.time}
          </span>
        </div>
        <div className="mono text-fg-3 tracking-wider flex items-center gap-4">
          {coverage?.anomalies_7d !== undefined && coverage.anomalies_7d > 0 && (
            <span>
              <span className="text-sev-high">●</span>{" "}
              7d 이상 {coverage.anomalies_7d.toLocaleString("ko-KR")}건
            </span>
          )}
          <span className="hidden md:inline">dart-native · editorial</span>
        </div>
      </div>
    </div>
  );
}
