# Retail Focus

## Decision

The Gongsi should optimize first for serious Korean retail investors, not casual brokerage-app users and not institutional asset managers.

The product wedge is:

> A DART disclosure radar for the names I actually care about.

## Why This Target

- The current product already fits a DIY fundamental workflow: watchlist, disclosure triage, anomaly severity, DD memo, governance, and Ask.
- Casual brokerage-app users are distribution-heavy and habit-driven. Competing with Toss, Naver, Kiwoom, Samsung, or Mirae on default quote/news UX is not realistic.
- Institutions may pay more, but they require SSO, RBAC, audit logs, quality reports, export contracts, retention policies, and SLA boundaries before daily dependency.
- Serious retail investors have a narrow but painful job: "Tell me what changed in my stocks before the market prices it in."

## Product Principle

Ask is a power-user layer. The daily product should start with signals:

1. What happened in my watchlist?
2. Why does it matter?
3. What evidence backs the label?
4. What should I verify next?

## Near-Term Roadmap

1. Watchlist-first daily brief
   - Latest high/medium disclosures for watched tickers.
   - One-line reason, original DART link, and DD memo link.
   - Email/browser push/Telegram digest before Slack or institutional workflows.

2. Better severity model
   - Dilution-aware scoring for paid-in capital increases, CB/BW, stock options.
   - Governance-aware scoring for major shareholder, insider, auditor, and lawsuit events.
   - Repetition and recency penalties: repeated financing or correction filings should matter.

3. Evidence-grade AI output
   - Every memo/answer claim should expose source filing, source field/span, model, prompt version, generated time, and confidence.
   - The UI should make it easy to jump from summary to original DART evidence.

4. Retail-friendly onboarding
   - "Add 3 tickers" before "Ask anything."
   - Explain severity with plain language: dilution, control, solvency, legal, earnings, shareholder return.
   - Keep BYOK in settings as an advanced option, not the first user promise.

5. Keep institutional readiness as a second track
   - Continue quality reports and auditability, but do not let institutional checklists drive the core UI.
