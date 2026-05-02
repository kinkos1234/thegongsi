"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { EmptyState } from "@/components/Skeleton";
import { LoginGate } from "@/components/LoginGate";
import { WatchlistBrief } from "@/components/WatchlistBrief";

type Item = { ticker: string; name: string | null; market: string | null; added_at: string };

const TOKEN_KEY = "comad_stock_token";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

const MARKET_LABEL: Record<string, string> = {
  KOSPI: "KOSPI",
  KOSDAQ: "KOSDAQ",
  KONEX: "KONEX",
  UNKNOWN: "상장폐지/기타",
};

export default function WatchlistPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [ticker, setTicker] = useState("");
  const [days, setDays] = useState(90);
  const [token, setToken] = useState<string | null>(null);
  const [backfilling, setBackfilling] = useState<{
    ticker: string;
    count: number;
    stage: "disclosures" | "memo" | "done";
  } | null>(null);

  useEffect(() => {
    setToken(typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null);
  }, []);

  useEffect(() => {
    if (!token) return;
    load(token);
  }, [token]);

  async function load(t: string) {
    const r = await fetch(`${API}/api/watchlist/`, { headers: { Authorization: `Bearer ${t}` } });
    if (r.ok) setItems(await r.json());
  }

  async function pollBackfill(t: string) {
    // Stage 1: 공시 도착 감지 (최대 60초)
    let count = 0;
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 1000));
      try {
        const r = await fetch(`${API}/api/disclosures/?ticker=${t}&limit=1`);
        if (r.ok) {
          const list = await r.json();
          if (list.length > 0) {
            const cnt = await fetch(`${API}/api/disclosures/count?ticker=${t}`);
            if (cnt.ok) {
              count = (await cnt.json()).count ?? list.length;
            } else {
              count = list.length;
            }
            setBackfilling({ ticker: t, count, stage: "memo" });
            break;
          }
        }
      } catch {}
    }
    if (count === 0) {
      setBackfilling(null);
      return;
    }
    // Stage 2: DD 메모 생성 감지 (최대 60초)
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const r = await fetch(`${API}/api/memos/${t}`);
        if (r.ok) {
          setBackfilling({ ticker: t, count, stage: "done" });
          await new Promise((r2) => setTimeout(r2, 3000));
          setBackfilling(null);
          return;
        }
      } catch {}
    }
    // 메모 실패해도 공시는 도착했으니 done 처리
    setBackfilling({ ticker: t, count, stage: "done" });
    await new Promise((r) => setTimeout(r, 2000));
    setBackfilling(null);
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    const t = ticker.trim();
    if (!t || !token) return;
    const r = await fetch(`${API}/api/watchlist/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ticker: t, backfill_days: days }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      alert(err.detail || "추가 실패");
      return;
    }
    const data = await r.json();
    setTicker("");
    load(token);
    if (data.backfill?.startsWith("queued")) {
      setBackfilling({ ticker: t, count: 0, stage: "disclosures" });
      pollBackfill(t);
    }
  }

  async function remove(t: string) {
    if (!token) return;
    await fetch(`${API}/api/watchlist/${t}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    load(token);
  }

  if (!token) {
    return (
      <LoginGate
        title="관심 종목은 로그인이 필요합니다."
        hint="종목코드를 등록하면 공시 백필·DD 메모가 자동 생성되고, 로그인한 세션에서 이어볼 수 있어요."
        next="/watchlist"
      />
    );
  }

  return (
    <main className="mx-auto max-w-[720px] px-8 py-20">
      <h1 className="font-serif text-[40px] leading-none tracking-[-0.01em]">관심 종목</h1>
      <WatchlistBrief token={token} />

      <form onSubmit={add} className="mt-10 space-y-3">
        <div className="flex gap-3">
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.replace(/[^\d]/g, "").slice(0, 6))}
            placeholder="6자리 종목코드 (예: 005930)"
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            aria-invalid={ticker.length > 0 && ticker.length !== 6}
            className="flex-1 bg-bg-2 border border-border px-4 py-3 mono text-[14px] focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={ticker.length !== 6}
            className="mono text-[13px] text-accent border border-accent px-4 hover:bg-accent-dim transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            add
          </button>
        </div>
        <div className="flex items-center gap-3 text-[12px] text-fg-3 mono">
          <label htmlFor="days">백필 기간</label>
          <select
            id="days"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-bg-2 border border-border px-2 py-1 text-fg"
          >
            <option value={0}>없음</option>
            <option value={30}>30일</option>
            <option value={90}>90일</option>
            <option value={180}>180일</option>
            <option value={365}>365일</option>
          </select>
        </div>
      </form>

      {backfilling && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-20 right-6 z-50 border-l-2 border-accent bg-bg-2 border border-border/50 px-4 py-3 flex items-center gap-3 shadow-lg"
        >
          <p className="text-[13px] text-fg-2">
            <span className="mono text-accent">{backfilling.ticker}</span>{" "}
            {backfilling.stage === "disclosures" && "공시 백필 중…"}
            {backfilling.stage === "memo" && (
              <>
                공시 <span className="mono text-fg">{backfilling.count}</span>건 · DD 메모 생성 중…
              </>
            )}
            {backfilling.stage === "done" && (
              <>
                <span className="text-accent">완료</span> — 공시 {backfilling.count}건
              </>
            )}
          </p>
          <div
            className={`h-2 w-2 rounded-full ${
              backfilling.stage === "done" ? "bg-accent" : "bg-accent animate-pulse"
            }`}
          />
        </div>
      )}

      <ul className="mt-12 border-t border-border/50">
        {items.length === 0 && (
          <li>
            <EmptyState
              title="아직 관심 종목이 없습니다."
              hint="상단 입력창에 6자리 종목코드(예: 005930)를 넣어 추가하세요."
            />
          </li>
        )}
        {items.map((i) => (
          <li key={i.ticker} className="flex items-center justify-between border-b border-border/50 py-4">
            <Link href={`/c/${i.ticker}`} className="flex items-baseline gap-3 group">
              <span className="font-serif text-[17px] text-fg group-hover:text-accent transition-colors">
                {i.name ?? "이름 수집 대기"}
              </span>
              <span className="mono text-[12px] text-fg-3">
                {i.ticker}
                {i.market && <span className="ml-2">· {MARKET_LABEL[i.market] || i.market}</span>}
              </span>
            </Link>
            <button
              onClick={() => remove(i.ticker)}
              aria-label={`${i.ticker} 관심종목에서 제거`}
              className="mono text-[12px] text-fg-3 hover:text-sev-high inline-flex items-center gap-1"
            >
              <X size={12} strokeWidth={1.75} />
              remove
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
