import type { Disclosure } from "@/types";

const SEV_COLOR: Record<string, string> = {
  high: "bg-sev-high",
  med: "bg-sev-med",
  low: "bg-fg-3",
};

export function DisclosureRow({ d }: { d: Disclosure }) {
  const dot = d.severity ? SEV_COLOR[d.severity] : "bg-fg-3";
  return (
    <a
      href={`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${d.rcept_no}`}
      target="_blank"
      rel="noreferrer"
      className="group flex items-baseline gap-5 border-b border-border/50 py-3 hover:bg-bg-3 px-2 -mx-2 transition-colors"
    >
      <span className="mono text-[12px] text-fg-3 w-[90px] shrink-0">{d.date}</span>
      <span className={`mt-[6px] h-[6px] w-[6px] rounded-full ${dot} shrink-0`} />
      <span className="flex-1 text-[14px] text-fg group-hover:text-fg">{d.title}</span>
      {d.summary && (
        <span className="hidden md:block text-[13px] text-fg-2 truncate max-w-[320px]">
          {d.summary}
        </span>
      )}
    </a>
  );
}
