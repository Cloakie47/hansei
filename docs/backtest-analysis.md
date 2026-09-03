# Backtest analysis, mechanical scoring over historical windows

## LOOKAHEAD-BIAS CAVEAT, READ FIRST

This is NOT proof of profitability and must never be shown as such.

- The scoring here is pure price ARITHMETIC: the setup classifier, the R015
  indicator vote, structural R:R, and the v2/v3 confidence formulas are all
  deterministic functions of historical prices and volumes. No model
  judgment enters the scoring, so the scoring itself is mostly safe from
  lookahead contamination.
- BUT the model writing this analysis may have prior knowledge of these
  historical periods. Any step that involved model judgment (which windows
  to sample, how to frame a result) is potentially contaminated. Treat a
  good number as a hypothesis, never as evidence of edge.
- The forward-outcome window measured is 24 HOURS, not the full 72h hold
  the system targets. Outcomes past 24h are not captured here.
- The sample sits in a broad up-tape: a random qualifying pair averaged
  +0.67% at 24h, so every long-side number is inflated by the drift.
- Sample: 432 candidate-instances across 16 historical windows (11 to 71
  days back), today's 27 floor-passing pairs. Small, and one slice of tape.

## 1. Baseline comparison (24h forward, mean return / hit rate)

  PACKETS (v2, the live scorer):  n=0
  PACKETS (v3, shadow scorer):    n=2,  mean -2.16%,  hit 50.0%
  RANDOM qualifying pair (all):   n=432, mean +0.67%, hit 50.7%
  REJECTED (classified, not a v2 packet): n=58, mean +0.67%, hit 44.8%
  BTC buy-and-hold (same windows): n=16, mean +0.32%, hit 50.0%

THE HONEST READING, stated plainly:

- THE GATES PRODUCE ESSENTIALLY NO PACKETS. Over 16 windows the full live
  (v2) stack produced ZERO packets. There is no packet sample to compare
  against anything. This matches the near-zero live rate we have seen all
  week: the gates are extremely selective.
- With n=0 (v2) and n=2 (v3), WE CANNOT CLAIM THE GATES BEAT A RANDOM ENTRY,
  THE REJECTS, OR BTC. There is no statistical basis. The two v3 packets
  that exist averaged -2.16%, i.e. they UNDERPERFORMED the random +0.67% and
  BTC +0.32% baselines, but n=2 is noise and proves nothing either way.
- The rejects (mean +0.67%, hit 44.8%) match random on mean and sit slightly
  below random on hit rate (44.8% vs 50.7%). That is mild, non-significant
  evidence that what the gates reject is not better than average, not proof
  that rejecting it added value.

Conclusion for this section: on this sample the system does not demonstrate
an edge, because it does not produce enough packets to measure one. A
strategy that almost never trades cannot be shown to beat a random entry.
That is the finding, stated without spin.

## 2. Confidence calibration (does a higher score mean a better outcome?)

Every classified draft bucketed by its confidence score; hit rate = share
with positive 24h return; mean = mean 24h return.

v2 (live scorer):
  50-55: n=0
  55-60: n=52, hit 38.5%, mean -0.24%
  60-65: n=6,  hit 100%,  mean +8.55%
  65-70: n=0
  70+:   n=0

v3 (shadow scorer):
  50-55: n=1,  hit 100%,  mean +13.20%
  55-60: n=19, hit 52.6%, mean +2.60%
  60-65: n=33, hit 39.4%, mean -1.33%
  65-70: n=5,  hit 40.0%, mean +3.997%
  70+:   n=0

THE HONEST READING:

- v2 shows WEAK POSITIVE SEPARATION but on almost no data: its sub-60 drafts
  averaged -0.24% (below random), its 60-65 drafts averaged +8.55% (well
  above). Directionally that is what a working confidence number should do,
  but the good bucket is n=6, small enough that a couple of lucky movers
  explain it. The 65-70 and 70+ buckets are empty, so monotonicity beyond
  60-65 is untested. v2 calibration is SUGGESTIVE, NOT ESTABLISHED.
- v3 DOES NOT SEPARATE, and arguably inverts: its 60-65 bucket (higher
  confidence, n=33) averaged -1.33% and hit only 39.4%, WORSE than its
  55-60 bucket (n=19, +2.60%, 52.6%). A 62% v3 draft did not outperform a
  57% v3 draft in this sample, it underperformed it. On this evidence v3's
  confidence number carries little information about outcome, and in the
  55-65 range it points the wrong way.

Answer to "does a 65% draft outperform a 55% draft?": for v2, provisionally
yes but on n=6; for v3, NO on this sample, it was the reverse. That is a
finding worth having, and it argues AGAINST promoting v3 on outcome grounds
until a larger, cleaner sample says otherwise. (No change is proposed here,
per instruction; this is analysis only.)

## What this does and does not support

Supports: the gates are highly selective (near-zero packets); v2's
confidence shows a hint of positive calibration on tiny data; v3 does not
separate on this sample.

Does NOT support: any claim of profitability, any claim the gates beat
random or BTC, any claim that v3's score is better calibrated than v2's.
The sample is too small on the packet side to conclude anything about edge,
and the up-tape inflates every long-side number. Read accordingly.
