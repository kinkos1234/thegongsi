import type { Company } from "@/types";

const MARKET_LABEL: Record<string, string> = {
  KOSPI: "KOSPI",
  KOSDAQ: "KOSDAQ",
  KONEX: "KONEX",
  UNKNOWN: "상장폐지/기타",
};

export function CompanyHeader({ c }: { c: Company }) {
  const up = (c.change ?? 0) > 0;
  const marketLabel = c.market ? (MARKET_LABEL[c.market] || c.market) : "—";
  return (
    <header className="flex items-baseline justify-between gap-6 border-b border-border pb-6">
      <div className="min-w-0">
        <h1
          className="font-serif leading-[1] tracking-[-0.015em] truncate"
          style={{ fontSize: "clamp(32px, 5.5vw, 56px)" }}
        >
          {c.name}
        </h1>
        <p className="mono mt-3 text-[12px] sm:text-[13px] text-fg-3 tracking-wider uppercase">
          {c.ticker} · {marketLabel}
          {c.sector ? ` · ${c.sector}` : ""}
        </p>
      </div>
      <div className="text-right shrink-0">
        <p
          className="mono leading-none tabular-nums"
          style={{ fontSize: "clamp(22px, 3vw, 32px)" }}
        >
          {c.price !== null ? c.price.toLocaleString("ko-KR") : "—"}
        </p>
        {c.change !== null && (
          <p className={`mono mt-2 text-[13px] sm:text-[14px] tabular-nums ${up ? "price-up" : "price-down"}`}>
            {up ? "+" : ""}
            {c.change.toFixed(2)}%
          </p>
        )}
      </div>
    </header>
  );
}
