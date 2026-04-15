"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Item = { ticker: string; name: string | null; market: string | null; added_at: string };

const TOKEN_KEY = "comad_stock_token";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export default function WatchlistPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [ticker, setTicker] = useState("");
  const [days, setDays] = useState(90);
  const [token, setToken] = useState<string | null>(null);
  const [backfilling, setBackfilling] = useState<{ ticker: string; count: number } | null>(null);

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
    // 1초 간격으로 disclosure 수 체크, 90초 타임아웃
    for (let i = 0; i < 90; i++) {
      await new Promise((r) => setTimeout(r, 1000));
      try {
        const r = await fetch(`${API}/api/disclosures/?ticker=${t}`);
        if (r.ok) {
          const list = await r.json();
          if (list.length > 0) {
            setBackfilling({ ticker: t, count: list.length });
            // 2초 유지 후 dismiss
            await new Promise((r2) => setTimeout(r2, 2000));
            setBackfilling(null);
            return;
          }
        }
      } catch {}
    }
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
      setBackfilling({ ticker: t, count: 0 });
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
      <main className="mx-auto max-w-[720px] px-8 py-20">
        <h1 className="font-serif text-[32px]">로그인이 필요합니다.</h1>
        <Link href="/login" className="mt-6 inline-block mono text-accent border-b border-accent">
          login →
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[720px] px-8 py-20">
      <h1 className="font-serif text-[40px] leading-none tracking-[-0.01em]">관심 종목</h1>

      <form onSubmit={add} className="mt-10 space-y-3">
        <div className="flex gap-3">
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="6자리 종목코드 (예: 005930)"
            className="flex-1 bg-bg-2 border border-border px-4 py-3 mono text-[14px] focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            className="mono text-[13px] text-accent border border-accent px-4 hover:bg-accent-dim transition-colors"
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
        <div className="fixed top-20 right-6 z-50 border-l-2 border-accent bg-bg-2 border border-border/50 px-4 py-3 flex items-center gap-3 shadow-lg">
          <p className="text-[13px] text-fg-2">
            <span className="mono text-accent">{backfilling.ticker}</span> 공시 백필 중…
            {backfilling.count > 0 && (
              <span className="mono text-fg-3 ml-2">({backfilling.count}건 도착)</span>
            )}
          </p>
          <div className="h-2 w-2 rounded-full bg-accent animate-pulse" />
        </div>
      )}

      <ul className="mt-12 border-t border-border/50">
        {items.length === 0 && (
          <li>
            <div className="py-16 text-center">
              <p className="font-serif text-[20px] text-fg-2">아직 관심 종목이 없습니다.</p>
              <p className="mt-3 text-[13px] text-fg-3">상단 입력창에 6자리 종목코드(예: 005930)를 넣어 추가하세요.</p>
            </div>
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
                {i.market && <span className="ml-2">· {i.market}</span>}
              </span>
            </Link>
            <button
              onClick={() => remove(i.ticker)}
              className="mono text-[12px] text-fg-3 hover:text-sev-high"
            >
              remove
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
