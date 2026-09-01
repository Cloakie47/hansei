"""HANSEI order placement — PAPER/LIVE routing.

The Binance MCP tools are only callable from inside the Claude Code session
(session OAuth); this script cannot reach the network itself. It owns every
deterministic step and the session performs exactly one MCP call in between:

  1. python scripts/place.py prepare <proposal.json>
       -> prints one JSON object: {"mode", "tool", "wrapped_tool", "arguments"}
       Claude Code then calls that tool with those arguments, verbatim.
  2. python scripts/place.py record <proposal.json> <response.json>
       -> appends the fill to logs/fills.jsonl (always, both modes, with "mode")
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


def log_fill(proposal, call, response):
    entry = {
        "id": proposal["id"],
        "ts": now_iso(),
        "mode": call["mode"],
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
    fill logged. invoke is the session-side MCP caller."""
    call = build_call(proposal, read_mode())
    response = invoke(call["tool"], call["arguments"])
    return log_fill(proposal, call, response)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "prepare":
        proposal = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        print(json.dumps(build_call(proposal, read_mode()), indent=2))
    elif cmd == "record":
        proposal = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        response = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        entry = log_fill(proposal, build_call(proposal, read_mode()), response)
        print(json.dumps({"logged": entry["id"], "mode": entry["mode"]}, indent=2))
    else:
        print("usage: place.py prepare <proposal.json> | record <proposal.json> <response.json>")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
