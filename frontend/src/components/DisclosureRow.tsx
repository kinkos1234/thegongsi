import type { Disclosure } from "@/types";
import { FeedbackButtons } from "./FeedbackButtons";

const SEV_COLOR: Record<string, string> = {
  high: "bg-sev-high",
  med: "bg-sev-med",
  low: "bg-fg-3",
};

const SEV_LABEL: Record<string, string> = {
  high: "심각도 높음",
  med: "심각도 중간",
  low: "심각도 낮음",
  uncertain: "심각도 불확실",
};

export function DisclosureRow({ d }: { d: Disclosure }) {
  const dot = d.severity ? SEV_COLOR[d.severity] : "bg-fg-3";
  const sevLabel = d.severity ? (SEV_LABEL[d.severity] || "심각도 정보 없음") : "심각도 정보 없음";
  return (
    <div className="group flex items-baseline gap-5 border-b border-border/50 py-3 hover:bg-bg-3 px-2 -mx-2 transition-colors">
      <a
        href={`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${d.rcept_no}`}
        target="_blank"
        rel="noreferrer"
        className="flex flex-1 items-baseline gap-5 min-w-0"
      >
        <span className="mono text-[12px] text-fg-3 w-[90px] shrink-0">{d.date}</span>
        <span role="img" aria-label={sevLabel} className={`mt-[6px] h-[6px] w-[6px] rounded-full ${dot} shrink-0`} />
        <span className="flex-1 text-[14px] text-fg group-hover:text-fg truncate">{d.title}</span>
        {d.summary && (
          <span className="hidden md:block text-[13px] text-fg-2 truncate max-w-[320px]">
            {d.summary}
          </span>
        )}
      </a>
      <FeedbackButtons target={{ kind: "disclosure", rcept_no: d.rcept_no }} />
    </div>
  );
}
