# UNCLASSIFIED-rate diagnosis — 2026-09-02 (scan 8, 12 of 16 unclassified)

Question: is the high unclassified rate the tape or the definitions?
Answer: BOTH, and the split is measurable. No thresholds changed — Pilot
decides.

## Per-candidate: closest setup and the exact failing margin

7 of 12 fail PULLBACK on exactly ONE test — the support-zone distance:
  0G    SMA20 dist 18.7% (zone: 4%)     TRUMP  12.7%
  DASH  18.8%                            ZEC    19.4%
  PUMP   9.0%                            SOL     9.4%
  ENSO  fails only trend (downtrend)
Others:
  NEAR  closest BREAKOUT — 8.5% below its consolidation high (approaching,
        not yet broken)
  TUT   closest REVERSAL — at 12% of range in a downtrend but volume 0.69x:
        quiet basing, not capitulation
  ONG   +26.6% then retracing at 17% of range — post-spike knife, fits
        nothing on purpose
  OP    uptrend, +7.2%, not retracing — continuation without a pullback
  ENA   uptrend, +4.9%, 22.9% above SMA20 — same

## Findings

1. ONE THRESHOLD IS OBVIOUSLY TOO TIGHT, but the fix is scaling, not
   loosening: the PULLBACK support zone is a fixed 4% of the 20d mean,
   while this universe's pairs average 4-8% DAILY moves. A volatile alt in
   a genuine uptrend pullback sits 9-19% from its 20d mean as a matter of
   course. The principled definition is per-pair: within ~1.0-1.5x the
   pair's own average daily move of the SMA20 (same pattern as the A
   trigger). At 1.5x, PUMP (9.0% vs avg 7.6%) and SOL (9.4% vs avg 6.5%)
   reclassify as PULLBACK candidates; the 18%+ cases stay out. NOT CHANGED.

2. TWO RECOGNISABLE SETUPS OUR FOUR CATEGORIES DO NOT COVER:
   - BASING: extended decline, bottom of range, volume QUIET (TUT — 0.69x).
     Accumulation before reversal; our REVERSAL demands capitulation volume.
   - CONSOLIDATION-APPROACH: coiling just under a consolidation high (NEAR,
     -8.5%). Today's approach is tomorrow's breakout; a watchlist state
     rather than a packet state.
   Also visible: uptrend CONTINUATION without a pullback (OP, ENA). Deliberately
   uncovered — it is the chase-guard's neighbour and should probably stay out.

3. THE TAPE IS DOING SOME OF IT: ENSO is in a downtrend and ONG is a
   post-spike knife — long-only spot has no honest setup for either, and
   UNCLASSIFIED is the correct verdict. Roughly 3-4 of the 12 are genuinely
   untradeable-long today.

## Split, in numbers

Of 12 unclassified: ~5 are the too-tight support zone (definitions), ~2 are
uncovered-but-recognisable setups (definitions), ~2 are deliberate
exclusions (continuation), ~3 are the tape (downtrends/knives). So roughly
7 of 12 point at definitions, 5 at reality. Pilot decisions available:
scale the support zone per-pair (recommended), add BASING and/or
CONSOLIDATION-APPROACH as categories, or leave all as-is.

## Pilot decisions (2026-09-02)

1. APPROVED — support zone scaled per-pair: within 1.5x the pair's own
   average daily move of the SMA20. Implemented.
2. APPROVED — BASING added as a category (Unit-drafted thresholds, stated
   in the commit: 5d decline >= 2.0x own avg, bottom quarter of range,
   volume <= 0.8x prior, |24h| <= 1x avg). Implemented.
3. REJECTED — CONSOLIDATION-APPROACH. Pilot's reason, recorded: coiling
   under a level is a watchlist state, not a trade — no entry, no stop,
   nothing has happened yet. Not implemented; do not re-propose without
   new evidence that approaches convert at a rate worth pre-positioning.
4. CONFIRMED DELIBERATE EXCLUSION — uptrend continuation without a
   pullback stays UNCLASSIFIED (it is the chase-guard's neighbour). A
   guard comment now sits in classify_setup so nobody "fixes" it later.
