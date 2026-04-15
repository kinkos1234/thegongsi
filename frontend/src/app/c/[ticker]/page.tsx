import { notFound } from "next/navigation";
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

  const [disclosures, quote, memo] = await Promise.all([
    safe<Disclosure[]>(fetch(`${api}/api/disclosures/?ticker=${ticker}`, { cache: "no-store" })),
    safe<Quote>(fetch(`${api}/api/quotes/${ticker}`, { cache: "no-store" })),
    safe<DDMemo>(fetch(`${api}/api/memos/${ticker}`, { cache: "no-store" })),
  ]);
  return {
    company,
    companyStatus,
    disclosures: disclosures ?? [],
    memo,
    quote,
  };
}

export default async function CompanyPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;

  if (!/^\d{6}$/.test(ticker)) {
    notFound();
  }

  const data = await fetchData(ticker);

  // backend·quote 모두 실패 = ticker 미존재 → 404
  if (!data.company && !data.quote?.price) {
    notFound();
  }

  const company: Company = data.company
    ? { ...data.company, price: data.quote?.price ?? data.company.price, change: data.quote?.change_percent ?? data.company.change }
    : {
        ticker,
        name: ticker,
        market: "KOSPI",
        sector: null,
        price: data.quote?.price ?? null,
        change: data.quote?.change_percent ?? null,
      };
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
            {data.disclosures.length === 0 ? (
              <p className="py-12 text-fg-3">
                공시 데이터 없음. DART 일일 수집(<span className="mono">scheduler.py --once</span>) 실행 후 다시 확인하세요.
              </p>
            ) : (
              data.disclosures.map((d) => <DisclosureRow key={d.rcept_no} d={d} />)
            )}
          </div>
        </section>

        <aside>
          {data.memo ? (
            <DDMemoCard memo={data.memo} />
          ) : (
            <NoMemoCard ticker={ticker} />
          )}
        </aside>
      </div>
    </main>
  );
}

function NoMemoCard({ ticker }: { ticker: string }) {
  return (
    <article className="bg-bg-2 border border-border/50 p-8">
      <h2 className="font-serif text-[24px] mb-3">DD 메모</h2>
      <p className="text-[14px] text-fg-2 leading-[1.65] mb-6">
        이 종목에 대한 메모가 아직 없습니다.
      </p>
      <form action={`/api/memos/generate`} method="post" className="mb-2">
        <GenerateButton ticker={ticker} />
      </form>
      <p className="text-[11px] text-fg-3 mono">
        POST /api/memos/generate &#123;&quot;ticker&quot;: &quot;{ticker}&quot;&#125;
      </p>
    </article>
  );
}

function GenerateButton({ ticker }: { ticker: string }) {
  return (
    <a
      href={`#`}
      className="mono text-[12px] text-accent border border-accent px-4 py-2 hover:bg-accent-dim transition-colors inline-block"
    >
      generate memo for {ticker} →
    </a>
  );
}
