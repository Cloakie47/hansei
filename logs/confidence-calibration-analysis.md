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

One wrinkle surfaced by the data: RUN3 ENSO counted as 3-source while its
book was ASK-heavy (imbalance 0.62) and its spread was 12 bps wide — the C
trigger fires on |imbalance| in either direction, so a bearish book currently
strengthens a BUY draft. (Correction 2026-09-02: first written as "run1
ENSO"; run1 ENSO's book was in fact bid-heavy at 2.04 — the defective
instance was run3's. The defect itself was real and is now fixed.)

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
  (ask-heavy, ENSO run3) to 2.92 (DASH run1). Discriminates strongly —
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

## Update after scan 4 and scan 5 (2026-09-02, post-fix reality check)

Scan 4 (cap 12, directional C): 22 pairs past floor, 12 deep, tiers 1
zero-source / 4 one-source / 7 two-source / ZERO three-source -> 0 packets.
Scan 5 (R011 live): 21 past floor, 12 deep, similar shape; SNDKBUSDT and 67
other tokenized pairs excluded from the universe entirely.

Directional-C recount over the original three scans: 9 of 10 three-source
instances survive (run3 ENSO demoted). So the fix costs ~10% of tier-3
throughput while removing a class of false confluence.

REVISED PROJECTION: the two-day sample now looks like the volatile end of
the range, not the base rate. With the directional fix, three-source
confluence appears in bursts (4 instances in run1, 0 in run4/5). A quieter
tape produces zero-packet scans routinely — run.py status now surfaces this
as "tape is quiet", by design. Revised estimate at 4 scans/day for 5 days:
roughly 1-3 packets/day on volatile days, 0-1 on quiet days -> 8-15 decided
proposals over 5 days, i.e. the under-15 outcome is now the CENTRAL case,
not the tail. Implications: (a) the 8-decided threshold for confidence v2
may itself take most of the week to reach; (b) the Sync Rate curve will be
sparse and must keep printing its denominators; (c) the cap raise to 12
helped candidate coverage but cannot create confluence that is not there.

## Confounding check (2026-09-02, after v2 approval)

Scan 6's ten two-source candidates re-scored under v2, split by pool
settings (assumption: excursion ranking preserved, old cap 12 covered all
high-excursion names in the 20m pool):

  Clear 60% under v2, NEW pool (15m floor, cap 16): 10 of 10
    CRV .662, FIL .638, UNI .637, ARB .633, OP .624, DASH .618,
    ONG .613, NEAR .613, 0G .612, ENSO .610
  Clear 60% under v2, OLD pool (20m floor, cap 12): 4 of 10
    UNI, ARB, NEAR, ENSO

So the answer to "v2 scores better vs the pool got wider": BOTH, roughly
40/60 — 4 packets would exist tonight from v2 alone on the old pool; 6 more
come from the widened universe.

FLAGGED HONESTLY, because the suppression log was built to catch exactly
this: under v2 with a base of 62, EVERY two-source candidate with a neutral
book and normal spread clears the floor — eight of ten scores sit in the
0.610-0.638 band, i.e. clustering just above 60%. The floor still catches
contra-book/wide-spread drafts (verified: such a draft scores 0.562), but
for ordinary two-source candidates R009 is now nearly non-binding. If the
Pilot wants the floor to keep real teeth at two sources, the lever is a
tier-dependent base (e.g. 0.58 for two-source) — that is a gate-relevant
change and NEEDS APPROVAL; not implemented.

## Decision record (2026-09-02, Pilot)

- The imbalance sign defect is FIXED in scan.py: source C is directional,
  contra-side books are tagged C-CONTRA (shown in packets, never counted by
  R007). Recount over the three scans: 9 of the 10 three-source instances
  survive; run3 ENSO (0.62 ask-heavy) demoted to 2-source.
- Deep-scan cap raised 8 -> 12 (throughput lever). R009's 60% floor and
  mechanical confidence v1 untouched.
- CONFIDENCE V2: APPROVED IN PRINCIPLE — base 62, plus log-scaled volume
  multiple, plus direction-aligned imbalance, minus a spread penalty.
  BLOCKED until at least 8 decided proposals exist to calibrate against.
  Range position stays out of confidence and belongs in the thesis.
