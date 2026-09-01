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


def proposal_notional_usdt(proposal):
    if proposal["type"] == "LIMIT":
        return proposal["price"] * proposal["quantity"]
    if "quoteOrderQty" in proposal:
        return proposal["quoteOrderQty"]
    return None


def usdt_free(account):
    for bal in account.get("balances", []):
        if bal.get("asset") == "USDT":
            return float(bal.get("free", 0))
    return 0.0


def affordability_check(proposal, account):
    """R001 pre-flight, enforced before any tool call in both modes.
    Raises on violation. Balance 0 returns SKIPPED (not a failure) so paper
    fills against an unfunded account are visibly marked in the log."""
    balance = usdt_free(account)
    if balance == 0:
        return {"status": "SKIPPED", "usdt_free": 0.0,
                "note": "balance 0 — R001 not enforceable, orderTest does not check balance"}
    notional = proposal_notional_usdt(proposal)
    if notional is None:
        raise RuntimeError(
            "cannot compute USDT notional for this proposal (MARKET by base "
            "quantity); refuse to place without a checkable notional (R001)")
    limit = R001_MAX_FRACTION * balance
    if notional > limit:
        raise RuntimeError(
            f"R001 violation: notional {notional:.2f} USDT exceeds 20% of "
            f"balance ({limit:.2f} of {balance:.2f}). Refusing to call anything.")
    return {"status": "OK", "usdt_free": balance, "notional_usdt": notional,
            "fraction_of_balance": round(notional / balance, 4)}


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


def log_fill(proposal, call, response, affordability=None):
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
    append_jsonl(FILLS_LOG, entry)
    if call["tool"] == "tool_execute":
        append_jsonl(TOOL_EXECUTE_LOG, {
            "ts": entry["ts"],
            "toolName": call["wrapped_tool"],
            "context": f"order placement for {proposal['id']} in {call['mode']} mode",
        })
    return entry


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
        proposal = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        account = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        response = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
        affordability = affordability_check(proposal, account)
        entry = log_fill(proposal, build_call(proposal, read_mode()), response, affordability)
        print(json.dumps({"logged": entry["id"], "mode": entry["mode"],
                          "affordability": affordability["status"]}, indent=2))
    else:
        print("usage: place.py prepare <proposal.json> <account.json> | "
              "record <proposal.json> <account.json> <response.json>")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
