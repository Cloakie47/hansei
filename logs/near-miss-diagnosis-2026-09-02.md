# Near-miss diagnosis — 2026-09-02 evening. DIAGNOSIS ONLY, nothing changed.

Question: after four zero-packet scans, is the tape offering nothing, or is
a gate structurally too tight? Data: logs/setups.jsonl (160 classification
events across the two UTC days), logs/suppressed.jsonl, scan JSONs.
Instrumentation notes, stated: vote fields exist only for the R015 era (12
classified candidates); pre-R015 eras had different gates and are counted
where comparable. Two unflagged LTCUSDT R014 entries are my own
gate-verification tests and are excluded.

## 1. Near-miss ranking (closest to a packet, first)

TIER 1 — died ONE derivable stop away (vote PASSED, R014 no-stop):
  1. PEPEUSDT PULLBACK (08:22Z) — passed its checklist, no structural stop
  2. PUMPUSDT PULLBACK (16:49Z) — passed its checklist 3/4, no structural stop
These are the two closest calls of the whole record: everything agreed
except that a stop could not be derived.

TIER 2 — died 0.003-0.006 confidence short (v2-era R009, pre-R015):
  3. UNIUSDT 0.597 (gap 0.003, three consecutive scans)
  4. 0GUSDT 0.596 (gap 0.004)
  5. ARBUSDT 0.594 (gap 0.006)
Era caveat: these predate the vote; under R015 the same candidates mostly
fail checklists outright, so the tiny gaps overstate closeness.

TIER 3 — one checklist item short (R015 era):
  6-10. PUMP (07:47), TRUMP (08:22, 16:49), XRP (17:07) — all PULLBACK,
  2/3, and ALL failing the identical pair: TREND up-structure + LOCATION.
  One candidate signature, repeated: retracing assets without clean
  up-structure in a chase-heavy tape.

TIER 4 — two or three items short: UNI BREAKOUT (1/3, twice), PEPE BASING
  (1/4, twice), TUT BASING (2/4). Far.

TIER 5 — never candidates: the 132 classifier kills.

## 2. Gate kill counts (both UTC days)

  Classifier (CHASE/UNCLASSIFIED): 132 of 160 events — 82.5%
     (94 UNCLASSIFIED, 38 CHASE)
  Indicator vote (R015 era only): 10 of 12 classified — 83% of survivors
  R014 structural R:R: 2 real kills (both "no derivable stop"; the 1.4:1
     numeric kill was a test) — but that is 2 OF THE ONLY 2 VOTE-PASSERS: 100%
  R009 confidence floor: 32 suppressions all-time, all pre-R015 eras; zero
     since the vote shipped (nothing has reached it)

The funnel in one line: 160 -> 28 classified -> 2 past the vote -> 0 past
R014 -> R009 untested in the current era.

## 3. The structural stop problem — THIS ONE IS REAL

"No derivable stop" has hit 6 of 28 classified candidates (21%), and the
distribution is the tell: 4 PULLBACK, 2 BASING, ZERO BREAKOUT, ZERO
REVERSAL. It killed BOTH vote-passers.

Cause, in the code's own terms: the stop is the 48h swing low, and the
degenerate-stop guard (correctly) refuses stops within 0.5x an average
daily move of entry. But a pullback IN PROGRESS and a basing pattern are,
BY DEFINITION, sitting at or near their 48h lows — the setups the
classifier prefers are precisely the ones whose 48h low is a hair from
entry. The 48h window derives stops from the very leg we are trying to
buy. A pullback's real structural stop is the PRIOR swing low (the
higher-low that defines the uptrend); a base's is below the BASE's floor
(the 7d low with a volatility buffer). The logic is not wrong — it is too
narrow for two of the four setups, and the data says so at 6-of-6.

VERDICT: real property of the derivation, not of the setups. A design
change (setup-aware stop derivation) needs Pilot approval under the
freeze; drafted on request, NOT implemented.

## 4. The plain answer

BOTH, in measured proportions — but the tape carries most of it:

- 82.5% of everything dies at the classifier because the tape is genuinely
  chase-heavy: an extended uptrend where most movers are already gone and
  most non-movers fit no long setup. That is the tape, and waiting is the
  correct response to it. The vote's kills also lean tape: the repeated
  TREND+LOCATION failure signature means "no clean uptrend pullbacks
  exist right now", which is a market fact.
- ONE gate is structurally too narrow for current conditions: R014's stop
  derivation, per section 3. It has a 100% kill rate on vote-passers, both
  from the same mechanical cause, and it exclusively affects the two
  setups the system was redesigned to prefer. If any single adjustment is
  worth considering, it is setup-aware stops — nothing else shows
  structural evidence of over-tightness on current data.

So: mostly tape — wait; one narrow-but-real derivation gap — your call.

## Post-fix update (18:5x UTC) — setup-aware stops shipped and verified

The Pilot approved the drafted derivation (all five choices as-is); it
shipped as the LAST gate change before hard freeze. First scan under it:

- 25 past floor, 16 deep, 4 classified — and ZERO "no derivable stop"
  refusals. Every classified candidate now carries a structural stop with
  its basis, or an honest low ratio:
    PEPE BASING rr 5.29 (5-day base floor — previously REFUSED)
    TRUMP PULLBACK rr 6.75 (prior higher-low fractal — previously REFUSED)
    UNI BREAKOUT rr 0.86 (unchanged derivation, honest low ratio)
    PUMP PULLBACK rr 0.68 (prior higher-low far below — honest structure;
      the old derivation refused it, the new one prices it and R014/R009
      still say no)
- Funnel outcome: PUMP passed its vote (the day's only vote-passer) and
  died at R009 at 55.6% — the gates moved from "cannot price this" to
  "priced it, and it does not pay". Zero packets, all reasons named.
- Refusal logging and STOP BASIS packet rendering verified in code paths;
  suppression entries now carry the computed rr (PUMP logged at 0.681).

Section 3's structural finding is RESOLVED: the derivation no longer takes
stops from the leg being bought, the two previously-refused setup types
price cleanly, and the degenerate guard still refuses bases too fresh to
define risk. Throughput matches the draft's estimate (~0-1/day, well under
the looseness ceiling).

## 5. UTC days for the video

Logs began 2026-09-01 UTC. The deadline is 2026-09-08 23:59 UTC. Running
daily through the deadline, the logs will show AT MOST 8 DISTINCT UTC DAYS
(09-01 through 09-08 inclusive). Two are complete now; six more are
available. IST runs 5.5h ahead, so each of your evenings spans a UTC day
boundary — describe the run as "8 UTC days" and the per-day metrics stay
consistent with every timestamp in the record.
