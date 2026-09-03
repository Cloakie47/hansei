# PROPOSED: indicator vote (R015, supersedes R007), DRAFT, not shipped

Status: Pilot directed the design 2026-09-02; the vote does NOT ship until
the Pilot approves this document. Items here: the five dimensions with
their measured correlations, the per-setup checklists, the BREAKOUT retest
term, the R007 supersession wording, and the throughput estimate.

## 1. The five dimensions (all from spot_klines)

TREND, market STRUCTURE primary: split the last 20 daily bars into two
10-bar halves; higher high AND higher low = up-structure (+), lower high
AND lower low = down (-), mixed = flat. Confirmation only (never
overriding): close vs SMA20 and SMA20 slope. An asset above its SMA making
lower highs reads as weakening, exactly as directed.

MOMENTUM, 7d and 14d trailing return, each RELATIVE TO BTC over the same
window (strips beta; a +6% move in a +8% BTC tape is weakness).

VOLATILITY STATE, Bollinger bandwidth (20d, 2 sigma) as a percentile of
its own trailing 60-day bandwidth history. Compression vs expansion,
per-pair by construction.

PARTICIPATION, DIRECTIONAL by requirement: signed volume share =
sum(sign(close-open) x quote volume) / sum(quote volume) over 14d, the
up/down split. Replaces volume-vs-average, which cannot tell heavy buying
from heavy selling.

LOCATION, Bollinger %B, plus distance from the day's VWAP
(weightedAvgPrice, already fetched) as the intraday check. Replaces raw 7d
range position.

## Measured correlation (the honesty check, done before proposing)

Panel: 341 samples, 31 floor-passing pairs x up to 12 daily observations,
each dimension computed exactly as defined above. Pearson r:

  TREND x MOMENTUM   +0.302        TREND x VOLSTATE   +0.276
  TREND x PARTICIP   +0.372        TREND x LOCATION   +0.587 (elevated)
  MOMENTUM x VOLSTATE +0.290       MOMENTUM x PARTICIP +0.386
  MOMENTUM x LOCATION +0.533 (elevated)
  VOLSTATE x PARTICIP +0.509 (elevated)
  VOLSTATE x LOCATION +0.408       PARTICIP x LOCATION +0.550 (elevated)

NO PAIR EXCEEDS 0.7, the five clear the hard bar and RSI/MACD/ROC-style
triple-counting is avoided. Stated honestly rather than hidden: LOCATION is
the least independent dimension (0.53-0.59 against three others, where
price sits in its bands inevitably co-moves with trend and flow). It stays
in the draft because 0.55-0.59 is shared-cause overlap, not duplication,
and location is the entry-quality check no other dimension provides. If the
Pilot prefers a stricter bar, LOCATION is the dimension to demote to
display-only.

## 2. Setup-specific checklists (the vote is not universal)

PULLBACK, 3 of 4 required (VOLSTATE unused):
  TREND: up-structure intact (HH + HL) and close above SMA20
  MOMENTUM: 14d return positive relative to BTC
  PARTICIPATION: signed-volume share >= -0.2 over the retrace (no distribution)
  LOCATION: %B in [0.15, 0.55] and price at or below the day's VWAP

BREAKOUT, 3 of 4 required (MOMENTUM unused, trailing momentum at a
breakout is the chase trap the classifier exists to block):
  PARTICIPATION: signed-volume share >= +0.3 (directional buying)
  VOLSTATE: bandwidth percentile was <= 40% within the last 5 days and is
    now rising (expansion FROM compression, not mid-blowout)
  TREND: structure not down (no LH + LL)
  LOCATION: %B >= 0.8 and price above VWAP

BASING, 4 of 4 required (TREND unused, down by construction):
  VOLSTATE: bandwidth percentile <= 20% (compressed)
  PARTICIPATION: signed-volume share improving, last 5d share above the
    prior 5d share (selling exhausting)
  MOMENTUM: 14d negative but decelerating: |7d| < 0.5 x |14d|
  LOCATION: %B <= 0.20

REVERSAL, 4 of 4 required (TREND unused):
  MOMENTUM: 7d <= -2.5x own avg daily move, and worse than BTC's 7d
  PARTICIPATION: capitulation signature, a >= 3x-volume down day within
    the last 3 days followed by a positive signed-volume day
  VOLSTATE: bandwidth percentile >= 80% (climax)
  LOCATION: %B <= 0.05

Checklist results render on the packet line-by-line; failures log to
logs/suppressed.jsonl with the failing dimensions named.

## 3. BREAKOUT level-retest quality term (v3, not a dimension)

+0.03 confidence when: price broke the consolidation high, returned to
within 0.5x its own average daily move of that level within 5 daily bars,
and closed back above it. To respect the +0.10 per-setup cap, BREAKOUT's
terms rebalance: volume 0.06 -> 0.05, tightness 0.03 -> 0.02, retest +0.03.
Reasoning: a held retest converts the level from resistance to support,
the single best confirmation a breakout gets; a term, not a gate.

## 4. R007 supersession wording (for rulebook.md on approval)

- ~~R007 (evidence from two structurally independent sources)~~ Superseded
  by R015. The source-count was a crude proxy for independent agreement;
  R015 measures the agreement directly.
- R015: A packet requires its setup's indicator checklist to pass, 3 of 4
  for PULLBACK and BREAKOUT, 4 of 4 for BASING and REVERSAL, drawn from
  five dimensions verified pairwise-independent (r < 0.7 measured). The
  checklist renders on the packet; failures are logged with the failing
  dimensions named.

Note on what supersession changes: the current "2+ triggering sources"
candidate gate is R007's operational arm and retires with it. That gate
was structurally hostile to quiet setups (a basing pair rarely fires a
volume/change trigger, the probe measured classified-but-one-source as
the single biggest killer). The checklist replaces it with tests that FIT
each setup, which is the entire point.

## 6. Expected packets per day under this draft

From the historical probe (5 windows) and two live days: 2-9 classified
candidates per scan; checklist pass rates estimated ~40% for 3-of-4 setups
and ~15-25% for 4-of-4 setups; R014 and the confidence floor still apply.
Estimate: 0-2 packets/day, centred just under 1/day, nearer the Pilot's
"three good packets a week" than to twenty chases, with zero-packet days
still common on trendless tape. It does not approach zero-always: the
vote resolves the quiet-setup starvation that the source-trigger gate
caused, which is why the estimate holds despite stricter checks.
