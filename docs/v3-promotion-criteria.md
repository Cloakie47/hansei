# v3 promotion criteria — THE canonical bar (so it cannot drift)

confidence_v3 is promoted from shadow to live scorer ONLY when ALL THREE
hold, verified against the shadow log, reported to the Pilot, and approved
by the Pilot. Set 2026-09-02/03; changes to this bar are themselves a
Pilot decision.

1. SAMPLE SIZE: at least 20 shadow-scored classified candidates in
   logs/confidence-shadow.jsonl.

2. QUIET-DAY CHECK: at least one genuinely quiet tape day in the shadow
   window — BTC hugging its SMA20, no 15%+ movers in the pool — with no
   v3 bunching in the 0.60-0.62 band on that day. (The anti-clustering
   discipline that caught v2's flat-base defect.)

3. FLOOR-BINDINGNESS (added 2026-09-03, Pilot-approved): within v3's
   favored setups (PULLBACK, BASING), the score distribution must straddle
   0.60 — equivalently, v3 must suppress a NONZERO share of classified
   candidates there over the shadow window. A confidence formula whose
   distribution lives entirely above the floor it is tested against has
   made R009 decorative for those setups.

## Standing as of 2026-09-03 (symmetric R:R term live in shadow)

1. Sample size: MET — 31 samples.
2. Quiet day: NOT MET — every shadow day so far has been an extended
   uptrend with setups classifying each scan.
3. Floor-bindingness: MET — 7 of 23 favored-setup samples score below
   0.60 (BASING 6/10 below, PULLBACK 1/13 below); the distribution
   straddles the floor. (Correction recorded in the shadow-gap diagnosis:
   the 2026-09-03 diagnosis originally claimed every favored-setup sample
   sat >= 0.613 — that was a reasoning error, not a computed minimum; the
   computed minimums are 0.567 BASING / 0.570 PULLBACK.)

TWO OF THREE MET. Not promoted; the quiet-day check is outstanding, and
promotion additionally requires explicit Pilot approval at that time.
