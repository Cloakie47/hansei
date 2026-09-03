# Manual OCO runbook, protective stop/target after a LIVE entry fill

```
+---------------------------------------------------------------------+
| !!  NEVER EXECUTED.  Every step below places a REAL ORDER with REAL |
| !!  MONEY. There is no paper/test path for order lists, orderTest  |
| !!  does not validate OCO. Nothing here has run once. Read the      |
| !!  whole file before typing anything. Binance will ask you to      |
| !!  confirm each write in its own UI; that prompt is your last      |
| !!  stop, read it, do not reflex-confirm.                          |
+---------------------------------------------------------------------+
```

Documentation only, no code, no automation. Use ONLY if a live entry
fill has actually happened (fills.jsonl shows a mode:LIVE BUY with a real
executedQty). The OCO rests a take-profit and a stop-loss on the exchange
so the position is protected between scans. This is the middle path from
docs/exit-protection-assessment.md; the automated version was deliberately
not built.

## Step 0, read the entry fill

From the LIVE BUY's response in logs/fills.jsonl, take:
- `executedQty`, base asset actually bought (e.g. "0.011670" BNB)
- `symbol`, and the packet's `target` and `stop` (from the approved draft
  in logs/approved/<id>.json, the R:R block)

## Step 1, compute the SELLABLE quantity

You cannot sell more base than you hold after fees. If the fee was paid in
the BASE asset (default when not using BNB-discount on a non-BNB pair),
subtract it; then round DOWN to the lot step. Rounding UP or forgetting the
fee is the classic first-attempt rejection.

Formula:
  net_qty  = executedQty - (executedQty * fee_rate)
  sellable = floor(net_qty / lot_step) * lot_step

- fee_rate: 0.00075 (0.1% taker with the 25% BNB discount) or 0.001 (no
  discount). If the response shows fee paid in a DIFFERENT asset (e.g. BNB
  while trading BNBUSDT is itself the base, check `commissionAsset`), the
  base qty is NOT reduced; sellable = floor(executedQty / lot_step)*lot_step.
- lot_step: the symbol's LOT_SIZE stepSize (BNBUSDT = 0.001). Confirm live
  with spot_exchangeInfo for the actual pair before trusting a remembered
  value.

WORKED EXAMPLE (8 USDT BNBUSDT entry at ~685, fee in base):
  executedQty = 0.011670
  net_qty     = 0.011670 - 0.011670*0.00075 = 0.011661
  sellable    = floor(0.011661 / 0.001) * 0.001 = 0.011

Then CHECK both legs clear the 5 USDT minNotional:
  target leg: 0.011 * 728 = 8.01 USDT   OK
  stop leg:   0.011 * 668 = 7.35 USDT   OK
If either is below 5, the OCO is invalid at this size, do not place it;
hold to the R013 time-stop exit instead.

## Step 2, the price relationship (state it so you cannot invert it)

You are SELLING to close a LONG. The rule, always:

    STOP  <  LAST (current price)  <  TARGET

- TARGET (take-profit) is ABOVE the current price, the good outcome.
- STOP (stop-loss) is BELOW the current price, the protective outcome.

If your target is below your stop, or either is on the wrong side of the
current price, Binance rejects the list. Round both to the PRICE_FILTER
tickSize (BNBUSDT = 0.01) before sending.

## Step 3, place the SELL OCO (one tool_execute call)

Fill every <PLACEHOLDER>. This wraps the hidden spot.orderListOco endpoint.

  tool_execute, toolName = "spot.orderListOco", arguments =
  {
    "symbol": "<SYMBOL>",                e.g. BNBUSDT
    "side": "SELL",
    "quantity": <SELLABLE>,              from Step 1, e.g. 0.011
    "aboveType": "LIMIT_MAKER",
    "abovePrice": <TARGET>,              ABOVE current price, tick-aligned
    "belowType": "STOP_LOSS_LIMIT",
    "belowStopPrice": <STOP>,            BELOW current price, tick-aligned
    "belowPrice": <STOP_LIMIT>,          set slightly below belowStopPrice
                                          (e.g. stop * 0.997) so the stop
                                          fills once triggered
    "belowTimeInForce": "GTC",
    "listClientOrderId": "<PACKET_ID>-oco"
  }

Notes:
- `aboveType` LIMIT_MAKER needs only abovePrice. `belowType`
  STOP_LOSS_LIMIT needs BOTH belowStopPrice (the trigger) and belowPrice
  (the limit it becomes). A market-style stop (STOP_LOSS, stopPrice only)
  also exists but STOP_LOSS_LIMIT is safer, it will not fill at an
  arbitrary gap price.
- If the field names are rejected, fall back to the deprecated
  spot.orderOco shape (side/quantity/price/stopPrice/stopLimitPrice), but
  try orderListOco first; orderOco is deprecated.
- Binance will prompt you to confirm. This is expected, one position, one
  protective list.

## Step 4, record it by hand in logs/fills.jsonl (append one line)

The OCO is itself an order the audit trail must show. Append (never edit):

  {"id":"<PACKET_ID>-oco","ts":"<UTC now, YYYY-MM-DDThh:mm:ssZ>",
   "mode":"LIVE","kind":"protective-oco","symbol":"<SYMBOL>","side":"SELL",
   "quantity":<SELLABLE>,"target":<TARGET>,"stop":<STOP>,
   "listClientOrderId":"<PACKET_ID>-oco",
   "response":<paste the tool_execute response verbatim>}

Also append a one-line note to logs/autonomous-changes.jsonl is NOT needed,
this is a Pilot action, not an autonomous change.

## Step 5, if you later want a MANUAL exit instead

A resting OCO LOCKS the position quantity; you must cancel it before a
manual market sell, or the sell is rejected for insufficient free balance.

1. Cancel the list:
   tool_execute, toolName = "spot.deleteOrderList", arguments =
   { "symbol": "<SYMBOL>", "listClientOrderId": "<PACKET_ID>-oco" }
   (or "orderListId": <the numeric id from the Step 3 response>)
   Confirm in the Binance prompt.
2. Then run the normal exit: python scripts/run.py exit <SYMBOL> --reason
   "<why>", approve it, and place the SELL through the usual prepare/record
   flow. Log that fill as mode LIVE.

## Step 6, if the OCO FIRES between sessions (position closed while away)

The exchange closed the position and nothing logged it. At the NEXT
session, reconcile by hand so the record stays honest:

1. Query what happened:
   spot_getOrder or spot_myTrades for <SYMBOL>, find the SELL that
   filled (either the target or the stop leg) and its executedQty / price.
2. Append the real exit to logs/fills.jsonl (append only):
   {"id":"<PACKET_ID>-oco-fill","ts":"<the fill's real ts>","mode":"LIVE",
    "kind":"oco-triggered-exit","symbol":"<SYMBOL>","side":"SELL",
    "quantity":<filled qty>,"fill_price":<price>,
    "leg":"<target|stop>","response":<the spot_getOrder record verbatim>}
3. Note in that night's debrief which leg fired and the realised move,
   this is real P&L, the first the system will have, and it must be
   reported plainly whether it was a win or a loss.

## Reminders

- Never place the OCO before the entry fill is confirmed in fills.jsonl.
- Never round the sell quantity UP.
- Never invert target/stop: STOP below, TARGET above, always.
- Every write here is real. If any number looks wrong at the Binance
  confirmation prompt, cancel, the 72h time stop still protects the
  position, and a missed OCO is recoverable; a wrong one placed is not.
