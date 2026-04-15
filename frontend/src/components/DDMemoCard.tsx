import type { DDMemo } from "@/types";
import type { ReactNode } from "react";

export function DDMemoCard({ memo }: { memo: DDMemo }) {
  return (
    <article className="bg-bg-2 border border-border/50 p-8">
      <header className="flex items-baseline justify-between border-b border-border/50 pb-4 mb-6">
        <h2 className="font-serif text-[24px]">DD 메모</h2>
        <p className="mono text-[12px] text-fg-3">v{memo.version}</p>
      </header>

      {/* Rams: BULL/BEAR side-by-side, THESIS는 결론이므로 serif 확대 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
        <SideBlock title="BULL" body={memo.bull} tone="accent" />
        <SideBlock title="BEAR" body={memo.bear} tone="down" />
      </div>

      <section className="border-t border-border/50 pt-6">
        <h3 className="mono text-[11px] tracking-wider uppercase mb-3 text-fg-3">THESIS</h3>
        <p className="font-serif text-[20px] leading-[1.5] text-fg whitespace-pre-wrap">
          {renderWithCitations(memo.thesis)}
        </p>
      </section>

      <p className="mt-8 text-[12px] text-fg-3">
        ※ 본 메모는 AI가 공시·뉴스만을 근거로 생성한 정보로, 투자자문이 아닙니다.
      </p>
    </article>
  );
}

function SideBlock({
  title,
  body,
  tone,
}: {
  title: string;
  body: string;
  tone: "accent" | "down";
}) {
  const color = tone === "accent" ? "text-accent" : "text-down";
  return (
    <div>
      <h3 className={`mono text-[11px] tracking-wider uppercase mb-3 ${color}`}>{title}</h3>
      <div className="text-[14px] leading-[1.65] text-fg-2 whitespace-pre-wrap">
        {renderWithCitations(body)}
      </div>
    </div>
  );
}

/** [출처: rcept_no=xxx] → mono 10px 컴팩트 링크 (DART 원문으로). */
function renderWithCitations(text: string): ReactNode[] {
  const parts = text.split(/(\[출처:\s*rcept_no=\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/\[출처:\s*rcept_no=(\d+)\]/);
    if (m) {
      const rcept = m[1];
      return (
        <a
          key={i}
          href={`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${rcept}`}
          target="_blank"
          rel="noreferrer"
          className="mono text-[10px] text-fg-3 hover:text-accent align-baseline px-1 whitespace-nowrap"
          title={`DART rcept_no=${rcept}`}
        >
          [{rcept.slice(0, 8)}…]
        </a>
      );
    }
    return <span key={i}>{p}</span>;
  });
}
