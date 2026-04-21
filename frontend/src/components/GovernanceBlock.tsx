"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { OwnershipDendrogram } from "./OwnershipDendrogram";

type Shareholder = {
  name: string;
  type: "person" | "corp" | "fund" | "special";
  stake_pct: number | null;
  shares: number | null;
  holder_ticker: string | null;
};

type Insider = {
  name: string;
  role: string;
  classification: "exec" | "outside" | "audit" | null;
  is_registered: boolean | null;
  own_shares: number | null;
};

type Linked = {
  ticker: string;
  name: string | null;
  stake_pct: number | null;
  as_of: string;
};

type Governance = {
  ticker: string;
  name: string | null;
  as_of: string | null;
  shareholders: Shareholder[];
  insiders: Insider[];
  parents: Linked[];
  children: Linked[];
  cycles: string[][];
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

const HOLDER_TYPE: Record<string, string> = {
  person: "개인",
  corp: "법인",
  fund: "기관",
  special: "특수관계",
};

const CLASSIFICATION: Record<string, string> = {
  exec: "등기/미등기임원",
  outside: "사외이사",
  audit: "감사위원",
};

/** 지배구조 데이터에서 한 줄 해석 문구 생성.
 *
 * - 오너 일가 직접 지분: holder_type=person인 shareholders 중 임원(insiders의 exec)과 겹치는 이름
 * - 계열사 간접 지분: holder_type=corp 지분 합
 * - 순환출자 고리 수
 */
function buildNarrative(d: Governance): string | null {
  const execNames = new Set(
    d.insiders.filter((i) => i.classification === "exec").map((i) => i.name),
  );
  const ownerDirect = d.shareholders
    .filter((s) => s.type === "person" && execNames.has(s.name))
    .reduce((acc, s) => acc + (s.stake_pct ?? 0), 0);
  const corpIndirect = d.shareholders
    .filter((s) => s.type === "corp")
    .reduce((acc, s) => acc + (s.stake_pct ?? 0), 0);
  const fundShare = d.shareholders
    .filter((s) => s.type === "fund")
    .reduce((acc, s) => acc + (s.stake_pct ?? 0), 0);

  const parts: string[] = [];
  if (ownerDirect > 0) {
    parts.push(`오너 일가 직접 ${ownerDirect.toFixed(2)}%`);
  }
  if (corpIndirect > 0) {
    parts.push(`계열사 지분 ${corpIndirect.toFixed(2)}%`);
  }
  if (fundShare > 0) {
    parts.push(`기관 ${fundShare.toFixed(2)}%`);
  }
  if (d.cycles.length > 0) {
    parts.push(`순환출자 ${d.cycles.length}건 감지`);
  }
  if (parts.length === 0) return null;
  return parts.join(" · ");
}

type ExtractState = "idle" | "running" | "done" | "cooldown" | "ip_limit" | "no_data" | "error";

/** 지배구조 블록 — 최대주주 / 임원 / 모자회사 / 순환출자 고리.
 *
 * 한국 시장 고유 시각: 재벌 지배구조 특성을 그대로 화면에 드러낸다.
 * 데이터 없으면 no-data fallback + 사용자가 직접 AI 추출 트리거 버튼 노출.
 */
export function GovernanceBlock({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Governance | null>(null);
  const [err, setErr] = useState(false);
  const [extract, setExtract] = useState<ExtractState>("idle");
  const [extractMsg, setExtractMsg] = useState<string | null>(null);

  const load = (signal?: AbortSignal) =>
    fetch(`${API}/api/companies/${ticker}/governance`, { signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setErr(true));

  useEffect(() => {
    const ctl = new AbortController();
    load(ctl.signal);
    return () => ctl.abort();
  }, [ticker]);

  async function triggerExtract() {
    setExtract("running");
    setExtractMsg(null);
    try {
      const r = await fetch(
        `${API}/api/companies/${ticker}/governance/extract`,
        { method: "POST" },
      );
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      const d = await r.json();
      const st: string = d.status || "error";
      if (st === "done" || st === "ok" || st === "already_extracted") {
        setExtract("done");
        await load();
      } else if (st === "cooldown") {
        setExtract("cooldown");
        const until = d.next_eligible_at
          ? new Date(d.next_eligible_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
          : null;
        setExtractMsg(until ? `최근 시도가 있어 ${until} 이후 재시도 가능` : "쿨다운 중");
      } else if (st === "ip_limit") {
        setExtract("ip_limit");
        setExtractMsg(`시간당 ${d.limits?.per_hour}회 · 일 ${d.limits?.per_day}회 초과`);
      } else if (st === "no_data") {
        setExtract("no_data");
        setExtractMsg("최근 공시에 지배구조 관련 내용이 없습니다");
      } else {
        setExtract("error");
        setExtractMsg(`알 수 없는 상태: ${st}`);
      }
    } catch (e) {
      setExtract("error");
      setExtractMsg(e instanceof Error ? e.message : "요청 실패");
    }
  }

  if (err || !data) return null;
  const { shareholders, insiders, parents, children, cycles } = data;
  const hasAny =
    shareholders.length > 0 ||
    insiders.length > 0 ||
    parents.length > 0 ||
    children.length > 0 ||
    cycles.length > 0;

  if (!hasAny) {
    const btnLabel =
      extract === "idle" ? "AI 지배구조 추출 시작 →"
      : extract === "running" ? "추출 중… (20-60초)"
      : extract === "done" ? "✓ 완료 — 새로고침 중"
      : extract === "no_data" ? "재시도 →"
      : extract === "cooldown" || extract === "ip_limit" ? "잠시 후 재시도 →"
      : "재시도 →";

    return (
      <section className="mt-10 border-t border-border/50 pt-8">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="font-serif text-[22px] tracking-tight">지배구조</h2>
          <span className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em]">
            no data
          </span>
        </div>
        <div className="border border-border/40 bg-bg-2/30 px-5 py-4">
          <p className="text-[13px] text-fg-2 leading-[1.65]">
            이 종목의 지배구조 스냅샷이 아직 수집되지 않았습니다. 아래 버튼을 누르면
            DART 공시 본문에서 Claude가 최대주주·임원·계열사 지분을 실시간으로 추출합니다.
          </p>
          <div className="mt-3">
            <button
              onClick={triggerExtract}
              disabled={extract === "running" || extract === "done"}
              className="mono text-[12px] text-accent border border-accent px-4 py-2 hover:bg-accent-dim transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {btnLabel}
            </button>
          </div>
          {extractMsg && (
            <p className="mono text-[11px] text-fg-3 mt-2">{extractMsg}</p>
          )}
          <p className="mono text-[10px] text-fg-3 mt-3">
            한 종목당 1시간 · IP당 시간 3회 / 일 10회 제한 — 비용 보호.
          </p>
        </div>
      </section>
    );
  }

  const narrative = buildNarrative(data);

  return (
    <section className="mt-10 border-t border-border/50 pt-8">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="font-serif text-[22px] tracking-tight">지배구조</h2>
        {data.as_of && (
          <span className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em]">
            as of {data.as_of}
          </span>
        )}
      </div>
      {narrative && (
        <p className="mb-6 text-[14px] text-fg-2 leading-[1.65] border-l-2 border-accent/50 pl-4">
          {narrative}
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {shareholders.length > 0 && (
          <div>
            <h3 className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em] mb-3">
              최대주주 TOP {shareholders.length}
            </h3>
            <ul className="divide-y divide-border/40">
              {shareholders.map((s) => (
                <li
                  key={`${s.name}-${s.holder_ticker ?? ""}`}
                  className="flex items-baseline justify-between gap-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    {s.holder_ticker ? (
                      <Link
                        href={`/c/${s.holder_ticker}`}
                        className="text-[14px] text-fg hover:text-accent truncate"
                      >
                        {s.name}
                      </Link>
                    ) : (
                      <span className="text-[14px] text-fg truncate">{s.name}</span>
                    )}
                    <p className="mono text-[11px] text-fg-3 mt-0.5">
                      {HOLDER_TYPE[s.type] ?? s.type}
                      {s.holder_ticker ? ` · ${s.holder_ticker}` : ""}
                    </p>
                  </div>
                  {s.stake_pct !== null && (
                    <span className="mono text-[13px] text-fg tabular-nums shrink-0">
                      {s.stake_pct.toFixed(2)}%
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {insiders.length > 0 && (
          <div>
            <h3 className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em] mb-3">
              등기·사외이사
            </h3>
            <ul className="divide-y divide-border/40">
              {insiders.map((i) => (
                <li
                  key={`${i.name}-${i.role}`}
                  className="flex items-baseline justify-between gap-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] text-fg truncate">{i.name}</p>
                    <p className="mono text-[11px] text-fg-3 mt-0.5">
                      {i.role}
                      {i.classification
                        ? ` · ${CLASSIFICATION[i.classification] ?? i.classification}`
                        : ""}
                      {i.is_registered === true ? " · 등기" : ""}
                      {i.is_registered === false ? " · 미등기" : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {(parents.length > 0 || children.length > 0) && (
        <>
          <div className="hidden md:block">
            <OwnershipDendrogram
              center={data.ticker}
              centerName={data.name}
              parents={parents}
              children={children}
            />
          </div>
          <div className="mt-6 md:hidden grid grid-cols-1 gap-6">
            {parents.length > 0 && (
              <LinkedBlock title="모기업·지분보유 법인" rows={parents} />
            )}
            {children.length > 0 && <LinkedBlock title="자회사·피투자사" rows={children} />}
          </div>
        </>
      )}

      {cycles.length > 0 && <CyclesBlock cycles={cycles} />}
    </section>
  );
}

function LinkedBlock({ title, rows }: { title: string; rows: Linked[] }) {
  return (
    <div>
      <h3 className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em] mb-3">
        {title}
      </h3>
      <ul className="divide-y divide-border/40">
        {rows.map((r) => (
          <li
            key={`${r.ticker}-${r.as_of}`}
            className="flex items-baseline justify-between gap-3 py-2"
          >
            <Link
              href={`/c/${r.ticker}`}
              className="min-w-0 flex-1 hover:text-accent transition-colors"
            >
              <span className="text-[14px] text-fg truncate block">
                {r.name ?? r.ticker}
              </span>
              <span className="mono text-[11px] text-fg-3 mt-0.5 block">
                {r.ticker} · {r.as_of}
              </span>
            </Link>
            {r.stake_pct !== null && (
              <span className="mono text-[13px] text-fg tabular-nums shrink-0">
                {r.stake_pct.toFixed(2)}%
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CyclesBlock({ cycles }: { cycles: string[][] }) {
  return (
    <div className="mt-8 border border-sev-high/40 bg-sev-high/5 px-4 py-3">
      <p className="mono text-[11px] text-sev-high uppercase tracking-[0.15em] mb-3">
        순환출자 고리 감지 · {cycles.length}건
      </p>
      <ul className="space-y-2">
        {cycles.map((cycle, i) => (
          <li
            key={`cycle-${i}`}
            className="mono text-[12px] text-fg-2 flex flex-wrap items-center gap-1.5"
          >
            {cycle.map((t, j) => (
              <span key={j} className="inline-flex items-center gap-1.5">
                <Link href={`/c/${t}`} className="text-fg hover:text-accent">
                  {t}
                </Link>
                {j < cycle.length - 1 && <span className="text-fg-3">→</span>}
              </span>
            ))}
          </li>
        ))}
      </ul>
      <p className="mono text-[10px] text-fg-3 mt-3">
        재벌·계열사 간 상호출자 탐지. SQL DFS 기반(최대 깊이 5).
      </p>
    </div>
  );
}
