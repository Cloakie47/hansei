# Quiet-tape diagnosis — 2026-09-02 evening

Trigger: two consecutive zero-packet scans (run.py status note fired).

## The numbers

Volume floor. Non-bstock TRADING USDT pairs by 24h quote volume right now:
  >= 30m: 21 pairs
  >= 20m: 25 pairs   <- current floor
  >= 15m: 40 pairs
  >= 10m: 50 pairs
  >=  5m: 74 pairs

Deep-scan cap. 12 of the 21-25 floor-passing pairs get B/C analysis — the
bottom half of the pool is never examined on quiet days when the excursion
ranking is flat.

Near-miss detail from scan 5 (each 2-source candidate's distance to its
missing third source): ENSO imbalance 1.04, ARB 1.21, NEAR 1.03, UNI 1.51 —
all missing C (need >= 1.6). Only UNI is close; the rest are nowhere near.
The C threshold is not the bottleneck; genuine book support simply is not
there tonight.

## Honest verdicts

FLOOR 20m: TOO HIGH for coverage, given the execution floor we actually
need. The scanner's real liquidity requirement is a tight spread and a
usable book at 8 USDT stake — trivially met far below 20m. Dropping to 15m
adds 15 pairs (+60% coverage) while staying above the thin-book zone where
wide-spread warnings dominate. DECISION (allowed tuning): floor 20m -> 15m.
10m rejected for now: the 10-15m band is where 12 bps spreads live.

CAP 12: TOO LOW once the floor drops (40 pairs eligible, 12 examined).
DECISION (allowed tuning): cap 12 -> 16. Scan cost rises ~33% (still ~1
minute); coverage of the eligible pool roughly doubles vs yesterday.

SOURCE A TRIGGER: the fixed 4% |change| threshold is calibrated for
volatile alts and structurally blind to majors — ETH moved 2.7% in scan 4
and scored zero A-triggers even though 2.7% is a large move FOR ETH.
DECISION (allowed trigger tuning, improves evidence honesty): the change
trigger becomes volatility-relative — fires when |24h change| >= max(2.5%,
1.6x the pair's own 7d average absolute daily change), computed from the
daily klines the scanner already fetches. Fixed thresholds stay for vol
ratio and VWAP distance. C_IMBALANCE 1.6 is NOT lowered: only one near-miss
(UNI 1.51) exists, and tuning a threshold to admit one of today's
candidates would be overfitting.

MECHANICAL CONFIDENCE V1: too strict for current conditions BY DESIGN —
2-source candidates map to 57% and never reach the Pilot. Whether 2-source
confluence DESERVES to reach the Pilot is a judgment call about the gate,
not a tuning knob: changing the mapping changes what crosses R009's floor.
REQUIRES APPROVAL — see the ask at the end of docs/optimizations-2026-09-02.md.

## What was implemented tonight (all logged in logs/autonomous-changes.jsonl)

- floor 15m, cap 16, volatility-relative A change trigger (this file's
  decisions), each as its own commit.
