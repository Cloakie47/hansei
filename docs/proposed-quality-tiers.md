# PROPOSED R018: quality tiers — DRAFT ONLY, not shipped

Motivation (Pilot, 2026-09-03): the expectation is established, high-volume
assets — BTC, ETH, BNB, SOL, XRP — but the only quality filter is a 15m
24h-volume floor, which a memecoin can clear on one hype day. Names that
actually reached packets: PUMP, TUT, PEPE, TRUMP, 0G.

## Criteria (objective, self-updating — no hardcoded list)

Market cap is stated as NOT OBTAINABLE with our tooling: the MCP's
analysis_getTokenAiReport returns an empty envelope (bug report filed) and
the spot API has no capitalization endpoint. The criteria therefore use two
measures we already compute from klines, both self-updating daily:

- LISTING AGE: days since the pair's first monthly candle on Binance spot.
- SUSTAINED VOLUME: MEDIAN daily quote volume over the trailing 30 days.
  The median, not the mean — one hype day cannot buy a tier.

TIER 1: age >= 730 days AND median 30d daily volume >= 50m USDT.
TIER 2: age >= 365 days AND median 30d daily volume >= 10m USDT.
TIER 3: everything else past the 15m floor.

## Who qualifies today (measured, all 29 recent candidate symbols)

TIER 1 (5): BTC (878m median, 9.1y), SOL (115m, 6.1y), XRP (81m, 8.3y),
BNB (63m, 8.8y), ZEC (59m, 7.5y). ETH was not in the recent candidate
sample but qualifies trivially. The objective criteria land almost exactly
on the Pilot's named list — plus ZEC, which genuinely is established and
high-volume, and the criteria are honest about that.

TIER 2 (6): DOGE, TRX, ADA, TUT, PUMP, and borderline peers. Honest
finding: TUT (28m median, 1.5y) and PUMP (20m, just past 1y) — memecoins —
clear Tier 2 legitimately on the numbers. Age plus volume measures
establishment, not meme-ness; any criteria pretending otherwise would be a
disguised blocklist.

TIER 3 (rest, ~18): PEPE, TRUMP, 0G, ENSO, HEMI, ACE, ONG, and — worth
noticing — some old-but-thin names: FIL (4.8m median), CRV (3.3m), DASH
(3.2m), OP (2.0m), AAVE (8.7m). The tier system demotes several assets we
previously packeted, not just memes.

## The three options, weighed on the last three days' data

A. RESTRICT the universe to Tier 1 (or 1+2):
   Tier-1-only: of all classified candidates in three days, exactly ONE was
   Tier 1 (XRP, a pullback that failed its vote 2/4). Zero vote-passes,
   zero packets — and honestly, likely ZERO PACKETS FOR THE REST OF THE
   WEEK, because majors rarely print fresh setups on this tape. Maximum
   quality, near-total silence.

B. CONFIDENCE BONUS for Tier 1 (e.g. +0.03):
   Changes nothing that matters: Tier 1 names rarely classify, so there is
   nothing to boost; Tier 3 memes keep leading the funnel. Cheapest option,
   weakest lever. Not recommended.

C. TIER-SCALED VOTE THRESHOLD (universe unchanged):
   Tier 1 keeps 3-of-4 (PULLBACK/BREAKOUT); Tier 2 requires 4-of-4 on every
   setup; Tier 3 requires 4-of-4 AND R:R >= 3:1. Both recent vote-passers
   (PEPE 3/3, PUMP 3/3 — both Tier 3) would have been killed; last-3-day
   packet count under C: 0 (same as actual, but with the memes' path
   steepened rather than their names blocked).

## Recommendation

A HYBRID of A and C, drafted as R018:

- **R018 (PROPOSED)** The tradeable universe is Tier 1 and Tier 2 only,
  where tiers are computed daily from listing age and trailing-30-day
  MEDIAN daily quote volume (T1: >=730d and >=50m; T2: >=365d and >=10m).
  Tier 3 pairs are excluded at ingest and logged, like R011/R016
  exclusions. Tier 2 packets require a 4-of-4 indicator vote regardless of
  setup; Tier 1 keeps the standard thresholds. Tiers render on every
  packet.

Reasoning: dropping Tier 3 removes exactly the names that prompted this
(PEPE, TRUMP, 0G, ENSO) plus the old-but-illiquid tail, while Tier 2's
stricter vote keeps DOGE/TRX/ADA-class assets reachable without letting a
1-year memecoin packet on a 3-of-4. It also spares the Pilot adjudicating
meme packets at all, which option C alone would not.

## Throughput cost, stated plainly

Under the recommended R018, the last three days replay to ZERO packets
(the two vote-passers were Tier 3). Expected forward rate: packets only
when a Tier 1/2 asset prints a real setup — realistically 0-2 per WEEK on
tape like this, not per day. If the demo needs funnel activity, the
suppression and tier-exclusion logs still fill daily; if it needs packets,
this rule makes them rarer and better, and that trade-off is the Pilot's
to make. NOT SHIPPED.
