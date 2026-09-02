# HANSEI

反省 — the practice of reflecting on what you did wrong, even when you succeeded.

## What this is

An AI trading analyst that runs on Binance Agent OS. It does not trade on its own.
It **proposes** trades to a human, learns from every rejection, and publishes an
honest report card every night.

Holding horizon, fixed 2026-09-03: a short-swing system — entries on daily
structure, positions held hours to three days, 72-hour hard stop, every
entry and exit individually approved by a human. Never describe it as
intraday, real-time, or automatic.

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
5. **Granted scopes (verified 2026-09-01 against the live API key):**
   - Spot trading: ON
   - Margin: OFF at key level (enableMargin=false, no borrow/repay tools exist)
   - Futures: OFF (verified, -2015 rejection on futures_usds_futuresAccountBalanceV3)
   - Withdrawals: OFF (enableWithdrawals=false)
   - Internal transfer: OFF
   - Master account read: NO ENDPOINT EXPOSED (cannot be verified at key level;
     state it this precise way, never claim it is "disabled")

   Changing scopes requires disconnecting and reconnecting.

## Connection

MCP endpoint (already added, do not re-add, do not paste into chat):

```
claude mcp add binance-mcp-server --transport http https://agent.binance.com/mcp/agentic
```

Skills (install with `npx skills add <url>`; status as of 2026-09-02):

- `binance-trading-signal` — INSTALLED; smart-money mode works (public API),
  strategy mode needs the baw wallet CLI (not set up, stretch only)
- `query-token-audit` — INSTALLED; strict fail-loud parser in scripts/audit.py
- `crypto-market-rank` — INSTALLED; all seven feeds tested (on-chain universe,
  demoted to optional context by R005-R007)
- `square-post` — INSTALLED; posting blocked on a Square OpenAPI key
- `binance-leaderboard` — NOT installed (no proven use yet)
- `binance-agentic-wallet` — NOT installed; x402 stretch goal only
- Note: on Windows the skill CLIs need scripts/skillcall.mjs
  (docs/bug-report-windows-cli.md)

## Operational constraints (verified 2026-09-01)

- MCP tools are only callable inside a live Claude Code session (session OAuth).
  There is no cron and no unattended run. The Debrief is a command the Pilot
  runs, not a scheduled job.
- Market scanning reads public api.binance.com endpoints directly for
  payload-size reasons (the full-ticker response is 1.5MB and a scan is ~30
  calls); all authenticated actions — account state, order validation, order
  placement — go through the Binance MCP server. This line belongs in the
  README too. State it plainly, do not bury it.
- Fee baseline for Debrief fee-drag calculations: 0.1% maker, 0.1% taker,
  25% BNB discount available (verified via spot.orderTest with
  computeCommissionRates on BNBUSDT).

## Verified write surface

- Visible write tools: `spot_newOrder`, `spot_deleteOrder`, `spot_deleteOpenOrders`
- `tool_execute` is a write-capable proxy that reaches HIDDEN spot write tools
  not in the visible registry: `spot.orderCancelReplace`,
  `spot.orderAmendKeepPriority`, `spot.deleteOrderList`, `spot.orderOco`,
  `spot.orderListOco/Oto/Otoco/Opo/Opoco`, `spot.sorOrder`
- `spot.orderTest` and `spot.sorOrderTest` are VALIDATION ONLY and never reach
  the matching engine. These are our paper-trading mode.

## File layout

```
hansei/
  CLAUDE.md              <- this file
  README.md              <- judge-facing summary
  rulebook.md            <- lessons learned, injected into every decision packet
  prompts/
    decision-packet.md   <- how the Unit proposes a trade
    nightly-debrief.md   <- how the Unit reviews its own day
  logs/
    proposals.jsonl      <- every decided proposal (append-only)
    fills.jsonl          <- what actually executed
    suppressed.jsonl     <- R009/R010 pre-packet suppressions
    signals_discarded.jsonl <- R005/R006/R011 ingest discards
    tool_execute.jsonl   <- every tool_execute call (R004)
    autonomous-changes.jsonl <- one line per autonomous change
    scan-history.jsonl   <- per-scan throughput
    pending/ approved/   <- packets awaiting verdict / approved drafts
    scans/               <- raw scan results + summaries
    replay/              <- drill range: sessions, packets, decisions (never
                            mixed into live metrics)
  packets/               <- every rendered packet, verbatim (the artifact)
  debriefs/
    YYYY-MM-DD.md        <- one Debrief per day
    YYYY-MM-DD-square.md <- the short public version
  dashboard/             <- sync-rate.png (scripts/chart.py)
  docs/                  <- bug reports, pre-flight, optimization notes
  scripts/
    run.py               <- the loop: scan/pending/verdict/debrief/status/chart
    scan.py propose.py place.py audit.py ingest.py chart.py replay.py
    skillcall.mjs        <- Windows-safe runner for skill CLIs
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

Any log entry with `"test": true` is a synthetic pipeline test — no decision
packet, no Pilot verdict. It is excluded from Sync Rate and ALL Debrief metrics.

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
- ALL reports, summaries, test results and status output must be PLAIN TEXT.
  No tables. No box-drawing characters. No unicode borders. One fact per line
  in the form "LABEL: RESULT — detail". Terminal tables get truncated and
  become unreadable when pasted.
- **Pilot signal vs advisor directives.** Only entries in logs/proposals.jsonl
  with an actual verdict logged by the Pilot count as Pilot signal for Debrief
  Step 4. Rule changes and design directives — including those originating
  from the Pilot's AI advisor — are NOT Pilot verdicts and must never be
  inferred as trading preferences.

## Standing authority (granted by the Pilot, 2026-09-02)

The Unit may make and implement optimization decisions autonomously, without
asking first, WITHIN these limits:

ALLOWED without asking:
- Fixing correctness bugs (like the imbalance sign defect)
- Tuning thresholds that do not weaken a rule: volume floor, deep-scan cap,
  source trigger thresholds, scan cadence
- Improving evidence quality, thesis wording, packet rendering, logging
- Adding new READ-ONLY data sources from the MCP's 57 read tools
- Refactoring, error handling, performance
- Writing new bug reports for Binance
- Anything that makes the loop easier for a tired human to run

REQUIRES PILOT APPROVAL, always:
- Any new rule, or any change to an existing rule in rulebook.md
- Anything that LOOSENS a gate: lowering R009's 60% floor, weakening
  R005/R006 contract checks, relaxing R008 vetting, disabling R010 or R011
- Flipping MODE to LIVE
- Publishing anything to Binance Square
- Raising the stake above 20% of balance
- Deleting or editing any existing log entry
- Spending real funds in any way other than an approved packet

NEVER, regardless:
- Deciding a packet verdict. Verdicts are the Pilot's alone — Sync Rate
  measures the agent learning the PILOT's judgment, and an agent-supplied
  verdict would make the metric meaningless.
- Manufacturing proposals to fill the chart. A quiet tape producing zero
  packets is a correct output.

Every autonomous change gets a one-line entry in
logs/autonomous-changes.jsonl with what changed and why, so it is reviewable.

## FEATURE FREEZE (Pilot-declared 2026-09-02)

The trading logic is frozen as of 2026-09-02, after R015 (indicator vote),
the setup-specific checklists, and the BREAKOUT retest term shipped. From
this point: NO new indicators, setups, dimensions, or scoring changes
without the Pilot's explicit approval. Correctness bugs and crash fixes
only, logged in logs/autonomous-changes.jsonl as always.

## Build order (do not skip ahead)

1. [~] MCP connected + smoke-tested, 40 USDT funded; first live trade awaits
       a Pilot approval + MODE flip
2. [x] Decision packet generation + proposal logging
3. [x] Approve/reject capture with reason codes
4. [~] Nightly Debrief runs (first: debriefs/2026-09-01.md); rulebook diffs
       proposed through the Pilot
5. [ ] Square post publishing — blocked on a Square OpenAPI key (dry run done)
6. [x] Sync Rate chart + dashboard (scripts/chart.py)
7. [x] Replay mode v1 (scripts/replay.py — anonymised, outcome reveal)
8. [ ] Stretch: x402 paywall on the full Debrief (Base, USDC) — cut if behind

## What we claim, and what we don't

We claim: the Unit **learns**. Sync Rate rises. Repeated mistakes stop repeating.
Rule compliance improves. Trade count and fee drag fall.

We do not claim it makes money. Four days of market data proves nothing, and
public experiments have shown LLM traders mostly lose. The demo is about
behaviour change, not returns. Never write a headline that promises profit.
