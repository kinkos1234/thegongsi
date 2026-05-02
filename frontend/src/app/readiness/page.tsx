type Check = {
  id: string;
  label: string;
  status: "pass" | "warn" | "fail";
  detail: string;
};

type Readiness = {
  as_of: string;
  score: number;
  status: string;
  coverage: {
    companies: number;
    disclosures: number;
    latest_disclosure_date: string | null;
    latest_disclosure_age_days: number | null;
    recent_7d: number;
    anomalies_7d: number;
    unclassified_7d: number;
    missing_summary_7d: number;
    latest_earnings_reported_date: string | null;
    latest_calendar_event_date: string | null;
  };
  memo_evidence: {
    total_versions: number;
    sampled_versions: number;
    with_disclosure_sources: number;
    with_model_metadata: number;
  };
  disclosure_evidence: {
    anomalies_7d: number;
    with_severity_evidence_7d: number;
  };
  operations: {
    admin_runs_24h: number;
    admin_failed_24h: number;
    latest_admin_run: string | null;
  };
  checks: Check[];
};
type QualityIssue = {
  rcept_no?: string;
  ticker?: string;
  company?: string | null;
  title?: string;
  date?: string;
  dart_url?: string;
  job?: string;
  error?: string | null;
  started_at?: string | null;
  name?: string;
  count?: number;
};
type DataQuality = {
  as_of: string;
  window_days: number;
  status: "pass" | "warn";
  counts: Record<string, number>;
  issues: Record<string, QualityIssue[]>;
};
type SeverityQuality = {
  suite: string;
  rule_set: string;
  total: number;
  passed: number;
  failed: number;
  accuracy: number;
  macro_f1: number;
  labels: Record<string, { precision: number; recall: number; f1: number; tp: number; fp: number; fn: number }>;
  errors: Array<{ id: string; report_nm: string; expected: string; predicted: string }>;
};

async function getReadiness(): Promise<Readiness | null> {
  const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
  try {
    const r = await fetch(`${api}/api/stats/readiness`, { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

async function getDataQuality(): Promise<DataQuality | null> {
  const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
  try {
    const r = await fetch(`${api}/api/stats/data-quality?days=7&limit=8`, { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

async function getSeverityQuality(): Promise<SeverityQuality | null> {
  const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
  try {
    const r = await fetch(`${api}/api/stats/quality/severity`, { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

function fmt(n: number | null | undefined) {
  if (n === null || n === undefined) return "-";
  return n.toLocaleString("ko-KR");
}

export default async function ReadinessPage() {
  const data = await getReadiness();
  const quality = await getDataQuality();
  const severityQuality = await getSeverityQuality();

  return (
    <main className="mx-auto max-w-[1080px] px-6 sm:px-8 py-16 sm:py-20">
      <p className="mono text-[11px] text-fg-3 uppercase tracking-[0.18em]">
        Institutional readiness
      </p>
      <h1 className="mt-3 font-serif text-[34px] sm:text-[44px] leading-[1.08]">
        PoC 신뢰 지표
      </h1>
      <p className="mt-5 max-w-[720px] text-[15px] leading-[1.75] text-fg-2">
        VC·투자운용사 검토에서 필요한 데이터 신선도, 커버리지, 이상 공시 분류,
        AI 메모 증거 메타데이터를 한 화면에 노출합니다.
      </p>

      {!data ? (
        <section className="mt-12 border border-border/60 bg-bg-2/60 p-6">
          <p className="text-[14px] text-fg-2">readiness 지표를 불러오지 못했습니다.</p>
        </section>
      ) : (
        <>
          <section className="mt-12 grid grid-cols-1 md:grid-cols-4 gap-6">
            <Metric label="score" value={`${data.score}`} suffix="/100" />
            <Metric label="disclosures" value={fmt(data.coverage.disclosures)} />
            <Metric label="companies" value={fmt(data.coverage.companies)} />
            <Metric label="7d anomalies" value={fmt(data.coverage.anomalies_7d)} />
          </section>

          <section className="mt-12 grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-10">
            <div className="border-t border-border/60 pt-6">
              <h2 className="font-serif text-[24px]">운영 체크</h2>
              <div className="mt-5 space-y-3">
                {data.checks.map((c) => (
                  <div key={c.id} className="flex items-start gap-4 border-b border-border/40 pb-3">
                    <span
                      className={`mt-[7px] h-2 w-2 rounded-full ${
                        c.status === "pass" ? "bg-accent" : "bg-sev-med"
                      }`}
                    />
                    <div>
                      <p className="text-[14px] text-fg">{c.label}</p>
                      <p className="mono mt-1 text-[11px] text-fg-3">{c.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-border/60 pt-6">
              <h2 className="font-serif text-[24px]">증거 상태</h2>
              <dl className="mt-5 space-y-3 text-[13px]">
                <Row label="latest disclosure" value={data.coverage.latest_disclosure_date ?? "-"} />
                <Row label="latest age" value={`${data.coverage.latest_disclosure_age_days ?? "-"} days`} />
                <Row label="recent 7d" value={fmt(data.coverage.recent_7d)} />
                <Row label="unclassified 7d" value={fmt(data.coverage.unclassified_7d)} />
                <Row label="missing summaries 7d" value={fmt(data.coverage.missing_summary_7d)} />
                <Row
                  label="severity evidence"
                  value={`${fmt(data.disclosure_evidence.with_severity_evidence_7d)}/${fmt(
                    data.disclosure_evidence.anomalies_7d,
                  )}`}
                />
                <Row
                  label="memo sources"
                  value={`${data.memo_evidence.with_disclosure_sources}/${data.memo_evidence.sampled_versions}`}
                />
                <Row label="admin runs 24h" value={fmt(data.operations.admin_runs_24h)} />
                <Row label="admin failed 24h" value={fmt(data.operations.admin_failed_24h)} />
                <Row label="latest admin run" value={data.operations.latest_admin_run?.slice(0, 19) ?? "-"} />
                <Row label="as of" value={data.as_of.slice(0, 19)} />
              </dl>
            </div>
          </section>

          {quality && <QualitySection quality={quality} />}
          {severityQuality && <SeverityQualitySection report={severityQuality} />}
        </>
      )}
    </main>
  );
}

function pct(value: number) {
  return `${Math.round(value * 1000) / 10}%`;
}

function SeverityQualitySection({ report }: { report: SeverityQuality }) {
  return (
    <section className="mt-14 border-t border-border/60 pt-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="font-serif text-[24px]">Severity 정확도</h2>
          <p className="mt-2 text-[13px] text-fg-2">
            Gold set 기준 룰 기반 이상공시 판정기의 회귀를 추적합니다.
          </p>
        </div>
        <span className="mono text-[12px] text-fg-3">{report.suite} · {report.rule_set}</span>
      </div>

      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="accuracy" value={pct(report.accuracy)} />
        <Metric label="macro f1" value={pct(report.macro_f1)} />
        <Metric label="gold cases" value={fmt(report.total)} />
        <Metric label="failed" value={fmt(report.failed)} />
      </div>

      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
        {Object.entries(report.labels).map(([label, m]) => (
          <div key={label} className="border-t border-border/50 pt-3">
            <p className="mono text-[11px] uppercase tracking-[0.12em] text-fg-3">{label}</p>
            <p className="mono mt-2 text-[13px] text-fg-2">
              precision {pct(m.precision)} · recall {pct(m.recall)} · f1 {pct(m.f1)}
            </p>
            <p className="mono mt-1 text-[11px] text-fg-3">tp={m.tp} fp={m.fp} fn={m.fn}</p>
          </div>
        ))}
      </div>

      {report.errors.length > 0 && (
        <ul className="mt-8 border-t border-border/40">
          {report.errors.slice(0, 5).map((e) => (
            <li key={e.id} className="border-b border-border/40 py-3 text-[13px]">
              <p className="text-fg">{e.report_nm}</p>
              <p className="mono mt-1 text-[11px] text-fg-3">expected={e.expected} predicted={e.predicted}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function QualitySection({ quality }: { quality: DataQuality }) {
  const groups = [
    ["unclassified_disclosures", "Unclassified disclosures"],
    ["missing_summaries", "Missing summaries"],
    ["missing_severity_evidence", "Missing severity evidence"],
    ["duplicate_company_names", "Duplicate company names"],
    ["failed_admin_jobs", "Failed admin jobs"],
  ] as const;
  return (
    <section className="mt-14 border-t border-border/60 pt-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="font-serif text-[24px]">품질 진단</h2>
          <p className="mt-2 text-[13px] text-fg-2">
            최근 {quality.window_days}일 기준으로 조치가 필요한 실제 row를 샘플링합니다.
          </p>
        </div>
        <span className={`mono text-[12px] ${quality.status === "pass" ? "text-accent" : "text-sev-med"}`}>
          {quality.status}
        </span>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-5 gap-4">
        {groups.map(([key, label]) => (
          <div key={key} className="border-t border-border/50 pt-3">
            <p className="mono text-[10px] uppercase tracking-[0.12em] text-fg-3">{label}</p>
            <p className="mono mt-2 text-[22px] text-fg">{fmt(quality.counts[key] ?? 0)}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
        {groups.map(([key, label]) => {
          const items = quality.issues[key] ?? [];
          return (
            <div key={key} className="border-t border-border/50 pt-4">
              <h3 className="mono text-[11px] uppercase tracking-[0.12em] text-fg-3">{label}</h3>
              {items.length === 0 ? (
                <p className="mt-3 text-[13px] text-fg-3">문제 없음</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {items.slice(0, 5).map((item, idx) => (
                    <li key={`${key}-${item.rcept_no ?? item.job ?? item.name ?? idx}`} className="text-[13px]">
                      <p className="text-fg truncate">
                        {item.title ?? item.name ?? item.job ?? item.rcept_no ?? "issue"}
                      </p>
                      <p className="mono mt-1 text-[11px] text-fg-3">
                        {item.ticker ? `${item.ticker} · ` : ""}
                        {item.date ?? item.started_at?.slice(0, 10) ?? ""}
                        {item.count ? ` · count=${item.count}` : ""}
                        {item.error ? ` · ${item.error}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ label, value, suffix = "" }: { label: string; value: string; suffix?: string }) {
  return (
    <div className="border-t border-border/60 pt-4">
      <p className="mono text-[11px] uppercase tracking-[0.15em] text-fg-3">{label}</p>
      <p className="mono mt-2 text-[28px] text-fg tabular-nums">
        {value}
        <span className="text-[14px] text-fg-3">{suffix}</span>
      </p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/40 pb-2">
      <dt className="mono text-[11px] uppercase tracking-[0.12em] text-fg-3">{label}</dt>
      <dd className="mono text-[12px] text-fg-2 text-right">{value}</dd>
    </div>
  );
}
