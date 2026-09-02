"""HANSEI signal scanner — CEX-native evidence from the universe we can trade.

Three structurally independent sources (R007):

  A  cross-sectional  spot ticker24hr across ALL USDT pairs: 24h change rank,
                      volume vs the pair's own 7-day average, distance from
                      the day's weightedAvgPrice. "This pair vs every other
                      pair right now."
  B  time series      spot klines for one candidate: position in the 7d range,
                      volume expansion vs prior days, latest 1h candle vs the
                      prior 24. "This pair vs its own history."
  C  order book       spot depth: spread, bid/ask imbalance within a band of
                      mid. "What is sitting there right now."

Each emitted evidence line is tagged with its source letter. propose.py
enforces R007 (>= 2 distinct sources) from those tags — three readings of one
source never count as two sources.

Data comes from the public api.binance.com market-data endpoints — the same
data the MCP read tools (spot_ticker24hr / spot_klines / spot_depth) wrap.
Account state and order placement remain MCP-only.

CLI:
  python scripts/scan.py scan [--floor 20000000] [--top 8]
      Full scan: Source A over all pairs, then B and C for the top candidates.
      Prints a JSON report with per-candidate tagged evidence and a
      packet_worthy verdict per candidate.
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.binance.com/api/v3"

# Stable/fiat quote assets masquerading as base assets of USDT pairs —
# never trade candidates.
STABLE_BASES = {"USDC", "FDUSD", "TUSD", "DAI", "EUR", "EURI", "AEUR", "USDP",
                "XUSD", "USD1", "BFUSD", "PAXG"}

VOLUME_FLOOR = 15_000_000   # 24h quote volume, USDT; 20m -> 15m 2026-09-02
                            # (+15 pairs coverage; 10-15m band rejected: thin books)
TOP_CANDIDATES = 16  # deep-scan cap; 8 -> 12 -> 16 (floor drop widened the pool)

# Candidate thresholds (transparent, tunable; every trigger is reported)
A_CHG_PCT = 4.0          # sort normalizer + fallback |24h change| threshold
A_CHG_PCT_MIN = 2.5      # relative-trigger floor: never fire under 2.5%
A_CHG_VOL_MULT = 1.6     # fire when |chg| >= 1.6x the pair's own 7d avg
                         # abs daily change — majors trigger on moves that are
                         # large FOR THEM (fixed 4% was blind to ETH-class vol)
A_VOL_RATIO = 1.8        # 24h volume >= 1.8x own 7d average
A_VWAP_DIST = 1.5        # |last vs weightedAvgPrice| in %
B_RANGE_EDGE = 0.15      # within 15% of 7d low/high
B_VOL_EXPAND = 1.5       # last 24h kline volume vs prior 6d daily avg
C_IMBALANCE = 1.6        # bid/ask notional ratio within ±1% of mid
C_MAX_SPREAD_BPS = 10    # wider than this = illiquid warning, not candidate


def get(path, **params):
    url = f"{API}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


# R011: tokenized equity / RWA (bstock) pairs are excluded at ingest, before
# the volume floor. Detection is FUNCTIONAL, not a ticker blocklist: every
# bstock pair carries permission group TRD_GRP_261 in exchangeInfo and no
# crypto pair does (verified 2026-09-02: exactly the 68 tokenized names,
# zero false positives — TRD_GRP_004-absence was rejected as a marker
# because it also catches privacy coins and fiat). Group ids are opaque, so
# if the marker ever matches nothing we warn instead of silently passing
# equities through.
BSTOCK_MARKER = "TRD_GRP_261"


def active_usdt_pairs():
    info = get("exchangeInfo", permissions="SPOT", showPermissionSets="true")
    pairs, bstocks = {}, set()
    for s in info["symbols"]:
        if not (s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
                and s.get("isSpotTradingAllowed") and s["baseAsset"] not in STABLE_BASES):
            continue
        ps = s.get("permissionSets") or [[]]
        if ps and BSTOCK_MARKER in set(ps[0]):
            bstocks.add(s["symbol"])
            continue
        pairs[s["symbol"]] = s
    if not bstocks:
        print("WARNING: R011 bstock marker matched zero pairs — the "
              f"{BSTOCK_MARKER} detector may have rotted; verify before trusting "
              "the universe.", file=sys.stderr)
    return pairs, bstocks


# ---------------------------------------------------------------------------
# SOURCE A — cross-sectional

def source_a(floor=VOLUME_FLOOR):
    pairs, bstocks = active_usdt_pairs()
    tickers = get("ticker/24hr")
    rows, r011_floor_passing = [], []
    for t in tickers:
        qv = float(t["quoteVolume"])
        if t["symbol"] in bstocks:
            if qv >= floor:
                # would have entered the pool — log the exclusion event
                r011_floor_passing.append({"symbol": t["symbol"], "quote_volume": qv})
            continue
        if t["symbol"] not in pairs:
            continue
        if qv < floor:
            continue
        last = float(t["lastPrice"])
        vwap = float(t["weightedAvgPrice"]) or last
        rows.append({
            "symbol": t["symbol"],
            "chg_pct": float(t["priceChangePercent"]),
            "quote_volume": qv,
            "last": last,
            "vwap_dist_pct": (last - vwap) / vwap * 100,
            "high": float(t["highPrice"]),
            "low": float(t["lowPrice"]),
        })
    # volume vs own 7d average, for the pairs that lead on change/vwap distance
    rows.sort(key=lambda r: max(abs(r["chg_pct"]) / A_CHG_PCT,
                                abs(r["vwap_dist_pct"]) / A_VWAP_DIST), reverse=True)
    for r in rows[:TOP_CANDIDATES * 3]:
        daily = get("klines", symbol=r["symbol"], interval="1d", limit=30)
        prior7 = [float(k[7]) for k in daily[-8:-1]]  # quote vol, prior 7 days
        r["vol_ratio_7d"] = (r["quote_volume"] / (sum(prior7) / len(prior7))) if prior7 else None
        closes = [float(k[4]) for k in daily]
        # pair's own volatility -> per-pair change threshold
        daily_chgs = [abs(float(k[4]) / float(k[1]) - 1) * 100 for k in daily[-8:-1]
                      if float(k[1])]
        avg_abs = sum(daily_chgs) / len(daily_chgs) if daily_chgs else None
        r["chg_threshold_pct"] = (max(A_CHG_PCT_MIN, A_CHG_VOL_MULT * avg_abs)
                                  if avg_abs is not None else A_CHG_PCT)
        # daily-structure aggregates for the setup classifier
        r["avg_abs_daily_pct"] = avg_abs
        if len(closes) >= 25:
            sma20 = sum(closes[-20:]) / 20
            sma20_prev5 = sum(closes[-25:-5]) / 20
            r["sma20"] = sma20
            r["sma20_prev5"] = sma20_prev5  # real slope for v3 trend-quality
            r["sma20_rising"] = sma20 > sma20_prev5
            r["chg_3d_pct"] = (closes[-1] / closes[-4] - 1) * 100
            r["chg_5d_pct"] = (closes[-1] / closes[-6] - 1) * 100
            # consolidation window: days -10..-3 (before the current move)
            window = daily[-10:-2]
            r["consol_high"] = max(float(k[2]) for k in window)
            r["consol_low"] = min(float(k[3]) for k in window)
    return rows, {"bstocks_excluded_total": len(bstocks),
                  "bstocks_above_floor": r011_floor_passing}


def a_evidence(row):
    ev, triggers = [], []
    chg_thr = row.get("chg_threshold_pct", A_CHG_PCT)
    if abs(row["chg_pct"]) >= chg_thr:
        triggers.append("chg")
    ev.append(("A", f"ticker24hr all-pairs -> {row['symbol']} 24h {row['chg_pct']:+.2f}%, "
                    f"quote volume {row['quote_volume']/1e6:.1f}m USDT "
                    f"(own-volatility trigger threshold {chg_thr:.1f}%)"))
    vr = row.get("vol_ratio_7d")
    if vr is not None:
        if vr >= A_VOL_RATIO:
            triggers.append("vol")
        ev.append(("A", f"volume vs own 7d avg -> {vr:.2f}x"))
    if abs(row["vwap_dist_pct"]) >= A_VWAP_DIST:
        triggers.append("vwap")
    ev.append(("A", f"last {row['last']:g} vs day VWAP -> {row['vwap_dist_pct']:+.2f}%"))
    return ev, triggers


# ---------------------------------------------------------------------------
# SOURCE B — time series

def source_b(symbol):
    h1 = get("klines", symbol=symbol, interval="1h", limit=168)
    closes = [float(k[4]) for k in h1]
    qvols = [float(k[7]) for k in h1]
    last = closes[-1]
    lo, hi = min(float(k[3]) for k in h1), max(float(k[2]) for k in h1)
    range_pos = (last - lo) / (hi - lo) if hi > lo else 0.5
    vol_24h = sum(qvols[-24:])
    prior_daily = sum(qvols[:-24]) / 6 if len(qvols) > 24 else None
    vol_expand = vol_24h / prior_daily if prior_daily else None
    last_candle = h1[-1]
    body = abs(float(last_candle[4]) - float(last_candle[1]))
    prior_bodies = [abs(float(k[4]) - float(k[1])) for k in h1[-25:-1]]
    body_ratio = body / (sum(prior_bodies) / len(prior_bodies)) if prior_bodies else None
    swing_low_48h = min(float(k[3]) for k in h1[-48:])

    ev, triggers = [], []
    ev.append(("B", f"klines 1h x168 -> price at {range_pos:.0%} of 7d range "
                    f"({lo:g} - {hi:g})"))
    if range_pos <= B_RANGE_EDGE or range_pos >= 1 - B_RANGE_EDGE:
        triggers.append("range-edge")
    if vol_expand is not None:
        ev.append(("B", f"last 24h kline volume {vol_expand:.2f}x prior 6d daily avg"))
        if vol_expand >= B_VOL_EXPAND:
            triggers.append("vol-expand")
    if body_ratio is not None:
        ev.append(("B", f"current 1h candle body {body_ratio:.2f}x avg of prior 24"))
        if body_ratio >= 2.0:
            triggers.append("candle")
    return {"range_pos": range_pos, "vol_expand": vol_expand, "body_ratio": body_ratio,
            "last": last, "hi_7d": hi, "lo_7d": lo, "swing_low_48h": swing_low_48h,
            "evidence": ev, "triggers": triggers}


# ---------------------------------------------------------------------------
# SOURCE C — order book

def source_c(symbol, side="BUY"):
    """Order book — DIRECTIONAL. An imbalance only triggers, and only counts
    as supporting evidence, when it aligns with the draft side: bid-heavy
    supports a BUY, ask-heavy supports a SELL. A book leaning the other way
    is tagged C-CONTRA — shown in the packet as contradicting context, never
    counted by R007 as a supporting source. (Sign defect fixed 2026-09-02;
    previously |imbalance| fired either way and a bearish book strengthened
    BUY drafts — see logs/confidence-calibration-analysis.md.)"""
    depth = get("depth", symbol=symbol, limit=100)
    bids = [(float(p), float(q)) for p, q in depth["bids"]]
    asks = [(float(p), float(q)) for p, q in depth["asks"]]
    if not bids or not asks:
        return {"evidence": [("C-CONTRA", f"depth -> empty book for {symbol}")], "triggers": []}
    best_bid, best_ask = bids[0][0], asks[0][0]
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10_000
    band = 0.01
    bid_notional = sum(p * q for p, q in bids if p >= mid * (1 - band))
    ask_notional = sum(p * q for p, q in asks if p <= mid * (1 + band))
    imbalance = bid_notional / ask_notional if ask_notional else float("inf")

    aligned = (imbalance >= C_IMBALANCE) if side == "BUY" else (imbalance <= 1 / C_IMBALANCE)
    contra = (imbalance <= 1 / C_IMBALANCE) if side == "BUY" else (imbalance >= C_IMBALANCE)
    tag = "C" if not contra else "C-CONTRA"
    imb_text = (f"depth ±1% of mid -> bids {bid_notional/1e3:.0f}k / asks "
                f"{ask_notional/1e3:.0f}k USDT, imbalance {imbalance:.2f}")
    if contra:
        imb_text = f"contradicts {side}: {imb_text}"
    ev = [(tag, imb_text), (tag, f"spread {spread_bps:.1f} bps")]
    triggers = []
    if aligned:
        triggers.append("imbalance")
    if spread_bps > C_MAX_SPREAD_BPS:
        triggers.append("wide-spread")  # a warning trigger, counts against
    return {"spread_bps": spread_bps, "imbalance": imbalance, "aligned": aligned,
            "evidence": ev, "triggers": triggers}


# ---------------------------------------------------------------------------
# Setup classifier (Pilot-directed 2026-09-02). The excursion ranking
# structurally surfaces movers — it is built to chase. Every candidate is
# classified before it can become a packet; CHASE and UNCLASSIFIED are
# BLOCKED, fail-closed. Thresholds are transparent and per-pair (multiples
# of the pair's own average daily move), and every classification is logged
# to logs/setups.jsonl, blocked ones included.

EXTENDED_MULT = 2.0     # |24h chg| >= 2x own avg daily move = extended
EXTENDED_3D_MULT = 3.0  # or 3d chg >= 3x
NEAR_HIGHS = 0.70       # range position counted as "near range highs"
# Support zone is PER-PAIR (Pilot-approved 2026-09-02): within 1.5x the
# pair's own average daily move of the SMA20 — the same volatility-relative
# pattern as the A trigger. Replaced a fixed 4% that was provably too tight
# for a universe averaging 4-8% daily moves (and it tightens for quiet
# majors, so this is scaling, not loosening).
SUPPORT_ZONE_MULT = 1.5
DECLINE_5D_MULT = 2.5   # 5d decline >= 2.5x own avg = "extended decline"
# BASING (Pilot-approved 2026-09-02): accumulation at the lows on QUIET
# volume — the reversal that has not announced itself yet.
BASING_RANGE_MAX = 0.25    # bottom quarter of the 7d range
BASING_DECLINE_MULT = 2.0  # got here via a decline >= 2x own avg (5d)
BASING_VOL_MAX = 0.8       # volume CONTRACTED vs prior days (quiet, not capitulation)
BASING_CALM_MULT = 1.0     # today's move within 1x own avg — no longer knifing


def classify_setup(row, b):
    avg = row.get("avg_abs_daily_pct") or A_CHG_PCT
    chg24, chg3, chg5 = row["chg_pct"], row.get("chg_3d_pct"), row.get("chg_5d_pct")
    rp = b["range_pos"]
    last, sma20 = b["last"], row.get("sma20")
    if sma20 is None or chg3 is None:
        return "UNCLASSIFIED", "insufficient daily history for classification"
    extended = abs(chg24) >= EXTENDED_MULT * avg or abs(chg3) >= EXTENDED_3D_MULT * avg
    if extended and rp >= NEAR_HIGHS:
        return "CHASE", (f"extended ({chg24:+.1f}% 24h / {chg3:+.1f}% 3d vs avg "
                         f"{avg:.1f}%) and at {rp:.0%} of range — blocked")
    trend_up = last > sma20 and row.get("sma20_rising")
    zone_pct = SUPPORT_ZONE_MULT * avg  # per-pair, volatility-scaled
    near_support = abs(last - sma20) / sma20 * 100 <= zone_pct
    if trend_up and chg24 < 0 and near_support and rp < NEAR_HIGHS:
        return "PULLBACK", (f"uptrend (close>{sma20:.4g}, SMA20 rising), retraced "
                            f"{chg24:+.1f}% to within {zone_pct:.1f}% of the 20d mean "
                            f"(1.5x own {avg:.1f}% avg daily move)")
    consol_high = row.get("consol_high")
    # A breakout must be an UPWARD move: an asset down on the day that merely
    # sits above an old consolidation is not breaking out (0G defect,
    # 2026-09-02 — classified BREAKOUT while -13% on the day).
    if (consol_high and last > consol_high and chg24 > 0
            and (b["vol_expand"] or 0) >= B_VOL_EXPAND):
        width_pct = (consol_high - row["consol_low"]) / last * 100
        return "BREAKOUT", (f"cleared the {width_pct:.1f}%-wide consolidation high "
                            f"{consol_high:.4g} on {b['vol_expand']:.1f}x volume")
    if (chg5 is not None and chg5 <= -DECLINE_5D_MULT * avg and rp <= 0.20
            and ((b["vol_expand"] or 0) >= B_VOL_EXPAND or (b.get("body_ratio") or 0) >= 2)):
        return "REVERSAL", (f"extended decline ({chg5:+.1f}% 5d vs avg {avg:.1f}%), "
                            f"at {rp:.0%} of range on elevated volume")
    if (chg5 is not None and chg5 <= -BASING_DECLINE_MULT * avg
            and rp <= BASING_RANGE_MAX
            and (b["vol_expand"] or 999) <= BASING_VOL_MAX
            and abs(chg24) <= BASING_CALM_MULT * avg):
        return "BASING", (f"declined {chg5:+.1f}% (5d, vs avg {avg:.1f}%), now at "
                          f"{rp:.0%} of range on {b['vol_expand']:.2f}x quiet volume, "
                          f"day move {chg24:+.1f}% within 1x avg — accumulation, not capitulation")
    # DELIBERATE EXCLUSION (Pilot-confirmed 2026-09-02): uptrend continuation
    # WITHOUT a pullback stays UNCLASSIFIED. It is the chase-guard's
    # neighbour — do not "fix" this by adding a continuation category.
    return "UNCLASSIFIED", (f"fits no setup: chg24 {chg24:+.1f}%, 3d {chg3:+.1f}%, "
                            f"range {rp:.0%}, trend_up={trend_up} — blocked fail-closed")


def risk_reward(row, b, setup):
    """Structural target/stop from actual swing levels, not fixed percents.
    Long-only: stop = 48h swing low; target = 7d swing high for PULLBACK and
    BREAKOUT (breakouts use the range top as first objective), 7d range mid
    for REVERSAL. Returns None when entry <= stop (broken structure)."""
    entry = b["last"]
    stop = b["swing_low_48h"]
    if setup in ("REVERSAL", "BASING"):
        target = (b["hi_7d"] + b["lo_7d"]) / 2  # conservative: range mid first
    else:
        target = b["hi_7d"]
    if entry <= stop or target <= entry:
        return None
    return {"entry": entry, "stop": stop, "target": target,
            "rr": (target - entry) / (entry - stop)}


def market_regime():
    """BTC context: UPTREND / RANGE / DOWNTREND from daily SMA20, plus 24h
    change. Printed on every scan and packet; NOT a gate (Pilot: observe
    alongside outcomes first)."""
    daily = get("klines", symbol="BTCUSDT", interval="1d", limit=30)
    closes = [float(k[4]) for k in daily]
    last = closes[-1]
    sma20 = sum(closes[-20:]) / 20
    sma20_prev5 = sum(closes[-25:-5]) / 20
    chg24 = (last / closes[-2] - 1) * 100
    if last > sma20 and sma20 > sma20_prev5:
        regime = "UPTREND"
    elif last < sma20 and sma20 < sma20_prev5:
        regime = "DOWNTREND"
    else:
        regime = "RANGE"
    return {"regime": regime, "btc_chg24_pct": round(chg24, 2),
            "btc_last": last, "btc_sma20": round(sma20, 2)}


def scan(floor=VOLUME_FLOOR, top=TOP_CANDIDATES):
    regime = market_regime()
    print(f"MARKET REGIME: BTC {regime['regime']}, 24h {regime['btc_chg24_pct']:+.2f}% "
          f"(last {regime['btc_last']:g} vs SMA20 {regime['btc_sma20']:g})", file=sys.stderr)
    rows, r011 = source_a(floor)
    # R011 exclusion log: every bstock that would have passed the volume floor
    # is logged with its reason; the full excluded count rides in the result.
    for ex in r011["bstocks_above_floor"]:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import place
        place.append_jsonl(Path(__file__).resolve().parent.parent / "logs" / "signals_discarded.jsonl", {
            "ts": place.now_iso(), "ticker": ex["symbol"].replace("USDT", ""),
            "contract": None, "chainId": None,
            "reason": (f"R011: {ex['symbol']} is a tokenized equity/RWA pair "
                       f"({BSTOCK_MARKER} marker), quote volume "
                       f"{ex['quote_volume']/1e6:.1f}m above floor — excluded from universe"),
        })
    candidates = []
    setups_log = Path(__file__).resolve().parent.parent / "logs" / "setups.jsonl"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import place as _place
    for row in rows[:top]:
        a_ev, a_trig = a_evidence(row)
        b = source_b(row["symbol"])
        c = source_c(row["symbol"], side="BUY")  # spot: drafts open long only
        setup, setup_detail = classify_setup(row, b)
        rr = risk_reward(row, b, setup) if setup not in ("CHASE", "UNCLASSIFIED") else None
        _place.append_jsonl(setups_log, {
            "ts": _place.now_iso(), "symbol": row["symbol"], "setup": setup,
            "detail": setup_detail, "blocked": setup in ("CHASE", "UNCLASSIFIED"),
            "rr": round(rr["rr"], 2) if rr else None,
            "regime": regime["regime"]})
        # A candidate is packet-worthy only when at least TWO structurally
        # different sources show an abnormal reading (R007 in spirit; the
        # hard check runs again in propose.py from the evidence tags) AND the
        # setup classifier admits it (CHASE/UNCLASSIFIED are blocked).
        sources_triggering = [s for s, trigs in
                              (("A", a_trig), ("B", b["triggers"]), ("C", c["triggers"]))
                              if trigs and "wide-spread" not in trigs]
        candidates.append({
            "symbol": row["symbol"],
            "chg_pct": row["chg_pct"],
            "triggers": {"A": a_trig, "B": b["triggers"], "C": c["triggers"]},
            "setup": setup,
            "setup_detail": setup_detail,
            "structure": {
                "sma20": row.get("sma20"), "sma20_prev5": row.get("sma20_prev5"),
                "sma20_rising": row.get("sma20_rising"),
                "chg_3d_pct": row.get("chg_3d_pct"), "chg_5d_pct": row.get("chg_5d_pct"),
                "avg_abs_daily_pct": row.get("avg_abs_daily_pct"),
                "consol_high": row.get("consol_high"), "consol_low": row.get("consol_low"),
                "last": b["last"], "range_pos": b["range_pos"],
                "vol_expand": b["vol_expand"], "body_ratio": b["body_ratio"],
            },
            "rr": ({k: round(v, 6) for k, v in rr.items()} if rr else None),
            "regime": regime,
            "packet_worthy": (len(sources_triggering) >= 2
                              and setup not in ("CHASE", "UNCLASSIFIED")),
            "metrics": {
                "vol_ratio_7d": row.get("vol_ratio_7d"),
                "vol_expand": b.get("vol_expand"),
                "chg_threshold_pct": row.get("chg_threshold_pct"),
                "range_pos": b.get("range_pos"),
                "imbalance": c.get("imbalance"),
                "aligned": c.get("aligned"),
                "spread_bps": c.get("spread_bps"),
                "quote_volume": row["quote_volume"],
            },
            "evidence": [{"source": s, "text": t} for s, t in a_ev + b["evidence"] + c["evidence"]],
        })
    return {
        "regime": regime,
        "pairs_past_floor": len(rows),
        "floor_usdt": floor,
        "scanned_deep": min(top, len(rows)),
        "r011_bstocks_excluded": r011["bstocks_excluded_total"],
        "r011_above_floor": [e["symbol"] for e in r011["bstocks_above_floor"]],
        "candidates": candidates,
        "packet_worthy": [c["symbol"] for c in candidates if c["packet_worthy"]],
    }


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    floor, top = VOLUME_FLOOR, TOP_CANDIDATES
    args = argv[2:] if len(argv) > 1 else []
    if "--floor" in args:
        floor = int(args[args.index("--floor") + 1])
    if "--top" in args:
        top = int(args[args.index("--top") + 1])
    # Startup balance freshness check — run at the start of every scan when a
    # balance context is supplied (the session fetches both MCP endpoints).
    if "--balance-ctx" in args:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import place
        ctx = json.loads(Path(args[args.index("--balance-ctx") + 1]).read_text(encoding="utf-8"))
        ok, msg = place.freshness_check(ctx["spot_account"], ctx.get("wallet_summary"))
        print(msg, file=sys.stderr)
    else:
        print("NOTE: balance freshness check skipped — no --balance-ctx supplied. "
              "Supply {spot_account, wallet_summary} JSON to compare sources.",
              file=sys.stderr)
    if len(argv) > 1 and argv[1] == "scan":
        print(json.dumps(scan(floor, top), indent=2, ensure_ascii=False))
        return 0
    print("usage: scan.py scan [--floor N] [--top N]")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
