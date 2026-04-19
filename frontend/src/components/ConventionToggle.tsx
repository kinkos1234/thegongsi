"use client";

import { useEffect, useState } from "react";

const KEY = "comad_stock_convention";
type Convention = "us" | "kr";

export function ConventionToggle() {
  const [conv, setConv] = useState<Convention>("us");

  useEffect(() => {
    const saved = (localStorage.getItem(KEY) as Convention) || "us";
    setConv(saved);
  }, []);

  function apply(next: Convention) {
    setConv(next);
    localStorage.setItem(KEY, next);
    document.documentElement.setAttribute("data-convention", next);
  }

  return (
    <div className="flex items-center gap-2" role="radiogroup" aria-label="가격 색상 관습">
      {(["us", "kr"] as const).map((v) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={conv === v}
          onClick={() => apply(v)}
          className={`mono text-[11px] uppercase tracking-wider px-2.5 py-1 border transition-colors ${
            conv === v
              ? "border-accent text-accent"
              : "border-border text-fg-3 hover:text-fg-2"
          }`}
        >
          {v === "us" ? "US · 상승 초록" : "KR · 상승 빨강"}
        </button>
      ))}
    </div>
  );
}
