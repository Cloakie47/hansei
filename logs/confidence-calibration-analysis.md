# Mechanical confidence v1 — measurement before any change

Data: all candidates from the three scans in logs/scans/ (2026-09-01 run1,
run2, 2026-09-02 run3). Tier = count of structurally independent sources
triggering, using run.py's exact rule (a C reading whose only trigger is
wide-spread does not count as a C trigger).

## 1. Actual tier distribution, per scan

RUN 1 (2026-09-01 afternoon), 8 candidates:
  1-source: 3 (ENA, TRUMP, PUMP)
  2-source: 1 (UNI)
  3-source: 4 (0G, ARB, ENSO, DASH)

RUN 2 (2026-09-01 evening), 8 candidates:
  1-source: 0
  2-source: 5 (ARB, PUMP, UNI, TRUMP, ENA)
  3-source: 3 (0G, ENSO, DASH)

RUN 3 (2026-09-02 morning), 8 candidates:
  1-source: 2 (TRUMP, ZEC)
  2-source: 3 (DASH, ARB, PUMP)
  3-source: 3 (ENSO, SOL, UNI)

Totals over 24 candidate-instances: 5 one-source, 9 two-source, 10
three-source. Under mapping v1 (50/57/62) only the 10 three-source instances
clear the 60% floor — but they are NOT 10 distinct ideas: the distinct
3-source names across all three scans are 0G, ARB, ENSO, DASH, SOL, UNI —
six names in ~22 hours, and ENSO hit 3-source in all three scans. Names
persist between scans; R010 (pending dedupe) and R003 (24h after rejection)
exist precisely to stop the repeats becoming packets.

One wrinkle surfaced by the data: run1 ENSO counted as 3-source while its
book was ASK-heavy (imbalance 0.62) and its spread was 12 bps wide — the C
trigger fires on |imbalance| in either direction, so a bearish book currently
strengthens a BUY draft. Noted for part 3; not changed.

## 2. Projection: 4 scans/day for 5 days

Assumptions, stated:
  a. Tier-3 rate holds at today's ~3.3 instances per scan.
  b. Repeats dominate: today produced 6 DISTINCT tier-3 names in 3 scans;
     the 4th scan of a day mostly re-finds the same names (run1->run2
     overlap was 100% of candidates). Assume 4-6 distinct tier-3 names/day.
  c. R010 holds each name to one packet while pending; the Pilot decides
     same-day, so a name can produce at most ~1 packet/day.
  d. R008 vetting passes for majors and old listings; assume it removes ~1
     name/day (recent listings like ENSO have unverified age).
  e. Market regime stays as volatile as these two days. A quiet tape cuts
     tier-3 sharply — this is the weakest assumption.

Estimate: 3-5 packets/day, so 15-25 packets over 5 days, central estimate
~18 decided proposals IF the Pilot decides every packet daily.

Said plainly: the under-15 risk is real. Two of five assumptions (b and e)
push down, and one quiet market day takes the central estimate to ~14. At 4
scans/day the mapping produces barely enough decided proposals to plot a
Sync Rate curve, with no margin. If the first two loop days come in under 3
packets/day, the mapping (or the scan universe: the 20m volume floor, top-8
deep-scan cap) is the binding constraint — widening candidates-scanned-deep
from 8 to 12 is the cheapest lever that does not touch confidence at all.

## 3. Within tier 3: what discriminates strong from weak (no change made)

The scan already computes, per candidate:

- VOLUME MULTIPLE (A: vol vs own 7d avg; B: 24h kline vol vs prior 6d).
  Observed range inside tier 3: 1.89x (DASH run3) to 15.37x (ARB run1).
  An 8x spread in the strongest shared quantity. DISCRIMINATES.
- BID/ASK IMBALANCE within 1% of mid. Observed inside tier 3: 0.62
  (ask-heavy, ENSO run1) to 2.92 (DASH run1). Discriminates strongly —
  but only if made DIRECTIONAL: bid-heavy should support a BUY and
  ask-heavy should count against it, instead of |imbalance| firing either
  way as it does now. As-is it is a defect, not a signal. DISCRIMINATES
  (after the direction fix).
- SPREAD (bps). Observed 1.0 (SOL) to 12.0 (ENSO). A cost/quality penalty:
  12 bps on an 8 USDT stake is real drag and correlates with the thin books
  where imbalance readings are least reliable. DISCRIMINATES (negatively).
- RANGE POSITION (0-100% of 7d range). Observed 8% to 85%. This separates
  setup TYPE (dip vs breakout), not setup STRENGTH — a 23% and an 81%
  position were both genuine 3-source signals today (SOL, UNI). Useful for
  the thesis template, NOT for confidence. DOES NOT DISCRIMINATE strength.
- CANDLE BODY RATIO (current 1h vs prior 24 avg). Observed 0.26x to 5.62x.
  Separates a fresh impulse (SOL 5.6x) from a stale drift; plausible but
  noisy at n=10 — one hour's bar. WEAK DISCRIMINATOR for now.

Conclusion: a 60-75% spread within tier 3 is justifiable from quantities
already computed — volume multiple (log-scaled), direction-aligned book
imbalance, and a spread penalty; range position stays out of it and candle
ratio waits for more data. Not implemented: mapping v1 stands until the
Pilot decides, and any v2 must fix the imbalance direction defect first or
it will reward bearish books on BUY drafts.
