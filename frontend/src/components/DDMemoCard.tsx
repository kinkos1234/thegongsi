import type { DDMemo } from "@/types";
import { Markdown } from "./Markdown";
import { FeedbackButtons } from "./FeedbackButtons";

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

/** 한국어 장문 문단을 시각적으로 분할.
 *  규칙:
 *  - heading/list/table/blockquote/code 라인은 건드리지 않음
 *  - 줄 길이 > 120자이거나 문장 >= 3개면 문장 경계에서 분할
 *  - ① ② ③ ④ ⑤ 같은 인라인 열거 기호 앞에서 줄바꿈 강제
 *  - 한국어 문장 종결(다./요./음./니까./함./까./나./라.)에서 split */
function addBreathingRoom(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  for (const line of lines) {
    if (/^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|\||`)/.test(line) || !line.trim()) {
      out.push(line);
      continue;
    }
    // 인라인 열거 기호 (①~⑳) 앞에 줄바꿈 강제
    let work = line.replace(/\s*([①-⑳])/g, "\n\n$1");
    // 문장 경계 split
    const parts = work.split(/\n\n/);
    const reflowed: string[] = [];
    for (const p of parts) {
      // 문장 끝 split — 마침표+공백 (앞이 숫자 아닌 경우, "3.14" 제외)
      const sentences = p.split(/(?<=[^\d\s])\.\s+/);
      if (p.length > 120 && sentences.length >= 2) {
        // split으로 마침표가 제거됐으므로 마지막 문장 빼고 '.' 복원
        const withPeriod = sentences.map((s, i) =>
          i < sentences.length - 1 ? s + "." : s,
        );
        // 각 문장을 별도 문단으로 (긴 문단에서 최대 시각적 호흡)
        reflowed.push(withPeriod.join("\n\n"));
      } else {
        reflowed.push(p);
      }
    }
    out.push(reflowed.join("\n\n"));
  }
  return out.join("\n");
}

export function DDMemoCard({ memo }: { memo: DDMemo }) {
  const disclosures = memo.sources?.disclosures ?? [];
  const model = memo.generated_by?.split("|")[0] ?? null;

  return (
    <article className="border-t border-b border-border/50 py-8">
      <header className="flex items-baseline justify-between mb-6">
        <h2 className="font-serif text-[24px]">DD 메모</h2>
        <div className="flex items-baseline gap-4">
          <FeedbackButtons target={{ kind: "memo", memo_version_id: memo.version_id }} />
          <p className="mono text-[12px] text-fg-3">v{memo.version}</p>
        </div>
      </header>

      {/* BULL | BEAR 2-col 상단 + THESIS 전체 너비 하단 (편집자 칼럼 + 결론) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-10 mb-8">
        <SideBlock title="BULL" body={stripInlineDisclaimer(memo.bull)} tone="accent" />
        <SideBlock title="BEAR" body={stripInlineDisclaimer(memo.bear)} tone="down" />
      </div>
      <section className="border-t border-border/50 pt-6">
        <h3 className="mono text-[11px] tracking-wider uppercase mb-3 text-fg-3">THESIS</h3>
        <Markdown content={addBreathingRoom(stripInlineDisclaimer(memo.thesis))} tone="serif" />
      </section>

      <p className="mt-8 text-[12px] italic text-fg-3">
        — 본 메모는 AI가 공시·뉴스만을 근거로 생성한 정보로, 투자자문이 아닙니다.
      </p>
      {(disclosures.length > 0 || model) && (
        <section className="mt-5 border-t border-border/40 pt-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mono text-[11px] text-fg-3">
            {model && <span>model {model}</span>}
            {memo.created_at && <span>generated {memo.created_at.slice(0, 10)}</span>}
            {disclosures.length > 0 && <span>evidence {disclosures.length} filings</span>}
          </div>
          {disclosures.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {disclosures.slice(0, 8).map((s) => (
                <a
                  key={s.rcept_no}
                  href={s.dart_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mono text-[11px] text-fg-3 border border-border/60 px-2 py-1 hover:text-accent hover:border-accent/60"
                >
                  {s.rcept_no.slice(0, 8)}…
                </a>
              ))}
            </div>
          )}
        </section>
      )}
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
