"use client";

import { useState } from "react";
import type { Disclosure } from "@/types";
import { DisclosurePreview } from "./DisclosurePreview";
import { FeedbackButtons } from "./FeedbackButtons";

const SEV_CONFIG: Record<string, { dot: string; text: string; glyph: string; full: string }> = {
  high: { dot: "bg-sev-high", text: "text-sev-high", glyph: "고", full: "심각도 높음" },
  med: { dot: "bg-sev-med", text: "text-sev-med", glyph: "중", full: "심각도 중간" },
  low: { dot: "bg-fg-3", text: "text-fg-3", glyph: "저", full: "심각도 낮음" },
  uncertain: { dot: "bg-fg-3", text: "text-fg-3", glyph: "?", full: "심각도 불확실" },
};

export function DisclosureRow({ d }: { d: Disclosure }) {
  const [preview, setPreview] = useState(false);
  const sev = d.severity ? SEV_CONFIG[d.severity] : null;
  return (
    <>
      <div className="group flex items-baseline gap-3 sm:gap-5 border-b border-border/50 py-3 hover:bg-bg-3 px-2 -mx-2 transition-colors">
        <button
          type="button"
          onClick={() => setPreview(true)}
          className="flex flex-1 items-baseline gap-3 sm:gap-5 min-w-0 text-left"
          aria-label={`${d.title} 미리보기 열기`}
        >
          <span className="mono text-[12px] text-fg-3 w-[76px] sm:w-[90px] shrink-0">
            {d.date}
          </span>
          {sev ? (
            <span
              role="img"
              aria-label={sev.full}
              title={sev.full}
              className={`shrink-0 mt-[6px] h-[7px] w-[7px] rounded-full ${sev.dot}`}
            />
          ) : (
            <span className="shrink-0 w-[7px] h-[7px]" aria-hidden="true" />
          )}
          <span className="flex-1 text-[14px] text-fg group-hover:text-accent transition-colors truncate">
            {d.title}
          </span>
          {d.summary && (
            <span className="hidden md:block text-[13px] text-fg-2 truncate max-w-[320px]">
              {d.summary}
            </span>
          )}
        </button>
        <FeedbackButtons target={{ kind: "disclosure", rcept_no: d.rcept_no }} />
      </div>
      {preview && <DisclosurePreview rceptNo={d.rcept_no} onClose={() => setPreview(false)} />}
    </>
  );
}
