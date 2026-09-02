# PROPOSED: setup-aware confidence (v3) — DRAFT ONLY, no live code changed

Status: approved in principle by the Pilot 2026-09-02; exact terms below are
for Pilot review. Implementation only on explicit approval. The incoherence
this fixes: volume expansion is real evidence for a BREAKOUT and misleading
for a BASING — one formula cannot serve both.

Unchanged, per Pilot: tier base (0.58 two-source / 0.62 three-source),
R009's 60% floor, caps 0.72 (two-source) / 0.80 (three-source), formula
floor 0.40, spread penalty (-min(0.05, spread_bps/200)) and contra-book
penalty (-min(0.06, 0.03*(1/imb - 1))) stay shared across all setups.

All scaled terms are linear clamps to [0, max]: term = max * clamp(x).

## 1. Per-setup evidence terms

PULLBACK (Pilot prior: proximity, quietness, trend quality; volume must not
help — AGREED, and extended: expansion should mildly hurt):
- Zone proximity, up to +0.04: x = 1 - dist_to_SMA20 / (1.5x own avg move).
  Closer to the mean = better entry and tighter structural risk.
- Quiet retrace, up to +0.03: x = (1.0 - vol_expand) / 0.5 (full at 0.5x).
  A pullback on fading volume is corrective; on heavy volume it is
  distribution wearing a dip costume.
- Trend quality, up to +0.03: x = SMA20 5-day slope / (2x own avg move).
  A steeply rising 20d mean means the trend being bought is real, not a
  wobble. (Implementation note: candidates must start storing sma20_prev5;
  today's re-score used partial credit from the boolean sma20_rising.)
- Volume expansion >= 1.5x: flat -0.02. Beyond "not helping": heavy selling
  into a retrace is a warning, and the term should say so.
- Aligned book: flat +0.02. Bids at the zone are the dip being bought.

BASING (Pilot prior: contraction, depth, stability; expansion counts
AGAINST — AGREED in full):
- Volume contraction, up to +0.04: x = (0.8 - vol_expand) / 0.4 (full at
  0.4x). Dry volume at the lows is supply exhaustion — the whole thesis.
- Depth in range, up to +0.03: x = (0.25 - range_pos) / 0.25. Deeper in the
  base = closer invalidation = better asymmetry.
- Stability, up to +0.03: x = 1 - |chg24| / own avg move. A calm tape at
  the low is accumulation behaviour; a volatile one is an unfinished decline.
- Volume expansion penalty, up to -0.05: x = (vol_expand - 0.8) / 0.7.
  Expansion at the lows after a decline is more likely continuation selling;
  if it is genuine capitulation, that is REVERSAL's category, not BASING's —
  the penalty keeps the two from blurring.
- Aligned book: flat +0.02.

BREAKOUT (Pilot prior: volume expansion stays the main term — AGREED):
- Volume expansion, up to +0.06 (the largest single term in the system):
  x = (vol_expand - 1.5) / 3.5 (full at 5x). Breakouts without
  participation fail; here volume IS the confirming evidence.
- Consolidation tightness, up to +0.03 (added beyond the prior):
  x = (3x own avg move - consolidation width%) / (3x own avg move).
  Tight coils store energy; wide sloppy ranges break out weakly. Argued in:
  it is the structural half of breakout quality that volume alone misses.
- Aligned book, up to +0.03: x = (imb - 1) / 1.5. Bids stacking under a
  fresh break support follow-through.

REVERSAL (Pilot prior: capitulation volume stays — AGREED, with one argued
nuance: its weight is capped BELOW breakout's, because extreme volume at
the lows is double-edged — it is the capitulation print AND the knife
warning; evidence, but not to be over-rewarded):
- Capitulation volume, up to +0.04: x = (vol_expand - 1.5) / 2.5.
- Decline extension, up to +0.03: x = (|chg5|/avg - 2.5) / 2.5. The more
  stretched the move, the stronger the mean-reversion snap.
- Capitulation print, up to +0.02: x = (body_ratio - 2) / 3. One outsized
  bar at the low is the event itself.
- Aligned book: flat +0.02.

Per-setup positive terms are individually capped as stated; no setup can
gain more than +0.10 before the shared R:R term.

## 2. Shared R:R quality term (all setups)

+0.015 * log2(R:R / 2), floor 0, CAP +0.045.
  R:R 2.1 -> +0.001 | 4:1 -> +0.015 | 8:1 -> +0.030 | 12:1 -> +0.039 |
  16:1+ -> capped +0.045.
Reasoning: a 12:1 structure is materially better evidence than 2.1:1, but
log-scaled and capped so a freak ratio cannot buy its way past weak setup
evidence — R:R seasons the score, never carries it. R014 (>= 2:1) remains a
hard gate before any of this.

## 3. Untouched

Tier base 0.58/0.62, R009 floor 0.60, caps 0.72/0.80 — exactly as approved
earlier today. The floor is not moving.

## 4. Anti-clustering re-score (scans 8-9, all classified candidates)

  PUMP  PULLBACK 0-source rr 4.5  -> 0.641  (clears, but 0-source: R007-blocked)
  TUT   BASING   2-source rr 12.0 -> 0.634  CLEARS
  TRUMP BASING   0-source rr 3.6  -> 0.627  (clears, but 0-source: R007-blocked)
  ARB   BREAKOUT 2-source rr 0.5  -> 0.594  suppressed (R014 kills it anyway)
  NEAR  PULLBACK 2-source rr 3.7  -> 0.579  suppressed (retrace on 1.78x
        EXPANDING volume — the quietness term correctly gives it nothing)

Distribution: 0.579-0.641, a 6-point spread with candidates on BOTH sides
of the floor and no bunching at 0.60-0.61. The one packet-eligible
candidate (TUT) is exactly the best structure on the board (12:1 basing on
0.75x volume). The scores separate for interpretable reasons, not by
default. Caveat stated: n=5 from one day's tape — the clustering check must
be re-run on the first quieter day before this ships.

## 5. Packets-per-day estimate under the draft

From two days of classified candidates: ~4-6 classified per day, ~2-3 of
those with 2-source confluence, ~1 clearing the draft score. Estimate:
0-2 packets/day, centred on ~1. Comfortably under the Pilot's 3-4/day
looseness ceiling; zero-packet days remain normal on trendless or
uniformly-extended tape.

## Not shipped

No live code changed. confidence_v2 (tier base + volume/imbalance/spread)
remains the active formula. Awaiting Pilot verdict on these exact terms.
