import { HomeSearch } from "@/components/HomeSearch";
import { UpcomingExDates } from "@/components/UpcomingExDates";
import { RecentEarnings } from "@/components/RecentEarnings";
import { MarketAnomalies } from "@/components/MarketAnomalies";
import { CoverageStats } from "@/components/CoverageStats";
import { BrandMark } from "@/components/BrandMark";
import { PulseRibbon } from "@/components/PulseRibbon";

export default function Home() {
  return (
    <>
      <section className="mx-auto max-w-[720px] px-6 sm:px-8 pt-20 sm:pt-28 pb-24 sm:pb-32">
        <div className="flex items-center gap-3">
          <BrandMark size={14} />
          <p className="mono text-fg-3 text-[12px] sm:text-[13px] tracking-[0.18em]">
            THE GONGSI · 더공시 · v0.3.1 · OSS
          </p>
        </div>

        <h1
          className="mt-6 sm:mt-8 font-serif leading-[1.08] tracking-[-0.02em]"
          style={{ fontSize: "clamp(40px, 8vw, 72px)" }}
        >
          내 종목 공시,
          <br />
          <span className="text-fg-2">놓치지 않게.</span>
        </h1>

        <p className="mt-8 sm:mt-10 text-[15px] sm:text-[17px] leading-[1.7] text-fg-2">
          관심종목의 DART 공시를 AI가 한국어로 요약하고, 유상증자·전환사채·최대주주 변경 같은
          위험 신호를 먼저 띄웁니다. 필요하면 DD 메모와 Ask로 근거까지 파고듭니다.
        </p>

        <HomeSearch />

        <MarketAnomalies limit={3} />
        <PulseRibbon days={30} />

        <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-[13px] sm:text-[14px]">
          <a
            href="/watchlist"
            className="mono border-b border-accent text-accent hover:bg-accent-dim hover:text-fg px-1 py-0.5 transition-colors"
          >
            관심종목 추가 →
          </a>
          <a
            href="/events"
            className="mono border-b border-border text-fg-2 hover:border-accent hover:text-accent px-1 py-0.5 transition-colors"
          >
            이상공시 큐 →
          </a>
          <span className="text-fg-3 mono">MIT · BYOK · self-hostable</span>
        </div>

        <CoverageStats />

        <UpcomingExDates days={7} />
        <RecentEarnings limit={5} />
      </section>

      <section className="border-t border-border/50">
        <div className="mx-auto max-w-[1080px] px-6 sm:px-8 py-20 sm:py-28 grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-16">
          <div>
            <p className="mono text-[11px] sm:text-[12px] text-fg-3 uppercase tracking-[0.18em]">
              왜 DART인가
            </p>
            <h2
              className="mt-4 font-serif leading-[1.15]"
              style={{ fontSize: "clamp(28px, 5vw, 40px)" }}
            >
              공시는 <span className="text-fg-2">원재료</span>,<br />
              문제는 <span className="text-fg-2">우선순위</span>.
            </h2>
          </div>
          <div className="space-y-6 pt-2 sm:pt-4">
            <p className="text-[15px] sm:text-[16px] leading-[1.75] text-fg-2">
              DART에는 연 100만건의 공시가 오른다. 개인 투자자가 매일 원문을 전부 읽기는 어렵지만,
              상장폐지·감사거절·희석·최대주주변경 같은 신호는 늦게 보면 비싸다.
            </p>
            <p className="text-[15px] sm:text-[16px] leading-[1.75] text-fg-2">
              The Gongsi는 관심종목을 기준으로 먼저 걸러주고, 이상 공시는 리뷰 큐와 DD 메모로
              이어줍니다. Ask는 더 깊게 파고드는 파워 기능입니다.
            </p>
            <p className="mono text-[11px] sm:text-[12px] text-fg-3 uppercase tracking-[0.18em] pt-2">
              참고
            </p>
            <ul className="text-[13px] sm:text-[14px] text-fg-2 space-y-1.5">
              <li>· Fey · Seeking Alpha · Hindenburg Research</li>
              <li>· Open source, Korean-first, ad-free</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="border-t border-border/50">
        <div className="mx-auto max-w-[1080px] px-6 sm:px-8 py-16 sm:py-20 grid grid-cols-1 md:grid-cols-3 gap-10 sm:gap-12">
          <Feature label="관심종목 레이더" value="내 종목 공시 · 이상 신호 · 리뷰 큐" />
          <Feature label="DD 메모" value="bull / bear / thesis · 원문 근거" />
          <Feature label="Ask" value="자연어 질의 · 그래프 + 공시 hybrid" />
        </div>
      </section>

      <footer className="border-t border-border/50 py-10 sm:py-12">
        <div className="mx-auto max-w-[1080px] px-6 sm:px-8 flex flex-wrap items-baseline justify-between gap-3">
          <p className="mono text-[11px] sm:text-[12px] text-fg-3">© 2026 The Gongsi · MIT</p>
          <p className="mono text-[11px] sm:text-[12px] text-fg-3">투자자문 아님 · 정보 제공만</p>
        </div>
      </footer>
    </>
  );
}

function Feature({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mono text-fg-3 text-[11px] sm:text-[12px] tracking-[0.18em] uppercase">
        {label}
      </p>
      <p className="mt-3 text-[14px] sm:text-[15px] leading-[1.65] text-fg">{value}</p>
    </div>
  );
}
