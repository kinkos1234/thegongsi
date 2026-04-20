"use client";

import { useEffect, useState } from "react";
import { CalendarDays, X, ExternalLink } from "lucide-react";

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
  ex_dividend: "배당락",
  last_with_right: "권리부 최종매매",
  record_date: "기준일",
  payment_date: "지급일",
  listing_date: "상장일",
};

// 주요 카테고리 (payment_date 제외) — 중요도 순
const CATEGORY_ORDER = [
  "ex_right",
  "ex_dividend",
  "last_with_right",
  "record_date",
  "listing_date",
];

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
const dartUrl = (rcept_no: string) =>
  `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${rcept_no}`;

export function UpcomingExDates({ days = 7 }: { days?: number }) {
  const [events, setEvents] = useState<Event[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selectedPayDate, setSelectedPayDate] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/calendar/upcoming?days=${days}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setEvents)
      .catch((e) => setErr(String(e)));
  }, [days]);

  if (err) return null;
  if (!events) {
    return (
      <div className="mt-10 text-[13px] text-fg-3 mono">
        권리락·배당락 캘린더 로딩 중…
      </div>
    );
  }
  if (events.length === 0) {
    return (
      <div className="mt-10 text-[13px] text-fg-3 mono">
        향후 {days}일 내 예정된 권리락·배당락 이벤트 없음
      </div>
    );
  }

  const mainEvents = events.filter((e) => e.event_type !== "payment_date");
  const paymentEvents = events.filter((e) => e.event_type === "payment_date");

  const mainByType = mainEvents.reduce<Record<string, Event[]>>((acc, ev) => {
    (acc[ev.event_type] = acc[ev.event_type] || []).push(ev);
    return acc;
  }, {});

  const paymentByDate = paymentEvents.reduce<Record<string, Event[]>>((acc, ev) => {
    (acc[ev.event_date] = acc[ev.event_date] || []).push(ev);
    return acc;
  }, {});
  const paymentDates = Object.keys(paymentByDate).sort();

  const activeCategories = CATEGORY_ORDER.filter((t) => mainByType[t]?.length);

  return (
    <section className="mt-10 border-t border-border/50 pt-8">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif text-[22px] tracking-tight inline-flex items-baseline gap-2">
          <CalendarDays size={16} strokeWidth={1.75} className="translate-y-[2px] text-fg-2" />
          D-{days} 권리락·배당락 캘린더
        </h2>
        <span className="mono text-[11px] text-fg-3 uppercase tracking-wider">
          {events.length} events
        </span>
      </div>

      {activeCategories.map((type) => (
        <div key={type} className="mt-6">
          <h3 className="font-serif text-[15px] tracking-tight text-fg-2 mb-2">
            {EVENT_LABEL[type] ?? type}
            <span className="mono text-[11px] text-fg-3 ml-2">
              ({mainByType[type].length})
            </span>
          </h3>
          <ul className="divide-y divide-border/50">
            {mainByType[type].map((r) => (
              <li
                key={`${r.ticker}-${r.rcept_no}`}
                className="py-2 grid grid-cols-[90px_1fr] gap-4"
              >
                <span className="mono text-[12px] text-fg-2">{r.event_date}</span>
                <a
                  href={`/c/${r.ticker}`}
                  className="block text-[13px] hover:text-accent"
                >
                  <span className="text-fg">{r.name ?? r.ticker}</span>{" "}
                  <span className="mono text-fg-3">({r.ticker})</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {paymentDates.length > 0 && (
        <div className="mt-8">
          <h3 className="font-serif text-[15px] tracking-tight text-fg-2 mb-2">
            배당 지급일
            <span className="mono text-[11px] text-fg-3 ml-2">
              ({paymentEvents.length})
            </span>
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {paymentDates.map((date) => {
              const rows = paymentByDate[date];
              return (
                <button
                  key={date}
                  type="button"
                  onClick={() => setSelectedPayDate(date)}
                  className="text-left border border-border/50 px-3 py-2 hover:border-accent hover:bg-bg-2 transition-colors"
                >
                  <div className="mono text-[12px] text-fg-2">{date}</div>
                  <div className="mono text-[11px] text-fg-3 mt-0.5">
                    {rows.length} 종목
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {selectedPayDate && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="paydate-modal-title"
          className="fixed inset-0 z-50 bg-bg/80 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4 md:p-8"
          onClick={() => setSelectedPayDate(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[560px] bg-bg-2 border border-border/60 shadow-2xl"
          >
            <header className="flex items-start justify-between border-b border-border/50 px-6 py-4 gap-4">
              <div className="min-w-0">
                <p
                  id="paydate-modal-title"
                  className="font-serif text-[18px] leading-tight"
                >
                  배당 지급일 · {selectedPayDate}
                </p>
                <p className="mono text-[11px] text-fg-3 mt-1">
                  {paymentByDate[selectedPayDate].length} 종목 · 이름 클릭 시 DART 원문
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPayDate(null)}
                aria-label="닫기"
                className="text-fg-3 hover:text-fg"
              >
                <X size={18} />
              </button>
            </header>
            <ul className="divide-y divide-border/50 max-h-[60vh] overflow-y-auto">
              {paymentByDate[selectedPayDate].map((r) => (
                <li key={`${r.ticker}-${r.rcept_no}`}>
                  <a
                    href={dartUrl(r.rcept_no)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 px-6 py-2.5 hover:bg-bg text-[13px]"
                  >
                    <span className="text-fg flex-1 truncate">
                      {r.name ?? r.ticker}
                    </span>
                    <span className="mono text-fg-3">({r.ticker})</span>
                    <ExternalLink size={12} className="text-fg-3" strokeWidth={1.75} />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
