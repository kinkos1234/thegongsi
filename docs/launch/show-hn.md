# Show HN Draft

## Title Options

1. **Show HN: comad-stock – Open-source AI research terminal for Korean equities (DART + GraphRAG)**
2. Show HN: DART-native research terminal — Korean filings → GraphRAG Q&A in Korean
3. Show HN: A Bloomberg-for-Korean-stocks that's open source and ad-free

**Pick #1** — most specific, mentions keywords HN audience recognizes.

## Body (≤ 3 paragraphs)

> Hi HN,
>
> comad-stock is an open-source AI research terminal for Korean listed companies. Korea's filing system (DART) publishes ~1M disclosures per year; the vast majority is routine, but a small fraction — going-concern doubt, insider trades, dilutive equity issuance, major-shareholder changes — flips investment theses. comad-stock auto-summarizes every filing in Korean, rule-flags anomalies with an optional LLM second pass, and answers natural-language questions over a Neo4j graph of supply chain / competitors / executives via Cypher generation → read-only execution → Korean synthesis (Claude Haiku, 2-hop).
>
> It's Korean-first, self-hostable with BYOK (you bring your own Claude/OpenAI keys; we encrypt them with Fernet). The graph is seeded with a small HBM supply-chain example; the roadmap is to auto-extract 50,000 edges from DART governance reports, FTC large-business-group disclosures, and LLM-NER over news corpora. There's a benchmark suite (AlphaFold-style: 100 gold queries, recall/precision tracked per release) so progress is measurable instead of vibe-based.
>
> Stack: FastAPI (async SQLAlchemy) + Next.js 16 + Neo4j 5 + pgvector. pytest 34/34. MIT. Positioned against Fey / Seeking Alpha for US markets; nothing comparable exists for Korea. I'd love feedback on the graph extraction design (docs/GRAPH_PIPELINE.md) and the DD-memo guardrails (citation fabrication validator + forbidden-word re-gen).

Links:
- GitHub: https://github.com/{TBD}/comad-stock
- Live demo: {TBD after deploy}
- Design doc (Fey-style UI): docs/DESIGN.md

## Comment prep (likely top responses)

### "Why not just use [네이버증권/토스증권]?"
> They're retail feeds: prices, news, ads. Zero filing summaries, zero relationship graph, zero natural-language Q&A. A pro research user alt-tabs to DART.fss.or.kr, reads raw HTML/PDF, and takes notes manually. comad-stock is for that workflow.

### "What's DART?"
> DART (Data Analysis, Retrieval and Transfer System) is Korea's SEC EDGAR. All listed companies file quarterly reports, major-event disclosures, governance structures, etc. in Korean. Public API limited to 10,000 requests/day per key.

### "LLM hallucination in financial text?"
> Two guards: (1) every memo citation references a rcept_no (DART filing ID), which is post-hoc validated against the DB; fabricated refs trigger regen. (2) forbidden-word scanner for 목표가/매수추천/매도추천 — the output is analysis, not advice. Full audit trail (user_id|key_owner|model) per memo version.

### "Why GraphRAG over pure vector search?"
> Most retail-investor questions ("what's Samsung's Q4 outlook?") are answered better by RAG. But a chunk of value is structural: "which HBM suppliers had a major-shareholder change in the last 6 months?" — that's a graph problem. We use Cypher generation for structural queries, pgvector for semantic (ingestion pipeline is next milestone). 2-hop means Cypher → execute → Claude synthesizes Korean answer from rows.

### "Korean? I can't read Korean"
> English README TL;DR is at the top. Core UI is Korean but Roman-alphabet + numbers work fine for demos. Primary users are Korean DIY investors and EM-Asia desks at global funds — both read Korean at minimum passively.

### "Show me numbers"
> Seed graph: 6 companies, 2 persons, 6 edges (HBM supply chain). Target: 50K edges by week 24. Demo recall/precision measured against bench/queries.yml.

## Meta (timing)

- **Weekday AM PT** — SF morning = Korea evening. Both audiences awake.
- Avoid Sunday (low traffic).
- Post yourself, log in, don't vote-ring.
- Ready for 200-400 comment replies within 4 hours. Block 2-3 hours on calendar.
