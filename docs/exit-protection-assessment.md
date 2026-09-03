# Exit-protection assessment, 2026-09-03. ASSESSMENT ONLY, nothing built.

The gap, stated: packets compute a structural target and stop, and those
numbers GATE the trade (R014), but nothing is ever placed on the
exchange. Between scans, a position is unprotected; the stop exists on
paper, not on the book.

## 1. Can we place an OCO after an entry fill?

YES, mechanically. The hidden write registry reachable through
tool_execute includes spot.orderListOco (the current endpoint; spot.orderOco
is deprecated but also present) and spot.deleteOrderList for cancellation,
all verified in scripts/tool-inventory.md when the write surface was
mapped. A long position closes with a SELL OCO: a LIMIT_MAKER/TAKE_PROFIT
leg at the target above, a STOP_LOSS(_LIMIT) leg at the stop below, same
quantity both legs, prices obeying limit > last > stop.

## 2. Confirmation model

Every write through the MCP triggers the platform's Pilot-confirmation, so
the expected flow at entry is TWO confirmations back-to-back: the entry
order, then the protective OCO seconds later, acceptable, since the Pilot
is by definition present at entry (hard constraint 4). CAVEAT, stated: we
have never executed a tool_execute-wrapped WRITE live; that the hidden
endpoints prompt identically to spot_newOrder is the platform's documented
behavior, not something we have observed. It is verifiable only on the
first live attempt.

## 3. Constraints at our 8 USDT size, measured

minNotional 5 USDT applies PER LEG. With an 8 USDT entry (minus taker
fee), the stop leg's notional stays valid down to a stop ~37% below entry,
measured: 3% stop -> ~7.75 USDT leg, 8% -> ~7.35, 20% -> ~6.39, 38% ->
4.96 (INVALID). Our structural stops run 2-10% below entry, so an 8 USDT
position supports a valid OCO with >2 USDT of headroom. Remaining
mechanics: both prices tick-aligned, quantity lot-aligned AND reduced by
the fee if paid in the asset (sell executedQty net of fee, rounded DOWN a
lot step, a classic first-attempt failure), stop legs count against
MAX_NUM_ALGO_ORDERS (5; we would use 1).

## 4. Can PAPER mode prove it? NO, and this is the decisive fact.

spot.orderTest and spot.sorOrderTest are SINGLE-ORDER validators. There is
NO test endpoint for the order-list family anywhere in the registry. We
could individually orderTest each leg (LIMIT sell; STOP_LOSS_LIMIT sell,
both supported types), which validates tick/lot/notional per leg, but the
OCO-SPECIFIC mechanics, the price relationship, list acceptance, quantity
locking, can only be validated by placing a REAL order list. Our entire
safety methodology has been "prove it in PAPER first"; for OCO that
methodology is unavailable.

## 5. Interaction with a Pilot-approved manual exit

A resting SELL OCO LOCKS the position's quantity. A manual exit therefore
requires: cancel the OCO first (spot.deleteOrderList, one write, one
confirmation), then place the market sell (second write, second
confirmation). Also true and currently unhandled: if the OCO FIRES between
sessions, the exchange closes the position with nobody logging it,
fills.jsonl would not learn of the exit until the next session reconciles
via spot_getOrder/spot_myTrades. That reconciliation machinery does not
exist and would be NEW code.

## 6. The plain answer: DOCUMENT THE GAP. Do not build.

Buildable safely in the time remaining? NO, and honestly so:
- The first-ever OCO validation would be a LIVE order (no test endpoint),
  debugging fee-adjusted quantities and price relations with real money on
  what would also be the first-ever live fill day.
- It triples the untested write surface (place OCO, cancel OCO, reconcile
  exchange-initiated fills) when the BASE entry flow itself has never run
  live.
- Exchange-initiated closes break the current logging model and need a
  reconciliation subsystem, a real feature, not a patch, under freeze.

MIDDLE PATH, prepared but not automated: if a live fill happens before the
deadline, the Pilot can place the OCO manually through printed tool calls
(the same prepare-style flow used everywhere), with the fill logged by
hand at the next session. A runbook for that is a documentation task, not
machinery, and can be written on request.

The current exit model, stated for the record and now in the README:
targets and stops are computed and gate the trade; no protective order
rests on the exchange; positions are protected by the 72h time stop (R013
proposes the exit at the next scan) and by the Pilot's presence, not by a
resting order. On a gap down between scans, the stop is advisory. That is
the truthful trade-off of confirm-before-execute custody with no
unattended execution path.

## Reconsideration, 2026-09-03 (leg-testing evidence)

The Pilot reconsidered on capital-loss grounds. New EVIDENCE, gathered by
leg-testing each OCO side through spot.orderTest (read-only, never reaches
the engine), on BNBUSDT at market 697.90:

- SELL LIMIT_MAKER qty 0.011 @ 728 (above market): PASS ({}).
- SELL STOP_LOSS_LIMIT qty 0.011 stop 668 / limit 666: PASS ({}).
- SELL STOP_LOSS_LIMIT qty 0.005 (notional ~3.3): REJECTED, -1013 NOTIONAL.
- SELL LIMIT_MAKER qty 0.011 @ 690 (BELOW market, would cross): PASS ({}).

So leg-testing DOES validate per-leg tick size, lot size, minNotional and
order type. It does NOT catch a LIMIT_MAKER priced on the wrong side of the
market (the last test passed orderTest but the live engine rejects it -2010),
does NOT validate the OCO price ordering (limit > last > stop), does NOT
validate list acceptance/quantity-locking, and does NOT check the
fee-adjusted sellable quantity (orderTest ignores balance). Correction to
the earlier assessment: it said OCO "cannot be proven in paper mode" full
stop; that was too absolute. The LEGS can be paper-validated, which removes
the most frequent first-attempt rejection class. The LIST semantics and the
balance/quantity correctness cannot.

Capital-at-risk framing: this is a spot long, no leverage, on a 40 USDT
demo account with an 8 USDT position and no withdrawal scope. The absolute
maximum a botched OCO or an unprotected gap can cost is the position value,
about 8 USDT, and realistically a fraction of it. The risk being managed is
single-digit dollars, and today there is no live position to protect (MODE
PAPER, zero packets all week).

Recommendation unchanged: do NOT build automatic OCO before the deadline.
Use the manual runbook (docs/oco-manual-runbook.md), now strengthened by the
leg-test-first step proven above, IF a live fill happens. Automation's
expensive, risky part is the exchange-initiated-fill reconciliation
subsystem, which a single supervised position does not need.
