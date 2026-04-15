export default function Home() {
  return (
    <main className="mx-auto max-w-[720px] px-8 py-32">
      <p className="mono text-fg-3 text-[13px] tracking-wider">COMAD-STOCK · v0.1 · OSS</p>

      <h1 className="mt-8 font-serif text-[72px] leading-[1.05] tracking-[-0.02em]">
        한국 주식,
        <br />
        <span className="text-fg-2">진지한 리서치로.</span>
      </h1>

      <p className="mt-12 text-[17px] leading-[1.7] text-fg-2">
        DART 공시를 AI가 한국어로 요약하고, 이상징후를 플래그하며,
        GraphRAG로 공급망·경쟁사·인사이더를 이어 붙입니다.
        네이버 증권을 두 세대 앞서, 광고 없이.
      </p>

      <div className="mt-16 flex items-center gap-6 text-[14px]">
        <a
          href="https://github.com/"
          className="mono border-b border-accent text-accent hover:bg-accent-dim hover:text-fg px-1 py-0.5 transition-colors"
        >
          github ↗
        </a>
        <span className="text-fg-3 mono">MIT · BYOK · self-hostable</span>
      </div>

      <div className="mt-40 grid grid-cols-3 gap-12 border-t border-border pt-12">
        <Feature label="DART 공시" value="전수 수집·요약" />
        <Feature label="GraphRAG Q&A" value="자연어 → Cypher" />
        <Feature label="AI DD 메모" value="bull/bear/thesis" />
      </div>
    </main>
  );
}

function Feature({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mono text-fg-3 text-[12px] tracking-wider uppercase">{label}</p>
      <p className="mt-2 text-[15px] text-fg">{value}</p>
    </div>
  );
}
