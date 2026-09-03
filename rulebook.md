# HANSEI Rulebook
Rules are numbered permanently. Deleted rules are struck through, never removed.

- **R001** Never propose more than 20% of sub-account balance in one position.
- ~~**R002** Run query-token-audit before proposing anything outside the top 20
  pairs.~~ Superseded by R008.
- **R003** Do not re-propose an idea rejected in the last 24h unless something
  material changed, and state what changed.
- **R004** Any restriction on a tool must also cover tool_execute invoked with
  that tool name as an argument. The visible tool list understates the write
  surface.
- **R005** Only propose assets that exist as an active Binance spot USDT pair.
  Signals for non-listed assets are discarded at ingest.
- **R006** A signal counts as evidence for a spot pair only if its contract
  address matches the canonical Binance-Peg or issuer contract for that asset.
  If the canonical contract cannot be determined, the signal is DISCARDED, not
  accepted. Ticker-string matches alone are never sufficient.
- ~~**R007** Evidence must draw on at least two structurally independent sources
  (cross-sectional, time series, order book, report). Multiple readings of one
  source count as one.~~ Superseded by R015. The source-count was a crude proxy
  for independent agreement; R015 measures the agreement directly.
- **R008** Every asset outside the top 20 must pass a vetting check before it
  can be proposed. Contract-based assets are vetted with query-token-audit.
  Assets with no contract (native L1 coins) are vetted against Binance spot
  listing data instead: the pair must have status TRADING, isSpotTradingAllowed
  true, no active trading restrictions, and a listing age above a stated
  minimum. An asset that cannot be vetted by either path is DISCARDED, not
  exempted.
- **R009** A draft with confidence below 60% is emitted as NO_PROPOSAL, not as
  a packet. Every suppressed draft is logged to logs/suppressed.jsonl with its
  symbol, side, confidence and evidence sources, so confidence clustering just
  above the floor is visible.
- **R010** No new packet may be generated for a symbol+side that already has a
  PENDING packet awaiting a verdict. The scan logs it as a duplicate-pending
  skip and moves on.
- **R011** Tokenized equity and RWA pairs (bstocks) are excluded from the
  trading universe. They follow external market hours, halt on corporate
  actions, and do not share the continuous-trading assumptions the scanner
  is built on.
- **R012** Every packet must state a complete exit plan: an invalidation
  condition AND a time stop. No open-ended positions.
- **R013** Maximum hold is 72 hours. When an open position ages past 72h,
  the Unit proposes an exit packet at the next scan; the Pilot decides it
  like any other proposal.
  (R012 and R013 wording drafted by the Unit, Pilot-approved as drafted
  2026-09-02, kept because the exit stays behind the same approval gate.)
- **R014** No packet may be generated with a reward-to-risk ratio below 2:1.
  Target and stop are derived from market structure, recent swing highs and
  lows, never from fixed percentages. A candidate that cannot produce a
  structural target and stop is blocked, not estimated.
- **R017** When BTC is down 3% or more on the day, every BUY entry draft
  takes a flat -0.04 confidence penalty before the R009 floor. Exit packets
  are exempt, closing into weakness is never obstructed. (The hard block
  on entries during a confirmed BTC downtrend is approved in principle,
  DEFERRED on throughput, recorded in docs/proposed-rules.md.)
- **R016** Pairs whose RAW average daily move exceeds 12% are excluded from
  the scan universe. A 12%-daily asset routinely travels ±20% inside the
  R013 72h hold, structural stops are meaningless at that amplitude and
  the pair is not swing-tradeable on our clock. Every exclusion is logged
  so the boundary stays visible. (12% = 1.5x the 8% threshold-scaling cap,
  keeping the capped-but-included band observable.)
- **R015** A packet requires its setup's indicator checklist to pass, 3 of 4
  for PULLBACK and BREAKOUT, 4 of 4 for BASING and REVERSAL, drawn from five
  dimensions verified pairwise-independent (all r < 0.7, measured on a
  341-sample panel; LOCATION is the weakest at r 0.53-0.59 against three
  others and is kept at full weight by Pilot decision, recorded for future
  reviewers). The checklist renders on the packet; failures are logged with
  the failing dimensions named. Exit packets are exempt, the vote qualifies
  an entry setup, and an exit has none.
