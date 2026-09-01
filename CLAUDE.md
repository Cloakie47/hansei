# HANSEI

反省 — the practice of reflecting on what you did wrong, even when you succeeded.

## What this is

An AI trading analyst that runs on Binance Agent OS. It does not trade on its own.
It **proposes** trades to a human, learns from every rejection, and publishes an
honest report card every night.

Built for the Binance Agent OS Mini Hackathon. **Deadline: 8 Sept 2026, 23:59 UTC.**
Track B (connect your MCPs and trade).

## The one-line pitch

> An AI trading analyst that proposes trades for you to approve, learns from every
> rejection, and publishes its own honest report card to Binance Square every night.

## Vocabulary (use this everywhere — UI, logs, README, demo)

| Term | Meaning |
|---|---|
| **Pilot** | The human. Approves or rejects every proposal. |
| **Unit** | The agent. Cannot act without the Pilot. |
| **Sync Rate** | Approval rate = approved proposals / total proposals. The headline metric. |
| **Debrief** | The nightly self-review. |
| **Rulebook** | `rulebook.md` — lessons the Unit has learned. Grows over time. |

## Hard constraints — do not design around these, design WITH them

1. **Every trade and transfer requires the Pilot's confirmation.** This is enforced
   by Binance, not by us. The Unit can never execute autonomously. This is a
   feature of the product, not a limitation to work around.
2. **There is no withdrawal scope.** The Unit can never move funds out of the
   Agentic sub-account.
3. **Whatever is in the sub-account is the entire loss ceiling.** Binance imposes
   no separate loss cap.
4. **Desktop only.** Claude Code must be open and the Pilot present.
5. **Granted scopes:** Market data (read), Account (read), Spot & Margin trading.
   Master account read, Futures, Margin Loan, and Internal Transfer are all
   **OFF** on purpose. Changing scopes requires disconnecting and reconnecting.

## Connection

MCP endpoint (already added, do not re-add, do not paste into chat):

```
claude mcp add binance-mcp-server --transport http https://agent.binance.com/mcp/agentic
```

Skills in use (install with `npx skills add <url>`):

- `binance-trading-signal` — smart money signals, backtests, daily/monthly reports
- `binance-leaderboard` — 6-dimension scoring (winrate/stability/drawdown/pnl)
- `query-token-audit` — scam and honeypot check before any proposal
- `crypto-market-rank` — sentiment, hype, smart-money inflow rankings
- `square-post` — publish the nightly Debrief to Binance Square
- `binance-agentic-wallet` — optional, x402 buyer-side payments (stretch goal only)

## File layout

```
hansei/
  CLAUDE.md              <- this file
  rulebook.md            <- lessons learned, injected into every decision packet
  prompts/
    decision-packet.md   <- how the Unit proposes a trade
    nightly-debrief.md   <- how the Unit reviews its own day
  logs/
    proposals.jsonl      <- every proposal, approved or rejected
    fills.jsonl          <- what actually executed
  debriefs/
    YYYY-MM-DD.md        <- one Debrief per day
    YYYY-MM-DD-square.md <- the short public version
  dashboard/             <- sync rate chart + rulebook growth
  scripts/
```

## Data schemas — never change these once logging starts

`logs/proposals.jsonl`, one JSON object per line:

```json
{
  "id": "p-20260901-001",
  "ts": "2026-09-01T14:22:00Z",
  "symbol": "BNBUSDT",
  "side": "BUY",
  "notional_usdt": 25,
  "confidence": 0.62,
  "thesis": "one sentence",
  "signals_used": ["binance-trading-signal", "crypto-market-rank"],
  "rules_checked": ["R003", "R007"],
  "invalidation": "what would prove this wrong",
  "audit_passed": true,
  "verdict": "APPROVED | REJECTED",
  "reject_reason": "SIZE | TIMING | CONVICTION | RISK | DUPLICATE | ASSET | OTHER",
  "pilot_note": "optional free text"
}
```

`rulebook.md` entries are numbered `R001`, `R002`, ... and never renumbered.
Deleted rules are struck through, not removed, so the history stays readable.

## Rules for you (Claude Code)

- **Never place an order without first printing the full decision packet** and
  waiting for the Pilot's explicit yes.
- **Never edit or backfill past log entries.** Append only. The integrity of the
  record is the whole product.
- **Never propose a trade that violates an active rule in `rulebook.md`.** If a
  rule blocks a good idea, say so and propose amending the rule instead.
- **Run `query-token-audit` before proposing anything that isn't a top-20 asset.**
- Keep position sizes small. This is a demo account.
- Do not give the Pilot financial advice. Present evidence, confidence, and
  invalidation conditions. The Pilot decides.

## Build order (do not skip ahead)

1. [ ] MCP connected, sub-account funded, one manual trade confirmed end to end
2. [ ] Decision packet generation + proposal logging
3. [ ] Approve/reject capture with reason codes
4. [ ] Nightly Debrief + rulebook updates
5. [ ] Square post publishing
6. [ ] Sync Rate chart + dashboard
7. [ ] Replay mode over historical data (dates hidden, symbols anonymised)
8. [ ] Stretch: x402 paywall on the full Debrief (Base, USDC) — cut if behind

## What we claim, and what we don't

We claim: the Unit **learns**. Sync Rate rises. Repeated mistakes stop repeating.
Rule compliance improves. Trade count and fee drag fall.

We do not claim it makes money. Four days of market data proves nothing, and
public experiments have shown LLM traders mostly lose. The demo is about
behaviour change, not returns. Never write a headline that promises profit.
