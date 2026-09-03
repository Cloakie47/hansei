# PROPOSED: setup-aware stop derivation, DRAFT ONLY, nothing shipped

Status: drafted 2026-09-02 for Pilot approval. Motivation, from the
near-miss diagnosis: R014's stop derives from the 48h swing low, and a
pullback or base in progress IS its own 48h low, 6 of 28 classified
candidates blocked with "no derivable stop" (4 PULLBACK, 2 BASING, zero
BREAKOUT/REVERSAL), including 100% of vote-passers. The derivation takes
its stop from the leg we are buying.

Unchanged everywhere: the degenerate-stop guard (entry - stop >= 0.5x own
capped avg daily move), the 72h travel cap on targets, R014's 2:1 floor,
fail-closed on ambiguity.

## PULLBACK, stop below the PRIOR higher-low

Identification: daily-bar fractal swing lows (a bar whose low is below the
lows of the two bars either side), computed over the last ~40 daily bars.
The prior higher-low is the MOST RECENT fractal swing low that is (a)
below entry and (b) outside the current leg (the last 3 daily bars are
excluded, they are the retrace itself). Stop = that swing low MINUS a
0.25x-avg-daily-move buffer, so a wick-sweep of the level does not tag the
exact tick.

REFUSE (blocked, never estimated) when: no fractal swing low exists below
entry outside the current leg; OR the identified prior low sits ABOVE the
current leg's low (the higher-low is already broken, the uptrend
structure the pullback thesis depends on has failed); OR the buffered stop
still violates the degenerate guard.

## BASING, stop below the base's floor

The basing period is the last 5 daily bars: the same horizon the
classifier's BASING conditions measure (5d decline into it, 5d volume
contraction). Floor = the minimum low of those 5 bars; stop = floor minus
the 0.25x buffer.

REFUSE when: fewer than 5 daily bars exist; OR the buffered stop violates
the degenerate guard, which the recompute shows is a REAL and correct
refusal: a base so tight that its floor sits within half a day's move of
entry has not built enough structure to define risk yet (both PEPE BASING
instances below).

## BREAKOUT, keep the current derivation, unchanged

Zero "no derivable stop" failures in the record. For a fresh breakout the
48h low IS the right structure, it is the pre-break consolidation zone,
not the leg being bought. No change proposed.

## REVERSAL, conceptually right, one amendment proposed

The 48h low is the CORRECT level for a reversal (below the capitulation
low, the thesis is dead). But entry sits near that low by construction, so
the raw level risks the same degeneracy. Amendment: apply the same
0.25x-avg buffer BELOW the 48h low. If the buffered stop still violates
the degenerate guard, refuse, an entry that close to the capitulation
extreme has no room to be wrong. (One REVERSAL in the record, XAUT, rr
3.35, the current derivation worked; the buffer is prophylactic.)

## Recompute: all 6 previously-blocked candidates under this draft

  PEPE  08:22 PULLBACK: R:R 5.44 (stop 3.310e-6 vs old 48h-low 3.410e-6), PASSES 2:1
  TRUMP 08:22 PULLBACK: R:R 4.34 (stop 2.065 vs old 2.217), PASSES
  TRUMP 16:49 PULLBACK: R:R 6.34 (stop 2.066 vs old 2.166), PASSES
  PUMP  16:49 PULLBACK: R:R 0.67, STILL BLOCKED. Its prior higher-low is
        far below (stop 0.00257 vs entry 0.00407); honest structure says
        the reward does not justify the risk. The draft does not rescue it.
  PEPE  16:49 BASING: REFUSED, degenerate guard (base floor within 0.5x
        avg of entry; the base is too fresh to define risk)
  PEPE  17:07 BASING: REFUSED, same

3 of 6 clear 2:1; 1 correctly stays blocked on honest structure; 2 are
correctly refused by the kept guard.

## Throughput impact, the looseness check

Of the 3 that clear R:R, only ONE also passed its indicator vote:
PEPE 08:22 PULLBACK (3/3). The two TRUMPs failed their votes (2/3) and
would have been suppressed regardless. PUMP, the other vote-passer,
stays blocked at 0.67:1.

So over the last two days this draft converts the packet count from 0 to
EXACTLY 1. Daily rate: ~0.5 packets/day on this tape, nowhere near the
2-3/day looseness ceiling. The draft un-blocks the structurally sound case
and nothing else; the gates around it keep doing their work.

## Not shipped

No code changed. The recompute above ran as scratch analysis. Awaiting the
Pilot's verdict on: the fractal definition, the 3-bar current-leg
exclusion, the 5-bar basing window, the 0.25x buffer, and the REVERSAL
amendment.
