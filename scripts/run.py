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

MECH_CONFIDENCE = {1: 0.50, 2: 0.57, 3: 0.62}  # v1 mapping (kept behind --v1)

# Mechanical confidence v2 — Pilot-approved 2026-09-02 (option b). R009's 60%
# floor is untouched; v2 changes only how a draft's confidence is computed:
#   base 0.62
#   + volume term: min(0.06, 0.02 * log2(volume multiple))   [log-scaled]
#   + imbalance term, DIRECTION-ALIGNED only: min(0.06, 0.03 * (imb - 1));
#     a contra-side book subtracts symmetrically
#   - spread penalty: min(0.05, spread_bps / 200)
#   Range position is EXCLUDED from confidence (setup type, not strength).
# Caps: 0.80 with three triggering sources, 0.72 with two (less available
# evidence cannot outscore full confluence). Floor of the formula: 0.40.
# Spec targets verified in code: strong confluence reaches 70%+, three
# sources never exceed 80%.
# TIER-DEPENDENT BASE (Pilot-approved 2026-09-02): 0.58 for two-source,
# 0.62 for three-source. Rationale, recorded: eight of ten two-source
# candidates clustered at 0.610-0.638 under a flat 0.62 base — the floor
# had stopped discriminating at that tier. A two-source draft must EARN its
# way over 60% on volume, aligned book, and tight spread, not arrive there
# by default.
CONF_V2_BASE_BY_TIER = {2: 0.58, 3: 0.62}
CONF_V2_CAP3, CONF_V2_CAP2 = 0.80, 0.72


def confidence_v2(n_sources, metrics):
    import math
    conf = CONF_V2_BASE_BY_TIER.get(min(n_sources, 3), 0.58)
    vol_mult = max(metrics.get("vol_ratio_7d") or 1.0, metrics.get("vol_expand") or 1.0)
    conf += min(0.06, 0.02 * math.log2(max(vol_mult, 1.0)))
    imb = metrics.get("imbalance")
    if imb:
        if metrics.get("aligned"):
            conf += min(0.06, 0.03 * (imb - 1))
        elif imb < 1:
            conf -= min(0.06, 0.03 * (1 / imb - 1))
    spread = metrics.get("spread_bps")
    if spread is not None:
        conf -= min(0.05, spread / 200)  # 10 bps -> -0.05 (max penalty)
    cap = CONF_V2_CAP3 if n_sources >= 3 else CONF_V2_CAP2
    return round(max(0.40, min(conf, cap)), 3)

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


# R008 auto-vetting for CEX-scan candidates outside the top 20. Rule
# semantics unchanged: native L1 coins (curated set — no contract exists)
# take the listing-data path; contract assets take query-token-audit via a
# curated canonical mainnet address (only addresses we are certain of).
# Anything not covered stays fail-closed BLOCKED, exactly as R008 says.
NATIVE_L1_BASES = {"FIL", "DASH", "ZEC", "DCR", "ETC", "ALGO", "XTZ", "EGLD",
                   "ICP", "HBAR", "APT", "SEI", "TIA", "INJ", "FLOW", "MINA",
                   "EOS", "KDA", "KAS", "XMR"}
MAINNET_CONTRACTS = {
    "CRV": ("0xd533a949740bb3306d119cc777fa900ba034cd52", "1"),
}


def auto_vet(symbol):
    import re as _re
    import audit
    base = _re.sub(r"USDT$", "", symbol)
    if base in propose.TOP_20_BASES:
        return None  # R008 N/A
    if base in NATIVE_L1_BASES:
        return audit.native_listing_vet(symbol)
    if base in MAINNET_CONTRACTS:
        ca, chain = MAINNET_CONTRACTS[base]
        return audit.vet_asset(contract_address=ca, chain_id=chain)
    return None  # unknown -> draft carries no vetting -> R008 blocks, fail-closed


# Setup-aware confidence v3 — Pilot-approved as drafted 2026-09-02
# (docs/proposed-setup-aware-confidence.md). SHADOW MODE: v2 remains the
# live scorer until the anti-clustering check passes on a genuinely quiet
# day; every classified candidate gets both scores logged to
# logs/confidence-shadow.jsonl for comparison. Tier base 0.58/0.62 and
# R009's 60% floor untouched.

SHADOW_LOG = ROOT / "logs" / "confidence-shadow.jsonl"


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def confidence_v3(setup, n_sources, metrics, structure, rr_value):
    import math
    conf = CONF_V2_BASE_BY_TIER.get(min(n_sources, 3), 0.58)
    s, m = structure, metrics
    ve = s.get("vol_expand") or 0
    avg = s.get("avg_abs_daily_pct") or 4.0
    rp = s.get("range_pos", 0.5)
    imb, aligned = m.get("imbalance"), m.get("aligned")
    chg24 = m.get("chg24", 0)
    if setup == "PULLBACK":
        if s.get("sma20"):
            zone = 1.5 * avg
            dist = abs(s["last"] - s["sma20"]) / s["sma20"] * 100
            conf += 0.04 * _clamp(1 - dist / zone)
        conf += 0.03 * _clamp((1.0 - ve) / 0.5)
        if s.get("sma20") and s.get("sma20_prev5"):
            slope_pct = (s["sma20"] / s["sma20_prev5"] - 1) * 100
            conf += 0.03 * _clamp(slope_pct / (2 * avg))
        if ve >= 1.5:
            conf -= 0.02
        if aligned:
            conf += 0.02
    elif setup == "BASING":
        conf += 0.04 * _clamp((0.8 - ve) / 0.4)
        conf += 0.03 * _clamp((0.25 - rp) / 0.25)
        conf += 0.03 * _clamp(1 - abs(chg24) / avg)
        conf -= 0.05 * _clamp((ve - 0.8) / 0.7)
        if aligned:
            conf += 0.02
    elif setup == "BREAKOUT":
        # Rebalanced 2026-09-02 for the retest term (respects the +0.10 cap):
        # volume 0.06 -> 0.05, tightness 0.03 -> 0.02, retest +0.03.
        conf += 0.05 * _clamp((ve - 1.5) / 3.5)
        if s.get("consol_high") and s.get("consol_low") and s.get("last"):
            width = (s["consol_high"] - s["consol_low"]) / s["last"] * 100
            conf += 0.02 * _clamp((3 * avg - width) / (3 * avg))
        if s.get("retest_held"):
            conf += 0.03  # broke, returned to the level, held it
        if aligned and imb:
            conf += 0.03 * _clamp((imb - 1) / 1.5)
    elif setup == "REVERSAL":
        conf += 0.04 * _clamp((ve - 1.5) / 2.5)
        chg5 = abs(s.get("chg_5d_pct") or 0)
        conf += 0.03 * _clamp((chg5 / avg - 2.5) / 2.5)
        conf += 0.02 * _clamp(((s.get("body_ratio") or 0) - 2) / 3)
        if aligned:
            conf += 0.02
    if rr_value and rr_value > 2:
        conf += min(0.045, 0.015 * math.log2(rr_value / 2))
    if imb and imb < 1:
        conf -= min(0.06, 0.03 * (1 / imb - 1))
    if m.get("spread_bps") is not None:
        conf -= min(0.05, m["spread_bps"] / 200)
    cap = CONF_V2_CAP3 if n_sources >= 3 else CONF_V2_CAP2
    return round(max(0.40, min(conf, cap)), 3)


def shadow_score(cand):
    """Log v2 and v3 side by side for every classified candidate."""
    if cand.get("setup") in (None, "CHASE", "UNCLASSIFIED") or "metrics" not in cand:
        return None
    import scan as scanmod
    n = scanmod.independent_source_count(cand["triggers"])  # deduped sources
    m = dict(cand["metrics"])
    m["chg24"] = cand["chg_pct"]
    rr_value = cand["rr"]["rr"] if cand.get("rr") else None
    v2 = confidence_v2(n, cand["metrics"])
    v3 = confidence_v3(cand["setup"], n, m, cand.get("structure", {}), rr_value)
    entry = {"ts": place.now_iso(), "symbol": cand["symbol"], "setup": cand["setup"],
             "n_sources": n, "rr": round(rr_value, 2) if rr_value else None,
             "v2": v2, "v3": v3}
    place.append_jsonl(SHADOW_LOG, entry)
    return entry


def exit_draft(symbol, base_qty, opened_ts, reason):
    """A SELL packet that closes an open position. Same gate stack as any
    proposal; exempt from the setup classifier and R014 (closing, not
    opening); the reason is mandatory. Confidence is fixed at 0.62: an exit
    is rule-execution, not a market forecast — documented, not tuned."""
    import scan as scanmod
    b = scanmod.source_b(symbol)
    c = scanmod.source_c(symbol, side="SELL")
    evidence = ([{"source": s, "text": t} for s, t in b["evidence"]]
                + [{"source": s, "text": t} for s, t in c["evidence"]]
                + [{"source": "POSITION", "text": f"open since {opened_ts}, "
                    f"{base_qty:g} {symbol.replace('USDT', '')} held"}])
    return {
        "symbol": symbol, "side": "SELL", "type": "MARKET",
        "quantity": base_qty,
        "exit": True, "exit_reason": reason,
        "confidence": 0.62,
        "evidence": evidence,
        "signals_used": ["spot_klines", "spot_depth", "fills.jsonl"],
        "thesis": f"Exit of the open {symbol} position: {reason}",
        "invalidation": "Not applicable — closing order; the position's own "
                        "invalidation/time stop triggered this exit.",
        "size_reasoning": f"Full position close: {base_qty:g} base units held.",
        "max_hold_hours": 24,
        "setup": "EXIT", "setup_detail": reason,
    }


def _open_positions(include_test=False):
    """Open positions from LIVE fills: (symbol -> {qty, opened_ts, age_h}).
    Uses executedQty from the fill response. PAPER fills never open
    positions (orderTest touches no matching engine)."""
    fills = []
    if place.FILLS_LOG.exists():
        fills = [json.loads(l) for l in place.FILLS_LOG.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    live = [f for f in fills if f.get("mode") == "LIVE"
            and (include_test or f.get("test") is not True)]
    net, opened = {}, {}
    for f in live:
        qty = float(f.get("response", {}).get("executedQty") or 0)
        sym = f["symbol"]
        if f["side"] == "BUY":
            net[sym] = net.get(sym, 0) + qty
            opened.setdefault(sym, f["ts"])
        else:
            net[sym] = net.get(sym, 0) - qty
            if net.get(sym, 0) <= 1e-12:
                net[sym] = 0
                opened.pop(sym, None)
    now = datetime.now(timezone.utc)
    out = {}
    for sym, qty in net.items():
        if qty > 0 and sym in opened:
            ts = datetime.strptime(opened[sym], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            out[sym] = {"qty": qty, "opened_ts": opened[sym],
                        "age_h": (now - ts).total_seconds() / 3600}
    return out


def check_time_stops(include_test=False):
    """R013 mechanism: any open position aged past 72h gets an exit packet
    PROPOSED at the next scan — the system never silently holds. The packet
    goes to the Pilot like any other; R010 stops duplicates while one is
    pending. Returns generated packet ids."""
    generated = []
    for sym, pos in _open_positions(include_test=include_test).items():
        if pos["age_h"] <= 72:
            continue
        if propose.pending_clash(sym, "SELL"):
            print(f"R013: {sym} aged {pos['age_h']:.1f}h — exit already pending, not duplicated")
            continue
        draft = exit_draft(sym, pos["qty"], pos["opened_ts"],
                           f"R013 time stop: position age {pos['age_h']:.1f}h exceeds the 72h maximum hold")
        ctx, _ = load_balance_ctx()
        pid, text, checks = propose.build_packet(draft, {}, ctx or {"balances": []})
        if pid:
            propose.save_pending(pid, draft, checks)
            propose.save_packet_text(pid, text)
            generated.append(pid)
            print(f"R013 TIME STOP: exit packet {pid} proposed for {sym} "
                  f"(age {pos['age_h']:.1f}h) -> packets/{pid}.txt — Pilot decides")
        else:
            print(f"R013: {sym} exit draft blocked: {text.splitlines()[0][:120]}")
    return generated


def cmd_exit(args):
    if not args:
        print("usage: run.py exit <SYMBOL> [--qty N --opened TS] --reason \"...\"")
        return 1
    symbol = args[0].upper()
    reason = args[args.index("--reason") + 1] if "--reason" in args else None
    if not reason:
        print("an exit must state a reason (--reason)")
        return 1
    qty = float(args[args.index("--qty") + 1]) if "--qty" in args else None
    opened = args[args.index("--opened") + 1] if "--opened" in args else None
    if qty is None:
        # derive from LIVE fills (executedQty of the position's fill)
        fills = [json.loads(l) for l in place.FILLS_LOG.read_text(encoding="utf-8").splitlines()
                 if l.strip()] if place.FILLS_LOG.exists() else []
        for f in reversed(fills):
            if (f.get("mode") == "LIVE" and f.get("test") is not True
                    and f["symbol"] == symbol and f["side"] == "BUY"):
                qty = float(f.get("response", {}).get("executedQty") or 0)
                opened = f["ts"]
                break
        if not qty:
            print(f"no open LIVE position found for {symbol}; pass --qty/--opened for a drill")
            return 1
    draft = exit_draft(symbol, qty, opened or "unknown", reason)
    ctx, err = load_balance_ctx()
    pid, text, checks = propose.build_packet(draft, {}, ctx or {"spot_account": {"balances": []}})
    print(text)
    if pid is None:
        return 2
    propose.save_pending(pid, draft, checks)
    propose.save_packet_text(pid, text)
    print(f"packet: packets/{pid}.txt")
    return 0


def mechanical_draft(cand, stake, use_v1=False, side="BUY"):
    trig = {s: t for s, t in cand["triggers"].items()
            if t and not (s == "C" and t == ["wide-spread"])}
    # Tier counts distinct signal FAMILIES, not raw sources: A-vol +
    # B-vol-expand is ONE volume signal, not two (2026-09-02 fix).
    import scan as scanmod
    n = scanmod.independent_source_count(cand["triggers"])
    if use_v1 or "metrics" not in cand:
        conf = MECH_CONFIDENCE.get(min(n, 3), 0.50)
    else:
        conf = confidence_v2(n, cand["metrics"])
    parts = "; ".join(f"{s}:{'+'.join(t)}" for s, t in sorted(trig.items()))
    return {
        "symbol": cand["symbol"], "side": side, "type": "MARKET",
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
        "max_hold_hours": 72,
        "setup": cand.get("setup"),
        "setup_detail": cand.get("setup_detail"),
        "rr": cand.get("rr"),
        "vote": cand.get("vote"),
        "market_regime": cand.get("regime"),
    }


def cmd_scan(args=()):
    use_v1 = "--v1" in args
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
    shadows = []
    for cand in result["candidates"]:
        sh = shadow_score(cand)  # v2/v3 side-by-side for every classified candidate
        if sh:
            shadows.append(sh)
    if shadows:
        print("shadow scores (v2 live / v3 shadow):")
        for sh in shadows:
            print(f"  {sh['symbol']}: {sh['setup']} {sh['n_sources']}-source "
                  f"rr={sh['rr']} v2={sh['v2']:.3f} v3={sh['v3']:.3f}")
    # R015 vote failures, with the failing dimensions named — the honest
    # explanation for every classified candidate that produced no packet.
    for cand in result["candidates"]:
        v = cand.get("vote")
        if (cand.get("setup") not in (None, "CHASE", "UNCLASSIFIED")
                and isinstance(v, dict) and not v["pass"]):
            print(f"  VOTE FAILED (R015): {cand['symbol']} {cand['setup']} "
                  f"{v['n_pass']}/4 (need {v['need']}) — failing: "
                  + "; ".join(v["failed"]))
    for cand in result["candidates"]:
        if not cand["packet_worthy"]:
            continue
        draft = mechanical_draft(cand, stake, use_v1=use_v1)
        if draft["confidence"] >= propose.CONFIDENCE_FLOOR:
            vet = auto_vet(draft["symbol"])  # only spend vet calls on floor-clearers
            if vet is not None:
                draft["vetting"] = vet
        pid, text, checks = propose.build_packet(draft, {}, ctx)
        if pid:
            propose.save_pending(pid, draft, checks)
            path = propose.save_packet_text(pid, text)
            packets.append(str(path))
        else:
            skipped.append(text.splitlines()[0][:130])
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
    # R013: never silently hold — aged positions get exit packets proposed
    check_time_stops()
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
    if verdict == "APPROVED" and not test:
        mode = place.read_mode()
        draft_path = f"logs/approved/{pid}.json"
        print(f"\nNEXT STEP (MODE={mode}) — place the order:")
        print(f"  1. python scripts/place.py prepare {draft_path} logs/balance-ctx.json")
        print("  2. make the MCP call it prints "
              + ("(tool_execute wrapping spot.orderTest — validation only)" if mode == "PAPER"
                 else "(spot_newOrder — Binance will then ask YOU to confirm)"))
        print(f"  3. python scripts/place.py record {draft_path} logs/balance-ctx.json <response.json>")
    try:
        import chart
        chart.main()
        print("dashboard/sync-rate.png refreshed")
    except Exception as e:
        print(f"(chart refresh skipped: {e})")
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


def cmd_positions():
    """Open positions from LIVE fills (net BUY-SELL per symbol), with age
    against the R013 72h ceiling. PAPER and test fills never open positions."""
    fills = []
    if place.FILLS_LOG.exists():
        fills = [json.loads(l) for l in place.FILLS_LOG.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    live = [f for f in fills if f.get("mode") == "LIVE" and f.get("test") is not True]
    if not live:
        print("no open positions (no LIVE fills recorded)")
        return 0
    from collections import defaultdict
    net = defaultdict(float)
    oldest_open = {}
    for f in live:
        qty = float(f.get("request", {}).get("quoteOrderQty")
                    or f.get("request", {}).get("arguments", {}).get("quoteOrderQty") or 0)
        sym = f["symbol"]
        if f["side"] == "BUY":
            net[sym] += qty
            oldest_open.setdefault(sym, f["ts"])
        else:
            net[sym] -= qty
            if net[sym] <= 0:
                net[sym] = 0
                oldest_open.pop(sym, None)
    open_syms = [s for s, v in net.items() if v > 0]
    if not open_syms:
        print("no open positions (all LIVE fills netted flat)")
        return 0
    now = datetime.now(timezone.utc)
    for sym in open_syms:
        opened = datetime.strptime(oldest_open[sym], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_h = (now - opened).total_seconds() / 3600
        flag = "  << OVER 72h — EXIT PROPOSAL DUE (R013)" if age_h > 72 else \
               f"  ({72 - age_h:.0f}h until R013 time stop)"
        print(f"{sym}: ~{net[sym]:.2f} USDT notional, opened {oldest_open[sym]}, age {age_h:.1f}h{flag}")
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
    # spec-superseded rejections count in Sync Rate but are excluded from
    # bias analysis and Pilot-preference inference (Pilot-directed).
    inferable = [p for p in day if not p.get("spec_superseded")]
    confid = [p["confidence"] for p in inferable if p.get("confidence") is not None]
    buys = [p for p in inferable if p.get("side") == "BUY"]
    directional = [p for p in inferable if p.get("side")]

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
        f"R010: {sum(1 for s in suppressed if s['rule']=='R010')}, "
        f"R014: {sum(1 for s in suppressed if s['rule']=='R014')})",
        "- Setup types decided today (inferable only): "
        + (json.dumps({s: {"n": sum(1 for p in inferable if p.get('setup') == s),
                           "approved": sum(1 for p in inferable
                                           if p.get('setup') == s and p['verdict'] == 'APPROVED')}
                       for s in sorted({p.get('setup') for p in inferable if p.get('setup')})})
           if any(p.get('setup') for p in inferable) else "none with setup data yet"),
        "- R:R of decided packets (inferable only): "
        + (json.dumps([{ 'id': p['id'], 'rr': p.get('rr'), 'verdict': p['verdict']}
                       for p in inferable if p.get('rr') is not None])
           if any(p.get('rr') is not None for p in inferable) else "none with R:R data yet"),
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
        "Only Pilot-logged verdicts count (see CLAUDE.md); spec-superseded "
        "rejections are excluded from preference inference. "
        f"Inferable Pilot verdicts today: "
        f"{sum(1 for p in inferable if p.get('verdict') in ('APPROVED', 'REJECTED'))}."
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
        return cmd_scan(argv[2:])
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
    if cmd == "chart":
        import chart
        return chart.main()
    if cmd == "positions":
        return cmd_positions()
    if cmd == "exit":
        return cmd_exit(argv[2:])
    if cmd == "replay":
        import replay
        return replay.main(["replay.py"] + argv[2:])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
