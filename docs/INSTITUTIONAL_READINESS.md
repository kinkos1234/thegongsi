# Institutional Readiness

The Gongsi is currently an alpha-grade research terminal suitable for investor
PoC conversations, not yet a production system that an asset manager should
depend on without review controls.

## Evaluation Axes

1. **Data fidelity**
   - DART collection freshness, missing-rate checks, duplicate and correction filing handling.
   - Company identity resolution across ticker, corp code, Korean name variants, and delisted or legacy symbols.
   - Market data sanity checks against an exchange-grade source before using prices in investment workflows.

2. **Evidence and reproducibility**
   - Every AI summary, severity label, and DD memo claim should retain `rcept_no`, source text span, model, prompt version, generated timestamp, and confidence.
   - Re-runs should be traceable. If output changes, the product should explain which source or model version changed.

3. **Analyst workflow fit**
   - Coverage universe, event inbox, review status, dismissal/escalation, analyst notes, and exportable research memos.
   - Daily Slack/email digest for watchlists and portfolio companies.

4. **Measured quality**
   - Gold sets for severity classification, disclosure event extraction, governance extraction, and GraphRAG answers.
   - Published precision/recall, false-positive rate, freshness, and latency metrics.

5. **Security and auditability**
   - SSO/OIDC, role-based access, team separation, audit logs, encrypted BYOK secrets, and retention controls.
   - Query logs and watchlists are sensitive research intent and must be treated as customer-confidential data.

6. **Operational maturity**
   - Data freshness dashboard, job failure alerts, backfill status, backups, restore drills, deploy rollback, and observability.
   - Free-tier infrastructure is acceptable for alpha, but institutional pilots need explicit reliability boundaries.

7. **Integration**
   - Documented API, CSV/Excel export, webhook delivery, Slack/Teams, and private deployment option.

## Current Gaps

- Time display had a KST double-offset bug, which is a high-trust surface for a disclosure product.
- Public documentation can drift from live operating numbers; this must be automated or checked before investor-facing use.
- Governance extraction can still produce duplicate legal entities when a company name resolves to old or alternate tickers.
- AI outputs are useful, but not yet fully citation-grade: source spans, prompt/model versioning, and confidence are not consistently exposed.
- The UI is still closer to a personal research terminal than an institutional review queue.
- Tests pass, but quality metrics are not yet packaged as an institutional evidence report.

## Roadmap

### Phase 1: PoC Trust Baseline

- Add a data quality dashboard: freshness, last successful jobs, missing-rate sample, duplicate/correction counts.
- Require citation metadata for AI outputs: `rcept_no`, source quote/span, generated model, prompt version, confidence.
- Build 200-500 item gold sets for severity and event extraction.
- Run nightly quality reports and expose the latest report in docs or admin UI.
- Remove visible trust breakers: time correctness, stale docs, duplicate governance entities, deprecation warnings.

### Phase 2: Analyst Workflow

- Add coverage universe management and a daily event inbox.
- Add review states: new, reviewed, dismissed, escalated.
- Add analyst notes and exportable memo formats.
- Add Slack/email digest and webhook delivery.
- Add saved questions and shareable answer packets with source evidence.

### Phase 3: Institutional Deployment

- Add SSO/OIDC, team RBAC, audit log, key rotation, and retention controls.
- Add private deployment documentation and environment hardening.
- Add an API contract and stable export schema.
- Move critical market data away from best-effort public scraping if it is used beyond UI context.
