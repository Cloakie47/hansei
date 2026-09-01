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

VOLUME_FLOOR = 20_000_000   # 24h quote volume, USDT
TOP_CANDIDATES = 8

# Candidate thresholds (transparent, tunable; every trigger is reported)
A_CHG_PCT = 4.0          # |24h change| worth attention
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


def active_usdt_pairs():
    info = get("exchangeInfo")
    return {s["symbol"]: s for s in info["symbols"]
            if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
            and s.get("isSpotTradingAllowed") and s["baseAsset"] not in STABLE_BASES}


# ---------------------------------------------------------------------------
# SOURCE A — cross-sectional

def source_a(floor=VOLUME_FLOOR):
    pairs = active_usdt_pairs()
    tickers = get("ticker/24hr")
    rows = []
    for t in tickers:
        if t["symbol"] not in pairs:
            continue
        qv = float(t["quoteVolume"])
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
        daily = get("klines", symbol=r["symbol"], interval="1d", limit=8)
        prior = [float(k[7]) for k in daily[:-1]]  # quote asset volume, prior days
        r["vol_ratio_7d"] = (r["quote_volume"] / (sum(prior) / len(prior))) if prior else None
    return rows


def a_evidence(row):
    ev, triggers = [], []
    if abs(row["chg_pct"]) >= A_CHG_PCT:
        triggers.append("chg")
    ev.append(("A", f"ticker24hr all-pairs -> {row['symbol']} 24h {row['chg_pct']:+.2f}%, "
                    f"quote volume {row['quote_volume']/1e6:.1f}m USDT"))
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
    return {"range_pos": range_pos, "vol_expand": vol_expand,
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

def scan(floor=VOLUME_FLOOR, top=TOP_CANDIDATES):
    rows = source_a(floor)
    candidates = []
    for row in rows[:top]:
        a_ev, a_trig = a_evidence(row)
        b = source_b(row["symbol"])
        c = source_c(row["symbol"], side="BUY")  # spot: drafts open long only
        # A candidate is packet-worthy only when at least TWO structurally
        # different sources show an abnormal reading (R007 in spirit; the
        # hard check runs again in propose.py from the evidence tags).
        sources_triggering = [s for s, trigs in
                              (("A", a_trig), ("B", b["triggers"]), ("C", c["triggers"]))
                              if trigs and "wide-spread" not in trigs]
        candidates.append({
            "symbol": row["symbol"],
            "chg_pct": row["chg_pct"],
            "triggers": {"A": a_trig, "B": b["triggers"], "C": c["triggers"]},
            "packet_worthy": len(sources_triggering) >= 2,
            "evidence": [{"source": s, "text": t} for s, t in a_ev + b["evidence"] + c["evidence"]],
        })
    return {
        "pairs_past_floor": len(rows),
        "floor_usdt": floor,
        "scanned_deep": min(top, len(rows)),
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
