"use client";

import { useEffect, useState } from "react";
import type { Disclosure } from "@/types";
import { DisclosureRow } from "./DisclosureRow";

const PAGE_SIZE = 20;
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

const SEV_LABEL: Record<string, string> = {
  all: "전체",
  high: "고",
  med: "중",
  low: "저",
  uncertain: "불명",
};

export function DisclosureList({ ticker, initial }: { ticker: string; initial: Disclosure[] }) {
  const [page, setPage] = useState(0);
  const [items, setItems] = useState<Disclosure[]>(initial);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [severity, setSeverity] = useState<"all" | "high" | "med" | "low" | "uncertain">("all");
  // 과거 공시 정밀검색 (Threads 피드백 대응)
  const [q, setQ] = useState("");
  const [qApplied, setQApplied] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      ticker,
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (severity !== "all") params.set("severity", severity);
    if (qApplied) params.set("q", qApplied);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    fetch(`${API}/api/disclosures/?${params}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list: Disclosure[]) => {
        setItems(list);
        if (list.length < PAGE_SIZE) {
          setTotal(page * PAGE_SIZE + list.length);
        }
      })
      .finally(() => setLoading(false));
  }, [ticker, page, severity, qApplied, dateFrom, dateTo]);

  const applySearch = () => {
    setPage(0);
    setQApplied(q);
  };
  const resetSearch = () => {
    setPage(0);
    setQ("");
    setQApplied("");
    setDateFrom("");
    setDateTo("");
  };

  const pageStart = page * PAGE_SIZE + 1;
  const pageEnd = page * PAGE_SIZE + items.length;
  const hasNext = items.length === PAGE_SIZE;
  const hasPrev = page > 0;

  const hasSearch = qApplied || dateFrom || dateTo;

  return (
    <div>
      {/* 과거 공시 정밀검색 바 */}
      <div className="mb-4 p-3 border border-border/40 bg-bg-2/30">
        <div className="flex flex-wrap gap-2 items-center">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applySearch()}
            placeholder="제목·요약 검색 (예: 유상증자, 배당)"
            className="flex-1 min-w-[200px] bg-bg border border-border/50 px-3 py-1.5 text-[13px] focus:border-accent outline-none"
            aria-label="공시 검색"
          />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setPage(0); setDateFrom(e.target.value); }}
            className="bg-bg border border-border/50 px-2 py-1.5 text-[12px] mono"
            aria-label="시작일"
          />
          <span className="text-fg-3 mono text-[12px]">~</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setPage(0); setDateTo(e.target.value); }}
            className="bg-bg border border-border/50 px-2 py-1.5 text-[12px] mono"
            aria-label="종료일"
          />
          <button
            onClick={applySearch}
            className="mono text-[12px] px-3 py-1.5 border border-accent text-accent hover:bg-accent-dim"
          >
            검색
          </button>
          {hasSearch && (
            <button
              onClick={resetSearch}
              className="mono text-[12px] px-2 py-1.5 text-fg-3 hover:text-fg"
            >
              ✕ 초기화
            </button>
          )}
        </div>
      </div>
      <div className="flex items-baseline justify-between mb-4">
        <div className="flex gap-1" role="tablist" aria-label="심각도 필터">
          {(["all", "high", "med", "low", "uncertain"] as const).map((s) => (
            <button
              key={s}
              role="tab"
              aria-selected={severity === s}
              onClick={() => {
                setPage(0);
                setSeverity(s);
              }}
              className={`text-[12px] px-2 py-1 tracking-wider transition-colors ${
                severity === s
                  ? "text-accent border-b border-accent"
                  : "text-fg-3 hover:text-fg-2"
              }`}
              title={s}
            >
              {SEV_LABEL[s]}
            </button>
          ))}
        </div>
        <span className="mono text-[11px] text-fg-3">
          {items.length > 0 ? `${pageStart}–${pageEnd}${total ? ` / ${total}` : ""}` : "—"}
        </span>
      </div>

      {loading && items.length === 0 && (
        <div className="py-12 space-y-2">
          <div className="h-8 bg-bg-2 animate-pulse" />
          <div className="h-8 bg-bg-2 animate-pulse" />
          <div className="h-8 bg-bg-2 animate-pulse" />
        </div>
      )}

      {!loading && items.length === 0 && (
        <p className="py-12 text-fg-3">
          {page > 0
            ? "마지막 페이지입니다."
            : severity !== "all"
              ? `'${SEV_LABEL[severity]}' 심각도 공시 없음. 필터 해제해보세요.`
              : "공시 데이터 없음. DART 수집 실행 후 다시 확인하세요."}
        </p>
      )}

      <div>
        {items.map((d) => (
          <DisclosureRow key={d.rcept_no} d={d} />
        ))}
      </div>

      {(hasPrev || hasNext) && (
        <div className="flex justify-between items-center mt-6 pt-4 border-t border-border/30">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={!hasPrev || loading}
            className="mono text-[12px] text-fg-3 hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed"
          >
            ← prev
          </button>
          <span className="mono text-[11px] text-fg-3">page {page + 1}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasNext || loading}
            className="mono text-[12px] text-fg-3 hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed"
          >
            next →
          </button>
        </div>
      )}
    </div>
  );
}
