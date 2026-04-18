"use client";

import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";

type EarningsRow = {
  ticker: string;
  name: string | null;
  quarter: string;
  scheduled: string | null;
  reported: string | null;
  revenue: number | null;
  op_profit: number | null;
  net_profit: number | null;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

// 백만원 단위 값을 사람 읽기 편한 표기로 (조·억). null/0 은 원문 유지.
function formatKRW(mmWon: number | null): string {
  if (mmWon === null) return "—";
  const abs = Math.abs(mmWon);
  if (abs >= 1_000_000) return `${(mmWon / 1_000_000).toFixed(1)}조`;
  if (abs >= 100) return `${(mmWon / 100).toFixed(0)}억`;
  return `${mmWon.toFixed(0)}백만`;
}

export function RecentEarnings({ limit = 5 }: { limit?: number }) {
  const [rows, setRows] = useState<EarningsRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/earnings/?upcoming=false`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((all: EarningsRow[]) => {
        // 매출 기준 내림차순. revenue null은 뒤로.
        const sorted = [...all].sort((a, b) => (b.revenue ?? -1) - (a.revenue ?? -1));
        setRows(sorted.slice(0, limit));
      })
      .catch((e) => setErr(String(e)));
  }, [limit]);

  if (err) return null;
  if (!rows) {
    return <div className="mt-10 text-[13px] text-fg-3 mono">실적 로딩 중…</div>;
  }
  if (rows.length === 0) {
    return (
      <div className="mt-10 text-[13px] text-fg-3 mono">최근 잠정실적 없음</div>
    );
  }

  return (
    <section className="mt-10 border-t border-border/50 pt-8">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-[22px] tracking-tight inline-flex items-baseline gap-2">
          <BarChart3 size={16} strokeWidth={1.75} className="translate-y-[2px] text-fg-2" />
          최근 잠정실적 (상위 {limit})
        </h2>
        <span className="mono text-[11px] text-fg-3 uppercase tracking-wider">
          {rows[0]?.quarter ?? "—"}
        </span>
      </div>
      <ul className="mt-6 divide-y divide-border/50">
        {rows.map((r) => (
          <li
            key={`${r.ticker}-${r.quarter}`}
            className="py-3 grid grid-cols-[160px_1fr_auto] gap-4 items-baseline"
          >
            <a
              href={`/c/${r.ticker}`}
              className="text-[13px] hover:text-accent truncate"
            >
              <span className="text-fg">{r.name ?? r.ticker}</span>{" "}
              <span className="mono text-[11px] text-fg-3">({r.ticker})</span>
            </a>
            <div className="text-[13px] text-fg-3 mono">
              매출 <span className="text-fg">{formatKRW(r.revenue)}</span>
              {" · "}
              영업익 <span className="text-fg">{formatKRW(r.op_profit)}</span>
              {" · "}
              순익 <span className="text-fg">{formatKRW(r.net_profit)}</span>
            </div>
            <span className="mono text-[11px] text-fg-3">
              {r.reported ?? r.scheduled ?? ""}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
