import type { DDMemo } from "@/types";
import { Markdown } from "./Markdown";

export function DDMemoCard({ memo }: { memo: DDMemo }) {
  return (
    <article className="bg-bg-2 border border-border/50 p-8">
      <header className="flex items-baseline justify-between border-b border-border/50 pb-4 mb-6">
        <h2 className="font-serif text-[24px]">DD 메모</h2>
        <p className="mono text-[12px] text-fg-3">v{memo.version}</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
        <SideBlock title="BULL" body={memo.bull} tone="accent" />
        <SideBlock title="BEAR" body={memo.bear} tone="down" />
      </div>

      <section className="border-t border-border/50 pt-6">
        <h3 className="mono text-[11px] tracking-wider uppercase mb-3 text-fg-3">THESIS</h3>
        <Markdown content={memo.thesis} tone="serif" />
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
      <Markdown content={body} tone="body" />
    </div>
  );
}
