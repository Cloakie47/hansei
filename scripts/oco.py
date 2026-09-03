"""Minimum resting-exit path: place a protective SELL OCO after a LIVE buy
fill so the position is guarded between scans. STRICT SCOPE (Pilot-approved
2026-09-03): compute legs, leg-test both sides, validate the price
relationship loudly, emit the tool_execute call for approval, log it, and
provide a cancel path. It NEVER places anything itself, exactly like
place.py: the session makes the MCP calls.

OUT OF SCOPE by decision: exchange-initiated-fill reconciliation. If the OCO
fires between sessions the Pilot logs it by hand from
docs/oco-manual-runbook.md. No partial-fill handling, no session-start
reconciliation here.

Flow (each MCP call is made by the session, not this script):
  1. python scripts/oco.py prepare <fill.json> <draft.json>
       computes sellable qty (fee-adjusted, lot-floored) and tick-rounded
       target/stop from the packet's own rr block; fetches last price
       (public); REFUSES loudly on target<=last<=stop inversion or a
       sub-minNotional leg; prints the two orderTest leg-test calls and,
       after them, the spot.orderListOco call. Emits, never places.
  2. session runs the two orderTest calls (validation only) and the
     orderListOco call (Binance prompts the Pilot to confirm).
  3. python scripts/oco.py record <draft.json> <oco_response.json>
       appends the placement to logs/resting_orders.jsonl.
  4. python scripts/oco.py cancel <SYMBOL> [--list-id ID | --client-id CID]
       emits the spot.deleteOrderList call (a resting OCO locks the
       quantity, so a manual exit must cancel it first).
"""

import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESTING_LOG = ROOT / "logs" / "resting_orders.jsonl"
SPOT_API = "https://api.binance.com/api/v3"


def _get(path):
    with urllib.request.urlopen(f"{SPOT_API}/{path}", timeout=20) as r:
        return json.loads(r.read().decode())


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _filters(symbol):
    s = _get(f"exchangeInfo?symbol={symbol}")["symbols"][0]
    f = {x["filterType"]: x for x in s["filters"]}
    return {"tick": float(f["PRICE_FILTER"]["tickSize"]),
            "step": float(f["LOT_SIZE"]["stepSize"]),
            "min_notional": float(f["NOTIONAL"]["minNotional"])}


def _floor_to(x, step):
    return math.floor(x / step) * step


def _round_tick(x, tick):
    # round toward a safe side happens at the call site; here nearest tick
    return round(round(x / tick) * tick, 8)


def sellable_qty(fill, step):
    """Base quantity actually sellable: executedQty minus fee IF the fee was
    paid in the base asset, floored to the lot step. Never rounds up."""
    executed = float(fill["response"]["executedQty"])
    base = fill["symbol"].replace("USDT", "")
    comm_asset = fill["response"].get("commissionAsset")
    comm = 0.0
    for fl in fill["response"].get("fills", []) or []:
        if fl.get("commissionAsset") == base:
            comm += float(fl.get("commission", 0))
    if comm == 0 and comm_asset == base:
        comm = float(fill["response"].get("commission", 0))
    net = executed - comm
    return round(_floor_to(net, step), 8)


def build(fill, draft):
    symbol = fill["symbol"]
    rr = draft.get("rr") or {}
    if "target" not in rr or "stop" not in rr:
        raise SystemExit("REFUSED: draft has no rr.target/rr.stop to build legs from.")
    filt = _filters(symbol)
    last = float(_get(f"ticker/price?symbol={symbol}")["price"])
    qty = sellable_qty(fill, filt["step"])
    # target rounds DOWN to a tick (stay reachable), stop rounds DOWN too
    # (trigger slightly earlier, never later); stop limit a tick below stop.
    target = _round_tick(rr["target"] - filt["tick"] / 2, filt["tick"])
    stop = _round_tick(rr["stop"] - filt["tick"] / 2, filt["tick"])
    stop_limit = _round_tick(stop * 0.997, filt["tick"])

    # LOUD validation: target > last > stop. Refuse on inversion, never fix.
    problems = []
    if not (target > last):
        problems.append(f"target {target} is not ABOVE last {last} (LIMIT_MAKER would cross)")
    if not (stop < last):
        problems.append(f"stop {stop} is not BELOW last {last}")
    if not (target > stop):
        problems.append(f"target {target} <= stop {stop} (inverted)")
    if qty <= 0:
        problems.append(f"sellable qty {qty} <= 0")
    for leg, price in (("target", target), ("stop", stop)):
        if qty * price < filt["min_notional"]:
            problems.append(f"{leg} leg notional {qty*price:.2f} < min {filt['min_notional']}")
    if problems:
        raise SystemExit("REFUSED (no correction applied):\n  - " + "\n  - ".join(problems))

    cid = f"{draft.get('id', fill.get('id', 'oco'))}-oco"
    legtests = [
        {"toolName": "spot.orderTest", "arguments": {
            "symbol": symbol, "side": "SELL", "type": "LIMIT_MAKER",
            "quantity": qty, "price": target}},
        {"toolName": "spot.orderTest", "arguments": {
            "symbol": symbol, "side": "SELL", "type": "STOP_LOSS_LIMIT",
            "quantity": qty, "stopPrice": stop, "price": stop_limit,
            "timeInForce": "GTC"}},
    ]
    oco = {"toolName": "spot.orderListOco", "arguments": {
        "symbol": symbol, "side": "SELL", "quantity": qty,
        "aboveType": "LIMIT_MAKER", "abovePrice": target,
        "belowType": "STOP_LOSS_LIMIT", "belowStopPrice": stop,
        "belowPrice": stop_limit, "belowTimeInForce": "GTC",
        "listClientOrderId": cid}}
    return {"symbol": symbol, "last": last, "qty": qty, "target": target,
            "stop": stop, "stop_limit": stop_limit, "client_id": cid,
            "legtests": legtests, "oco_call": oco}


def cmd_prepare(argv):
    fill = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    draft = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    b = build(fill, draft)
    print(f"RESTING OCO for {b['symbol']}: sell {b['qty']} at target {b['target']} "
          f"/ stop {b['stop']} (last {b['last']}); relationship stop < last < target OK.")
    print("\nSTEP 1 - leg-test BOTH sides (validation only, never reaches the engine):")
    for lt in b["legtests"]:
        print("  tool_execute " + json.dumps(lt))
    print("\nSTEP 2 - only if BOTH legs return {} (or commission info), place the OCO "
          "(Binance will prompt you to confirm):")
    print("  tool_execute " + json.dumps(b["oco_call"]))
    print(f"\nSTEP 3 - record it: python scripts/oco.py record {argv[1]} <oco_response.json>")
    return 0


def cmd_record(argv):
    draft = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    resp = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    entry = {"ts": now_iso(), "kind": "resting-oco", "symbol": draft["symbol"],
             "client_id": f"{draft.get('id', 'oco')}-oco",
             "target": (draft.get("rr") or {}).get("target"),
             "stop": (draft.get("rr") or {}).get("stop"),
             "order_list_id": resp.get("orderListId"), "response": resp}
    with open(RESTING_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ": "), ensure_ascii=False) + "\n")
    print(f"logged resting OCO for {entry['symbol']} to {RESTING_LOG}")
    return 0


def open_oco_for(symbol):
    """Most recent logged resting OCO for a symbol that has not been logged
    cancelled. Used by the exit flow to cancel-first."""
    if not RESTING_LOG.exists():
        return None
    live = None
    for line in RESTING_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e["symbol"] != symbol:
            continue
        if e.get("kind") == "resting-oco":
            live = e
        elif e.get("kind") == "oco-cancelled":
            live = None
    return live


def cmd_cancel(argv):
    symbol = argv[0].upper()
    list_id = argv[argv.index("--list-id") + 1] if "--list-id" in argv else None
    client_id = argv[argv.index("--client-id") + 1] if "--client-id" in argv else None
    if not (list_id or client_id):
        prev = open_oco_for(symbol)
        if prev:
            list_id = prev.get("order_list_id")
            client_id = prev.get("client_id")
        if not (list_id or client_id):
            print(f"no open resting OCO logged for {symbol}; pass --list-id or --client-id")
            return 1
    args = {"symbol": symbol}
    if list_id is not None:
        args["orderListId"] = list_id
    else:
        args["listClientOrderId"] = client_id
    print("A resting OCO locks the position quantity. Cancel it BEFORE a manual "
          "sell, or the sell is rejected for insufficient balance.")
    print("  tool_execute " + json.dumps({"toolName": "spot.deleteOrderList", "arguments": args}))
    print(f"\nAfter it confirms, record the cancel: "
          f"python scripts/oco.py record-cancel {symbol} {list_id or client_id}")
    return 0


def cmd_record_cancel(argv):
    symbol = argv[0].upper()
    ident = argv[1]
    with open(RESTING_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now_iso(), "kind": "oco-cancelled",
                            "symbol": symbol, "ident": ident},
                           separators=(",", ": ")) + "\n")
    print(f"logged cancel of resting OCO for {symbol}")
    return 0


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "prepare":
        return cmd_prepare(argv[2:])
    if cmd == "record":
        return cmd_record(argv[2:])
    if cmd == "cancel":
        return cmd_cancel(argv[2:])
    if cmd == "record-cancel":
        return cmd_record_cancel(argv[2:])
    print("usage: oco.py prepare <fill.json> <draft.json> | record <draft.json> "
          "<oco_response.json> | cancel <SYMBOL> [--list-id ID|--client-id CID] | "
          "record-cancel <SYMBOL> <ID>")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
