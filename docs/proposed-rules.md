# Proposed rules awaiting Pilot approval

NOT in rulebook.md. Rules take effect only when the Pilot approves them.

## R017: PARTIALLY SHIPPED 2026-09-03 — soft brake live, hard block deferred

Pilot decision: the -0.04 confidence penalty on BUY entries when BTC is
down 3%+ on the day is SHIPPED (in rulebook.md as R017; exits exempt;
renders on packets and in the R017 rule-check line). The hard block on
confirmed-downtrend entries is APPROVED IN PRINCIPLE, DEFERRED ON
THROUGHPUT — same reasoning as R018: four days left, zero approvals,
zero fills; a new blocking gate is the wrong risk. Revisit after the
deadline. The loud regime warning stays as-is. Original draft below.

## Original draft (2026-09-03): regime gate for BUY entries

- **R017 (PROPOSED)** No new BUY entry packet may be generated while BTC is
  in a CONFIRMED DOWNTREND — daily close below the 20-day SMA with the SMA
  falling (the regime classifier's existing definition). Additionally, when
  BTC is down 3% or more on the day in any regime, BUY entry drafts take a
  flat -0.04 confidence penalty (soft brake, not a block). Exit packets are
  always exempt — closing into weakness must never be obstructed.

Thresholds and reasoning: the DOWNTREND definition reuses the classifier
already computed every scan (no new machinery, auditable in the regime
line); alt longs carry beta above 1 to BTC, so pullback/basing base rates
invert when the reference asset itself is trending down — a structurally
sound alt setup in a BTC downtrend is usually a lower high being bought.
The -3% daily trigger is roughly a 2-sigma BTC day (recent daily sigma
~1.5%): sharp enough that continuation risk dominates, but a one-day shock
should penalise rather than blackout, since capitulation days are exactly
when REVERSAL/BASING setups begin to form. The hard block on confirmed
downtrend + soft penalty on shock days keeps the gate simple, mechanically
checkable next day, and leaves the Pilot able to see (via the recorded
regime field on every decided proposal) whether DOWNTREND packets would
have fared worse — the evidence that would justify or retire the rule.
NOT SHIPPED — awaiting Pilot approval.

## Resolved

- R016 — APPROVED 2026-09-02 as drafted; in rulebook.md, enforced at ingest
  in scan.py, every exclusion logged to logs/signals_discarded.jsonl.

- R014 — APPROVED 2026-09-02 with the Pilot's wording; now in rulebook.md,
  gate active in propose.build_packet, every block logged to
  logs/suppressed.jsonl with the computed R:R.
