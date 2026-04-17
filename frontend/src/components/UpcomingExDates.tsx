"use client";

import { useEffect, useState } from "react";

type Event = {
  ticker: string;
  name: string | null;
  event_type: string;
  event_date: string;
  rcept_no: string;
  title: string | null;
};

const EVENT_LABEL: Record<string, string> = {
  ex_right: "권리락",
  last_with_right: "권리부 최종매매",
  record_date: "기준일",
  payment_date: "지급일",
  listing_date: "상장일",
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export function UpcomingExDates({ days = 7 }: { days?: number }) {
  const [events, setEvents] = useState<Event[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/calendar/upcoming?days=${days}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setEvents)
      .catch((e) => setErr(String(e)));
  }, [days]);

  if (err) return null;
  if (!events) {
    return (
      <div className="mt-10 text-[13px] text-fg-3 mono">권리락·배당락 캘린더 로딩 중…</div>
    );
  }
  if (events.length === 0) {
    return (
      <div className="mt-10 text-[13px] text-fg-3 mono">
        향후 {days}일 내 예정된 권리락·배당락 이벤트 없음
      </div>
    );
  }

  const grouped = events.reduce<Record<string, Event[]>>((acc, ev) => {
    (acc[ev.event_date] = acc[ev.event_date] || []).push(ev);
    return acc;
  }, {});

  return (
    <section className="mt-10 border-t border-border/50 pt-8">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-[22px] tracking-tight">D-{days} 권리락·배당락 캘린더</h2>
        <span className="mono text-[11px] text-fg-3 uppercase tracking-wider">
          {events.length} events
        </span>
      </div>
      <ul className="mt-6 divide-y divide-border/50">
        {Object.entries(grouped).map(([date, rows]) => (
          <li key={date} className="py-3 grid grid-cols-[90px_1fr] gap-4">
            <span className="mono text-[12px] text-fg-2">{date}</span>
            <div className="space-y-1">
              {rows.map((r) => (
                <a
                  key={`${r.ticker}-${r.event_type}-${r.rcept_no}`}
                  href={`/c/${r.ticker}`}
                  className="block text-[13px] hover:text-accent"
                >
                  <span className="mono text-fg-3">[{EVENT_LABEL[r.event_type] ?? r.event_type}]</span>{" "}
                  <span className="text-fg">{r.name ?? r.ticker}</span>{" "}
                  <span className="mono text-fg-3">({r.ticker})</span>
                </a>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
