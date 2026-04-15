"use client";

import { useEffect, useState } from "react";

type Item = { rcept_no: string; title: string; date: string; severity: "high" | "med" };
type Summary = { count: number; high: number; med: number; items: Item[] };

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export function TodayAnomalies({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Summary | null>(null);

  useEffect(() => {
    fetch(`${API}/api/companies/${ticker}/today-anomalies`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => setData(null));
  }, [ticker]);

  if (!data || data.count === 0) return null;

  return (
    <aside className="mt-6 border border-sev-med/40 bg-bg-2 px-5 py-4">
      <div className="flex items-baseline justify-between mb-2">
        <p className="mono text-[11px] text-sev-med uppercase tracking-wider">
          최근 7일 이상 공시 {data.count}건
        </p>
        <p className="mono text-[11px] text-fg-3">
          HIGH {data.high} · MED {data.med}
        </p>
      </div>
      <ul className="space-y-1.5">
        {data.items.map((d) => (
          <li key={d.rcept_no} className="flex items-baseline gap-3 text-[13px]">
            <span className="mono text-[11px] text-fg-3 w-[80px] shrink-0">{d.date}</span>
            <span
              className={`mono text-[10px] uppercase ${
                d.severity === "high" ? "text-sev-high" : "text-sev-med"
              }`}
            >
              {d.severity === "high" ? "고" : "중"}
            </span>
            <a
              href={`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${d.rcept_no}`}
              target="_blank"
              rel="noreferrer"
              className="text-fg-2 hover:text-fg"
            >
              {d.title}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
