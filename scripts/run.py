"""HANSEI loop entry point — five commands so a tired human at 1am can run
the loop without thinking:

  run.py scan     freshness check, scan, generate packets, print file paths
  run.py pending  list undecided packets (id, symbol, side, confidence)
  run.py verdict <id> <y|n> [reason_code]   log the verdict, nothing else
  run.py debrief [--date YYYY-MM-DD] [--out-dir D]   compute + write both files
  run.py status   sync rate with denominator, decided count, open packets

MCP split: where a step needs an authenticated call, this prints the EXACT
tool call to make and accepts the response back as a file — the same
prepare/record split place.py uses. Everything else is local.

Balance context: run.py scan needs logs/balance-ctx.json. If it is missing
or stale the command prints the three MCP calls to make and the `run.py
balance` command that assembles their responses into the context file.

Mechanical confidence (v1, documented so calibration can judge it): a draft's
confidence is set purely by how many structurally independent sources
triggered — 1 source: 0.50, 2: 0.57, 3: 0.62. No hand-tuning per candidate.
R009 then suppresses anything under 0.60, so only multi-source confluence
reaches the Pilot. If the calibration buckets later show 62% is wrong, the
mapping changes in ONE place here and the change is visible in git.
"""

import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import place
import propose
import scan as scanmod

ROOT = HERE.parent
BALANCE_CTX = ROOT / "logs" / "balance-ctx.json"
BALANCE_MAX_AGE_S = 30 * 60
SCAN_HISTORY = ROOT / "logs" / "scan-history.jsonl"

MECH_CONFIDENCE = {1: 0.50, 2: 0.57, 3: 0.62}

BALANCE_INSTRUCTIONS = """\
BALANCE CONTEXT NEEDED — make these three MCP calls and save each response:

  1. spot_getAccount            arguments: {"omitZeroBalances": true}   -> spot.json
  2. wallet_queryUserWalletBalance  arguments: {"quoteAsset": "USDT"}   -> wallet.json
  3. wallet_depositHistory      arguments: {}                           -> deposits.json

then assemble the context:

  python scripts/run.py balance spot.json wallet.json deposits.json

and re-run: python scripts/run.py scan
"""


def now_utc_date():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def cmd_balance(args):
    spot = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    wallet = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    deposits = json.loads(Path(args[2]).read_text(encoding="utf-8")) if len(args) > 2 else []
    last_flow = max((int(d.get("insertTime", 0)) for d in deposits), default=0)
    only_usdt = all(d.get("coin") == "USDT" for d in deposits) if deposits else False
    ctx = {"fetched_at": int(time.time() * 1000), "spot_account": spot,
           "wallet_summary": wallet, "last_flow_ms": last_flow,
           "deposits_only_usdt": only_usdt}
    BALANCE_CTX.write_text(json.dumps(ctx, indent=2, ensure_ascii=False), encoding="utf-8")
    ok, msg = place.freshness_check(spot, wallet)
    print(f"balance context written: {BALANCE_CTX}")
    print(msg)
    return 0


def load_balance_ctx():
    if not BALANCE_CTX.exists():
        return None, "no balance context"
    ctx = json.loads(BALANCE_CTX.read_text(encoding="utf-8"))
    age = time.time() - ctx.get("fetched_at", 0) / 1000
    if age > BALANCE_MAX_AGE_S:
        return None, f"balance context is {age/60:.0f} minutes old (max {BALANCE_MAX_AGE_S//60})"
    return ctx, None


def mechanical_draft(cand, stake):
    trig = {s: t for s, t in cand["triggers"].items()
            if t and not (s == "C" and t == ["wide-spread"])}
    n = len(trig)
    conf = MECH_CONFIDENCE.get(n, 0.50)
    parts = "; ".join(f"{s}:{'+'.join(t)}" for s, t in sorted(trig.items()))
    return {
        "symbol": cand["symbol"], "side": "BUY", "type": "MARKET",
        "quoteOrderQty": stake, "confidence": conf,
        "evidence": cand["evidence"],
        "signals_used": ["spot_ticker24hr(all-pairs)", "spot_klines", "spot_depth"],
        "thesis": (f"{cand['symbol']} moved {cand['chg_pct']:+.2f}% in 24h with "
                   f"{n} independent source(s) triggering ({parts}). Mechanical "
                   f"draft v1 — confidence is the source count mapping, see run.py."),
        "invalidation": ("The triggering excursion reversing: 24h change sign flip, "
                         "volume ratio back under 1x its 7d average, or the book "
                         "imbalance crossing back through 1.0 — whichever fired."),
        "size_reasoning": (f"{stake} USDT = 20% of live balance (R001 ceiling, "
                           f"6 USDT floor) via place.default_stake."),
    }


def cmd_scan():
    ctx, err = load_balance_ctx()
    if ctx is None:
        print(f"CANNOT SCAN: {err}.")
        print(BALANCE_INSTRUCTIONS)
        return 3
    ok, msg = place.freshness_check(ctx["spot_account"], ctx.get("wallet_summary"))
    print(msg)
    balance = place.resolve_balance(ctx)
    stake = place.default_stake(balance["usdt_free"])  # raises below floor
    print(f"balance {balance['usdt_free']:.2f} USDT via {balance['path']} -> stake {stake:.2f} USDT")

    result = scanmod.scan()
    print(f"pairs past floor: {result['pairs_past_floor']} | deep: {result['scanned_deep']} "
          f"| packet-worthy: {len(result['packet_worthy'])}")
    packets, skipped = [], []
    for cand in result["candidates"]:
        if not cand["packet_worthy"]:
            continue
        draft = mechanical_draft(cand, stake)
        pid, text, checks = propose.build_packet(draft, {}, ctx)
        if pid:
            propose.save_pending(pid, draft, checks)
            path = propose.save_packet_text(pid, text)
            packets.append(str(path))
        else:
            skipped.append(text.split(".")[0])
    for s in skipped:
        print(f"  {s}")
    place.append_jsonl(SCAN_HISTORY, {
        "ts": place.now_iso(),
        "pairs_past_floor": result["pairs_past_floor"],
        "scanned_deep": result["scanned_deep"],
        "packet_worthy": len(result["packet_worthy"]),
        "packets": len(packets),
        "suppressed": len(skipped),
    })
    if packets:
        print("PACKETS GENERATED:")
        for p in packets:
            print(f"  {p}")
    else:
        print("NO PACKETS — if nothing else clears the bar today, log it:")
        print('  python scripts/propose.py no-proposal "<reason>"')
    return 0


def undecided():
    out = []
    for p in sorted(propose.PENDING_DIR.glob("p-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out.append({"id": d["id"], "symbol": d["draft"]["symbol"],
                    "side": d["draft"]["side"], "confidence": d["draft"]["confidence"]})
    return out


def cmd_pending():
    rows = undecided()
    if not rows:
        print("no pending packets")
        return 0
    for r in rows:
        print(f"{r['id']}  {r['symbol']}  {r['side']}  confidence {r['confidence']:.0%}")
    return 0


def cmd_verdict(args):
    test = "--test" in args
    args = [a for a in args if a != "--test"]
    pid, yn = args[0], args[1].lower()
    if yn not in ("y", "n"):
        print("verdict must be y or n")
        return 1
    verdict = "APPROVED" if yn == "y" else "REJECTED"
    reason = args[2].upper() if len(args) > 2 else None
    entry = propose.record_verdict(pid, verdict, reason, test=test)
    print(f"logged: {entry['id']} {entry['verdict']}"
          + (f" ({entry['reject_reason']})" if entry.get("reject_reason") else ""))
    return 0


def decided(proposals):
    return [p for p in proposals if p.get("verdict") in ("APPROVED", "REJECTED", "NO_PROPOSAL")]


def cmd_status():
    proposals = [p for p in propose.load_proposals(include_test=False)]
    dec = decided(proposals)
    approved = sum(1 for p in dec if p["verdict"] == "APPROVED")
    today = now_utc_date()
    dec_today = [p for p in dec if p["ts"][:10] == today]
    app_today = sum(1 for p in dec_today if p["verdict"] == "APPROVED")
    print(f"sync rate (all time): {100*approved/len(dec):.0f}% ({approved} of {len(dec)})"
          if dec else "sync rate (all time): no decided proposals")
    print(f"sync rate (today {today} UTC): "
          + (f"{100*app_today/len(dec_today):.0f}% ({app_today} of {len(dec_today)})"
             if dec_today else "no decided proposals yet"))
    print(f"decided proposals: {len(dec)} total")
    rows = undecided()
    print(f"open packets: {len(rows)}")
    for r in rows:
        print(f"  {r['id']}  {r['symbol']}  {r['side']}  {r['confidence']:.0%}")
    if SCAN_HISTORY.exists():
        hist = [json.loads(l) for l in SCAN_HISTORY.read_text(encoding="utf-8").splitlines()
                if l.strip()][-5:]
        counts = [h["packets"] for h in hist]
        print(f"packets per scan (last {len(counts)}): {', '.join(str(c) for c in counts)}")
        if len(counts) >= 2 and counts[-1] == 0 and counts[-2] == 0:
            print("NOTE: tape is quiet — two consecutive zero-packet scans. "
                  "Not an error; no idea clearing the bar is a valid output.")
    else:
        print("packets per scan: no scan history yet")
    mode = place.read_mode()
    print(f"MODE: {mode}")
    return 0


def cmd_debrief(args):
    date = args[args.index("--date") + 1] if "--date" in args else now_utc_date()
    out_dir = Path(args[args.index("--out-dir") + 1]) if "--out-dir" in args else ROOT / "debriefs"
    full_path = out_dir / f"{date}.md"
    square_path = out_dir / f"{date}-square.md"
    if full_path.exists():
        print(f"REFUSING: {full_path} already exists (append-only). "
              f"Use --date or --out-dir for a rerun.")
        return 2

    proposals = propose.load_proposals(include_test=False)
    day = [p for p in proposals if p["ts"][:10] == date]
    dec = decided(day)
    approved = [p for p in dec if p["verdict"] == "APPROVED"]
    rejected = [p for p in dec if p["verdict"] == "REJECTED"]
    all_dec = decided(proposals)
    reasons = defaultdict(int)
    for p in rejected:
        reasons[p.get("reject_reason") or "?"] += 1
    fills = []
    if place.FILLS_LOG.exists():
        fills = [json.loads(l) for l in place.FILLS_LOG.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
        fills = [f for f in fills if f.get("test") is not True and f["ts"][:10] == date]
    suppressed = []
    sup_log = ROOT / "logs" / "suppressed.jsonl"
    if sup_log.exists():
        suppressed = [json.loads(l) for l in sup_log.read_text(encoding="utf-8").splitlines()
                      if l.strip()]
        suppressed = [s for s in suppressed if s.get("test") is not True and s["ts"][:10] == date]
    confid = [p["confidence"] for p in day if p.get("confidence") is not None]
    buys = [p for p in day if p.get("side") == "BUY"]
    directional = [p for p in day if p.get("side")]

    def rate(a, d):
        return f"{100*len(a)/len(d):.0f}% ({len(a)} of {len(d)})" if d else "n/a (0 decided)"

    lines = [
        f"# Debrief — {date} (generated by run.py debrief; analysis sections need the Unit)",
        "",
        "## Step 1 — The numbers (computed)",
        f"- Sync Rate today: {rate(approved, dec)}. NO_PROPOSAL counts in the denominator.",
        f"- Sync Rate all-time: {rate([p for p in all_dec if p['verdict']=='APPROVED'], all_dec)}",
        f"- Decided today: {len(dec)} (approved {len(approved)}, rejected {len(rejected)}, "
        f"no-proposal {sum(1 for p in dec if p['verdict']=='NO_PROPOSAL')})",
        f"- Rejections by code: {dict(reasons) if reasons else 'none'}",
        f"- Fills today: {len(fills)} | notional "
        f"{sum(propose.place.proposal_notional_usdt(f.get('request', {}).get('arguments', f.get('request', {}))) or 0 for f in fills):.2f} USDT"
        if fills else "- Fills today: 0 | notional 0 USDT | fees 0 USDT — no P&L, stated not omitted",
        f"- Suppressions today: {len(suppressed)} "
        f"(R009: {sum(1 for s in suppressed if s['rule']=='R009')}, "
        f"R010: {sum(1 for s in suppressed if s['rule']=='R010')})",
        f"- Calibration: {len([p for p in all_dec if p.get('confidence')])} decided packets with "
        "confidence all-time — too few to bucket honestly" if
        len([p for p in all_dec if p.get('confidence')]) < 10 else
        "- Calibration: see buckets below",
        "- Rule compliance: violations must be counted by the Unit against packets/",
        "",
        "## Step 2 — What went wrong  [UNIT ANALYSIS REQUIRED — two worst decisions]",
        "",
        "## Step 3 — Bias check (computed where possible)",
        f"- Directional: {len(buys)} of {len(directional)} directional proposals were BUY"
        if directional else "- Directional: no directional proposals today",
        f"- Mean confidence today: {sum(confid)/len(confid):.0%} (n={len(confid)})"
        if confid else "- Confidence: no confidence-bearing proposals today",
        "- Remaining bias checks: [UNIT ANALYSIS REQUIRED or insufficient data]",
        "",
        "## Step 4 — Learning from the Pilot",
        "Only Pilot-logged verdicts count (see CLAUDE.md). "
        f"Pilot verdicts today: {len(approved) + len(rejected)}."
        " [UNIT ANALYSIS REQUIRED if > 0; otherwise insufficient Pilot signal]",
        "",
        "## Step 5 — Rulebook diff  [UNIT PROPOSES, PILOT APPROVES — max 2 add, 1 strike]",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    square = [
        f"HANSEI · {date}", "",
        f"Sync Rate: {rate(approved, dec)}",
        f"Proposals decided: {len(dec)} · Approved: {len(approved)} · Filled: {len(fills)}",
        f"Suppressed pre-packet: {len(suppressed)} (R009/R010)", "",
        "What I got wrong today:",
        "[FILL: the real mistake — a post without one is written wrong]", "",
        "What changed in my rulebook:",
        "[FILL: approved diff or 'no change']",
    ]
    square_path.write_text("\n".join(square) + "\n", encoding="utf-8")
    print(f"written: {full_path}")
    print(f"written: {square_path}")
    print("NOTE: sections marked [UNIT ANALYSIS REQUIRED] and [FILL] need the "
          "Unit/Pilot before the debrief counts as run.")
    return 0


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "scan":
        return cmd_scan()
    if cmd == "balance":
        return cmd_balance(argv[2:])
    if cmd == "pending":
        return cmd_pending()
    if cmd == "verdict":
        return cmd_verdict(argv[2:])
    if cmd == "debrief":
        return cmd_debrief(argv[2:])
    if cmd == "status":
        return cmd_status()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
