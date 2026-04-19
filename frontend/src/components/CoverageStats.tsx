"use client";

import { useEffect, useState } from "react";

type Stats = {
  disclosures?: number;
  companies?: number;
  anomalies_7d?: number;
  since?: string | null;
  daily_avg?: number | null;
  updated_at?: string;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

function formatK(n: number | undefined): string {
  if (n === undefined || n === null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}K`;
  return n.toLocaleString("ko-KR");
}

export function CoverageStats() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    fetch(`${API}/api/stats/coverage`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setStats)
      .catch(() => setErr(true));
    return () => ctl.abort();
  }, []);

  if (err) return null;

  const hint = buildHint(stats);

  return (
    <section className="mt-10 border-t border-border/50 pt-6">
      <dl className="grid grid-cols-3 gap-4">
        <StatCell label="누적 공시" value={formatK(stats?.disclosures)} />
        <StatCell
          label="커버리지"
          value={stats?.companies !== undefined ? `${formatK(stats.companies)}사` : "—"}
        />
        <StatCell
          label="7일 이상"
          value={
            stats?.anomalies_7d !== undefined
              ? `${formatK(stats.anomalies_7d)}건`
              : "—"
          }
        />
      </dl>
      {hint && (
        <p className="mono text-[11px] text-fg-3 mt-3 tracking-wider">{hint}</p>
      )}
    </section>
  );
}

function buildHint(s: Stats | null): string | null {
  if (!s) return null;
  const parts: string[] = [];
  if (s.since) parts.push(`since ${s.since}`);
  if (s.daily_avg) parts.push(`일평균 ${s.daily_avg.toLocaleString("ko-KR")}건`);
  parts.push("KOSPI · KOSDAQ");
  return parts.join(" · ");
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="mono text-[10px] sm:text-[11px] text-fg-3 uppercase tracking-[0.15em]">
        {label}
      </dt>
      <dd className="mono mt-1.5 text-[18px] sm:text-[22px] text-fg tabular-nums">
        {value}
      </dd>
    </div>
  );
}
