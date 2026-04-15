import type { DDMemo } from "@/types";
import { Markdown } from "./Markdown";

/** LLM이 본문 끝에 자동 삽입하는 '투자자문 아님' disclaimer를 제거.
 *  카드 footer에 표준 문구가 이미 있어 중복이므로. */
function stripInlineDisclaimer(text: string): string {
  return text
    // `> ⚠️ ... 투자자문 ... `  (blockquote)
    .replace(/>\s*[⚠️⚠].*?투자자문.*?(?:\n\n|\n*$)/gs, "")
    // `⚠️ 본 메모는 투자자문 ... ` (inline)
    .replace(/[⚠️⚠].*?투자자문.*?(?:\n\n|\n*$)/gs, "")
    // `**⚠ ... **`
    .replace(/\*\*[⚠️⚠].*?\*\*\s*/gs, "")
    // 마지막 `---` 구분선만 남는 경우 제거
    .replace(/\n*---\s*$/g, "")
    .trim();
}

/** 한국어 장문 문단을 2~3문장 기준으로 재분할.
 *  LLM이 한 문단에 6+ 문장을 욱여넣는 경우 프론트에서 시각적 호흡 추가.
 *  마크다운 리스트/헤딩/테이블 줄은 건드리지 않음. */
function addBreathingRoom(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  for (const line of lines) {
    // heading, list item, table row, blockquote, code 등은 그대로
    if (/^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|\||`)/.test(line) || !line.trim()) {
      out.push(line);
      continue;
    }
    // 한국어 문장 끝 '다.' '요.' '음.' 뒤에 공백이 있고 4 문장 넘으면 2 문장마다 \n\n
    const sentences = line.split(/(?<=[다요음니까]\.)\s+/);
    if (sentences.length >= 4) {
      const reflowed: string[] = [];
      for (let i = 0; i < sentences.length; i += 2) {
        reflowed.push(sentences.slice(i, i + 2).join(" "));
      }
      out.push(reflowed.join("\n\n"));
    } else {
      out.push(line);
    }
  }
  return out.join("\n");
}

export function DDMemoCard({ memo }: { memo: DDMemo }) {
  return (
    <article className="bg-bg-2 border border-border/50 p-8">
      <header className="flex items-baseline justify-between border-b border-border/50 pb-4 mb-6">
        <h2 className="font-serif text-[24px]">DD 메모</h2>
        <p className="mono text-[12px] text-fg-3">v{memo.version}</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
        <SideBlock title="BULL" body={stripInlineDisclaimer(memo.bull)} tone="accent" />
        <SideBlock title="BEAR" body={stripInlineDisclaimer(memo.bear)} tone="down" />
      </div>

      <section className="border-t border-border/50 pt-6">
        <h3 className="mono text-[11px] tracking-wider uppercase mb-3 text-fg-3">THESIS</h3>
        <Markdown content={addBreathingRoom(stripInlineDisclaimer(memo.thesis))} tone="serif" />
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
