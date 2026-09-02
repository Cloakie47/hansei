"""HANSEI order placement — PAPER/LIVE routing.

The Binance MCP tools are only callable from inside the Claude Code session
(session OAuth); this script cannot reach the network itself. It owns every
deterministic step and the session performs exactly one MCP call in between:

  0. Claude Code calls spot_getAccount and saves the response to account.json.
  1. python scripts/place.py prepare <proposal.json> <account.json>
       -> runs the affordability pre-flight (R001: max 20% of USDT balance per
          position) BEFORE emitting any tool call, in both modes. A violation
          raises and nothing is emitted. Balance 0 -> AFFORDABILITY: SKIPPED
          (orderTest cannot check balance, so the entry is marked instead).
       -> prints one JSON object: {"mode", "tool", "wrapped_tool", "arguments",
          "affordability"}. Claude Code then calls that tool verbatim.
  2. python scripts/place.py record <proposal.json> <account.json> <response.json>
       -> appends the fill to logs/fills.jsonl (always, both modes, with "mode"
          and "affordability")
       -> appends to logs/tool_execute.jsonl whenever the call went through
          tool_execute, with the wrapped toolName (R004)

Routing — the ONLY difference between modes:
  MODE=PAPER -> tool_execute wrapping spot.orderTest  (validation only,
                never reaches the matching engine)
  MODE=LIVE  -> spot_newOrder
MODE comes from .env at the repo root. Missing file or missing key means
PAPER. Nothing ever defaults to LIVE.

place(proposal, invoke) is the single in-process entry point; the CLI
subcommands exist so the MCP call can happen outside this process.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
FILLS_LOG = ROOT / "logs" / "fills.jsonl"
TOOL_EXECUTE_LOG = ROOT / "logs" / "tool_execute.jsonl"

PAPER_TOOL = "tool_execute"
PAPER_WRAPPED = "spot.orderTest"
LIVE_TOOL = "spot_newOrder"

# The only tools this module may emit when MODE is not LIVE. Validation-only:
# neither ever reaches the matching engine.
PAPER_SAFE_TOOLS = {"spot.orderTest", "spot.sorOrderTest"}


def assert_paper_safe(call):
    """If MODE is not LIVE, the resolved tool must be a validation-only test
    order. Anything else is a routing bug — raise and call nothing (R004)."""
    if call["mode"] == "LIVE":
        return
    resolved = (call["arguments"].get("toolName")
                if call["tool"] == "tool_execute" else call["tool"])
    if resolved not in PAPER_SAFE_TOOLS:
        raise RuntimeError(
            f"MODE ROUTER BUG: mode={call['mode']} resolved to tool "
            f"'{resolved}', which is not validation-only "
            f"({sorted(PAPER_SAFE_TOOLS)}). Refusing to call anything.")


def read_mode():
    """MODE from .env. Anything other than an explicit LIVE is PAPER."""
    mode = "PAPER"
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("MODE="):
                mode = line.split("=", 1)[1].strip().upper()
    if mode != "LIVE":
        mode = "PAPER"
    return mode


R001_MAX_FRACTION = 0.20
# Hard floor: Binance spot min notional is 5 USDT; we never propose below 6
# to leave headroom for price movement between draft and fill.
MIN_STAKE_USDT = 6.0


def default_stake(usdt_balance):
    """Stake derives from live balance: 20% of balance (R001 ceiling).
    Refuses when 20% of balance is under the 6 USDT floor — there is no
    'small but compliant' size below it."""
    stake = round(R001_MAX_FRACTION * usdt_balance, 2)
    if stake < MIN_STAKE_USDT:
        raise RuntimeError(
            f"stake refused: 20% of balance ({stake:.2f} USDT) is below the "
            f"{MIN_STAKE_USDT:.0f} USDT floor. Balance must be >= "
            f"{MIN_STAKE_USDT / R001_MAX_FRACTION:.0f} USDT to propose at all.")
    return stake


def proposal_notional_usdt(proposal):
    if proposal["type"] == "LIMIT":
        return proposal["price"] * proposal["quantity"]
    if "quoteOrderQty" in proposal:
        return proposal["quoteOrderQty"]
    return None


def _account_free_usdt(acct):
    for bal in acct.get("balances", []):
        if bal.get("asset") == "USDT":
            return float(bal.get("free", 0))
    return 0.0


def _account_holds_non_usdt(acct):
    return any(bal.get("asset") != "USDT" and
               (float(bal.get("free", 0)) or float(bal.get("locked", 0)))
               for bal in acct.get("balances", []))


def _wallet_spot_balance(wallet_summary):
    for w in wallet_summary or []:
        if w.get("walletName") == "Spot":
            return float(w.get("balance", 0))
    return 0.0


def last_live_fill_ms():
    latest = 0
    if FILLS_LOG.exists():
        from datetime import datetime, timezone
        for line in FILLS_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            f = json.loads(line)
            if f.get("mode") == "LIVE":
                ts = datetime.strptime(f["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                latest = max(latest, int(ts.timestamp() * 1000))
    return latest


def resolve_balance(ctx):
    """Trustworthy free USDT, or a refusal. Never guesses.

    ctx is either the legacy spot_getAccount dict ({"balances": [...]}) or a
    combined context: {"spot_account": <spot_getAccount>, "wallet_summary":
    <wallet_queryUserWalletBalance quoteAsset=USDT>, "last_flow_ms": <ms of
    most recent known deposit/withdrawal>, "deposits_only_usdt": bool}.

    Path 1: spot_getAccount free USDT, ONLY when its updateTime is at least
    as fresh as every known balance flow (supplied deposits plus LIVE fills
    recorded locally). spot_getAccount has been observed serving a stale
    cached snapshot after a deposit (docs/bug-report-stale-getaccount.md).
    Path 2: wallet-summary Spot valuation, ONLY while nothing but USDT is
    held (no non-USDT asset in the account snapshot, no LIVE fill recorded,
    and the caller attests deposits were USDT-only) — the valuation equals
    free USDT only under that assumption.
    Otherwise: raise. A trade must never be sized against a guess."""
    if isinstance(ctx, dict) and "spot_account" in ctx:
        acct = ctx["spot_account"]
        wallet = ctx.get("wallet_summary")
        known_flow = max(int(ctx.get("last_flow_ms") or 0), last_live_fill_ms())
        update_time = int(acct.get("updateTime") or 0)
        if update_time >= known_flow:
            return {"usdt_free": _account_free_usdt(acct),
                    "path": "spot_getAccount(fresh)",
                    "detail": f"updateTime {update_time} >= last known flow {known_flow}"}
        non_usdt = _account_holds_non_usdt(acct) or last_live_fill_ms() > 0
        if wallet is not None and not non_usdt and ctx.get("deposits_only_usdt") is True:
            return {"usdt_free": _wallet_spot_balance(wallet),
                    "path": "wallet_summary(usdt-only)",
                    "detail": (f"spot_getAccount stale (updateTime {update_time} < "
                               f"flow {known_flow}); wallet Spot valuation trusted — "
                               f"no non-USDT holdings, no LIVE fills, deposits USDT-only")}
        raise RuntimeError(
            "cannot establish trustworthy free USDT: spot_getAccount is stale "
            f"(updateTime {update_time} < last known flow {known_flow}) and the "
            "wallet-summary fallback is invalid "
            f"({'non-USDT assets are held' if non_usdt else 'wallet summary missing or deposits not attested USDT-only'}). "
            "Refusing to size a trade against a guess.")
    if isinstance(ctx, dict) and "balances" in ctx:
        # Legacy spot_getAccount dict with no flow context: the only known
        # flows are local LIVE fills; getAccount must be at least that fresh.
        known_flow = last_live_fill_ms()
        update_time = int(ctx.get("updateTime") or 0)
        if update_time >= known_flow:
            return {"usdt_free": _account_free_usdt(ctx),
                    "path": "spot_getAccount(legacy)",
                    "detail": "no external flow context supplied"}
        raise RuntimeError(
            "cannot establish trustworthy free USDT: legacy account snapshot "
            f"(updateTime {update_time}) is older than the last LIVE fill "
            f"({known_flow}). Refusing to size a trade against a guess.")
    raise RuntimeError(
        "cannot establish trustworthy free USDT: unrecognised balance context "
        f"({type(ctx).__name__}). A bare wallet summary is never sufficient. "
        "Refusing to size a trade against a guess.")


def usdt_free(account):
    """Back-compat wrapper: trustworthy balance or raise (see resolve_balance)."""
    return resolve_balance(account)["usdt_free"]


def affordability_check(proposal, account):
    """R001 pre-flight, enforced before any tool call in both modes.
    Raises on violation. Balance 0 returns SKIPPED (not a failure) so paper
    fills against an unfunded account are visibly marked in the log."""
    if proposal.get("exit"):
        # Closing a position needs no USDT and reduces exposure; the sizing
        # cap does not apply. Distinct status so checkers report it honestly.
        return {"status": "EXIT", "balance_source": "n/a (exit)",
                "note": "exit reduces exposure — R001 sizing cap not applicable"}
    src = resolve_balance(account)  # raises when no trustworthy figure exists
    balance = src["usdt_free"]
    if balance == 0:
        return {"status": "SKIPPED", "usdt_free": 0.0,
                "balance_source": src["path"],
                "note": "balance 0 — R001 not enforceable, orderTest does not check balance"}
    notional = proposal_notional_usdt(proposal)
    if notional is None:
        raise RuntimeError(
            "cannot compute USDT notional for this proposal (MARKET by base "
            "quantity); refuse to place without a checkable notional (R001)")
    if notional < MIN_STAKE_USDT:
        raise RuntimeError(
            f"stake floor violation: notional {notional:.2f} USDT is below the "
            f"{MIN_STAKE_USDT:.0f} USDT floor (exchange min 5 + headroom). "
            f"Refusing to call anything.")
    limit = R001_MAX_FRACTION * balance
    if notional > limit:
        raise RuntimeError(
            f"R001 violation: notional {notional:.2f} USDT exceeds 20% of "
            f"balance ({limit:.2f} of {balance:.2f}). Refusing to call anything.")
    return {"status": "OK", "usdt_free": balance, "notional_usdt": notional,
            "fraction_of_balance": round(notional / balance, 4),
            "balance_source": src["path"]}


def build_order_args(proposal):
    """Identical order arguments for both modes."""
    args = {
        "symbol": proposal["symbol"],
        "side": proposal["side"],
        "type": proposal["type"],
        "newClientOrderId": proposal["id"],
        "newOrderRespType": "FULL",
    }
    if proposal["type"] == "LIMIT":
        args["timeInForce"] = proposal.get("timeInForce", "GTC")
        args["price"] = proposal["price"]
        args["quantity"] = proposal["quantity"]
    elif proposal["type"] == "MARKET":
        if "quoteOrderQty" in proposal:
            args["quoteOrderQty"] = proposal["quoteOrderQty"]
        else:
            args["quantity"] = proposal["quantity"]
    else:
        raise ValueError(f"unsupported order type: {proposal['type']}")
    return args


def build_call(proposal, mode):
    """Route to the tool for this mode. The only mode-dependent code path."""
    order_args = build_order_args(proposal)
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


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, separators=(",", ": "), ensure_ascii=False) + "\n")


def log_fill(proposal, call, response, affordability=None, test=False):
    entry = {
        "id": proposal["id"],
        "ts": now_iso(),
        "mode": call["mode"],
        "affordability": affordability,
        "symbol": proposal["symbol"],
        "side": proposal["side"],
        "type": proposal["type"],
        "tool": call["tool"],
        "wrapped_tool": call["wrapped_tool"],
        "request": call["arguments"],
        "response": response,
    }
    if test:
        entry["test"] = True  # pipeline drill — excluded from all metrics
    append_jsonl(FILLS_LOG, entry)
    if call["tool"] == "tool_execute":
        append_jsonl(TOOL_EXECUTE_LOG, {
            "ts": entry["ts"],
            "toolName": call["wrapped_tool"],
            "context": f"order placement for {proposal['id']} in {call['mode']} mode",
        })
    return entry


def freshness_check(spot_account, wallet_summary, tolerance=0.01):
    """Startup check: spot_getAccount vs wallet_queryUserWalletBalance
    (quoteAsset=USDT) on USDT. Returns (ok, message); a disagreement gets a
    loud warning — see docs/bug-report-stale-getaccount.md."""
    acct_usdt = _account_free_usdt(spot_account)
    wallet_usdt = _wallet_spot_balance(wallet_summary)
    update_time = int(spot_account.get("updateTime") or 0)
    if abs(acct_usdt - wallet_usdt) <= tolerance:
        return True, (f"balance freshness OK: spot_getAccount USDT {acct_usdt} agrees "
                      f"with wallet summary {wallet_usdt} (updateTime {update_time})")
    return False, (
        "\n" + "!" * 72 +
        f"\n!! BALANCE FRESHNESS WARNING — sources disagree on USDT"
        f"\n!! spot_getAccount free USDT : {acct_usdt} (updateTime {update_time})"
        f"\n!! wallet summary Spot USDT  : {wallet_usdt}"
        f"\n!! spot_getAccount is likely serving a stale snapshot"
        f"\n!! (docs/bug-report-stale-getaccount.md). Do NOT size trades from"
        f"\n!! spot_getAccount until it reflects the latest deposit/fill."
        "\n" + "!" * 72)


def place(proposal, invoke):
    """Single entry point: proposal in, order placed via invoke(tool, args),
    fill logged. invoke is the session-side MCP caller. The affordability
    pre-flight runs before the order call in both modes."""
    account = invoke("spot_getAccount", {"omitZeroBalances": True})
    affordability = affordability_check(proposal, account)  # raises on R001
    call = build_call(proposal, read_mode())
    response = invoke(call["tool"], call["arguments"])
    return log_fill(proposal, call, response, affordability)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "prepare":
        proposal = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        account = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        affordability = affordability_check(proposal, account)  # raises on R001
        call = build_call(proposal, read_mode())
        call["affordability"] = affordability
        print(json.dumps(call, indent=2))
    elif cmd == "record":
        test = "--test" in argv
        args = [a for a in argv if a != "--test"]
        proposal = json.loads(Path(args[2]).read_text(encoding="utf-8"))
        account = json.loads(Path(args[3]).read_text(encoding="utf-8"))
        response = json.loads(Path(args[4]).read_text(encoding="utf-8"))
        affordability = affordability_check(proposal, account)
        entry = log_fill(proposal, build_call(proposal, read_mode()), response,
                         affordability, test=test)
        print(json.dumps({"logged": entry["id"], "mode": entry["mode"],
                          "affordability": affordability["status"]}, indent=2))
    elif cmd == "freshness":
        ctx = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        ok, msg = freshness_check(ctx["spot_account"], ctx.get("wallet_summary"))
        print(msg)
        return 0 if ok else 4
    elif cmd == "stake":
        account = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        balance = usdt_free(account)
        stake = default_stake(balance)  # raises below the floor
        print(json.dumps({"usdt_free": balance, "stake_usdt": stake,
                          "fraction": R001_MAX_FRACTION, "floor_usdt": MIN_STAKE_USDT}))
    else:
        print("usage: place.py prepare <proposal.json> <account.json> | "
              "record <proposal.json> <account.json> <response.json> | "
              "stake <account.json>")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
