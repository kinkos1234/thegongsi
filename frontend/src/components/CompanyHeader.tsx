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
    <header className="flex items-baseline justify-between border-b border-border pb-6">
      <div>
        <h1 className="font-serif text-[40px] leading-none tracking-[-0.01em]">{c.name}</h1>
        <p className="mono mt-2 text-[13px] text-fg-3">
          {c.ticker} · {marketLabel}
          {c.sector ? ` · ${c.sector}` : ""}
        </p>
      </div>
      <div className="text-right">
        <p className="mono text-[28px] leading-none">
          {c.price !== null ? c.price.toLocaleString("ko-KR") : "—"}
        </p>
        {c.change !== null && (
          <p
            className={`mono mt-2 text-[14px] ${up ? "text-accent" : "text-down"}`}
          >
            {up ? "+" : ""}
            {c.change.toFixed(2)}%
          </p>
        )}
      </div>
    </header>
  );
}
