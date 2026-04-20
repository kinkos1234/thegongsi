"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Row = {
  rcept_no: string;
  ticker: string;
  name?: string | null;
  corp_name?: string | null;
  date?: string;
  rcept_dt?: string;
  title: string;
  severity: "high" | "med" | "low" | "uncertain" | null;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

function severityLabel(s: Row["severity"]): string {
  if (s === "high") return "심각도 높음";
  if (s === "med") return "심각도 중간";
  if (s === "low") return "심각도 낮음";
  if (s === "uncertain") return "심각도 불확실";
  return "심각도 정보 없음";
}

function deriveTone(rows: Row[] | null) {
  if (!rows || rows.length === 0) {
    return { label: "최근 공시", border: "border-border/60", text: "text-fg-3" };
  }
  // 모든 행이 오늘자면 "오늘의", 아니면 "최근" — DART 주말·공휴일 공백 + 수집
  // 지연을 정직하게 표현 (2026-04-20에 4-17자 공시만 떠도 "오늘의"라고 속이지 않음).
  const todayIso = new Date().toISOString().slice(0, 10);
  const dateOf = (r: Row) => (r.date || r.rcept_dt || "").slice(0, 10);
  const allToday = rows.every((r) => dateOf(r) === todayIso);
  const prefix = allToday ? "오늘의" : "최근";

  const hasHigh = rows.some((r) => r.severity === "high");
  const hasMed = rows.some((r) => r.severity === "med");
  if (hasHigh) {
    return {
      label: `${prefix} 이상 공시 · HIGH`,
      border: "border-sev-high/30",
      text: "text-sev-high",
    };
  }
  if (hasMed) {
    return {
      label: `${prefix} 주요 공시 · MED`,
      border: "border-sev-med/30",
      text: "text-sev-med",
    };
  }
  return {
    label: `${prefix} 최신 공시`,
    border: "border-border/60",
    text: "text-fg-3",
  };
}

export function MarketAnomalies({ limit = 3 }: { limit?: number }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    async function load() {
      try {
        const r1 = await fetch(`${API}/api/disclosures/?severity=high&limit=${limit}`, {
          signal: ctl.signal,
        });
        if (!r1.ok) throw new Error("network");
        const list1: Row[] = await r1.json();
        if (list1.length > 0) {
          setRows(list1);
          return;
        }
        // fallback 1: medium severity
        const r2 = await fetch(`${API}/api/disclosures/?severity=med&limit=${limit}`, {
          signal: ctl.signal,
        });
        if (r2.ok) {
          const list2: Row[] = await r2.json();
          if (list2.length > 0) {
            setRows(list2);
            return;
          }
        }
        // fallback 2: recent regardless of severity
        const r3 = await fetch(`${API}/api/disclosures/?limit=${limit}`, {
          signal: ctl.signal,
        });
        if (r3.ok) {
          setRows(await r3.json());
          return;
        }
        setRows([]);
      } catch {
        setErr(true);
      }
    }
    load();
    return () => ctl.abort();
  }, [limit]);

  if (err) return null;

  // rows의 최고 severity로 톤 결정
  const tone = deriveTone(rows);

  return (
    <section
      className={`mt-10 border ${tone.border} bg-bg-2/60 px-5 py-4`}
      aria-label={tone.label}
    >
      <header className="flex items-baseline justify-between mb-3">
        <p className={`mono text-[11px] uppercase tracking-[0.15em] ${tone.text}`}>
          {tone.label}
        </p>
        <Link
          href="/ask"
          className="mono text-[11px] text-fg-3 hover:text-accent tracking-wider"
        >
          all →
        </Link>
      </header>
      {!rows && (
        <ul className="space-y-2" aria-busy="true">
          {Array.from({ length: limit }).map((_, i) => (
            <li key={i} className="h-[18px] bg-bg-3/60 animate-pulse" />
          ))}
        </ul>
      )}
      {rows && rows.length === 0 && (
        <p className="text-[13px] text-fg-3">
          표시할 공시가 없습니다.
        </p>
      )}
      {rows && rows.length > 0 && (
        <ul className="space-y-1.5">
          {rows.map((d) => {
            const date = (d.date || d.rcept_dt || "").slice(0, 10);
            const dotClass =
              d.severity === "high"
                ? "bg-sev-high"
                : d.severity === "med"
                ? "bg-sev-med"
                : "bg-fg-3";
            return (
              <li key={d.rcept_no} className="flex items-baseline gap-3 text-[13px]">
                <span className="mono text-[11px] text-fg-3 w-[80px] shrink-0">
                  {date}
                </span>
                <span
                  className={`inline-flex h-[6px] w-[6px] rounded-full ${dotClass} shrink-0 translate-y-[2px]`}
                  title={severityLabel(d.severity)}
                  aria-label={severityLabel(d.severity)}
                />
                <Link
                  href={`/c/${d.ticker}`}
                  className="flex-1 min-w-0 flex items-baseline gap-2 hover:text-accent transition-colors"
                  title={d.title}
                >
                  <span className="mono text-[11px] text-fg-3 shrink-0">{d.ticker}</span>
                  <span className="text-fg-2 truncate">{d.title}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
