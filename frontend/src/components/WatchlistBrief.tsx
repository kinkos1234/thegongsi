"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

type BriefItem = {
  id: string;
  ticker: string;
  company: string | null;
  market: string | null;
  sector: string | null;
  date: string;
  title: string;
  severity: "high" | "med" | "low" | "uncertain";
  reason: string | null;
  summary: string | null;
  status: "new" | "reviewed" | "dismissed" | "escalated";
  evidence: { rcept_no: string; dart_url: string };
};

type Brief = {
  as_of: string;
  days: number;
  watchlist_count: number;
  counts: {
    high: number;
    med: number;
    new: number;
    reviewed: number;
    dismissed: number;
    escalated: number;
  };
  items: BriefItem[];
  quiet_tickers: string[];
};

export function WatchlistBrief({ token }: { token: string }) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    fetch(`${API}/api/watchlist/brief?days=7&limit=20`, {
      signal: ctl.signal,
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setBrief)
      .catch(() => setErr(true));
    return () => ctl.abort();
  }, [token]);

  if (err) return null;

  return (
    <section className="mt-10 border-t border-border/50 pt-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mono text-[11px] text-fg-3 uppercase tracking-[0.18em]">
            Watchlist brief
          </p>
          <h2 className="mt-2 font-serif text-[26px] leading-[1.15]">내 종목 이상공시</h2>
        </div>
        {brief && (
          <div className="grid grid-cols-3 gap-5 min-w-[220px]">
            <MiniStat label="high" value={brief.counts.high} tone="high" />
            <MiniStat label="med" value={brief.counts.med} tone="med" />
            <MiniStat label="new" value={brief.counts.new} />
          </div>
        )}
      </div>

      {!brief && (
        <div className="mt-6 space-y-2" aria-busy="true">
          <div className="h-[52px] bg-bg-2 animate-pulse" />
          <div className="h-[52px] bg-bg-2 animate-pulse" />
        </div>
      )}

      {brief && brief.watchlist_count === 0 && (
        <p className="mt-5 text-[13px] text-fg-3">
          관심종목을 추가하면 최근 7일 high/medium 공시가 이곳에 먼저 뜹니다.
        </p>
      )}

      {brief && brief.watchlist_count > 0 && brief.items.length === 0 && (
        <div className="mt-5 border border-border/50 bg-bg-2/40 px-4 py-3">
          <p className="text-[14px] text-fg-2">
            최근 {brief.days}일 내 관심종목 high/medium 공시는 없습니다.
          </p>
          {brief.quiet_tickers.length > 0 && (
            <p className="mono mt-2 text-[11px] text-fg-3">
              quiet {brief.quiet_tickers.slice(0, 8).join(" · ")}
              {brief.quiet_tickers.length > 8 ? " · ..." : ""}
            </p>
          )}
        </div>
      )}

      {brief && brief.items.length > 0 && (
        <div className="mt-6 border-t border-border/50">
          {brief.items.map((item) => (
            <article key={item.id} className="border-b border-border/50 py-4">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <Severity severity={item.severity} />
                <span className="mono text-[12px] text-fg-3">{item.date}</span>
                <Link href={`/c/${item.ticker}`} className="text-[14px] text-fg hover:text-accent">
                  {item.company ?? item.ticker}
                </Link>
                <span className="mono text-[11px] text-fg-3">{item.ticker}</span>
                {item.status !== "new" && (
                  <span className="mono text-[11px] text-fg-3">{item.status}</span>
                )}
              </div>
              <p className="mt-2 text-[14px] leading-[1.55] text-fg-2">{item.title}</p>
              {item.reason && (
                <p className="mt-1.5 text-[12px] leading-[1.5] text-fg-3">{item.reason}</p>
              )}
              <div className="mt-3 flex flex-wrap items-center gap-4">
                <Link href={`/c/${item.ticker}`} className="mono text-[11px] text-accent border-b border-accent">
                  DD 보기 →
                </Link>
                <a
                  href={item.evidence.dart_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mono text-[11px] text-fg-3 hover:text-accent inline-flex items-center gap-1"
                >
                  DART 원문
                  <ExternalLink size={11} strokeWidth={1.75} />
                </a>
              </div>
            </article>
          ))}
          <div className="mt-4 flex items-baseline justify-between gap-3">
            <p className="mono text-[11px] text-fg-3">as of {brief.as_of.slice(0, 19)}</p>
            <Link href="/events" className="mono text-[11px] text-fg-3 hover:text-accent">
              전체 이상공시 큐 →
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: number; tone?: "high" | "med" }) {
  const color = tone === "high" ? "text-sev-high" : tone === "med" ? "text-sev-med" : "text-fg";
  return (
    <div className="border-t border-border/60 pt-2">
      <p className="mono text-[10px] uppercase tracking-[0.15em] text-fg-3">{label}</p>
      <p className={`mono mt-1 text-[22px] tabular-nums ${color}`}>{value.toLocaleString("ko-KR")}</p>
    </div>
  );
}

function Severity({ severity }: { severity: BriefItem["severity"] }) {
  const color =
    severity === "high"
      ? "bg-sev-high text-bg"
      : severity === "med"
        ? "bg-sev-med text-bg"
        : "bg-bg-3 text-fg-2";
  return <span className={`mono px-2 py-0.5 text-[10px] uppercase ${color}`}>{severity}</span>;
}
