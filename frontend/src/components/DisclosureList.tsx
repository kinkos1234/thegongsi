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
  // initial은 서버에서 처음 가져온 첫 페이지
  const [page, setPage] = useState(0);
  const [items, setItems] = useState<Disclosure[]>(initial);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [severity, setSeverity] = useState<"all" | "high" | "med" | "low" | "uncertain">("all");

  useEffect(() => {
    // severity 필터 또는 페이지 변경 시 리페치
    setLoading(true);
    const params = new URLSearchParams({
      ticker,
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (severity !== "all") params.set("severity", severity);
    fetch(`${API}/api/disclosures/?${params}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list: Disclosure[]) => {
        setItems(list);
        if (list.length < PAGE_SIZE) {
          setTotal(page * PAGE_SIZE + list.length);
        }
      })
      .finally(() => setLoading(false));
  }, [ticker, page, severity]);

  const pageStart = page * PAGE_SIZE + 1;
  const pageEnd = page * PAGE_SIZE + items.length;
  const hasNext = items.length === PAGE_SIZE;
  const hasPrev = page > 0;

  return (
    <div>
      <div className="flex items-baseline justify-between mb-4">
        <div className="flex gap-1">
          {(["all", "high", "med", "low", "uncertain"] as const).map((s) => (
            <button
              key={s}
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
          공시 데이터 없음.
          {severity !== "all" ? ` ('${SEV_LABEL[severity]}' 필터 해제해보세요)` : " DART 수집 실행 후 다시 확인하세요."}
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
