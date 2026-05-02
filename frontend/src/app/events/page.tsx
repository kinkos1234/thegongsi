"use client";

import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Search, SlidersHorizontal } from "lucide-react";
import { EventReviewButtons } from "@/components/EventReviewButtons";

type EventItem = {
  id: string;
  status: "new" | "reviewed" | "dismissed" | "escalated";
  severity: "high" | "med" | "low" | "uncertain";
  priority: number;
  ticker: string;
  company: string | null;
  market: string | null;
  sector: string | null;
  date: string;
  title: string;
  reason: string | null;
  summary: string | null;
  evidence: { rcept_no: string; dart_url: string };
  actions: string[];
  review_note?: string | null;
  reviewed_at?: string | null;
};

type Inbox = {
  as_of: string;
  days: number;
  counts: { high: number; med: number; new: number; reviewed?: number; dismissed?: number; escalated?: number };
  items: EventItem[];
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
const TOKEN_KEY = "comad_stock_token";
type SeverityFilter = "all" | "high" | "med";
type StatusFilter = "active" | "all" | EventItem["status"];

export default function EventsPage() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [err, setErr] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("active");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    setToken(token);
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    setErr(false);
    setInbox(null);
    fetch(`${API}/api/stats/event-inbox?days=${days}&limit=120`, { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setInbox)
      .catch(() => setErr(true));
  }, [days]);

  const filteredItems = useMemo(() => {
    const items = inbox?.items ?? [];
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      if (severity !== "all" && item.severity !== severity) return false;
      if (status === "active" && (item.status === "reviewed" || item.status === "dismissed")) return false;
      if (status !== "active" && status !== "all" && item.status !== status) return false;
      if (!q) return true;
      const haystack = [
        item.ticker,
        item.company,
        item.market,
        item.sector,
        item.title,
        item.reason,
        item.date,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [inbox, query, severity, status]);

  const topTicker = useMemo(() => {
    const counts = new Map<string, { n: number; company: string | null }>();
    for (const item of filteredItems) {
      const current = counts.get(item.ticker) ?? { n: 0, company: item.company };
      current.n += 1;
      counts.set(item.ticker, current);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1].n - a[1].n)[0] ?? null;
  }, [filteredItems]);

  return (
    <main className="mx-auto max-w-[1180px] px-6 sm:px-8 py-12 sm:py-16">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="mono text-[11px] uppercase tracking-[0.18em] text-fg-3">
            Disclosure event inbox
          </p>
          <h1 className="mt-3 font-serif text-[34px] sm:text-[44px] leading-[1.08]">
            이상공시 큐
          </h1>
          <p className="mt-4 max-w-[720px] text-[15px] leading-[1.7] text-fg-2">
            최근 high/medium 공시를 중요도와 반복 신호 중심으로 훑습니다.
            로그인하면 검토 상태와 메모가 저장됩니다.
          </p>
        </div>
        {inbox && (
          <div className="grid grid-cols-3 gap-4 min-w-[300px]">
            <MiniStat label="표시" value={filteredItems.length} />
            <MiniStat label="high" value={filteredItems.filter((i) => i.severity === "high").length} tone="high" />
            <MiniStat label="med" value={filteredItems.filter((i) => i.severity === "med").length} tone="med" />
          </div>
        )}
      </div>

      <section className="mt-10 border-y border-border/60 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mono inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.14em] text-fg-3">
              <SlidersHorizontal size={13} strokeWidth={1.8} />
              filter
            </span>
            <Segmented
              value={String(days)}
              options={[
                ["7", "7일"],
                ["14", "14일"],
                ["30", "30일"],
              ]}
              onChange={(v) => setDays(Number(v))}
            />
            <Segmented
              value={severity}
              options={[
                ["all", "전체"],
                ["high", "HIGH"],
                ["med", "MED"],
              ]}
              onChange={(v) => setSeverity(v as SeverityFilter)}
            />
            <Segmented
              value={status}
              options={[
                ["active", "미처리"],
                ["all", "전체"],
                ["escalated", "주의"],
                ["reviewed", "검토"],
              ]}
              onChange={(v) => setStatus(v as StatusFilter)}
            />
          </div>
          <label className="relative block min-w-[240px] lg:w-[320px]">
            <Search
              size={15}
              strokeWidth={1.8}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-3"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="종목, 회사명, 공시명 검색"
              className="w-full border border-border/60 bg-bg-2 py-2 pl-9 pr-3 text-[13px] text-fg placeholder:text-fg-3 focus:border-accent focus:outline-none"
            />
          </label>
        </div>
      </section>

      {inbox && (
        <section className="grid grid-cols-1 gap-4 border-b border-border/60 py-5 md:grid-cols-3">
          <Insight label="최신 기준일" value={filteredItems[0]?.date ?? "—"} />
          <Insight
            label="반복 종목"
            value={topTicker ? `${topTicker[0]} · ${topTicker[1].n}건` : "—"}
            hint={topTicker?.[1].company ?? undefined}
          />
          <Insight
            label="검토 상태"
            value={`신규 ${filteredItems.filter((i) => i.status === "new").length} · 주의 ${
              filteredItems.filter((i) => i.status === "escalated").length
            }`}
          />
        </section>
      )}

      {token && (
        <div className="mt-5 flex flex-wrap gap-4">
          <button
            type="button"
            onClick={() => {
              fetch(`${API}/api/events/reviews/export.csv`, {
                headers: { Authorization: `Bearer ${token}` },
              })
                .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
                .then((blob) => {
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "thegongsi-event-reviews.csv";
                  a.click();
                  URL.revokeObjectURL(url);
                })
                .catch(() => setErr(true));
            }}
            className="mono text-[12px] text-accent border-b border-accent"
          >
            export review log →
          </button>
          <span className="mono text-[12px] text-fg-3">
            reviewed {inbox?.counts.reviewed ?? 0} · dismissed {inbox?.counts.dismissed ?? 0} · escalated{" "}
            {inbox?.counts.escalated ?? 0}
          </span>
        </div>
      )}

      {err ? (
        <section className="mt-12 border border-border/60 bg-bg-2/60 p-6">
          <p className="text-[14px] text-fg-2">이벤트 큐를 불러오지 못했습니다.</p>
        </section>
      ) : !inbox ? (
        <section className="mt-12 space-y-3" aria-busy="true">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-[74px] bg-bg-2/70 animate-pulse" />
          ))}
        </section>
      ) : inbox.items.length === 0 ? (
        <section className="mt-12 border border-border/60 bg-bg-2/60 p-6">
          <p className="text-[14px] text-fg-2">최근 {inbox.days}일 high/med 공시가 없습니다.</p>
        </section>
      ) : filteredItems.length === 0 ? (
        <section className="mt-8 border border-border/60 bg-bg-2/60 p-6">
          <p className="text-[14px] text-fg-2">조건에 맞는 공시가 없습니다.</p>
        </section>
      ) : (
        <section className="mt-8 border-t border-border/60">
          <div className="divide-y divide-border/50">
            {filteredItems.map((item) => (
              <article
                key={item.id}
                className="grid grid-cols-1 gap-4 py-4 md:grid-cols-[74px_minmax(0,1fr)_auto] md:items-start"
              >
                <div className="flex items-center gap-2 md:block">
                  <SeverityBadge severity={item.severity} />
                  <span className="mono text-[12px] text-fg-3 md:mt-2 md:block">{item.date.slice(5)}</span>
                </div>
                <div className="min-w-0">
                  <a href={`/c/${item.ticker}`} className="group block">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="mono text-[12px] text-accent">{item.ticker}</span>
                      <span className="text-[15px] font-medium text-fg group-hover:text-accent">
                        {item.company ?? item.ticker}
                      </span>
                      {item.market && item.market !== "UNKNOWN" && (
                        <span className="mono text-[10px] uppercase text-fg-3">{item.market}</span>
                      )}
                      {item.sector && <span className="text-[12px] text-fg-3">{item.sector}</span>}
                    </div>
                    <p className="mt-1.5 text-[14px] leading-[1.55] text-fg-2 group-hover:text-fg">
                      {item.title}
                    </p>
                  </a>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {item.reason && <ReasonChip reason={item.reason} />}
                    <a
                      href={item.evidence.dart_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mono inline-flex items-center gap-1 text-[11px] text-fg-3 hover:text-accent"
                    >
                      DART <ExternalLink size={12} strokeWidth={1.8} />
                    </a>
                  </div>
                </div>
                <EventReviewButtons
                  rceptNo={item.id}
                  initialStatus={item.status}
                  initialNote={item.review_note}
                />
              </article>
            ))}
          </div>
          <p className="mt-5 mono text-[11px] text-fg-3">as of {inbox.as_of.slice(0, 19)}</p>
        </section>
      )}
    </main>
  );
}

function Segmented({
  value,
  options,
  onChange,
}: {
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex border border-border/60 bg-bg-2">
      {options.map(([v, label]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`mono px-2.5 py-1.5 text-[11px] transition-colors ${
            value === v ? "bg-accent text-bg" : "text-fg-3 hover:text-accent"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Insight({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="mono text-[10px] uppercase tracking-[0.15em] text-fg-3">{label}</p>
      <p className="mono mt-1 text-[17px] text-fg tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-[12px] text-fg-3 truncate">{hint}</p>}
    </div>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: number; tone?: "high" | "med" }) {
  const color = tone === "high" ? "text-sev-high" : tone === "med" ? "text-sev-med" : "text-fg";
  return (
    <div className="border-t border-border/60 pt-3">
      <p className="mono text-[10px] uppercase tracking-[0.15em] text-fg-3">{label}</p>
      <p className={`mono mt-1 text-[24px] tabular-nums ${color}`}>{value.toLocaleString("ko-KR")}</p>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: EventItem["severity"] }) {
  const color =
    severity === "high" ? "bg-sev-high text-bg" : severity === "med" ? "bg-sev-med text-bg" : "bg-bg-3 text-fg-2";
  return (
    <span className={`mono inline-flex px-2 py-1 text-[11px] uppercase ${color}`}>
      {severity}
    </span>
  );
}

function ReasonChip({ reason }: { reason: string }) {
  const keyword = reason.match(/'([^']+)'/)?.[1] ?? reason.replace("키워드 매칭:", "").trim();
  return (
    <span className="inline-flex border border-border/50 bg-bg-2 px-2 py-0.5 text-[11px] text-fg-3">
      {keyword}
    </span>
  );
}
