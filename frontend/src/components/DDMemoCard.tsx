import type { DDMemo } from "@/types";

export function DDMemoCard({ memo }: { memo: DDMemo }) {
  return (
    <article className="bg-bg-2 border border-border/50 p-8">
      <header className="flex items-baseline justify-between border-b border-border/50 pb-4 mb-6">
        <h2 className="font-serif text-[24px]">DD 메모</h2>
        <p className="mono text-[12px] text-fg-3">v{memo.version}</p>
      </header>

      <Section title="BULL" body={memo.bull} tone="accent" />
      <Section title="BEAR" body={memo.bear} tone="down" />
      <Section title="THESIS" body={memo.thesis} tone="fg" />

      <p className="mt-8 text-[12px] text-fg-3">
        ※ 본 메모는 AI가 공시·뉴스만을 근거로 생성한 정보로, 투자자문이 아닙니다.
      </p>
    </article>
  );
}

function Section({
  title,
  body,
  tone,
}: {
  title: string;
  body: string;
  tone: "accent" | "down" | "fg";
}) {
  const color = tone === "accent" ? "text-accent" : tone === "down" ? "text-down" : "text-fg";
  return (
    <section className="mb-8 last:mb-0">
      <h3 className={`mono text-[12px] tracking-wider uppercase mb-3 ${color}`}>{title}</h3>
      <div className="text-[15px] leading-[1.7] text-fg-2 whitespace-pre-wrap">{body}</div>
    </section>
  );
}
