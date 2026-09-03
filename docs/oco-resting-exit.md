# Resting-exit path (protective OCO after a live fill)

Built 2026-09-03, Pilot-approved, 2-hour time box (completed inside it).
Code: scripts/oco.py, wired into scripts/run.py exit.

## What this adds

After a LIVE buy fill, a protective SELL OCO can now be prepared and placed
so the position is guarded on the exchange between scans: a take-profit leg
at the packet's target and a stop-loss leg at the packet's stop. Before
this, a filled position was protected only by the 72-hour time stop (which
fires only when a scan runs) and the Pilot's presence, so it could fall
significantly between sessions with nothing resting on the book.

The flow (scripts/oco.py), every MCP call made by the session, never by the
script:
1. prepare: compute the sellable quantity (executedQty minus base-asset fee,
   floored to the lot step, never rounded up) and tick-rounded target/stop
   from the packet's own rr block; fetch last price (public); validate the
   relationship; emit the two leg-test calls and the orderListOco call.
2. the session runs the two orderTest leg-tests, then the orderListOco call
   (Binance prompts the Pilot to confirm). Proven both legs validate.
3. record: append the placement to logs/resting_orders.jsonl.
4. cancel: emit spot.deleteOrderList; record-cancel logs the cancel.

## Why it matters

Binance ships the order-list tools (spot.orderListOco, spot.deleteOrderList)
in the hidden write registry reachable through tool_execute, but the MCP's
documented examples do not use them, only single spot orders. An agent that
follows the documented examples therefore places an entry and walks away,
leaving the position unguarded between sessions with no resting stop. This
path closes that gap for the supervised case: the human approves the entry,
and immediately approves a resting OCO that protects it until the next scan
or the time stop.

## The leg-test limitation (stated plainly)

There is no test endpoint for the order-list family, orderTest validates
single orders only. So each leg is leg-tested separately, which was proven
to catch per-leg tick size, lot size, minNotional, and order type
(a sub-minNotional leg is rejected -1013). Leg-testing does NOT catch: a
LIMIT_MAKER priced on the wrong side of the market (verified: a would-cross
price passes orderTest but the live engine rejects it -2010), the OCO price
ordering, list acceptance, or the fee-adjusted quantity being truly
sellable (orderTest ignores balance). This path compensates for the first
gap in code: it validates loudly that target > last > stop and refuses on
inversion without correcting it silently, so the would-cross case is caught
before emission. The remaining gaps (list acceptance, exact balance) can
only surface on the real placement, which is why the first live use is
still a supervised, Pilot-confirmed act.

## Reconciliation subsystem (built 2026-09-03, Pilot-approved)

The earlier version left session-start reconciliation out of scope. The
Pilot then approved building it, because a silent divergence between
fills.jsonl and the exchange is the worst gap in a product whose claim is an
honest audit trail. It is now built (scripts/oco.py reconcile).

At the start of every scan, run.py checks logs/resting_orders.jsonl for any
open OCO and, if found, prints the queries to run (spot_getOpenOrders and
spot_myTrades per symbol) because scan cannot make authenticated MCP calls
itself. `oco.py reconcile <symbol> <openorders> <trades>` then classifies:
target leg filled, stop leg filled, cancelled externally, still resting, or
partially filled. Proven in PAPER on all five cases.

- A detected close APPENDS a new fill to fills.jsonl with the real price,
  quantity, fee and timestamp, flagged `reconciled: true`. It NEVER edits an
  existing line: the record shows the exchange acted and we discovered it
  after the fact, because that is what happened.
- A reconciled close prints loudly at scan start with the symbol, which leg
  fired, and the realised P&L, the first real P&L the system produces,
  reported whether a win or a loss.
- A partial fill logs what filled, reports the residual position, and says
  so plainly rather than guessing.
- run.py positions nets the reconciled close, so it never shows a phantom
  position (proven: an open position went flat after reconciliation).
- Cancelled-externally prints loudly that the position is UNPROTECTED.

The manual runbook (docs/oco-manual-runbook.md) remains as a backup path.

## Exit-flow interaction

A resting OCO locks the position quantity, so a manual exit must cancel it
first or the sell is rejected for insufficient balance. run.py exit now
checks logs/resting_orders.jsonl for an open OCO on the symbol and prints
the cancel-first step before generating the exit packet.
