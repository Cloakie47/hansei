# Live-trade pre-flight — verified 2026-09-02

Status of every safety layer before the first LIVE order. Nothing has been
placed. Flipping MODE is the Pilot's action, not the Unit's.

## 1. Funds

- 40 USDT confirmed in the SPOT wallet of the Agentic sub-account (uid
  1273127438). No transfer needed — Funding wallet is 0.
- Source of truth: wallet_queryUserWalletBalance (quoteAsset=USDT) shows
  Spot = 40; depositHistory confirms 40 USDT via BSC, status 1 (success),
  walletType 0 = Spot, credited 2026-09-01T18:16Z.
- Known issue: spot_getAccount serves a stale cached snapshot (USDT
  0.00000000, updateTime frozen at 2026-09-01T16:15Z, before the deposit).
  usdt_free() therefore accepts the wallet-summary format as fallback.
  Re-verify spot_getAccount freshness before the first LIVE order; if it is
  still stale at fill time the fill log will record the wallet-summary figure.

## 2. Mode state

- .env contains exactly: MODE=PAPER
- place.read_mode() resolves to PAPER. Anything other than an explicit
  MODE=LIVE (missing file, missing key, typo) resolves to PAPER.

## 3. assert_paper_safe

Re-tested today: a simulated misroute (mode PAPER resolving to
spot_newOrder) raises "MODE ROUTER BUG: ... Refusing to call anything."
before any call is emitted. The guard allows only spot.orderTest and
spot.sorOrderTest when mode is not LIVE.

## 4. Exactly what changes when MODE flips to LIVE

The ONLY mode-dependent code path is build_call() in scripts/place.py,
quoted verbatim:

    if mode == "PAPER":
        order_args["computeCommissionRates"] = True
        call = {
            "mode": mode,
            "tool": PAPER_TOOL,
            "wrapped_tool": PAPER_WRAPPED,
            "arguments": {"toolName": PAPER_WRAPPED, "arguments": order_args},
        }
    else:
        call = {
            "mode": mode,
            "tool": LIVE_TOOL,
            "wrapped_tool": None,
            "arguments": order_args,
        }
    assert_paper_safe(call)
    return call

with the constants:

    PAPER_TOOL = "tool_execute"
    PAPER_WRAPPED = "spot.orderTest"
    LIVE_TOOL = "spot_newOrder"

In LIVE the identical order arguments go to spot_newOrder directly instead
of tool_execute-wrapping spot.orderTest, and computeCommissionRates (a
test-order-only parameter) is not added. Nothing else differs: same
affordability pre-flight, same argument builder, same fills.jsonl entry
shape ("mode": "LIVE" instead of "PAPER").

## 5. LIVE confirmation flow, end to end

1. Scan produces a candidate; the Unit drafts it. Gates run in order:
   R009 confidence floor, R010 duplicate-pending, then the rulebook checks
   (R001 sizing against live balance, R003 rejection dedupe, R008 vetting,
   R007 source independence).
2. The packet renders to packets/<id>.txt and the Unit presents it. The
   Pilot answers y or n. On n: reason code, logged, done. Nothing is called.
3. On y: the verdict is logged to proposals.jsonl (APPROVED), then
   place.py prepare runs the affordability pre-flight again against the
   live balance and emits the routed call — with MODE=LIVE that is
   spot_newOrder with the packet's arguments, newClientOrderId = packet id.
4. The session invokes spot_newOrder via the MCP server. **Binance then
   asks the Pilot to confirm the order in their own UI — this is Binance's
   enforcement layer (hard constraint 1), not ours. The order does not
   execute until the Pilot confirms it there.** Expect it; let it happen.
5. On fill, place.py record appends to fills.jsonl with "mode": "LIVE",
   the request, and the raw response. Append-only, never edited.

Two human confirmations therefore precede any live fill: the packet y/n in
this terminal, and Binance's own confirmation prompt. The Unit can trigger
neither.

## Remaining before first LIVE order

- Pilot verdicts on pending packets (p-20260901-005, -006, -007).
- Pilot flips MODE=LIVE in .env (Unit does not touch it).
- spot_getAccount freshness re-check at execution time.
