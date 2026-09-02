# v3-vs-v2 shadow gap diagnosis — 2026-09-03. DIAGNOSIS ONLY, nothing changed.

## POST-FIX UPDATE + A CORRECTION (later the same day)

The Pilot approved both recommendations: floor-bindingness is now the
third promotion criterion (canonical bar: docs/v3-promotion-criteria.md)
and v3's R:R term is SYMMETRIC — same log scale, capped both ways
(max(-0.045, min(0.045, 0.015*log2(rr/2)))). All 31 shadow samples re-run
(additive recompute is exact: every sample sits far from the formula's
floor and caps):

- WITHIN-SETUP DISTRIBUTIONS (symmetric term):
    PULLBACK: n=13, min 0.570, median 0.647, max 0.714 — 12/13 >= floor
    BASING:   n=10, min 0.567, median 0.593, max 0.645 — 4/10 >= floor
    BREAKOUT: n=8,  min 0.533, median 0.569, max 0.572 — 0/8 >= floor
- FLOOR BINDING in favored setups: YES — 7 of 23 suppressed. Straddles.
- FLOOR-CROSSERS: all 14 still cross. The symmetric term moved only the
  three broken-structure PUMP samples (rr 0.68-0.69): 0.649-0.665 down to
  0.626-0.642 — the right direction, but STILL above the floor; R014
  remains their actual killer. Stated plainly: the symmetric term reduces
  the reward for broken structure, it does not eliminate it. If the Pilot
  wants broken structure floor-killed at R009, the penalty scale (0.015)
  would need roughly tripling — not proposed, just quantified.
- PEPE's 7.75:1 pullback: 0.652 unchanged (rr > 2, symmetry irrelevant),
  still clears.

CORRECTION, on the record: the original diagnosis below claims every
favored-setup sample scored >= 0.60 with a minimum of 0.613. That was
WRONG — a conclusion reasoned from the crossers list instead of a computed
minimum. The actual minimums in the same log were 0.567 (BASING) and
0.570 (PULLBACK): the floor was already partially binding for BASING
before the fix, and criterion 3 was closer to met than the diagnosis
implied. The recommendation survives the error (PULLBACK was 12/13 above
the floor either way), but the claim did not, and this file now says so.

Original diagnosis follows, uncorrected, as written.

---

Trigger: PUMP logged v2 56.8% / v3 66.5%, the largest gap on record.
Sample: 31 shadow rows (all classified candidates since v3 shipped).

## 1. The gap (v3 minus v2)

Overall: mean +0.051, median +0.068, range -0.014 to +0.122.
By setup:
  PULLBACK: n=13, mean +0.085, median +0.093
  BASING:   n=10, mean +0.059, median +0.067
  BREAKOUT: n=8,  mean -0.013, median -0.014  (v3 is STRICTER here)
  REVERSAL: no samples yet.

## 2. Floor-crossers

v2-suppressed but v3-passing: 14 of 31 — every one PULLBACK or BASING
(TUT x2, PUMP x5, TRUMP x4, PEPE x2, XRP x1; scores in the shadow log,
e.g. PEPE PULLBACK 0.530 -> 0.652). Reverse crossers — v2-passing,
v3-suppressed: 6, ALL the same UNI BREAKOUT reading (0.601 -> 0.587).

## 3. Systematic or setup-shaped?

Setup-shaped, with a hard asymmetry: v3 scores higher on 12/13 PULLBACKs
and 10/10 BASINGs, and on 0/8 BREAKOUTs. So "broadly more generous" is NOT
the right description — breakouts got stricter, exactly as the rebalance
intended.

BUT the honest finding inside the favored setups: EVERY pullback/basing
sample scores at or above 0.60 under v3 (the lowest is 0.613). Within the
two setups v3 was designed for, the 60% floor is currently NON-BINDING —
R009 does no work there, and all discrimination has been delegated to the
vote and R014. That is defensible as design (confidence measures setup
fit; the vote and structure gates select), but it is the same shape as
v2's flat-base clustering, now wearing setup-specific clothes: a score
distribution living entirely above the floor it is supposed to be tested
against. One concrete symptom: PUMP's 0.68:1 R:R candidates score
0.649-0.665 — v3's R:R term only ADDS for good structure and never
subtracts for bad, so a structurally broken candidate keeps a high score
and survives to R014 rather than dying at R009.

## 4. If v3 were live, packets over the record

Full-gate simulation (vote PASS + R:R >= 2 + v3 >= 0.60): EXACTLY 1 —
PEPE PULLBACK at 19:14Z (rr 7.75, v3 0.652, vote 3/3), which v2 suppressed
at 0.530. Three early samples predate vote instrumentation, but their
adjacent-scan votes all failed, so the bound is firm: 1 packet vs the
actual 0. Throughput impact of promotion: +1 packet per ~2 days, well
under every ceiling.

## Verdict for the promotion criteria

The Pilot's suspicion is half-confirmed, and the half matters: v3 is NOT
globally permissive (breakouts tightened), but within PULLBACK/BASING its
distribution sits wholly above the floor, so promoting on a clustering
check alone would miss it. RECOMMENDATION (not implemented): add a
FLOOR-BINDINGNESS check to the promotion criteria — over the shadow
window, v3 must suppress a nonzero share of classified candidates in its
favored setups, or the within-setup distribution must straddle 0.60.
Additionally worth Pilot consideration at promotion time: whether v3's
R:R term should subtract below 2:1 rather than merely not add. Criteria
unchanged, v3 remains shadow, nothing promoted.
