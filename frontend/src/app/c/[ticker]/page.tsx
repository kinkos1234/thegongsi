import { CompanyHeader } from "@/components/CompanyHeader";
import { DisclosureRow } from "@/components/DisclosureRow";
import { DDMemoCard } from "@/components/DDMemoCard";
import { Sparkline } from "@/components/Sparkline";
import type { Company, Disclosure, DDMemo, Quote } from "@/types";

async function fetchData(ticker: string): Promise<{
  company: Company | null;
  companyStatus: number;
  disclosures: Disclosure[];
  memo: DDMemo | null;
  quote: Quote | null;
}> {
  const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
  const safe = async <T,>(p: Promise<Response>): Promise<T | null> => {
    try {
      const r = await p;
      return r.ok ? await r.json() : null;
    } catch {
      return null;
    }
  };

  let companyStatus = 200;
  let company: Company | null = null;
  try {
    const r = await fetch(`${api}/api/companies/${ticker}`, { cache: "no-store" });
    companyStatus = r.status;
    if (r.ok) company = await r.json();
  } catch {
    companyStatus = 0;
  }

  const [disclosures, quote] = await Promise.all([
    safe<Disclosure[]>(fetch(`${api}/api/disclosures/?ticker=${ticker}`, { cache: "no-store" })),
    safe<Quote>(fetch(`${api}/api/quotes/${ticker}`, { cache: "no-store" })),
  ]);
  return {
    company,
    companyStatus,
    disclosures: disclosures ?? [],
    memo: null,
    quote,
  };
}

import { notFound } from "next/navigation";

export default async function CompanyPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;

  // 6자리 숫자가 아니면 즉시 404 (Bach)
  if (!/^\d{6}$/.test(ticker)) {
    notFound();
  }

  const data = await fetchData(ticker);

  // backend/quote 모두 실패 = ticker 미존재 → 404
  if (data.companyStatus === 404 && !data.quote?.price) {
    notFound();
  }

  // 개발 편의: mock은 ticker가 005930일 때만 제공
  if (!data.company && !data.quote?.price && ticker !== "005930") {
    notFound();
  }
  const baseCompany = data.company ?? mock(ticker);
  const company = data.quote?.price != null
    ? { ...baseCompany, price: data.quote.price, change: data.quote.change_percent }
    : baseCompany;
  const disclosures = data.disclosures.length ? data.disclosures : (ticker === "005930" ? mockDisc() : []);
  const memo = data.memo ?? mockMemo();
  const up = (company.change ?? 0) >= 0;

  return (
    <main className="mx-auto max-w-[1080px] px-8 py-16">
      <CompanyHeader c={company} />

      {data.quote?.series && data.quote.series.length > 0 && (
        <section className="mt-10">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="mono text-[11px] text-fg-3 uppercase tracking-wider">
              최근 {data.quote.series.length}거래일 · 종가
            </h2>
            <span className="mono text-[11px] text-fg-3">
              {data.quote.cached ? `cached ${Math.round(data.quote.age_sec / 60)}m` : "fresh"}
            </span>
          </div>
          <Sparkline data={data.quote.series} up={up} />
        </section>
      )}

      <div className="mt-16 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-16">
        <section>
          <h2 className="font-serif text-[24px] mb-6">공시</h2>
          <div>
            {disclosures.length === 0 ? (
              <p className="py-12 text-fg-3">공시 데이터 없음. DART 수집 실행 후 다시 확인하세요.</p>
            ) : (
              disclosures.map((d) => <DisclosureRow key={d.rcept_no} d={d} />)
            )}
          </div>
        </section>

        <aside>
          <DDMemoCard memo={memo} />
        </aside>
      </div>
    </main>
  );
}

function mock(ticker: string): Company {
  return {
    ticker,
    name: ticker === "005930" ? "삼성전자" : "예시 종목",
    market: "KOSPI",
    sector: "반도체",
    price: 72800,
    change: 1.24,
  };
}

function mockDisc(): Disclosure[] {
  return [
    { rcept_no: "20260415000001", ticker: "005930", title: "분기보고서 (2026.Q1)", date: "2026-04-15", summary: "매출 73조 · 영업익 9.8조", severity: "low" },
    { rcept_no: "20260414000055", ticker: "005930", title: "주요사항보고서(자기주식취득결정)", date: "2026-04-14", summary: "자사주 3,000억 규모 매입", severity: "med" },
    { rcept_no: "20260412000088", ticker: "005930", title: "최대주주등소유주식변동신고서", date: "2026-04-12", summary: "이재용 회장 0.01% 변동", severity: "med" },
    { rcept_no: "20260410000012", ticker: "005930", title: "임원·주요주주 특정증권등 소유상황보고서", date: "2026-04-10", summary: null, severity: "low" },
  ];
}

function mockMemo(): DDMemo {
  return {
    memo_id: "mock",
    version_id: "mock",
    version: 1,
    bull:
      "HBM3E 점유율 확대와 파운드리 2나노 수율 개선이 2H26 이익 모멘텀으로 작용. [출처: rcept_no=20260415000001]\n폴더블 점유율은 글로벌 1위 유지, 평균판매가 상승.",
    bear:
      "메모리 사이클 피크 우려, 중국 HBM 추격 속도.\n자사주 취득이 주주환원 시그널이나 성장 투자 대신이라는 해석 여지. [출처: rcept_no=20260414000055]",
    thesis:
      "Risk/Reward 균형. HBM 경쟁 심화와 가격 변동성을 주시하되, 파운드리 턴어라운드가 확인되면 중장기 re-rating 가능.",
  };
}
